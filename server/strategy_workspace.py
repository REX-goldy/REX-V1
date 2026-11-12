"""Persistent research workspace for strategies, variations and experiments.

This layer is additive. It stores documentation, research notes, variation
metadata and references to immutable backtest run artifacts. It never executes
a strategy itself and never writes into the historical dataset or run archive.
"""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import tempfile
import threading
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from hashlib import sha256
from backtests.costs import CostProfile
from backtests.validation import validate_run
from research.free_ohlc.resampler import COMPLETENESS_RULE, RESAMPLER_VERSION
from server import research_service
from server import zone_store
from server.file_lock import locked
from models.zone import Zone, ZoneBook, ZoneKind, ZoneSource

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE_PATH = ROOT / "data" / "workspace" / "strategy_workspace.json"
STORE_VERSION = 1
STATUSES = ("Draft", "Research", "Experimental", "Validated", "Archived")
EXPERIMENT_KINDS = ("baseline", "experiment", "repeat", "out_of_sample")
EXPERIMENT_STATUSES = ("Planned", "Running", "Completed", "Failed", "Archived")
EXPERIMENT_SNAPSHOT_VERSION = 1
MODEL_VERSIONS = {
    "experiment_snapshot": EXPERIMENT_SNAPSHOT_VERSION,
    "run_schema": "ui_run_v1",
    "resampler": RESAMPLER_VERSION,
    "completeness_rule": COMPLETENESS_RULE,
    "cost_profiles": "cost_profiles_v1",
    "fill_model": "conservative_ohlc_fill_v1",
    "execution_sizing": "fill_time_fixed_risk_v1",
}
TIMEFRAMES = ("M1", "M5", "M15", "H1", "H4")
MAX_TEXT = 20_000
MAX_TAG = 40
MAX_TAGS = 20
MAX_PARAMETERS = 50

_lock = threading.RLock()


class WorkspaceError(Exception):
    """Base class for workspace errors."""


class WorkspaceNotFound(WorkspaceError, LookupError, ValueError):
    """Requested strategy, variation, note or experiment does not exist."""


class WorkspaceConflict(WorkspaceError, ValueError):
    """The requested change conflicts with immutable research history."""


class WorkspaceValidationError(WorkspaceError, ValueError):
    """Input is invalid for the workspace model."""


class WorkspaceStoreError(WorkspaceError):
    """The workspace file cannot be read or written safely."""


class ReproductionError(WorkspaceError):
    """A completed experiment cannot be reproduced from its snapshot."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def workspace_path() -> Path:
    override = os.environ.get("REX_WORKSPACE_FILE", "").strip()
    return Path(override) if override else DEFAULT_STORE_PATH


_workspace_locked = locked(workspace_path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str, label: str = "") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:32] or "item"
    return f"{prefix}_{slug}_{uuid.uuid4().hex[:8]}"


def _text(value: Any, field: str, *, required: bool = False, limit: int = MAX_TEXT) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise WorkspaceValidationError(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise WorkspaceValidationError(f"{field} cannot be empty")
    if len(value) > limit:
        raise WorkspaceValidationError(f"{field} cannot exceed {limit} characters")
    return value


def _status(value: Any, field: str = "status") -> str:
    if value not in STATUSES:
        raise WorkspaceValidationError(
            f"{field} must be one of: {', '.join(STATUSES)}"
        )
    return value


def _tags(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise WorkspaceValidationError("tags must be a list of strings")
    result = []
    seen = set()
    for raw in value:
        tag = raw.strip()
        if not tag:
            continue
        if len(tag) > MAX_TAG:
            raise WorkspaceValidationError(f"each tag must be at most {MAX_TAG} characters")
        folded = tag.casefold()
        if folded not in seen:
            seen.add(folded)
            result.append(tag)
    if len(result) > MAX_TAGS:
        raise WorkspaceValidationError(f"at most {MAX_TAGS} tags are allowed")
    return result


def _string_list(value: Any, field: str, *, allowed: tuple[str, ...] | None = None) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise WorkspaceValidationError(f"{field} must be a list of strings")
    result: list[str] = []
    for item in value:
        cleaned = item.strip().upper()
        if not cleaned:
            continue
        if allowed is not None and cleaned not in allowed:
            raise WorkspaceValidationError(
                f"{field} contains unsupported value: {item}"
            )
        if cleaned not in result:
            result.append(cleaned)
    return result


def _registry_strategy(registry_id: str | None) -> dict[str, Any] | None:
    if not registry_id:
        return None
    for item in research_service.list_strategies():
        if item["id"] == registry_id:
            return item
    raise WorkspaceValidationError(f"Unknown registry strategy: {registry_id}")


def _default_parameters(registry: dict[str, Any] | None) -> dict[str, Any]:
    if not registry:
        return {}
    return {item["name"]: item["default"] for item in registry["parameters"]}


def _validate_parameter_config(
    registry: dict[str, Any] | None, value: Any
) -> dict[str, Any]:
    if value is None:
        return _default_parameters(registry)
    if not isinstance(value, dict):
        raise WorkspaceValidationError("parameter_config must be an object")
    if len(value) > MAX_PARAMETERS:
        raise WorkspaceValidationError("too many parameters")
    if registry is None:
        # Documentation-only variations may carry arbitrary JSON-scalar config,
        # but they can never be executed.
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise WorkspaceValidationError("parameter names must be non-empty strings")
            if not isinstance(item, (str, int, float, bool)) and item is not None:
                raise WorkspaceValidationError("parameter values must be JSON scalars")
        return dict(value)

    definitions = {item["name"]: item for item in registry["parameters"]}
    unknown = sorted(set(value) - set(definitions))
    if unknown:
        raise WorkspaceValidationError(
            f"Unknown parameters for {registry['id']}: {', '.join(unknown)}"
        )
    result: dict[str, Any] = {}
    for name, definition in definitions.items():
        if name not in value:
            result[name] = definition["default"]
            continue
        item = value[name]
        kind = definition["type"]
        if kind == "integer":
            if isinstance(item, bool) or not isinstance(item, int):
                raise WorkspaceValidationError(f"{name} must be an integer")
            parsed = item
        elif kind == "number":
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise WorkspaceValidationError(f"{name} must be a number")
            parsed = float(item)
        elif kind == "boolean":
            if not isinstance(item, bool):
                raise WorkspaceValidationError(f"{name} must be a boolean")
            parsed = item
        else:
            if not isinstance(item, str):
                raise WorkspaceValidationError(f"{name} must be a string")
            parsed = item
        minimum = definition.get("min")
        maximum = definition.get("max")
        if minimum is not None and parsed < minimum:
            raise WorkspaceValidationError(f"{name} must be >= {minimum}")
        if maximum is not None and parsed > maximum:
            raise WorkspaceValidationError(f"{name} must be <= {maximum}")
        result[name] = parsed
    return result


def _empty_store() -> dict[str, Any]:
    return {"version": STORE_VERSION, "strategies": []}


def _rules(**overrides: Any) -> dict[str, Any]:
    base = {
        "entry_conditions": [],
        "confirmation_conditions": [],
        "exit_conditions": [],
        "stop_loss": "Not implemented at strategy level.",
        "take_profit": "Not implemented at strategy level.",
        "invalidation": "Not documented in the current implementation.",
        "required_indicators": [],
        "required_market_features": ["OHLC bars"],
        "required_zone_configuration": "None",
        "supported_instruments": [],
        "supported_timeframes": list(TIMEFRAMES),
    }
    base.update(overrides)
    return base


def _seed_parameters(strategy_id: str) -> dict[str, Any]:
    return _default_parameters(_registry_strategy(strategy_id))


def _seed_variation(
    strategy_id: str,
    title: str,
    description: str,
    parameters: dict[str, Any],
    instruments: list[str],
    timeframes: list[str],
    *,
    created: str,
) -> dict[str, Any]:
    return {
        "id": _new_id("var", f"{strategy_id}-baseline"),
        "title": title,
        "description": description,
        "hypothesis": "Baseline configuration; no variation hypothesis is claimed yet.",
        "changes_from_parent": "Original baseline configuration from the registered implementation.",
        "entry_rule_differences": "",
        "exit_rule_differences": "",
        "filter_differences": "",
        "parameter_config": parameters,
        "zone_ids": [],
        "instruments": instruments,
        "timeframes": timeframes,
        "status": "Research",
        "notes": "",
        "is_baseline": True,
        "implementation_status": "implemented",
        "registry_strategy_id": strategy_id,
        "configuration_version": 1,
        "cloned_from": None,
        "created_at": created,
        "updated_at": created,
        "archived_at": None,
    }


def _seed_strategies() -> list[dict[str, Any]]:
    """Seed the workspace from the three actual registered strategies.

    The rules below are transcribed from the current implementation and the
    existing Strategy Lab descriptions. They are documentation, not a second
    execution path. No performance result is seeded.
    """
    created = _now()
    seeded: list[dict[str, Any]] = []

    def add(
        *,
        registry_id: str,
        title: str,
        short: str,
        description: str,
        hypothesis: str,
        objective: str,
        category: str,
        tags: list[str],
        rules: dict[str, Any],
        instruments: list[str],
        timeframes: list[str],
        proposed: list[str] | None = None,
    ) -> None:
        strategy_record_id = f"sw_{registry_id.lower().replace('_', '-')}"
        variation = _seed_variation(
            registry_id,
            "V1 — Original baseline",
            "Original registered implementation with default Strategy Lab parameters.",
            _seed_parameters(registry_id),
            instruments,
            timeframes,
            created=created,
        )
        seeded.append(
            {
                "id": strategy_record_id,
                "title": title,
                "registry_strategy_id": registry_id,
                "short_description": short,
                "description": description,
                "hypothesis": hypothesis,
                "research_objective": objective,
                "category": category,
                "status": "Research",
                "tags": tags,
                "created_at": created,
                "updated_at": created,
                "archived_at": None,
                "rules": {
                    "implemented": rules,
                    "proposed": proposed or [],
                    "experimental": [],
                },
                "notes": [],
                "variations": [variation],
                "experiments": [],
            }
        )

    add(
        registry_id="CORE_ZONE_BREAKOUT",
        title="Zone Breakout",
        short="Manual-zone interaction and breakout signal study.",
        description=(
            "Stateful evaluation of manually configured supply/demand zones. "
            "Signals describe zone entry, break above/below and close outside. "
            "The service exposes it as a signal study, not a trade simulation."
        ),
        hypothesis=(
            "Repeated reactions around documented supply/demand zones may identify "
            "structural levels worth studying; this hypothesis is not proven."
        ),
        objective="Measure zone interactions and break transitions under causal replay.",
        category="Market structure",
        tags=["zones", "breakout", "signal-study"],
        rules=_rules(
            entry_conditions=[
                "A close enters a configured zone after the previous bar was outside.",
                "On the first observation, the bar range must overlap the zone.",
            ],
            confirmation_conditions=[
                "Break above/below is evaluated from the prior zone position.",
                "CLOSE_OUTSIDE is emitted whenever close is outside the zone.",
            ],
            exit_conditions=["No strategy exit; no trades are simulated."],
            invalidation="Per-zone last position is updated after every evaluation; reset clears state.",
            required_market_features=["OHLC bars", "Manual zone book"],
            required_zone_configuration="Required. Current books: EURUSD (8), GBPUSD (1).",
            supported_instruments=["EURUSD", "GBPUSD"],
        ),
        instruments=["EURUSD", "GBPUSD"],
        timeframes=list(TIMEFRAMES),
        proposed=[
            "Reduce per-bar CLOSE_OUTSIDE emissions to state-changing interactions (QA finding QA-D-005).",
            "Add a trade-simulation factory before claiming execution behavior.",
        ],
    )
    add(
        registry_id="S002",
        title="Breakout Retest",
        short="Breakout followed by a bounded retest of the broken zone boundary.",
        description=(
            "A close beyond a configured zone starts a bounded wait. A retest within "
            "tolerance and back on the breakout side emits a long/short signal; the "
            "existing execution layer maps it to a trade plan."
        ),
        hypothesis=(
            "A confirmed breakout followed by a successful retest may provide better "
            "entry quality than entering immediately on breakout. This is a research "
            "hypothesis, not a demonstrated edge."
        ),
        objective=(
            "Compare retest variations against the original breakout-retest baseline "
            "under comparable datasets and date ranges."
        ),
        category="Market structure",
        tags=["zones", "breakout", "retest", "trade-simulation"],
        rules=_rules(
            entry_conditions=[
                "Bullish: close > zone.high starts a wait at the upper boundary.",
                "Bearish: close < zone.low starts a wait at the lower boundary.",
            ],
            confirmation_conditions=[
                "Bullish retest: low <= broken level + tolerance and close > broken level.",
                "Bearish retest: high >= broken level - tolerance and close < broken level.",
                "The breakout candle cannot also be the retest candle.",
            ],
            exit_conditions=[
                "Stop-loss, take-profit, timeout, ambiguity or end-of-data force close from the shared simulator.",
            ],
            stop_loss="Signal-bar low for long; signal-bar high for short (existing factory).",
            take_profit="Fixed R-multiple target, default 2.0R, recalculated at actual fill.",
            invalidation="A close through the opposite boundary switches the wait direction; max_wait expires the setup.",
            required_market_features=["OHLC bars", "Manual zone book"],
            required_zone_configuration="Required. Current books: EURUSD (8), GBPUSD (1).",
            supported_instruments=["EURUSD", "GBPUSD"],
        ),
        instruments=["EURUSD", "GBPUSD"],
        timeframes=list(TIMEFRAMES),
        proposed=[
            "Use a structural non-zero fallback stop when the retest closes at its extreme (QA-D-006).",
            "Expose zone availability before submission (QA-D-007).",
        ],
    )
    add(
        registry_id="S008",
        title="Liquidity Sweep",
        short="Sweep of a prior swing high/low with a close back inside.",
        description=(
            "Sweeps the prior lookback swing high/low, requires a close back inside "
            "and a minimum wick ratio. The existing sweep factory and trade simulator "
            "handle execution when trade simulation is enabled."
        ),
        hypothesis=(
            "Liquidity sweeps of recent swing extremes may mark short-term rejection; "
            "the hypothesis is unproven and must be tested across comparable samples."
        ),
        objective=(
            "Evaluate sweep-quality variations under identical datasets, timeframes "
            "and ranges without changing the registered baseline."
        ),
        category="Liquidity",
        tags=["liquidity", "sweeps", "trade-simulation"],
        rules=_rules(
            entry_conditions=[
                "Bullish: current low < prior swing low - tolerance.",
                "Bearish: current high > prior swing high + tolerance.",
            ],
            confirmation_conditions=[
                "Close returns inside the prior swing.",
                "Lower/upper wick ratio meets min_wick_ratio.",
            ],
            exit_conditions=[
                "Stop-loss, take-profit, timeout, ambiguity or end-of-data force close from the shared simulator.",
            ],
            stop_loss="Signal-bar low for bullish sweeps; signal-bar high for bearish sweeps.",
            take_profit="Fixed R-multiple target, default 2.0R, recalculated at actual fill.",
            invalidation="A bar without a valid sweep produces no signal; reset clears duplicate-timestamp state.",
            required_market_features=["OHLC bars; prior swing lookback"],
            required_zone_configuration="None.",
            supported_instruments=["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCAD"],
        ),
        instruments=["EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "USDCAD"],
        timeframes=list(TIMEFRAMES),
        proposed=[
            "Add a higher-timeframe trend filter as a separately documented variation.",
            "Add a volatility filter as a separately documented variation.",
        ],
    )
    return seeded


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
            if isinstance(payload, dict) and payload.get("version") == STORE_VERSION:
                _validate_store(payload)
                shutil.copy2(backup, path)
                return payload
        except (OSError, ValueError):
            pass
    raise WorkspaceStoreError(
        f"Workspace file is corrupt; original preserved at {corrupt.name}"
    ) from original


def _read_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        store = {"version": STORE_VERSION, "strategies": _seed_strategies()}
        _write_store(path, store)
        return store
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _recover_store(path, exc)
    if not isinstance(payload, dict) or payload.get("version") != STORE_VERSION:
        raise WorkspaceStoreError("Unsupported workspace store version")
    if not isinstance(payload.get("strategies"), list):
        raise WorkspaceStoreError("Workspace store is corrupt")
    _validate_store(payload)
    return payload


def _validate_store(payload: dict[str, Any]) -> None:
    seen: set[str] = set()
    for strategy in payload["strategies"]:
        if not isinstance(strategy, dict) or not isinstance(strategy.get("id"), str):
            raise WorkspaceStoreError("Workspace contains an invalid strategy")
        if strategy["id"] in seen:
            raise WorkspaceStoreError("Workspace contains duplicate strategy ids")
        seen.add(strategy["id"])
        variations = strategy.get("variations")
        if not isinstance(variations, list):
            raise WorkspaceStoreError("Workspace strategy has invalid variations")
        variation_ids = [item.get("id") for item in variations if isinstance(item, dict)]
        if len(variation_ids) != len(set(variation_ids)):
            raise WorkspaceStoreError("Workspace contains duplicate variation ids")
        baselines = [item for item in variations if item.get("is_baseline")]
        if len(baselines) != 1:
            raise WorkspaceStoreError("Each strategy must have exactly one baseline variation")
        if not isinstance(strategy.get("experiments"), list):
            raise WorkspaceStoreError("Workspace strategy has invalid experiments")


def _write_store(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    _backup_store(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
    except OSError as exc:
        raise WorkspaceStoreError("Unable to write the workspace store") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
        _backup_store(path)
    except OSError as exc:
        raise WorkspaceStoreError("Unable to write the workspace store") from exc
    finally:
        if os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass


def _load() -> dict[str, Any]:
    with _lock:
        return _read_store(workspace_path())


def _strategy(store: dict[str, Any], strategy_id: str) -> dict[str, Any]:
    for item in store["strategies"]:
        if item["id"] == strategy_id:
            return item
    raise WorkspaceNotFound(f"Strategy not found: {strategy_id}")


def _variation(strategy: dict[str, Any], variation_id: str) -> dict[str, Any]:
    for item in strategy["variations"]:
        if item["id"] == variation_id:
            return item
    raise WorkspaceNotFound(f"Variation not found: {variation_id}")


def _experiment_count(strategy: dict[str, Any], variation_id: str) -> int:
    return sum(
        1
        for item in strategy["experiments"]
        if item.get("variation_id") == variation_id
    )


def _latest_experiment(strategy: dict[str, Any]) -> dict[str, Any] | None:
    experiments = list(strategy.get("experiments", []))
    if not experiments:
        return None
    return max(experiments, key=lambda item: item.get("executed_at") or "")


def _run_available(run_id: str) -> bool:
    try:
        research_service.get_run(run_id)
        return True
    except Exception:
        return False


def _zone_snapshots(zone_ids: list[str] | None, *, strict: bool = True) -> list[dict[str, Any]]:
    snapshots = []
    for zone_id in zone_ids or []:
        try:
            zone = zone_store.get_zone(zone_id)
        except Exception as exc:
            if strict:
                raise WorkspaceValidationError(
                    f"Selected zone is unavailable: {zone_id}"
                ) from exc
            continue
        if zone.get("status") == "archived":
            raise WorkspaceValidationError(
                f"Selected zone is archived: {zone_id}"
            )
        snapshots.append(
            {
                "id": zone["id"],
                "version": zone["version"],
                "dataset_id": zone.get("dataset_id"),
                "instrument": zone.get("instrument"),
                "source_timeframe": zone["source_timeframe"],
                "zone_type": zone["zone_type"],
                "low": zone["low"],
                "high": zone["high"],
                "start_timestamp": zone.get("start_timestamp"),
                "effective_timestamp": zone["effective_timestamp"],
                "invalidation_timestamp": zone["invalidation_timestamp"],
                "status": zone["status"],
                "strength": zone["strength"],
                "provenance": zone.get("provenance"),
                "historical_import": zone.get("historical_import", False),
                "created_at": zone.get("created_at"),
                "versions": copy.deepcopy(zone.get("versions", [])),
            }
        )
    return snapshots


def _strategy_snapshot(strategy: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(strategy.get(key))
        for key in (
            "id", "title", "registry_strategy_id", "short_description",
            "description", "hypothesis", "research_objective",
            "trading_concept", "risk_assumptions", "category", "rules",
            "variations", "created_at", "updated_at",
        )
    }


def _variation_snapshot(variation: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(variation)


def _dataset_snapshot(dataset_id: str, run: dict[str, Any]) -> dict[str, Any]:
    dataset = run.get("dataset") or {}
    metadata = copy.deepcopy(dataset.get("metadata", {}))
    try:
        metadata = copy.deepcopy(
            research_service.dataset_detail(dataset_id).get("metadata", metadata)
        )
    except Exception:
        pass
    return {
        "dataset_id": dataset_id,
        "hash": _dataset_hash(dataset_id),
        "symbol": dataset.get("symbol"),
        "timeframe": dataset.get("timeframe"),
        "provider": dataset.get("provider"),
        "first_timestamp": dataset.get("first_timestamp"),
        "last_timestamp": dataset.get("last_timestamp"),
        "bar_count": dataset.get("bar_count"),
        "metadata": metadata,
        "quality": copy.deepcopy(run.get("dataset_quality", {})),
    }


def _dataset_hash(dataset_id: str | None) -> str | None:
    if not dataset_id:
        return None
    try:
        symbol, timeframe, year = dataset_id.split("/")
        path = research_service.data_root() / symbol / timeframe / f"{int(year)}.csv"
        return sha256(path.read_bytes()).hexdigest()
    except Exception:
        return None


def _summary(strategy: dict[str, Any]) -> dict[str, Any]:
    variations = strategy.get("variations", [])
    baseline = next((item for item in variations if item.get("is_baseline")), None)
    experiments = strategy.get("experiments", [])
    for experiment in experiments:
        experiment.setdefault("strategy_id", strategy["id"])
    latest = _latest_experiment(strategy)
    instruments: list[str] = []
    timeframes: list[str] = []
    for variation in variations:
        for item in variation.get("instruments", []):
            if item not in instruments:
                instruments.append(item)
        for item in variation.get("timeframes", []):
            if item not in timeframes:
                timeframes.append(item)
    return {
        "id": strategy["id"],
        "title": strategy["title"],
        "registry_strategy_id": strategy.get("registry_strategy_id"),
        "short_description": strategy.get("short_description", ""),
        "description": strategy.get("description", ""),
        "hypothesis": strategy.get("hypothesis", ""),
        "research_objective": strategy.get("research_objective", ""),
        "trading_concept": strategy.get("trading_concept")
        or strategy.get("short_description", ""),
        "risk_assumptions": strategy.get("risk_assumptions")
        or "Research only: fixed-risk sizing, R-multiple outcomes, costs are optional assumptions.",
        "category": strategy.get("category", "Uncategorised"),
        "status": strategy.get("status", "Research"),
        "tags": list(strategy.get("tags", [])),
        "created_at": strategy.get("created_at"),
        "updated_at": strategy.get("updated_at"),
        "variation_count": len(variations),
        "baseline_variation_id": baseline.get("id") if baseline else None,
        "instruments": instruments,
        "timeframes": timeframes,
        "last_experiment_at": latest.get("executed_at") if latest else None,
        "linked_run_count": len(
            {item.get("run_id") for item in experiments if item.get("run_id")}
        ),
        "latest_experiment": _experiment_view(latest) if latest else None,
    }


def _experiment_view(experiment: dict[str, Any] | None) -> dict[str, Any] | None:
    if not experiment:
        return None
    result = experiment.get("result_reference", {})
    return {
        "id": experiment.get("id"),
        "strategy_id": experiment.get("strategy_id"),
        "name": experiment.get("name"),
        "variation_id": experiment.get("variation_id"),
        "kind": experiment.get("kind"),
        "experiment_kind": experiment.get("experiment_kind", experiment.get("kind")),
        "run_id": experiment.get("run_id"),
        "run_available": _run_available(experiment.get("run_id", "")),
        "dataset_id": experiment.get("dataset_id"),
        "instrument": experiment.get("instrument"),
        "timeframe": experiment.get("timeframe"),
        "start_date": experiment.get("start_date"),
        "end_date": experiment.get("end_date"),
        "executed_at": experiment.get("executed_at"),
        "status": experiment.get("status", "Completed"),
        "research_objective": experiment.get("research_objective", ""),
        "expected_outcome": experiment.get("expected_outcome", ""),
        "actual_outcome": experiment.get("actual_outcome", ""),
        "hypothesis_supported": experiment.get("hypothesis_supported"),
        "next_steps": experiment.get("next_steps", ""),
        "dataset_hash": experiment.get("dataset_hash"),
        "execution_configuration": copy.deepcopy(experiment.get("execution_configuration", {})),
        "risk_configuration": copy.deepcopy(experiment.get("risk_configuration", {})),
        "gross_results": copy.deepcopy(experiment.get("gross_results", {})),
        "net_results": copy.deepcopy(experiment.get("net_results", {})),
        "cost_profile": copy.deepcopy(experiment.get("cost_profile", {})),
        "validation_status": experiment.get("validation_status", "not_run"),
        "variation_version": experiment.get("variation_version"),
        "snapshot_version": experiment.get("snapshot_version"),
        "strategy_snapshot": copy.deepcopy(experiment.get("strategy_snapshot", {})),
        "variation_snapshot": copy.deepcopy(experiment.get("variation_snapshot", {})),
        "dataset_snapshot": copy.deepcopy(experiment.get("dataset_snapshot", {})),
        "model_versions": copy.deepcopy(experiment.get("model_versions", {})),
        "validation_reference": copy.deepcopy(experiment.get("validation_reference")),
        "reproductions": copy.deepcopy(experiment.get("reproductions", [])),
        "amendments": copy.deepcopy(experiment.get("amendments", [])),
        "hypothesis": experiment.get("hypothesis"),
        "configuration": copy.deepcopy(experiment.get("configuration", {})),
        "result_reference": copy.deepcopy(result),
        "notes": experiment.get("notes", ""),
        "metrics": copy.deepcopy(result.get("metrics", {})),
        "total_r": result.get("total_r"),
        "bar_count": result.get("bar_count"),
        "warnings": list(result.get("warnings", [])),
    }


def _detail(strategy: dict[str, Any]) -> dict[str, Any]:
    for experiment in strategy.get("experiments", []):
        experiment.setdefault("strategy_id", strategy["id"])
    result = _summary(strategy)
    result["rules"] = copy.deepcopy(strategy.get("rules", {}))
    result["notes"] = copy.deepcopy(strategy.get("notes", []))
    result["variations"] = copy.deepcopy(strategy.get("variations", []))
    result["experiments"] = [
        _experiment_view(item) for item in strategy.get("experiments", [])
    ]
    result["comparison"] = _comparison(strategy)
    return result


def _comparison(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for experiment in strategy.get("experiments", []):
        reference = experiment.get("result_reference", {})
        key = (
            experiment.get("dataset_id"),
            experiment.get("instrument"),
            experiment.get("timeframe"),
            experiment.get("start_date"),
            experiment.get("end_date"),
        )
        groups.setdefault(key, []).append(experiment)
    output: list[dict[str, Any]] = []
    for key, experiments in groups.items():
        variation_ids = {item.get("variation_id") for item in experiments}
        if len(variation_ids) < 2:
            continue
        rows = []
        for experiment in sorted(experiments, key=lambda item: item.get("executed_at") or ""):
            variation = next(
                (item for item in strategy["variations"] if item["id"] == experiment.get("variation_id")),
                None,
            )
            reference = experiment.get("result_reference", {})
            metrics = reference.get("metrics", {})
            rows.append(
                {
                    "experiment_id": experiment.get("id"),
                    "variation_id": experiment.get("variation_id"),
                    "variation_title": variation.get("title") if variation else "Archived variation",
                    "kind": experiment.get("kind"),
                    "run_id": experiment.get("run_id"),
                    "run_available": _run_available(experiment.get("run_id", "")),
                    "trade_count": metrics.get("total_trades"),
                    "win_rate": metrics.get("win_rate"),
                    "profit_factor": metrics.get("profit_factor"),
                    "expectancy": metrics.get("expectancy"),
                    "max_drawdown_r": metrics.get("max_drawdown_r"),
                    "avg_holding_duration": metrics.get("avg_holding_duration"),
                    "total_r": reference.get("total_r"),
                    "net_expectancy": (experiment.get("net_results") or {}).get("expectancy"),
                    "net_total_r": (
                        round(
                            float((experiment.get("net_results") or {}).get("expectancy", 0.0))
                            * int(metrics.get("total_trades", 0)),
                            10,
                        )
                        if (experiment.get("net_results") or {}).get("total_trades")
                        else None
                    ),
                    "cost_profile_id": (experiment.get("cost_profile") or {}).get("id"),
                    "total_cost_r": (experiment.get("result_reference") or {}).get("total_cost_r"),
                    "validation_status": experiment.get("validation_status"),
                    "sample_size_warning": (metrics.get("total_trades") or 0) < 100,
                }
            )
        output.append(
            {
                "dataset_id": key[0],
                "instrument": key[1],
                "timeframe": key[2],
                "start_date": key[3],
                "end_date": key[4],
                "comparable": True,
                "rows": rows,
            }
        )
    return output


@_workspace_locked
def list_strategies(
    *,
    query: str = "",
    status: str | None = None,
    category: str | None = None,
    sort: str = "recent",
) -> list[dict[str, Any]]:
    store = _load()
    needle = query.strip().casefold()
    rows = []
    for strategy in store["strategies"]:
        if status and strategy.get("status") != status:
            continue
        if category and strategy.get("category") != category:
            continue
        haystack = " ".join(
            [
                strategy.get("title", ""),
                strategy.get("registry_strategy_id") or "",
                strategy.get("short_description", ""),
                strategy.get("description", ""),
                " ".join(strategy.get("tags", [])),
            ]
        ).casefold()
        if needle and needle not in haystack:
            continue
        rows.append(_summary(strategy))
    if sort == "title":
        rows.sort(key=lambda item: item["title"].casefold())
    elif sort == "experiments":
        rows.sort(
            key=lambda item: (
                item["last_experiment_at"] or "",
                item["updated_at"] or "",
            ),
            reverse=True,
        )
    else:
        rows.sort(key=lambda item: item["updated_at"] or "", reverse=True)
    return rows


@_workspace_locked
def get_strategy(strategy_id: str) -> dict[str, Any]:
    return _detail(_strategy(_load(), strategy_id))


@_workspace_locked
def create_strategy(payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        store = _load()
        title = _text(payload.get("title"), "title", required=True, limit=200)
        if any(
            item["title"].casefold() == title.casefold()
            for item in store["strategies"]
        ):
            raise WorkspaceConflict(f"Strategy title already exists: {title}")
        registry_id = payload.get("registry_strategy_id") or None
        registry = _registry_strategy(registry_id)
        now = _now()
        strategy_id = _new_id("sw", title)
        variation = {
            "id": _new_id("var", f"{title}-baseline"),
            "title": _text(
                payload.get("baseline_title") or "V1 — Original baseline",
                "baseline_title",
                required=True,
                limit=200,
            ),
            "description": _text(
                payload.get("baseline_description")
                or "Baseline configuration created with the strategy.",
                "baseline_description",
                limit=MAX_TEXT,
            ),
            "hypothesis": _text(payload.get("baseline_hypothesis"), "baseline_hypothesis"),
            "changes_from_parent": "Original baseline.",
            "entry_rule_differences": "",
            "exit_rule_differences": "",
            "filter_differences": "",
            "parameter_config": _validate_parameter_config(
                registry, payload.get("baseline_parameters")
            ),
            "instruments": _string_list(
                payload.get("instruments"), "instruments"
            ),
            "timeframes": _string_list(
                payload.get("timeframes"),
                "timeframes",
                allowed=TIMEFRAMES,
            ) or list(TIMEFRAMES),
            "status": _status(payload.get("status") or "Draft"),
            "notes": _text(payload.get("baseline_notes"), "baseline_notes"),
            "is_baseline": True,
            "implementation_status": "implemented" if registry else "documentation_only",
            "registry_strategy_id": registry_id,
            "configuration_version": 1,
            "cloned_from": None,
            "created_at": now,
            "updated_at": now,
            "archived_at": None,
        }
        strategy = {
            "id": strategy_id,
            "title": title,
            "registry_strategy_id": registry_id,
            "short_description": _text(
                payload.get("short_description"), "short_description", required=True, limit=300
            ),
            "description": _text(payload.get("description"), "description"),
            "hypothesis": _text(payload.get("hypothesis"), "hypothesis"),
            "research_objective": _text(
                payload.get("research_objective"), "research_objective"
            ),
            "trading_concept": _text(payload.get("trading_concept"), "trading_concept"),
            "risk_assumptions": _text(payload.get("risk_assumptions"), "risk_assumptions"),
            "category": _text(
                payload.get("category") or "Uncategorised",
                "category",
                required=True,
                limit=100,
            ),
            "status": _status(payload.get("status") or "Draft"),
            "tags": _tags(payload.get("tags")),
            "created_at": now,
            "updated_at": now,
            "archived_at": None,
            "rules": {
                "implemented": (
                    copy.deepcopy(payload.get("implemented_rules", {}))
                    if registry
                    else {}
                ),
                "proposed": list(payload.get("proposed_rules", [])),
                "experimental": list(payload.get("experimental_rules", [])),
            },
            "notes": [],
            "variations": [variation],
            "experiments": [],
        }
        store["strategies"].append(strategy)
        _write_store(workspace_path(), store)
        return _detail(strategy)


@_workspace_locked
def update_strategy(strategy_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        store = _load()
        strategy = _strategy(store, strategy_id)
        for field, limit in (
            ("title", 200),
            ("short_description", 300),
            ("description", MAX_TEXT),
            ("hypothesis", MAX_TEXT),
            ("research_objective", MAX_TEXT),
            ("trading_concept", MAX_TEXT),
            ("risk_assumptions", MAX_TEXT),
            ("category", 100),
        ):
            if field in payload:
                value = _text(payload[field], field, required=field in {"title", "short_description", "category"}, limit=limit)
                if field == "title" and any(
                    item["id"] != strategy_id
                    and item["title"].casefold() == value.casefold()
                    for item in store["strategies"]
                ):
                    raise WorkspaceConflict(f"Strategy title already exists: {value}")
                strategy[field] = value
        if "status" in payload:
            strategy["status"] = _status(payload["status"])
            if strategy["status"] == "Archived":
                strategy["archived_at"] = _now()
            else:
                strategy["archived_at"] = None
        if "tags" in payload:
            strategy["tags"] = _tags(payload["tags"])
        if "rules" in payload:
            rules = payload["rules"]
            if not isinstance(rules, dict):
                raise WorkspaceValidationError("rules must be an object")
            for key in ("implemented", "proposed", "experimental"):
                if key in rules:
                    strategy["rules"][key] = copy.deepcopy(rules[key])
        strategy["updated_at"] = _now()
        _write_store(workspace_path(), store)
        return _detail(strategy)


@_workspace_locked
def archive_strategy(strategy_id: str) -> dict[str, Any]:
    return update_strategy(strategy_id, {"status": "Archived"})


@_workspace_locked
def add_note(strategy_id: str, body: str) -> dict[str, Any]:
    with _lock:
        store = _load()
        strategy = _strategy(store, strategy_id)
        note = {
            "id": _new_id("note", body[:30]),
            "body": _text(body, "body", required=True),
            "created_at": _now(),
            "updated_at": _now(),
        }
        strategy["notes"].append(note)
        strategy["updated_at"] = note["updated_at"]
        _write_store(workspace_path(), store)
        return note


@_workspace_locked
def update_note(strategy_id: str, note_id: str, body: str) -> dict[str, Any]:
    with _lock:
        store = _load()
        strategy = _strategy(store, strategy_id)
        note = next((item for item in strategy["notes"] if item.get("id") == note_id), None)
        if note is None:
            raise WorkspaceNotFound(f"Note not found: {note_id}")
        note["body"] = _text(body, "body", required=True)
        note["updated_at"] = _now()
        strategy["updated_at"] = note["updated_at"]
        _write_store(workspace_path(), store)
        return note


@_workspace_locked
def delete_note(strategy_id: str, note_id: str) -> dict[str, Any]:
    with _lock:
        store = _load()
        strategy = _strategy(store, strategy_id)
        before = len(strategy["notes"])
        strategy["notes"] = [item for item in strategy["notes"] if item.get("id") != note_id]
        if len(strategy["notes"]) == before:
            raise WorkspaceNotFound(f"Note not found: {note_id}")
        strategy["updated_at"] = _now()
        _write_store(workspace_path(), store)
        return {"deleted": note_id}


@_workspace_locked
def create_variation(strategy_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        store = _load()
        strategy = _strategy(store, strategy_id)
        if strategy.get("status") == "Archived":
            raise WorkspaceConflict("Archived strategies cannot receive new variations.")
        registry = _registry_strategy(strategy.get("registry_strategy_id"))
        now = _now()
        variation = {
            "id": _new_id("var", payload.get("title") or "variation"),
            "title": _text(payload.get("title"), "title", required=True, limit=200),
            "description": _text(payload.get("description"), "description"),
            "hypothesis": _text(payload.get("hypothesis"), "hypothesis"),
            "changes_from_parent": _text(
                payload.get("changes_from_parent"), "changes_from_parent"
            ),
            "entry_rule_differences": _text(
                payload.get("entry_rule_differences"), "entry_rule_differences"
            ),
            "exit_rule_differences": _text(
                payload.get("exit_rule_differences"), "exit_rule_differences"
            ),
            "filter_differences": _text(
                payload.get("filter_differences"), "filter_differences"
            ),
            "parameter_config": _validate_parameter_config(
                registry, payload.get("parameter_config")
            ),
            "zone_ids": [str(item).strip() for item in payload.get("zone_ids", []) if str(item).strip()],
            "instruments": _string_list(payload.get("instruments"), "instruments"),
            "timeframes": _string_list(
                payload.get("timeframes"), "timeframes", allowed=TIMEFRAMES
            ) or list(TIMEFRAMES),
            "status": _status(payload.get("status") or "Draft"),
            "notes": _text(payload.get("notes"), "notes"),
            "is_baseline": False,
            "implementation_status": "implemented" if registry else "documentation_only",
            "registry_strategy_id": strategy.get("registry_strategy_id"),
            "configuration_version": 1,
            "cloned_from": payload.get("cloned_from") or None,
            "created_at": now,
            "updated_at": now,
            "archived_at": None,
        }
        strategy["variations"].append(variation)
        strategy["updated_at"] = now
        _write_store(workspace_path(), store)
        return _detail(strategy)


@_workspace_locked
def update_variation(
    strategy_id: str, variation_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    with _lock:
        store = _load()
        strategy = _strategy(store, strategy_id)
        variation = _variation(strategy, variation_id)
        if variation.get("is_baseline") and _experiment_count(strategy, variation_id) > 0:
            raise WorkspaceConflict(
                "The baseline variation is locked after its first experiment. "
                "Clone it to a new variation for a versioned change."
            )
        registry = _registry_strategy(strategy.get("registry_strategy_id"))
        for field, limit in (
            ("title", 200),
            ("description", MAX_TEXT),
            ("hypothesis", MAX_TEXT),
            ("changes_from_parent", MAX_TEXT),
            ("entry_rule_differences", MAX_TEXT),
            ("exit_rule_differences", MAX_TEXT),
            ("filter_differences", MAX_TEXT),
            ("notes", MAX_TEXT),
        ):
            if field in payload:
                variation[field] = _text(payload[field], field, limit=limit)
        if "parameter_config" in payload:
            variation["parameter_config"] = _validate_parameter_config(
                registry, payload["parameter_config"]
            )
            variation["configuration_version"] = int(
                variation.get("configuration_version", 1)
            ) + 1
        if "zone_ids" in payload:
            variation["zone_ids"] = [
                str(item).strip() for item in payload["zone_ids"] if str(item).strip()
            ]
        if "instruments" in payload:
            variation["instruments"] = _string_list(payload["instruments"], "instruments")
        if "timeframes" in payload:
            variation["timeframes"] = _string_list(
                payload["timeframes"], "timeframes", allowed=TIMEFRAMES
            )
        if "status" in payload:
            variation["status"] = _status(payload["status"])
            variation["archived_at"] = _now() if variation["status"] == "Archived" else None
        variation["updated_at"] = _now()
        strategy["updated_at"] = variation["updated_at"]
        _write_store(workspace_path(), store)
        return _detail(strategy)


@_workspace_locked
def clone_variation(strategy_id: str, variation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        store = _load()
        strategy = _strategy(store, strategy_id)
        source = _variation(strategy, variation_id)
        body = copy.deepcopy(source)
        body.update(
            {
                "id": _new_id("var", payload.get("title") or source.get("title", "copy")),
                "title": _text(
                    payload.get("title") or f"{source.get('title', 'Variation')} — copy",
                    "title",
                    required=True,
                    limit=200,
                ),
                "is_baseline": False,
                "configuration_version": 1,
                "cloned_from": source["id"],
                "created_at": _now(),
                "updated_at": _now(),
                "archived_at": None,
            }
        )
        body["description"] = _text(
            payload.get("description") or source.get("description", ""),
            "description",
        )
        body["hypothesis"] = _text(
            payload.get("hypothesis") or source.get("hypothesis", ""), "hypothesis"
        )
        strategy["variations"].append(body)
        strategy["updated_at"] = body["updated_at"]
        _write_store(workspace_path(), store)
        return _detail(strategy)


@_workspace_locked
def archive_variation(strategy_id: str, variation_id: str) -> dict[str, Any]:
    with _lock:
        store = _load()
        strategy = _strategy(store, strategy_id)
        variation = _variation(strategy, variation_id)
        if variation.get("is_baseline"):
            raise WorkspaceConflict("The baseline variation cannot be archived.")
        return update_variation(strategy_id, variation_id, {"status": "Archived"})


@_workspace_locked
def record_experiment(strategy_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        store = _load()
        strategy = _strategy(store, strategy_id)
        if strategy.get("status") == "Archived":
            raise WorkspaceConflict("Archived strategies cannot receive new experiments.")
        variation_id = _text(payload.get("variation_id"), "variation_id", required=True)
        variation = _variation(strategy, variation_id)
        if variation.get("implementation_status") != "implemented":
            raise WorkspaceConflict(
                "This variation is documentation-only and cannot be executed. "
                "Link it to a registered implementation first."
            )
        if variation.get("status") == "Archived":
            raise WorkspaceConflict("Archived variations cannot receive new experiments.")
        registry_id = strategy.get("registry_strategy_id")
        if not registry_id:
            raise WorkspaceConflict("Strategy has no registered implementation.")
        run_id = _text(payload.get("run_id"), "run_id", required=True, limit=80)
        if any(item.get("run_id") == run_id for item in strategy["experiments"]):
            raise WorkspaceConflict("This run is already linked to an experiment.")
        try:
            run = research_service.get_run(run_id)
        except Exception as exc:
            raise WorkspaceValidationError(f"Backtest run is unavailable: {run_id}") from exc
        run_strategy_id = (run.get("strategy") or {}).get("id")
        if run_strategy_id != registry_id:
            raise WorkspaceValidationError(
                f"Run strategy {run_strategy_id!r} does not match workspace registry "
                f"strategy {registry_id!r}."
            )
        request = run.get("request") or {}
        dataset = run.get("dataset") or {}
        if variation.get("instruments") and dataset.get("symbol") not in variation["instruments"]:
            raise WorkspaceValidationError(
                f"Run instrument {dataset.get('symbol')!r} is not in this variation's instruments."
            )
        if variation.get("timeframes") and request.get("timeframe") not in variation["timeframes"]:
            raise WorkspaceValidationError(
                f"Run timeframe {request.get('timeframe')!r} is not in this variation's timeframes."
            )
        kind = payload.get("experiment_kind")
        existing = _experiment_count(strategy, variation_id)
        if kind is None:
            if existing == 0 and variation.get("is_baseline"):
                kind = "baseline"
            elif existing:
                kind = "repeat"
            else:
                kind = "experiment"
        if kind not in EXPERIMENT_KINDS:
            raise WorkspaceValidationError(
                "experiment_kind must be one of: " + ", ".join(EXPERIMENT_KINDS)
            )
        now = _now()
        executed_at = run.get("created_at") or now
        reference = {
            "run_id": run_id,
            "run_created_at": executed_at,
            "dataset_id": run.get("dataset_id"),
            "bar_count": run.get("bar_count"),
            "metrics": copy.deepcopy(run.get("metrics", {})),
            "warnings": list(run.get("warnings", [])),
            "assumptions": copy.deepcopy(run.get("assumptions", {})),
            "total_r": (
                round(
                    float((run.get("metrics") or {}).get("expectancy", 0.0))
                    * int((run.get("metrics") or {}).get("total_trades", 0)),
                    10,
                )
                if (run.get("metrics") or {}).get("total_trades")
                else 0.0
            ),
            "trades_truncated": bool(run.get("trades_truncated", False)),
            "total_cost_r": round(
                sum(float(item.get("total_cost_r") or 0.0) for item in run.get("trades", [])),
                10,
            ),
        }
        validation = validate_run(run)
        validation_ok = bool(validation.get("valid"))
        zone_snapshots = _zone_snapshots(list(run.get("zone_ids", [])))
        model_versions = copy.deepcopy(MODEL_VERSIONS)
        experiment = {
            "id": _new_id("exp", payload.get("name") or variation.get("title", "experiment")),
            "strategy_id": strategy_id,
            "name": _text(
                payload.get("name") or f"{variation.get('title')} · {run.get('dataset_id')}",
                "name",
                required=True,
                limit=200,
            ),
            "variation_id": variation_id,
            "variation_version": variation.get("configuration_version", 1),
            "hypothesis": _text(payload.get("hypothesis") or variation.get("hypothesis", ""), "hypothesis"),
            "experiment_kind": kind,
            "kind": kind,
            "status": "Completed" if validation_ok else "Failed",
            "dataset_id": run.get("dataset_id"),
            "dataset_hash": _dataset_hash(run.get("dataset_id")),
            "instrument": dataset.get("symbol"),
            "timeframe": request.get("timeframe"),
            "start_date": request.get("start"),
            "end_date": request.get("end"),
            "configuration": {
                "registry_strategy_id": registry_id,
                "variation_id": variation_id,
                "variation_version": variation.get("configuration_version", 1),
                "parameters": copy.deepcopy(run.get("parameters", {})),
                "r_multiple": request.get("r_multiple"),
                "equity": request.get("equity"),
                "risk_fraction": request.get("risk_fraction"),
                "entry_model": (run.get("assumptions") or {}).get("entry_model"),
                "zone_ids": list(run.get("zone_ids", [])),
                "zone_snapshots": zone_snapshots,
            },
            "strategy_snapshot": _strategy_snapshot(strategy),
            "variation_snapshot": _variation_snapshot(variation),
            "dataset_snapshot": _dataset_snapshot(run.get("dataset_id"), run),
            "backtest_parameters": {
                "dataset_id": run.get("dataset_id"),
                "strategy_id": registry_id,
                "timeframe": request.get("timeframe"),
                "start_date": request.get("start"),
                "end_date": request.get("end"),
                "parameters": copy.deepcopy(run.get("parameters", {})),
            },
            "model_versions": model_versions,
            "snapshot_version": EXPERIMENT_SNAPSHOT_VERSION,
            "validation_reference": {
                "status": "passed" if validation.get("valid") else "failed",
                "error_count": validation.get("error_count"),
                "warning_count": validation.get("warning_count"),
                "checked_trades": validation.get("checked_trades"),
            },
            "execution_configuration": {
                "entry_model": (run.get("assumptions") or {}).get("entry_model"),
                "timestamps": (run.get("assumptions") or {}).get("timestamps"),
                "costs_applied": (run.get("assumptions") or {}).get("costs_applied"),
                "policy": "fixed_risk_reward_v1",
                "sizing": "fill_time_fixed_risk_v1",
            },
            "risk_configuration": {
                "equity": request.get("equity"),
                "risk_fraction": request.get("risk_fraction"),
                "r_multiple": request.get("r_multiple"),
            },
            "cost_profile": copy.deepcopy(run.get("cost_profile", {})),
            "gross_results": copy.deepcopy(run.get("metrics", {})),
            "net_results": copy.deepcopy(run.get("net_metrics", {})),
            "validation_status": "passed" if validation_ok else "failed",
            "validation": validation,
            "research_objective": _text(
                payload.get("research_objective") or strategy.get("research_objective", ""),
                "research_objective",
            ),
            "expected_outcome": _text(payload.get("expected_outcome"), "expected_outcome"),
            "actual_outcome": _text(
                payload.get("actual_outcome")
                or f"gross expectancy {run.get('metrics', {}).get('expectancy')}R; "
                   f"net expectancy {(run.get('net_metrics') or {}).get('expectancy')}R",
                "actual_outcome",
            ),
            "hypothesis_supported": payload.get("hypothesis_supported")
            if isinstance(payload.get("hypothesis_supported"), bool)
            else None,
            "next_steps": _text(payload.get("next_steps"), "next_steps"),
            "executed_at": executed_at,
            "run_id": run_id,
            "result_reference": reference,
            "notes": _text(payload.get("notes"), "notes"),
            "created_at": now,
            "completed_at": executed_at if validation_ok else None,
            "reproductions": [],
        }
        strategy["experiments"].append(experiment)
        strategy["updated_at"] = now
        _write_store(workspace_path(), store)
        return _detail(strategy)


@_workspace_locked
def create_planned_experiment(strategy_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        store = _load()
        strategy = _strategy(store, strategy_id)
        if strategy.get("status") == "Archived":
            raise WorkspaceConflict("Archived strategies cannot receive planned experiments.")
        variation_id = _text(payload.get("variation_id"), "variation_id", required=True)
        variation = _variation(strategy, variation_id)
        if variation.get("implementation_status") != "implemented":
            raise WorkspaceConflict("Documentation-only variations cannot be planned for execution.")
        dataset_id = _text(payload.get("dataset_id"), "dataset_id", required=True)
        try:
            dataset = research_service.dataset_detail(dataset_id, timeframe=str(payload.get("timeframe") or "M1"))
        except Exception as exc:
            raise WorkspaceValidationError(f"Dataset is unavailable: {dataset_id}") from exc
        registry_id = strategy.get("registry_strategy_id")
        if not registry_id:
            raise WorkspaceConflict("Strategy has no registered implementation.")
        parameters = _validate_parameter_config(
            _registry_strategy(registry_id), payload.get("parameter_config")
        )
        cost_profile = payload.get("cost_profile") or {}
        now = _now()
        experiment = {
            "id": _new_id("exp", payload.get("name") or variation.get("title", "planned")),
            "strategy_id": strategy_id,
            "name": _text(payload.get("name") or f"{variation.get('title')} · planned", "name", required=True, limit=200),
            "variation_id": variation_id,
            "variation_version": variation.get("configuration_version", 1),
            "hypothesis": _text(payload.get("hypothesis") or variation.get("hypothesis", ""), "hypothesis"),
            "research_objective": _text(payload.get("research_objective") or strategy.get("research_objective", ""), "research_objective"),
            "expected_outcome": _text(payload.get("expected_outcome"), "expected_outcome"),
            "actual_outcome": "",
            "hypothesis_supported": None,
            "next_steps": _text(payload.get("next_steps"), "next_steps"),
            "status": "Planned",
            "experiment_kind": _text(payload.get("experiment_kind") or "experiment", "experiment_kind"),
            "kind": payload.get("experiment_kind") or "experiment",
            "dataset_id": dataset_id,
            "dataset_hash": _dataset_hash(dataset_id),
            "instrument": dataset.get("symbol"),
            "timeframe": str(payload.get("timeframe") or dataset.get("timeframe") or "M1"),
            "start_date": payload.get("start_date"),
            "end_date": payload.get("end_date"),
            "configuration": {
                "registry_strategy_id": registry_id,
                "variation_id": variation_id,
                "variation_version": variation.get("configuration_version", 1),
                "parameters": parameters,
                "zone_ids": list(payload.get("zone_ids") or []),
                "zone_snapshots": _zone_snapshots(list(payload.get("zone_ids") or [])),
            },
            "strategy_snapshot": _strategy_snapshot(strategy),
            "variation_snapshot": _variation_snapshot(variation),
            "dataset_snapshot": _dataset_snapshot(dataset_id, {"dataset": dataset}),
            "backtest_parameters": {
                "dataset_id": dataset_id,
                "strategy_id": registry_id,
                "timeframe": str(payload.get("timeframe") or dataset.get("timeframe") or "M1"),
                "start_date": payload.get("start_date"),
                "end_date": payload.get("end_date"),
                "parameters": parameters,
            },
            "model_versions": copy.deepcopy(MODEL_VERSIONS),
            "snapshot_version": EXPERIMENT_SNAPSHOT_VERSION,
            "validation_reference": None,
            "reproductions": [],
            "execution_configuration": {
                "cost_profile_id": cost_profile.get("id") if isinstance(cost_profile, dict) else None,
                "cost_profile": cost_profile if isinstance(cost_profile, dict) else {},
            },
            "risk_configuration": {
                "equity": payload.get("equity"),
                "risk_fraction": payload.get("risk_fraction"),
                "r_multiple": payload.get("r_multiple"),
            },
            "cost_profile": cost_profile if isinstance(cost_profile, dict) else {},
            "gross_results": {},
            "net_results": {},
            "validation_status": "not_run",
            "validation": None,
            "run_id": None,
            "result_reference": {},
            "notes": _text(payload.get("notes"), "notes"),
            "created_at": now,
            "completed_at": None,
        }
        strategy["experiments"].append(experiment)
        strategy["updated_at"] = now
        _write_store(workspace_path(), store)
        return _detail(strategy)


@_workspace_locked
def update_experiment(strategy_id: str, experiment_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        store = _load()
        strategy = _strategy(store, strategy_id)
        experiment = next(
            (item for item in strategy["experiments"] if item.get("id") == experiment_id),
            None,
        )
        if experiment is None:
            raise WorkspaceNotFound(f"Experiment not found: {experiment_id}")
        narrative_fields = {"notes", "actual_outcome", "next_steps", "hypothesis_supported"}
        if experiment.get("status") == "Completed" and narrative_fields.intersection(payload):
            raise WorkspaceConflict(
                "Completed experiments are immutable; use append-only amendments."
            )
        if "status" in payload:
            status = payload["status"]
            if status not in EXPERIMENT_STATUSES:
                raise WorkspaceValidationError(
                    "status must be one of: " + ", ".join(EXPERIMENT_STATUSES)
                )
            if experiment.get("status") == "Completed" and status not in {"Completed", "Archived"}:
                raise WorkspaceConflict("Completed experiment results cannot be reopened.")
            if status == "Completed":
                if not experiment.get("run_id") or not experiment.get("result_reference"):
                    raise WorkspaceConflict(
                        "Completed experiments require a linked run and result reference."
                    )
                if experiment.get("validation_status") != "passed":
                    raise WorkspaceConflict(
                        "Completed experiments require a successful independent validation."
                    )
            experiment["status"] = status
            if status == "Completed" and not experiment.get("completed_at"):
                experiment["completed_at"] = _now()
        for field in ("notes", "actual_outcome", "next_steps"):
            if field in payload:
                experiment[field] = _text(payload[field], field)
        if "hypothesis_supported" in payload:
            if payload["hypothesis_supported"] is not None and not isinstance(payload["hypothesis_supported"], bool):
                raise WorkspaceValidationError("hypothesis_supported must be boolean or null")
            experiment["hypothesis_supported"] = payload["hypothesis_supported"]
        strategy["updated_at"] = _now()
        _write_store(workspace_path(), store)
        return _detail(strategy)


@_workspace_locked
def amend_experiment(
    strategy_id: str, experiment_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Append an amendment to a completed experiment without changing the original."""
    with _lock:
        store = _load()
        strategy = _strategy(store, strategy_id)
        experiment = next(
            (item for item in strategy["experiments"] if item.get("id") == experiment_id),
            None,
        )
        if experiment is None:
            raise WorkspaceNotFound(f"Experiment not found: {experiment_id}")
        if experiment.get("status") != "Completed":
            raise WorkspaceConflict("Only completed experiments can be amended.")
        allowed = {"notes", "actual_outcome", "hypothesis_supported", "next_steps"}
        changes = {key: payload[key] for key in allowed if key in payload}
        if not changes:
            raise WorkspaceValidationError("No amendable field supplied.")
        amendments = experiment.setdefault("amendments", [])
        for field, new_value in changes.items():
            previous = experiment.get(field)
            if field == "hypothesis_supported" and new_value is not None and not isinstance(new_value, bool):
                raise WorkspaceValidationError("hypothesis_supported must be boolean or null")
            amendments.append(
                {
                    "id": _new_id("amend", field),
                    "experiment_id": experiment_id,
                    "created_at": _now(),
                    "author": _text(payload.get("author") or "local-user", "author"),
                    "field": field,
                    "previous_value": copy.deepcopy(previous),
                    "new_value": copy.deepcopy(new_value),
                    "reason": _text(payload.get("reason") or "Amended research note", "reason"),
                }
            )
        strategy["updated_at"] = _now()
        _write_store(workspace_path(), store)
        return _detail(strategy)


def _zone_books_from_snapshots(snapshots: list[dict[str, Any]]) -> dict[str, ZoneBook]:
    grouped: dict[str, list[Zone]] = {}
    for item in snapshots:
        instrument = str(item.get("instrument") or "")
        if not instrument:
            raise ReproductionError("ZONE_SNAPSHOT_INVALID", "Zone snapshot has no instrument.")
        kind = item.get("zone_type")
        zone = Zone(
            id=int(sha256(str(item.get("id", "")).encode()).hexdigest()[:8], 16),
            name=f"repro:{str(item.get('id', ''))[:8]}",
            low=float(item["low"]),
            high=float(item["high"]),
            timeframe=str(item.get("source_timeframe") or "M1").lower(),
            strength=int(item.get("strength", 0)),
            kind=ZoneKind(kind) if kind in {"supply", "demand"} else None,
            source=ZoneSource.MANUAL,
        )
        grouped.setdefault(instrument, []).append(zone)
    return {symbol: ZoneBook(symbol=symbol, zones=tuple(zones)) for symbol, zones in grouped.items()}


def _compare_reproduction(original: dict[str, Any], reproduced: dict[str, Any]) -> dict[str, Any]:
    differences: list[str] = []
    for group in ("metrics", "net_metrics"):
        left = original.get(group) or {}
        right = reproduced.get(group) or {}
        for key in (
            "total_trades",
            "win_rate",
            "profit_factor",
            "expectancy",
            "max_drawdown_r",
            "total_signals",
        ):
            a = left.get(key)
            b = right.get(key)
            if a is None and b is None:
                continue
            if a is None or b is None or abs(float(a) - float(b)) > 1e-8:
                differences.append(f"{group}.{key}: {a} != {b}")
    return {"matches": not differences, "differences": differences}


@_workspace_locked
def reproduce_experiment(strategy_id: str, experiment_id: str) -> dict[str, Any]:
    """Replay a completed experiment from its immutable snapshot via BacktestRunner."""
    with _lock:
        store = _load()
        strategy = _strategy(store, strategy_id)
        experiment = next(
            (item for item in strategy["experiments"] if item.get("id") == experiment_id),
            None,
        )
        if experiment is None:
            raise WorkspaceNotFound(f"Experiment not found: {experiment_id}")
        if experiment.get("status") != "Completed":
            raise ReproductionError("EXPERIMENT_NOT_COMPLETED", "Only completed experiments can be reproduced.")
        snapshot_version = experiment.get("snapshot_version")
        strategy_snapshot = experiment.get("strategy_snapshot")
        variation_snapshot = experiment.get("variation_snapshot")
        dataset_snapshot = experiment.get("dataset_snapshot")
        backtest = experiment.get("backtest_parameters")
        model_versions = experiment.get("model_versions")
        if (
            snapshot_version != EXPERIMENT_SNAPSHOT_VERSION
            or not strategy_snapshot
            or not variation_snapshot
            or not dataset_snapshot
            or not backtest
            or not model_versions
        ):
            raise ReproductionError(
                "SNAPSHOT_MISSING",
                "This experiment predates the immutable-snapshot format and cannot be reproduced exactly.",
            )
        if model_versions != MODEL_VERSIONS:
            raise ReproductionError(
                "MODEL_VERSION_INCOMPATIBLE",
                "The current code/model versions differ from the experiment snapshot.",
            )
        expected_hash = dataset_snapshot.get("hash")
        actual_hash = _dataset_hash(experiment.get("dataset_id"))
        if not expected_hash or expected_hash != actual_hash:
            raise ReproductionError(
                "DATASET_HASH_MISMATCH",
                "The dataset hash does not match the experiment snapshot.",
            )
        current_strategy = next(
            (item for item in research_service.list_strategies()
             if item["id"] == strategy_snapshot.get("registry_strategy_id")),
            None,
        )
        if current_strategy is None or current_strategy["id"] != strategy.get("registry_strategy_id"):
            raise ReproductionError(
                "STRATEGY_UNAVAILABLE",
                "The registered strategy for this snapshot is unavailable or changed.",
            )
        if strategy_snapshot.get("rules") != strategy.get("rules"):
            raise ReproductionError(
                "STRATEGY_DEFINITION_CHANGED",
                "The strategy rules differ from the immutable experiment snapshot.",
            )
        configuration = experiment.get("configuration") or {}
        zone_snapshots = configuration.get("zone_snapshots") or []
        requested_zones = configuration.get("zone_ids") or []
        if requested_zones and len(zone_snapshots) != len(requested_zones):
            raise ReproductionError(
                "ZONE_SNAPSHOT_INCOMPLETE",
                "The experiment snapshot does not contain every selected zone version.",
            )
        zones = _zone_books_from_snapshots(zone_snapshots)
        try:
            profile = CostProfile.from_dict(experiment.get("cost_profile") or {})
        except Exception as exc:
            raise ReproductionError(
                "COST_SNAPSHOT_INVALID",
                "The experiment cost profile snapshot is unavailable or invalid.",
            ) from exc
        risk = experiment.get("risk_configuration") or {}
        request = experiment.get("backtest_parameters") or {}
        try:
            start = date.fromisoformat(str(request.get("start_date"))) if request.get("start_date") else None
            end = date.fromisoformat(str(request.get("end_date"))) if request.get("end_date") else None
            reproduced_run = research_service.run_backtest(
                dataset_id=str(experiment.get("dataset_id")),
                strategy_id=str(strategy_snapshot.get("registry_strategy_id")),
                timeframe=str(experiment.get("timeframe") or "M1"),
                parameters=copy.deepcopy(configuration.get("parameters", {})),
                start=start,
                end=end,
                r_multiple=float(risk.get("r_multiple", 2.0)),
                equity=float(risk.get("equity", 100_000.0)),
                risk_fraction=float(risk.get("risk_fraction", 0.01)),
                cost_profile_id=profile.id,
                zone_ids=list(requested_zones),
                zone_books_override=zones,
                cost_profile_override=profile,
            )
        except Exception as exc:
            if isinstance(exc, ReproductionError):
                raise
            raise ReproductionError(
                "REPRODUCTION_EXECUTION_FAILED",
                f"BacktestRunner could not reproduce the snapshot: {exc}",
            ) from exc
        original_run = None
        try:
            original_run = research_service.get_run(str(experiment.get("run_id")))
        except Exception:
            original_run = None
        comparison = (
            _compare_reproduction(original_run, reproduced_run)
            if original_run is not None
            else {"matches": None, "differences": ["original run unavailable"]}
        )
        record = {
            "id": _new_id("repro", experiment_id),
            "source_experiment_id": experiment_id,
            "run_id": reproduced_run.get("id"),
            "created_at": _now(),
            "status": "Completed",
            "snapshot_version": snapshot_version,
            "comparison": comparison,
        }
        experiment.setdefault("reproductions", []).append(record)
        strategy["updated_at"] = _now()
        _write_store(workspace_path(), store)
        detail = _detail(strategy)
        return {"experiment": next(item for item in detail["experiments"] if item["id"] == experiment_id), "reproduction": record}


@_workspace_locked
def delete_experiment(strategy_id: str, experiment_id: str) -> dict[str, Any]:
    """Experiments are archived, never deleted."""
    return update_experiment(strategy_id, experiment_id, {"status": "Archived"})


@_workspace_locked
def dashboard() -> dict[str, Any]:
    """Real-data research dashboard summary for P2."""
    store = _load()
    strategies = store["strategies"]
    by_status: dict[str, int] = {status: 0 for status in STATUSES}
    variation_count = 0
    experiments = []
    for strategy in strategies:
        by_status[strategy.get("status", "Research")] = (
            by_status.get(strategy.get("status", "Research"), 0) + 1
        )
        variation_count += len(strategy.get("variations", []))
        for experiment in strategy.get("experiments", []):
            experiment.setdefault("strategy_id", strategy["id"])
            experiments.append(
                {
                    **_experiment_view(experiment),
                    "strategy_title": strategy.get("title"),
                }
            )
    experiments.sort(key=lambda item: item.get("executed_at") or "", reverse=True)
    status_counts: dict[str, int] = {
        status: 0 for status in EXPERIMENT_STATUSES
    }
    for experiment in experiments:
        status_counts[experiment.get("status", "Completed")] = (
            status_counts.get(experiment.get("status", "Completed"), 0) + 1
        )
    datasets = research_service.list_datasets()
    return {
        "strategy_count": len(strategies),
        "variation_count": variation_count,
        "baseline_count": sum(
            1 for item in strategies if item.get("variations")
        ),
        "strategy_status_counts": by_status,
        "experiment_status_counts": status_counts,
        "experiment_count": len(experiments),
        "recent_experiments": experiments[:8],
        "recent_runs": research_service.list_runs(limit=8),
        "dataset_count": len(datasets),
        "dataset_warning_count": sum(
            1 for item in datasets if item.get("status") != "ok"
        ),
        "outstanding_experiments": sum(
            1 for item in experiments if item.get("status") in {"Planned", "Running"}
        ),
        "failed_experiments": status_counts.get("Failed", 0),
        "validation_failures": sum(
            1
            for item in experiments
            if item.get("validation_status") == "failed"
        ),
    }
