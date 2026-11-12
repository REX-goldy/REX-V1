"""Persistent manual supply/demand zones with temporal versions.

Config zones remain the legacy read-only source. New zones are stored separately
from candle data and every edit creates a new version. Backtests receive only
zones that were effective before the simulated range and not invalidated during
it (a deliberately conservative temporal rule).
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.zone_loader import load_zones
from server.file_lock import locked
from models.zone import Zone, ZoneBook, ZoneKind, ZoneSource

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "workspace" / "manual_zones.json"
CONFIG_PATH = ROOT / "config" / "zones.json"
STORE_VERSION = 1
STATUSES = ("active", "invalidated", "archived")
TYPES = ("supply", "demand", "neutral")
TIMEFRAMES = ("M1", "M5", "M15", "H1", "H4", "D1", "WEEKLY", "DAILY")
_lock = threading.RLock()


class ZoneStoreError(ValueError):
    """Invalid zone-store operation."""


class ZoneNotFound(ZoneStoreError, LookupError):
    """Requested zone does not exist or is read-only."""


def zone_store_path() -> Path:
    override = os.environ.get("REX_ZONES_FILE", "").strip()
    return Path(override) if override else DEFAULT_PATH


_zone_locked = locked(zone_store_path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:28] or "zone"
    return f"zone_{slug}_{uuid.uuid4().hex[:8]}"


def _numeric_id(zone_id: str) -> int:
    digest = hashlib.sha256(zone_id.encode()).hexdigest()[:8]
    return int(digest, 16)


def _parse_time(value: str | None, field: str) -> str | None:
    if value is None or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ZoneStoreError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _zone(record: dict[str, Any]) -> dict[str, Any]:
    record = copy.deepcopy(record)
    record.setdefault("versions", [])
    return record


def _validate_record(payload: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    if "created_at" in payload:
        raise ZoneStoreError("created_at is server-generated and cannot be supplied")
    base = existing or {}
    dataset_id = str(payload.get("dataset_id", base.get("dataset_id", ""))).strip()
    if not re.fullmatch(r"[A-Z0-9]{3,12}/[A-Z0-9]{1,8}/\d{4}", dataset_id.upper()):
        raise ZoneStoreError("dataset_id must be SYMBOL/TIMEFRAME/YEAR")
    instrument = dataset_id.split("/")[0].upper()
    low = payload.get("low", existing.get("low") if existing else None)
    high = payload.get("high", existing.get("high") if existing else None)
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        raise ZoneStoreError("low and high must be numbers")
    if not 0 < float(low) < float(high):
        raise ZoneStoreError("zone requires 0 < low < high")
    zone_type = str(payload.get("zone_type", existing.get("zone_type") if existing else "neutral")).lower()
    if zone_type not in TYPES:
        raise ZoneStoreError("zone_type must be supply, demand or neutral")
    timeframe = str(payload.get("source_timeframe", existing.get("source_timeframe") if existing else "")).upper()
    if timeframe not in TIMEFRAMES:
        raise ZoneStoreError("source_timeframe is invalid")
    status = str(payload.get("status", existing.get("status") if existing else "active")).lower()
    if status not in STATUSES:
        raise ZoneStoreError("status must be active, invalidated or archived")
    strength = payload.get("strength", existing.get("strength") if existing else 5)
    if isinstance(strength, bool) or not isinstance(strength, int) or not 0 <= strength <= 10:
        raise ZoneStoreError("strength must be an integer from 0 to 10")
    start_raw = payload.get("start_timestamp", base.get("start_timestamp"))
    effective_raw = payload.get("effective_timestamp", base.get("effective_timestamp"))
    invalidation_raw = payload.get("invalidation_timestamp", base.get("invalidation_timestamp"))
    start_timestamp = _parse_time(None if start_raw in (None, "") else str(start_raw), "start_timestamp")
    effective = _parse_time(None if effective_raw in (None, "") else str(effective_raw), "effective_timestamp")
    invalidation = _parse_time(None if invalidation_raw in (None, "") else str(invalidation_raw), "invalidation_timestamp")
    if effective is None:
        raise ZoneStoreError("effective_timestamp is required")
    if invalidation is not None and invalidation <= effective:
        raise ZoneStoreError("invalidation_timestamp must be after effective_timestamp")
    return {
        "dataset_id": dataset_id.upper(),
        "instrument": instrument,
        "source_timeframe": timeframe,
        "zone_type": zone_type,
        "low": float(low),
        "high": float(high),
        "start_timestamp": start_timestamp,
        "effective_timestamp": effective,
        "invalidation_timestamp": invalidation,
        "status": status,
        "strength": strength,
        "notes": str(payload.get("notes", existing.get("notes", "") if existing else "") or ""),
        "strategy_id": payload.get("strategy_id", existing.get("strategy_id") if existing else None) or None,
        "variation_id": payload.get("variation_id", existing.get("variation_id") if existing else None) or None,
        "provenance": "manual",
        "source": "manual",
    }


def _empty() -> dict[str, Any]:
    return {"version": STORE_VERSION, "zones": []}


def _valid_json(path: Path) -> bool:
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True
    except (OSError, ValueError):
        return False


def _backup_store(path: Path) -> None:
    if not path.exists() or not _valid_json(path):
        return
    try:
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    except OSError:
        pass


def _recover_store(path: Path, original: Exception) -> dict[str, Any]:
    backup = path.with_name(path.name + ".bak")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    corrupt = path.with_name(f"{path.name}.corrupt-{stamp}")
    try:
        shutil.copy2(path, corrupt)
    except OSError:
        pass
    if backup.exists():
        try:
            payload = json.loads(backup.read_text(encoding="utf-8"))
            if (
                isinstance(payload, dict)
                and payload.get("version") == STORE_VERSION
                and isinstance(payload.get("zones"), list)
            ):
                shutil.copy2(backup, path)
                return payload
        except (OSError, ValueError):
            pass
    raise ZoneStoreError(
        f"Zone store is corrupt; original preserved at {corrupt.name}"
    ) from original


def _read() -> dict[str, Any]:
    path = zone_store_path()
    if not path.exists():
        return _empty()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _recover_store(path, exc)
    if not isinstance(payload, dict) or payload.get("version") != STORE_VERSION:
        raise ZoneStoreError("Unsupported zone store version")
    zones = payload.get("zones")
    if not isinstance(zones, list):
        raise ZoneStoreError("Zone store is corrupt")
    return payload


def _write(payload: dict[str, Any]) -> None:
    path = zone_store_path()
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    _backup_store(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    except OSError as exc:
        raise ZoneStoreError("Unable to write zone store") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
        _backup_store(path)
    except OSError as exc:
        raise ZoneStoreError("Unable to write zone store") from exc
    finally:
        if os.path.exists(temp):
            try:
                os.unlink(temp)
            except OSError:
                pass


def _legacy_records() -> list[dict[str, Any]]:
    if not CONFIG_PATH.is_file():
        return []
    try:
        books = load_zones(CONFIG_PATH)
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for symbol, book in books.items():
        for zone in book.zones:
            out.append(
                {
                    "id": f"legacy:{symbol}:{zone.id}",
                    "dataset_id": f"{symbol}/M1/2026",
                    "instrument": symbol,
                    "source_timeframe": zone.timeframe.upper(),
                    "zone_type": zone.kind.value if zone.kind is not None else "neutral",
                    "low": zone.low,
                    "high": zone.high,
                    "start_timestamp": None,
                    "effective_timestamp": None,
                    "invalidation_timestamp": None,
                    "status": "active",
                    "strength": zone.strength,
                    "historical_import": False,
                    "import_source": None,
                    "import_operator": None,
                    "imported_at": None,
                    "notes": "Legacy config/zones.json entry; read-only in the zone manager.",
                    "strategy_id": None,
                    "variation_id": None,
                    "provenance": "config",
                    "source": "legacy",
                    "version": 1,
                    "created_at": None,
                    "updated_at": None,
                    "legacy": True,
                    "versions": [],
                }
            )
    return out


@_zone_locked
def list_zones(*, symbol: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    with _lock:
        store = _read()
        rows = _legacy_records() + [_zone(item) for item in store["zones"]]
    if symbol:
        rows = [item for item in rows if item["instrument"] == symbol.upper()]
    if status:
        rows = [item for item in rows if item["status"] == status]
    return sorted(rows, key=lambda item: (item["instrument"], item["low"], item["id"]))


@_zone_locked
def get_zone(zone_id: str) -> dict[str, Any]:
    for item in list_zones():
        if item["id"] == zone_id:
            return item
    raise ZoneNotFound(f"Zone not found: {zone_id}")


@_zone_locked
def create_zone(payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        store = _read()
        validated = _validate_record(payload)
        now = _now()
        historical = bool(payload.get("historical_import"))
        if historical:
            source = str(payload.get("import_source", "") or "").strip()
            operator = str(payload.get("import_operator", "") or "").strip()
            if not source or not operator:
                raise ZoneStoreError(
                    "historical imports require import_source and import_operator"
                )
            validated["provenance"] = "historical_import"
            validated["historical_import"] = True
            validated["import_source"] = source
            validated["import_operator"] = operator
            validated["imported_at"] = now
        else:
            if datetime.fromisoformat(validated["effective_timestamp"]) < datetime.fromisoformat(now):
                raise ZoneStoreError(
                    "a manually created zone cannot be effective before its creation time; "
                    "use the audited historical-import workflow"
                )
            validated["provenance"] = "manual"
            validated["historical_import"] = False
            validated["import_source"] = None
            validated["import_operator"] = None
            validated["imported_at"] = None
        record = {
            "id": _new_id(validated["dataset_id"]),
            **validated,
            "version": 1,
            "created_at": now,
            "updated_at": now,
            "legacy": False,
            "versions": [],
        }
        store["zones"].append(record)
        _write(store)
        return _zone(record)


@_zone_locked
def update_zone(zone_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        store = _read()
        for index, record in enumerate(store["zones"]):
            if record["id"] != zone_id:
                continue
            updated = _validate_record(payload, existing=record)
            if not record.get("historical_import"):
                created = datetime.fromisoformat(record["created_at"])
                effective = datetime.fromisoformat(updated["effective_timestamp"])
                if effective < created:
                    raise ZoneStoreError(
                        "a manually created zone cannot be moved to an effective time "
                        "before its creation; use a historical import"
                    )
            snapshot = copy.deepcopy(record)
            record["versions"].append(snapshot)
            record.update(updated)
            record["version"] = int(record.get("version", 1)) + 1
            record["updated_at"] = _now()
            store["zones"][index] = record
            _write(store)
            return _zone(record)
    raise ZoneNotFound(f"Zone not found or read-only: {zone_id}")


@_zone_locked
def archive_zone(zone_id: str) -> dict[str, Any]:
    with _lock:
        store = _read()
        for index, record in enumerate(store["zones"]):
            if record["id"] != zone_id:
                continue
            snapshot = copy.deepcopy(record)
            record["versions"].append(snapshot)
            record["status"] = "archived"
            record["version"] = int(record.get("version", 1)) + 1
            record["updated_at"] = _now()
            store["zones"][index] = record
            _write(store)
            return _zone(record)
    raise ZoneNotFound(f"Zone not found or read-only: {zone_id}")


@_zone_locked
def build_zone_books(
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    zone_ids: list[str] | None = None,
) -> dict[str, ZoneBook]:
    """Build strategy-ready books using temporal availability.

    Manual zones must have `effective_timestamp <= start` and must not be
    invalidated before `end`; this conservative rule prevents future/invalidated
    zones from leaking into a run. Legacy config zones have no timestamps and are
    retained as the existing static behavior.
    """
    with _lock:
        store = _read()
    books: dict[str, list[Zone]] = {}
    if zone_ids:
        selected = set(zone_ids)
        records = [item for item in store["zones"] if item["id"] in selected]
    else:
        records = list(store["zones"])
    def comparable(value: str, reference: datetime) -> datetime:
        stamp = datetime.fromisoformat(value)
        if reference.tzinfo is None:
            return stamp.astimezone(timezone.utc).replace(tzinfo=None)
        return stamp.astimezone(timezone.utc)

    for item in records:
        if item.get("status") != "active":
            continue
        effective = item.get("effective_timestamp")
        invalidation = item.get("invalidation_timestamp")
        created = item.get("created_at")
        if not item.get("historical_import") and created and effective:
            if comparable(effective, datetime.fromisoformat(created)) < datetime.fromisoformat(created):
                # Legacy/backdated manual annotations are not historically usable.
                continue
        if start is not None and effective:
            if comparable(effective, start) > start:
                continue
        if end is not None and invalidation:
            if comparable(invalidation, end) <= end:
                continue
        kind = ZoneKind(item["zone_type"]) if item["zone_type"] in {"supply", "demand"} else None
        zone = Zone(
            id=_numeric_id(item["id"]),
            name=f"manual:{item['id'][:8]}",
            low=float(item["low"]),
            high=float(item["high"]),
            timeframe=str(item["source_timeframe"]).lower(),
            strength=int(item["strength"]),
            kind=kind,
            source=ZoneSource.MANUAL,
        )
        books.setdefault(item["instrument"], []).append(zone)
    # Legacy static config zones remain available; they are not in the manual store.
    if not zone_ids:
        try:
            legacy = load_zones(CONFIG_PATH)
        except Exception:
            legacy = {}
        for symbol, book in legacy.items():
            books.setdefault(symbol, []).extend(book.zones)
    return {
        symbol: ZoneBook(symbol=symbol, zones=tuple(zones))
        for symbol, zones in books.items()
        if zones
    }
