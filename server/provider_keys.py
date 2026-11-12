"""Secure server-side credential store for data providers.

Keys are stored in a JSON file that is only readable by the server process
(``0600`` on POSIX).  Secrets are never returned to callers: the public
credential views expose a short hint (the last four characters) only.

The environment remains a valid fallback so existing deployments that export
``TWELVE_DATA_API_KEY`` keep working.  A stored key takes precedence over the
environment.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE_PATH = ROOT / "data" / "provider_keys.json"
STORE_VERSION = 1
MAX_KEY_LENGTH = 512
_MASK = "••••"

_lock = threading.RLock()


class ProviderKeyError(Exception):
    """Base error for provider credential handling."""


class ProviderKeyStoreError(ProviderKeyError):
    """Raised when the credential store cannot be read or written safely."""


class UnknownProviderError(ProviderKeyError, LookupError, ValueError):
    """Raised when a provider id is not present in the registry."""


class InvalidProviderKeyError(ProviderKeyError, ValueError):
    """Raised when a submitted key is empty, too long, or malformed."""


@dataclass(frozen=True)
class ProviderDefinition:
    """Static description of a provider that can hold a credential."""

    id: str
    name: str
    env_var: str
    required: bool
    description: str


# Ordered registry.  Adding a provider is a single entry here.
PROVIDER_REGISTRY: tuple[ProviderDefinition, ...] = (
    ProviderDefinition(
        id="twelve_data",
        name="Twelve Data",
        env_var="TWELVE_DATA_API_KEY",
        required=True,
        description="Twelve Data historical M1 candles",
    ),
    ProviderDefinition(
        id="dukascopy",
        name="Dukascopy",
        env_var="DUKASCOPY_API_KEY",
        required=False,
        description=(
            "Dukascopy historical adapter; current downloader does not require a key"
        ),
    ),
)
PROVIDERS: dict[str, ProviderDefinition] = {
    provider.id: provider for provider in PROVIDER_REGISTRY
}


def store_path() -> Path:
    """Return the active credential store path."""
    override = os.environ.get("REX_KEYS_FILE", "")
    if override and override.strip():
        return Path(override)
    return DEFAULT_STORE_PATH


def _provider(provider_id: str) -> ProviderDefinition:
    try:
        return PROVIDERS[provider_id]
    except (KeyError, TypeError) as exc:
        raise UnknownProviderError(
            f"Unknown provider: {provider_id!r}"
        ) from exc


def _validate_key(api_key: str) -> str:
    if not isinstance(api_key, str):
        raise InvalidProviderKeyError("API key must be a string")
    if any(ord(char) < 32 or ord(char) == 127 for char in api_key):
        raise InvalidProviderKeyError(
            "API key cannot contain control characters or newlines"
        )
    key = api_key.strip()
    if not key:
        raise InvalidProviderKeyError("API key cannot be empty")
    if len(key) > MAX_KEY_LENGTH:
        raise InvalidProviderKeyError(
            f"API key cannot be longer than {MAX_KEY_LENGTH} characters"
        )
    return key


def _empty_store() -> dict[str, Any]:
    return {"version": STORE_VERSION, "providers": {}}


def _read_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_store()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProviderKeyStoreError("Unable to read the provider key store") from exc
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ProviderKeyStoreError("Provider key store is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ProviderKeyStoreError("Provider key store must be a JSON object")
    if payload.get("version") != STORE_VERSION:
        raise ProviderKeyStoreError("Unsupported provider key store version")
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        raise ProviderKeyStoreError("Provider key store is corrupt")

    cleaned: dict[str, dict[str, str]] = {}
    for provider_id, entry in providers.items():
        if not isinstance(provider_id, str) or not isinstance(entry, dict):
            raise ProviderKeyStoreError("Provider key store is corrupt")
        api_key = entry.get("api_key")
        if not isinstance(api_key, str):
            raise ProviderKeyStoreError("Provider key store is corrupt")
        updated_at = entry.get("updated_at")
        if updated_at is not None and not isinstance(updated_at, str):
            raise ProviderKeyStoreError("Provider key store is corrupt")
        saved = {"api_key": api_key}
        if updated_at is not None:
            saved["updated_at"] = updated_at
        cleaned[provider_id] = saved
    return {"version": STORE_VERSION, "providers": cleaned}


def _write_store(path: Path, providers: dict[str, dict[str, str]]) -> None:
    payload = {"version": STORE_VERSION, "providers": providers}
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
    except OSError as exc:
        raise ProviderKeyStoreError("Unable to write the provider key store") from exc

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    except OSError as exc:
        raise ProviderKeyStoreError("Unable to write the provider key store") from exc
    finally:
        if os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass


def _hint(secret: str) -> str:
    # Never reveal the whole credential, even when it is only four characters.
    if len(secret) <= 4:
        return _MASK
    return secret[-4:]


def _credential(
    provider: ProviderDefinition,
    stored: dict[str, str] | None,
) -> dict[str, Any]:
    env_value = os.environ.get(provider.env_var, "")
    env_key = env_value.strip() if env_value else ""
    if stored is not None:
        secret: str | None = stored.get("api_key") or None
        source = "stored"
        updated_at: str | None = stored.get("updated_at")
    elif env_key:
        secret = env_key
        source = "environment"
        updated_at = None
    else:
        secret = None
        source = "none"
        updated_at = None

    return {
        "id": provider.id,
        "name": provider.name,
        "description": provider.description,
        "env_var": provider.env_var,
        "required": provider.required,
        "configured": secret is not None,
        "source": source,
        "hint": _hint(secret) if secret is not None else _MASK,
        "updated_at": updated_at,
    }


def set_provider_key(provider_id: str, api_key: str) -> dict[str, Any]:
    """Store ``api_key`` for a registered provider and return its masked view."""
    provider = _provider(provider_id)
    key = _validate_key(api_key)
    updated_at = datetime.now(timezone.utc).isoformat()
    path = store_path()
    with _lock:
        store = _read_store(path)
        providers = store["providers"]
        providers[provider.id] = {"api_key": key, "updated_at": updated_at}
        _write_store(path, providers)
        return _credential(provider, providers[provider.id])


def delete_provider_key(provider_id: str) -> dict[str, Any]:
    """Remove a stored key, leaving any environment fallback untouched."""
    provider = _provider(provider_id)
    path = store_path()
    with _lock:
        store = _read_store(path)
        providers = store["providers"]
        if provider.id in providers:
            providers.pop(provider.id, None)
            _write_store(path, providers)
        return _credential(provider, providers.get(provider.id))


def get_provider_key(provider_id: str) -> str | None:
    """Return the stored key first, then the environment value, else ``None``."""
    provider = _provider(provider_id)
    path = store_path()
    with _lock:
        store = _read_store(path)
        stored = store["providers"].get(provider.id)
    if stored is not None:
        key = stored.get("api_key", "").strip()
        if key:
            return key
    env_value = os.environ.get(provider.env_var, "")
    env_key = env_value.strip() if env_value else ""
    return env_key or None


def has_provider_key(provider_id: str) -> bool:
    """Return whether a provider has a stored or environment credential."""
    return get_provider_key(provider_id) is not None


def list_provider_credentials() -> list[dict[str, Any]]:
    """Return masked credential status for every registered provider."""
    path = store_path()
    with _lock:
        store = _read_store(path)
        providers = store["providers"]
    return [
        _credential(provider, providers.get(provider.id))
        for provider in PROVIDER_REGISTRY
    ]
