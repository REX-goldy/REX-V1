"""Read/run services for the REX terminal.

This module is intentionally thin: it composes existing REX components
(historical storage/parser, registry, BacktestRunner, downloader) and shapes
their results for the UI. It does not implement a second backtest engine.
"""

from __future__ import annotations

import copy
import json
import os
import re
import threading
import uuid
from collections import Counter
from dataclasses import asdict, replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from backtests.backtest_runner import BacktestRunner
from backtests.costs import CostProfile, TransactionCostModel, get_cost_profile
from backtests.results import BacktestResult
from core.market import registered_instruments
from execution.factories import (
    SweepTradeSetupFactory,
    ZoneBreakoutRetestTradeSetupFactory,
)
from execution.planner import TradePlanner
from execution.policies import FixedRiskRewardPolicy
from execution.sizers import FixedRiskSizer
from historical.bar_contract import assess_dataset_quality
from historical.calendar import is_fx_market_open_minute_utc
from historical.config import load_historical_config
from historical.downloader import HistoricalDownloader, build_source
from historical.exceptions import HistoricalConfigurationError, HistoricalParseError
from historical.parser import HistoricalDataParser
from historical.quality import DatasetQualityError, build_dataset_quality_report
from server.zone_store import build_zone_books
from historical.storage import HistoricalStorage
from models.account_context import AccountContext
from models.bar import Bar
from research.free_ohlc.resampler import resample_bars, timeframe_minutes
from server.provider_keys import get_provider_key, has_provider_key
from strategies.breakout import BreakoutStrategy
from strategies.breakout_retest import S002_BreakoutRetest
from strategies.liquidity_sweep import LiquiditySweepStrategy
from strategies.registry import build_default_registry

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data" / "historical"
DEFAULT_RUNS_DIR = ROOT / "research" / "outputs" / "ui_runs"
MAX_DOWNLOAD_DAYS = 31
DOWNLOAD_SYMBOLS = (
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
    "USDCAD",
    "NZDUSD",
    "USDCHF",
)
DOWNLOAD_TIMEFRAMES = ("M1",)
UI_TIMEFRAMES = ("M1", "M5", "M15", "H1", "H4")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_download_lock = threading.Lock()
_summary_cache: dict[tuple[str, int, int, int], dict[str, Any]] = {}
_summary_cache_lock = threading.Lock()
_frame_cache: dict[tuple[str, int, str], tuple[Bar, ...]] = {}
_frame_cache_lock = threading.Lock()
_bars_cache: dict[tuple[str, int, int], tuple[Bar, ...]] = {}
_bars_cache_lock = threading.Lock()


class DownloadBusyError(RuntimeError):
    """Raised when another download is already running."""


class DatasetNotFoundError(LookupError):
    """Raised when a dataset file cannot be resolved."""


def data_root() -> Path:
    return Path(os.environ.get("REX_DATA_DIR", str(DEFAULT_DATA_DIR)))


def runs_root() -> Path:
    return Path(os.environ.get("REX_RUNS_DIR", str(DEFAULT_RUNS_DIR)))


def has_twelve_data_key() -> bool:
    return has_provider_key("twelve_data")


# ---------------------------------------------------------------------------
# Instruments and strategies
# ---------------------------------------------------------------------------


def list_instruments() -> list[dict[str, Any]]:
    instruments: list[dict[str, Any]] = []
    for item in registered_instruments():
        instruments.append(
            {
                "symbol": item.symbol,
                "market": item.market.id,
                "asset_class": item.market.asset_class.value,
                "pip_size": item.effective_pip_size,
                "tick_size": item.tick_size,
                "research_enabled": item.research_enabled,
                "display_name": item.market.display_name,
            }
        )
    return instruments


STRATEGY_SPECS: dict[str, dict[str, Any]] = {
    "CORE_ZONE_BREAKOUT": {
        "trade_simulation": False,
        "requires_zones": True,
        "parameters": [],
        "note": (
            "Signal study only. The default execution layer has no breakout "
            "setup factory, so this strategy cannot be trade-simulated yet."
        ),
    },
    "S002": {
        "trade_simulation": True,
        "requires_zones": True,
        "parameters": [
            {
                "name": "tolerance",
                "label": "Retest tolerance",
                "type": "number",
                "default": 0.0005,
                "min": 0.00001,
                "max": 0.05,
                "step": 0.0001,
                "help": "Price tolerance around the broken zone boundary.",
            },
            {
                "name": "max_wait",
                "label": "Max wait (bars)",
                "type": "integer",
                "default": 5,
                "min": 1,
                "max": 200,
                "step": 1,
                "help": "Bars after breakout to accept a retest.",
            },
        ],
        "note": "Zone breakout → retest. Uses static manual zones.",
    },
    "S008": {
        "trade_simulation": True,
        "requires_zones": False,
        "parameters": [
            {
                "name": "lookback",
                "label": "Swing lookback",
                "type": "integer",
                "default": 10,
                "min": 2,
                "max": 200,
                "step": 1,
                "help": "Bars used to define the prior swing high/low.",
            },
            {
                "name": "min_wick_ratio",
                "label": "Minimum wick ratio",
                "type": "number",
                "default": 0.6,
                "min": 0.0,
                "max": 1.0,
                "step": 0.01,
                "help": "Wick-to-range ratio required for a sweep.",
            },
            {
                "name": "tolerance",
                "label": "Sweep tolerance",
                "type": "number",
                "default": 0.0,
                "min": 0.0,
                "max": 0.05,
                "step": 0.0001,
                "help": "Extra distance beyond the swing required to sweep.",
            },
        ],
        "note": "Liquidity sweep. Trade simulation is wired to the sweep factory.",
    },
}


def list_strategies() -> list[dict[str, Any]]:
    strategies: list[dict[str, Any]] = []
    for strategy_id, strategy_class in build_default_registry().items():
        spec = STRATEGY_SPECS.get(strategy_id, {})
        strategies.append(
            {
                "id": strategy_id,
                "name": strategy_class.strategy_name,
                "description": strategy_class.description,
                "trade_simulation": bool(spec.get("trade_simulation", False)),
                "requires_zones": bool(spec.get("requires_zones", False)),
                "parameters": spec.get("parameters", []),
                "note": spec.get("note", ""),
            }
        )
    return strategies


# ---------------------------------------------------------------------------
# Dataset scanning
# ---------------------------------------------------------------------------


def _dataset_path(symbol: str, timeframe: str, year: int) -> Path:
    if not re.fullmatch(r"[A-Z0-9]{3,12}", symbol.upper()):
        raise DatasetNotFoundError("Invalid symbol")
    if not re.fullmatch(r"[A-Z0-9]{1,8}", timeframe.upper()):
        raise DatasetNotFoundError("Invalid timeframe")
    if not 1990 <= int(year) <= 2200:
        raise DatasetNotFoundError("Invalid year")
    return data_root() / symbol.upper() / timeframe.upper() / f"{int(year)}.csv"


def _dataset_id(symbol: str, timeframe: str, year: int) -> str:
    return f"{symbol.upper()}/{timeframe.upper()}/{int(year)}"


def _parse_dataset_id(dataset_id: str) -> tuple[str, str, int]:
    parts = dataset_id.split("/")
    if len(parts) != 3:
        raise DatasetNotFoundError("Dataset id must be SYMBOL/TIMEFRAME/YEAR")
    symbol, timeframe, year_text = parts
    try:
        year = int(year_text)
    except ValueError as exc:
        raise DatasetNotFoundError("Dataset year is invalid") from exc
    path = _dataset_path(symbol, timeframe, year)
    if not path.is_file():
        raise DatasetNotFoundError(f"Dataset not found: {dataset_id}")
    return symbol.upper(), timeframe.upper(), year


def _load_bars(symbol: str, timeframe: str, year: int) -> list[Bar]:
    path = _dataset_path(symbol, timeframe, year)
    if not path.is_file():
        raise DatasetNotFoundError(f"Dataset not found: {path.name}")
    try:
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        key = None
    if key is not None:
        with _bars_cache_lock:
            cached = _bars_cache.get(key)
        if cached is not None:
            return list(cached)
    parsed = tuple(HistoricalDataParser().parse_file(path, symbol))
    if key is not None:
        with _bars_cache_lock:
            _bars_cache[key] = parsed
    return list(parsed)


def _normalize_timeframe(timeframe: str) -> str:
    tf = timeframe.strip().upper()
    if tf not in UI_TIMEFRAMES:
        raise ValueError(
            "Timeframe must be one of: " + ", ".join(UI_TIMEFRAMES)
        )
    return tf


def _load_frame_bars(
    symbol: str,
    stored_timeframe: str,
    year: int,
    timeframe: str,
) -> list[Bar]:
    tf = _normalize_timeframe(timeframe)
    if tf == stored_timeframe.upper():
        return _load_bars(symbol, stored_timeframe, year)
    if stored_timeframe.upper() != "M1":
        raise ValueError(
            f"Dataset {symbol}/{stored_timeframe}/{year} is not M1; "
            "higher timeframes are only derived from M1 storage."
        )
    path = _dataset_path(symbol, stored_timeframe, year)
    try:
        key = (str(path), path.stat().st_mtime_ns, tf)
    except OSError:
        key = None
    if key is not None:
        with _frame_cache_lock:
            cached = _frame_cache.get(key)
        if cached is not None:
            return list(cached)
    stored = _load_bars(symbol, stored_timeframe, year)
    resolved = tuple(resample_bars(stored, target_timeframe=tf).bars)
    if key is not None:
        with _frame_cache_lock:
            _frame_cache[key] = resolved
    return list(resolved)


def _frame_summary(
    symbol: str,
    stored_timeframe: str,
    year: int,
    timeframe: str,
) -> dict[str, Any]:
    tf = _normalize_timeframe(timeframe)
    base = _dataset_summary(symbol, stored_timeframe, year)
    if tf == stored_timeframe.upper():
        base["derived"] = False
        base["available_timeframes"] = (
            list(UI_TIMEFRAMES) if stored_timeframe.upper() == "M1" else [stored_timeframe.upper()]
        )
        return base
    try:
        bars = _load_frame_bars(symbol, stored_timeframe, year, tf)
    except (ValueError, HistoricalParseError) as exc:
        base["derived"] = True
        base["timeframe"] = tf
        base["error"] = str(exc)
        return base
    quality = assess_dataset_quality(
        bars,
        instrument=symbol,
        timeframe=tf,
        provider=str(base.get("provider") or "unknown"),
        coverage_start=base["coverage"].get("start"),
        coverage_end=base["coverage"].get("end"),
        expected_step_minutes=timeframe_minutes(tf),
    )
    unexpected = _unexpected_gap_count(bars, timeframe_minutes(tf))
    frame_warnings = list(base.get("warnings", []))
    if unexpected:
        frame_warnings.append(
            f"{unexpected} unexpected timestamp gaps beyond FX closures."
        )
    frame_warnings.append(
        f"{tf} is derived from stored M1 with the existing resampler; "
        "incomplete buckets are skipped and no derived data is persisted."
    )
    result = dict(base)
    result.update(
        {
            "id": f"{symbol}/{stored_timeframe.upper()}/{year}",
            "timeframe": tf,
            "derived": True,
            "derived_from": stored_timeframe.upper(),
            "bar_count": quality.bar_count,
            "first_timestamp": (
                quality.first_timestamp.isoformat() if quality.first_timestamp else None
            ),
            "last_timestamp": (
                quality.last_timestamp.isoformat() if quality.last_timestamp else None
            ),
            "available_timeframes": list(UI_TIMEFRAMES),
            "warnings": frame_warnings,
            "quality": {
                "duplicate_count": quality.duplicate_count,
                "invalid_bar_count": quality.invalid_bar_count,
                "timestamp_gap_count": quality.timestamp_gap_count,
                "unexpected_gap_count": unexpected,
                "notes": list(quality.notes),
            },
        }
    )
    result["coverage"] = dict(base.get("coverage", {}))
    result["coverage"]["actual_start"] = result["first_timestamp"]
    result["coverage"]["actual_end"] = result["last_timestamp"]
    result["status"] = "warning" if result["warnings"] else "ok"
    return result


def _range_bars(
    bars: list[Bar],
    start: date | None,
    end: date | None,
) -> list[Bar]:
    selected = bars
    if start:
        selected = [bar for bar in selected if bar.timestamp.date() >= start]
    if end:
        selected = [bar for bar in selected if bar.timestamp.date() <= end]
    return selected


def range_summary(
    dataset_id: str,
    *,
    timeframe: str = "M1",
    start: date | None = None,
    end: date | None = None,
) -> dict[str, Any]:
    symbol, stored_timeframe, year = _parse_dataset_id(dataset_id)
    tf = _normalize_timeframe(timeframe)
    frame = _frame_summary(symbol, stored_timeframe, year, tf)
    bars = _load_frame_bars(symbol, stored_timeframe, year, tf)
    first = bars[0].timestamp if bars else None
    last = bars[-1].timestamp if bars else None
    errors: list[str] = []
    if start and end and start > end:
        errors.append("Start date is after the end date.")
    if not bars:
        errors.append("This frame contains no bars.")
    else:
        assert first is not None and last is not None
        if start and start < first.date():
            errors.append(
                f"Start date {start.isoformat()} is before the first available bar "
                f"({first.date().isoformat()})."
            )
        if end and end > last.date():
            errors.append(
                f"End date {end.isoformat()} is after the last available bar "
                f"({last.date().isoformat()})."
            )
    selected = _range_bars(bars, start, end)
    if bars and not selected:
        errors.append("The selected range contains no bars.")
    elif len(selected) < 2:
        errors.append(
            f"The selected range contains {len(selected)} bar(s); at least 2 are required."
        )
    step = timeframe_minutes(tf) * 60
    gap_count = 0
    unexpected_gaps = 0
    for left, right in zip(selected, selected[1:]):
        if (right.timestamp - left.timestamp).total_seconds() > step:
            gap_count += 1
            cursor = left.timestamp + timedelta(minutes=1)
            while cursor < right.timestamp:
                if is_fx_market_open_minute_utc(cursor):
                    unexpected_gaps += 1
                    break
                cursor += timedelta(minutes=1)
    return {
        "dataset_id": dataset_id,
        "timeframe": tf,
        "derived": bool(frame.get("derived")),
        "requested_start": start.isoformat() if start else None,
        "requested_end": end.isoformat() if end else None,
        "first_available": first.isoformat() if first else None,
        "last_available": last.isoformat() if last else None,
        "bar_count": len(selected),
        "total_frame_bars": len(bars),
        "gap_count": gap_count,
        "unexpected_gap_count": unexpected_gaps,
        "valid": not errors,
        "error": " ".join(errors),
        "frame_warnings": frame.get("warnings", []),
        "quality": frame.get("quality", {}),
    }


def _read_meta(symbol: str, timeframe: str, year: int) -> dict[str, Any]:
    meta = HistoricalStorage(data_root()).read_metadata(symbol, timeframe, year)
    return meta or {}


def _unexpected_gap_count(bars: list[Bar], step_minutes: int = 1) -> int:
    """Count gaps that contain at least one FX-open minute (not closures)."""
    count = 0
    for left, right in zip(bars, bars[1:]):
        if (right.timestamp - left.timestamp).total_seconds() <= step_minutes * 60:
            continue
        cursor = left.timestamp + timedelta(minutes=1)
        while cursor < right.timestamp:
            if is_fx_market_open_minute_utc(cursor):
                count += 1
                break
            cursor += timedelta(minutes=1)
    return count


def _dataset_summary(symbol: str, timeframe: str, year: int) -> dict[str, Any]:
    path = _dataset_path(symbol, timeframe, year)
    meta_path = path.with_suffix(".meta.json")
    try:
        stat = path.stat()
        meta_stat = meta_path.stat()
        cache_key = (
            str(path),
            stat.st_mtime_ns,
            stat.st_size,
            meta_stat.st_mtime_ns,
        )
    except OSError:
        cache_key = None
    if cache_key is not None:
        with _summary_cache_lock:
            cached = _summary_cache.get(cache_key)
        if cached is not None:
            return copy.deepcopy(cached)
    meta = _read_meta(symbol, timeframe, year)
    provider = str(meta.get("provider") or "unknown")
    warnings: list[str] = []
    try:
        bars = _load_bars(symbol, timeframe, year)
    except (HistoricalParseError, DatasetNotFoundError) as exc:
        return {
            "id": _dataset_id(symbol, timeframe, year),
            "symbol": symbol,
            "timeframe": timeframe,
            "year": year,
            "provider": provider,
            "bar_count": 0,
            "size_bytes": path.stat().st_size if path.exists() else 0,
            "status": "error",
            "warnings": [str(exc)],
            "coverage": {},
            "quality": {"unexpected_gap_count": 0},
            "first_timestamp": None,
            "last_timestamp": None,
            "derived": False,
            "available_timeframes": (
                list(UI_TIMEFRAMES) if timeframe.upper() == "M1" else [timeframe.upper()]
            ),
        }

    quality = assess_dataset_quality(
        bars,
        instrument=symbol,
        timeframe=timeframe,
        provider=provider,
        coverage_start=meta.get("start_date"),
        coverage_end=meta.get("end_date"),
        expected_step_minutes=1,
    )
    unexpected_gaps = _unexpected_gap_count(bars)
    if provider == "unknown":
        warnings.append("No provenance metadata; provider is unknown.")
    if quality.duplicate_count:
        warnings.append(f"{quality.duplicate_count} duplicate timestamps.")
    if quality.invalid_bar_count:
        warnings.append(f"{quality.invalid_bar_count} invalid OHLC bars.")
    if unexpected_gaps:
        warnings.append(
            f"{unexpected_gaps} unexpected timestamp gaps (beyond FX closures)."
        )
    status = "error" if (quality.duplicate_count or quality.invalid_bar_count) else (
        "warning" if warnings else "ok"
    )
    result = {
        "id": _dataset_id(symbol, timeframe, year),
        "symbol": symbol,
        "timeframe": timeframe,
        "year": year,
        "provider": provider,
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name,
        "bar_count": quality.bar_count,
        "size_bytes": path.stat().st_size,
        "status": status,
        "warnings": warnings,
        "coverage": {
            "start": meta.get("start_date"),
            "end": meta.get("end_date"),
            "requested_start": meta.get("requested_start_date"),
            "requested_end": meta.get("requested_end_date"),
            "actual_start": meta.get("actual_start_date"),
            "actual_end": meta.get("actual_end_date"),
            "retrieved_at": meta.get("retrieved_at"),
        },
        "quality": {
            "duplicate_count": quality.duplicate_count,
            "invalid_bar_count": quality.invalid_bar_count,
            "timestamp_gap_count": quality.timestamp_gap_count,
            "unexpected_gap_count": unexpected_gaps,
            "notes": list(quality.notes),
        },
        "first_timestamp": (
            quality.first_timestamp.isoformat() if quality.first_timestamp else None
        ),
        "last_timestamp": (
            quality.last_timestamp.isoformat() if quality.last_timestamp else None
        ),
        "derived": False,
        "available_timeframes": (
            list(UI_TIMEFRAMES) if timeframe.upper() == "M1" else [timeframe.upper()]
        ),
    }
    if cache_key is not None:
        with _summary_cache_lock:
            _summary_cache[cache_key] = copy.deepcopy(result)
    return result


def list_datasets() -> list[dict[str, Any]]:
    root = data_root()
    if not root.is_dir():
        return []
    summaries: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/*/*.csv")):
        try:
            year = int(path.stem)
        except ValueError:
            continue
        symbol = path.parent.parent.name.upper()
        timeframe = path.parent.name.upper()
        summaries.append(_dataset_summary(symbol, timeframe, year))
    return summaries


def frame_detail(dataset_id: str, timeframe: str = "M1") -> dict[str, Any]:
    symbol, stored_timeframe, year = _parse_dataset_id(dataset_id)
    return _frame_summary(symbol, stored_timeframe, year, timeframe)


def dataset_detail(dataset_id: str, timeframe: str = "M1") -> dict[str, Any]:
    symbol, stored_timeframe, year = _parse_dataset_id(dataset_id)
    summary = _frame_summary(symbol, stored_timeframe, year, timeframe)
    summary["metadata"] = _read_meta(symbol, stored_timeframe, year)
    return summary


def dataset_bars(
    dataset_id: str,
    *,
    timeframe: str = "M1",
    start: date | None = None,
    end: date | None = None,
    limit: int = 600,
) -> list[dict[str, Any]]:
    symbol, stored_timeframe, year = _parse_dataset_id(dataset_id)
    tf = _normalize_timeframe(timeframe)
    if start and end and start > end:
        raise ValueError("start_date cannot be after end_date")
    bars = _load_frame_bars(symbol, stored_timeframe, year, tf)
    bars = _range_bars(bars, start, end)
    if limit > 0:
        bars = bars[-limit:]
    return [
        {
            "time": int(bar.timestamp.replace(tzinfo=timezone.utc).timestamp()),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        for bar in bars
    ]


# ---------------------------------------------------------------------------
# Backtests and run artifacts
# ---------------------------------------------------------------------------


def _coerce_parameters(strategy_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    spec = STRATEGY_SPECS.get(strategy_id)
    if spec is None:
        raise ValueError(f"Strategy '{strategy_id}' is not exposed in the UI")
    definitions = {item["name"]: item for item in spec["parameters"]}
    unknown = sorted(set(raw) - set(definitions))
    if unknown:
        raise ValueError(f"Unknown parameters: {', '.join(unknown)}")
    params: dict[str, Any] = {}
    for name, item in definitions.items():
        value = raw.get(name, item["default"])
        if item["type"] == "integer":
            if isinstance(value, bool):
                raise ValueError(f"{name} must be an integer")
            try:
                parsed = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be an integer") from exc
        elif item["type"] == "number":
            if isinstance(value, bool):
                raise ValueError(f"{name} must be a number")
            try:
                parsed = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be a number") from exc
        elif item["type"] == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a boolean")
            parsed = value
        else:
            parsed = value
        minimum = item.get("min")
        maximum = item.get("max")
        if minimum is not None and parsed < minimum:
            raise ValueError(f"{name} must be >= {minimum}")
        if maximum is not None and parsed > maximum:
            raise ValueError(f"{name} must be <= {maximum}")
        params[name] = parsed
    return params


def _zone_books(
    *,
    start: Any | None = None,
    end: Any | None = None,
    zone_ids: list[str] | None = None,
) -> dict[str, Any]:
    return build_zone_books(start=start, end=end, zone_ids=zone_ids)


def _equity_curve(result: BacktestResult) -> dict[str, list[dict[str, Any]]]:
    trades = sorted(result.closed_trades, key=lambda item: item.exit_time)
    equity_by_time: dict[int, float] = {}
    drawdown_by_time: dict[int, float] = {}
    cumulative = 0.0
    peak = 0.0
    for trade in trades:
        cumulative += trade.pnl_r
        peak = max(peak, cumulative)
        stamp = int(trade.exit_time.replace(tzinfo=timezone.utc).timestamp())
        # Several trades can exit on the same bar; chart times must be unique.
        equity_by_time[stamp] = round(cumulative, 4)
        drawdown_by_time[stamp] = round(peak - cumulative, 4)
    stamps = sorted(equity_by_time)
    return {
        "equity": [{"time": stamp, "value": equity_by_time[stamp]} for stamp in stamps],
        "drawdown": [
            {"time": stamp, "value": drawdown_by_time[stamp]} for stamp in stamps
        ],
    }


def _trade_rows(result: BacktestResult, limit: int = 2000) -> tuple[list[dict[str, Any]], bool]:
    trades = sorted(result.closed_trades, key=lambda item: item.exit_time)
    truncated = len(trades) > limit
    rows: list[dict[str, Any]] = []
    for trade in trades[-limit:]:
        rows.append(
            {
                "symbol": trade.symbol,
                "direction": trade.direction.value,
                "entry_time": trade.entry_time.isoformat(),
                "exit_time": trade.exit_time.isoformat(),
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "sl_price": trade.sl_price,
                "tp_price": trade.tp_price,
                "pnl_r": round(trade.pnl_r, 4),
                "close_reason": trade.close_reason,
                "holding_duration_candles": trade.holding_duration_candles,
                "strategy_id": trade.strategy_id,
                "planned_entry_price": trade.planned_entry_price,
                "planned_position_size": trade.planned_position_size,
                "planned_risk_amount": trade.planned_risk_amount,
                "position_size": trade.position_size,
                "realized_risk_amount": trade.realized_risk_amount,
                "entry_slippage": trade.entry_slippage,
                "execution_assumption": trade.execution_assumption,
                "spread_cost_r": trade.spread_cost_r,
                "slippage_cost_r": trade.slippage_cost_r,
                "commission_cost_r": trade.commission_cost_r,
                "swap_cost_r": trade.swap_cost_r,
                "total_cost_r": trade.total_cost_r,
                "net_pnl_r": trade.net_pnl_r,
                "cost_profile_id": trade.cost_profile_id,
            }
        )
    return rows, truncated


def _run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{uuid.uuid4().hex[:8]}"


def _dataset_quality_payload(dataset_id: str) -> dict[str, Any] | None:
    try:
        report = build_dataset_quality_report(dataset_id)
    except DatasetQualityError:
        return None
    return {
        "status": report["quality"]["status"],
        "counts": report["counts"],
        "quality": report["quality"],
        "gaps": report["gaps"],
        "derived": report["derived"],
        "provenance": report["provenance"],
    }


def run_backtest(
    *,
    dataset_id: str,
    strategy_id: str,
    parameters: dict[str, Any] | None = None,
    start: date | None = None,
    end: date | None = None,
    timeframe: str = "M1",
    r_multiple: float = 2.0,
    equity: float = 100_000.0,
    risk_fraction: float = 0.01,
    cost_profile_id: str = "zero_costs",
    zone_ids: list[str] | None = None,
    zone_books_override: dict[str, Any] | None = None,
    cost_profile_override: CostProfile | None = None,
) -> dict[str, Any]:
    if r_multiple <= 0:
        raise ValueError("r_multiple must be positive")
    cost_profile = cost_profile_override or get_cost_profile(cost_profile_id)
    cost_model = TransactionCostModel(cost_profile)
    if equity <= 0:
        raise ValueError("equity must be positive")
    if not 0 < risk_fraction <= 0.1:
        raise ValueError("risk_fraction must be between 0 and 0.1")

    symbol, stored_timeframe, year = _parse_dataset_id(dataset_id)
    tf = _normalize_timeframe(timeframe)
    frame = _frame_summary(symbol, stored_timeframe, year, tf)
    all_bars = _load_frame_bars(symbol, stored_timeframe, year, tf)
    if not all_bars:
        raise ValueError(f"No {tf} bars are available in {dataset_id}.")
    first = all_bars[0].timestamp
    last = all_bars[-1].timestamp
    if start and end and start > end:
        raise ValueError("Start date is after the end date.")
    if start and start < first.date():
        raise ValueError(
            f"Start date {start.isoformat()} is before the first available "
            f"{tf} bar ({first.date().isoformat()})."
        )
    if end and end > last.date():
        raise ValueError(
            f"End date {end.isoformat()} is after the last available "
            f"{tf} bar ({last.date().isoformat()})."
        )
    bars = _range_bars(all_bars, start, end)
    if len(bars) < 2:
        raise ValueError(
            f"The selected range contains {len(bars)} {tf} bar(s); at least 2 are required."
        )

    params = _coerce_parameters(strategy_id, parameters or {})
    minimum_bars = 2
    if strategy_id == "S008":
        minimum_bars = int(params.get("lookback", 10)) + 2
    if len(bars) < minimum_bars:
        raise ValueError(
            f"The selected range contains {len(bars)} bars, but {strategy_id} "
            f"needs at least {minimum_bars} with the current parameters."
        )
    zone_book = None
    if STRATEGY_SPECS[strategy_id]["requires_zones"]:
        zone_start = (
            datetime.combine(start, time.min)
            if start is not None
            else (all_bars[0].timestamp if all_bars else None)
        )
        zone_end = (
            datetime.combine(end, time.max)
            if end is not None
            else (all_bars[-1].timestamp if all_bars else None)
        )
        zone_book = (
            zone_books_override.get(symbol)
            if zone_books_override is not None
            else _zone_books(
                start=zone_start,
                end=zone_end,
                zone_ids=zone_ids,
            ).get(symbol)
        )
    if STRATEGY_SPECS[strategy_id]["requires_zones"] and zone_book is None:
        raise ValueError(f"No zone book is configured for {symbol} in config/zones.json")

    if strategy_id == "S002":
        assert zone_book is not None
        strategy: object = S002_BreakoutRetest(zone_book, **params)
        setup_factory: object | None = ZoneBreakoutRetestTradeSetupFactory()
    elif strategy_id == "S008":
        strategy = LiquiditySweepStrategy(**params)
        setup_factory = SweepTradeSetupFactory()
    elif strategy_id == "CORE_ZONE_BREAKOUT":
        assert zone_book is not None
        strategy = BreakoutStrategy(zone_book)
        setup_factory = None
    else:
        raise ValueError(f"Unsupported strategy: {strategy_id}")

    simulate = STRATEGY_SPECS[strategy_id]["trade_simulation"]
    planner = TradePlanner(
        policy=FixedRiskRewardPolicy(r_multiple=r_multiple),
        sizer=FixedRiskSizer(),
        account=AccountContext(equity=equity, risk_fraction=risk_fraction),
    )
    result = BacktestRunner().run(
        strategy,
        bars,
        simulate_trades=simulate,
        trade_planner=planner if simulate else None,
        setup_factory=setup_factory if simulate else None,
        cost_model=cost_model if simulate else None,
    )

    warnings: list[str] = []
    if not simulate:
        warnings.append(
            "Signal study only: this strategy has no trade-simulation factory."
        )
    if simulate:
        if cost_profile.kind == "legacy":
            warnings.append(
                "Transaction costs (spread, commission, slippage) are not applied; this is the cost-free legacy baseline."
            )
        else:
            warnings.append(
                f"Estimated/proxy cost profile '{cost_profile.name}': costs are assumptions, not observed historical bid/ask."
            )
        warnings.append(
            "Performance is in R-multiples; no currency equity or compounding."
        )
    if STRATEGY_SPECS[strategy_id]["requires_zones"]:
        warnings.append(
            "Zone levels are static manual annotations without confirmation timestamps."
        )
    if result.ambiguous_exits:
        warnings.append(
            f"{result.ambiguous_exits} ambiguous intrabar exits were resolved from the simulated fill: stop-first when both levels were inside the bar, or the gapped open when it traded beyond the stop."
        )
    if simulate and result.total_trades and result.total_trades < 100:
        warnings.append(
            f"Small sample: {result.total_trades} closed trades. Not statistically reliable."
        )
    if frame.get("derived"):
        warnings.append(
            f"{tf} is derived from stored M1 with the existing resampler; "
            "incomplete buckets are skipped and no derived data is persisted."
        )
    selected_gaps = 0
    step = timeframe_minutes(tf) * 60
    for left, right in zip(bars, bars[1:]):
        if (right.timestamp - left.timestamp).total_seconds() > step:
            selected_gaps += 1
    if selected_gaps:
        warnings.append(
            f"Selected range contains {selected_gaps} timestamp gap(s) larger than one {tf} bar "
            "(market closures included)."
        )

    trades, trades_truncated = _trade_rows(result)
    curve = _equity_curve(result)
    signal_counts = Counter(outcome.signal_type for outcome in result.signal_outcomes)
    trade_days = Counter(trade.entry_time.date().isoformat() for trade in result.closed_trades)
    trade_distribution = [
        {"date": day, "trades": count} for day, count in sorted(trade_days.items())
    ]

    run = {
        "schema_version": "ui_run_v1",
        "id": _run_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_id": frame["id"],
        "dataset": frame,
        "strategy": {
            "id": strategy_id,
            "name": getattr(strategy, "strategy_name", strategy_id),
            "description": getattr(strategy, "description", ""),
        },
        "parameters": params,
        "request": {
            "start": start.isoformat() if start else first.date().isoformat(),
            "end": end.isoformat() if end else last.date().isoformat(),
            "timeframe": tf,
            "r_multiple": r_multiple,
            "equity": equity,
            "risk_fraction": risk_fraction,
        },
        "range": {
            "start": start.isoformat() if start else first.date().isoformat(),
            "end": end.isoformat() if end else last.date().isoformat(),
            "bar_count": len(bars),
            "gap_count": selected_gaps,
        },
        "bar_count": len(bars),
        "simulated": simulate,
        "metrics": {
            "total_signals": result.total_signals,
            "total_trades": result.total_trades,
            "wins": result.wins,
            "losses": result.losses,
            "win_rate": result.win_rate,
            "profit_factor": result.profit_factor,
            "expectancy": result.expectancy,
            "max_drawdown_r": result.max_drawdown,
            "largest_win": result.largest_win,
            "largest_loss": result.largest_loss,
            "ambiguous_exits": result.ambiguous_exits,
            "avg_holding_duration": result.avg_holding_duration,
        },
        "reconciliation": result.reconcile_signals(),
        "signals": {
            "total": result.total_signals,
            "by_type": dict(sorted(signal_counts.items())),
        },
        "equity_curve": curve,
        "trade_distribution": trade_distribution,
        "trades": trades,
        "trades_truncated": trades_truncated,
        "warnings": warnings,
        "warning_count": len(warnings),
        "net_metrics": (
            asdict(result.net_metrics) if result.net_metrics is not None else None
        ),
        "cost_profile": result.cost_profile or cost_profile.to_dict(),
        "zone_ids": list(zone_ids or []),
        "dataset_quality": _dataset_quality_payload(frame["id"]),
        "assumptions": {
            "costs_applied": bool(simulate and cost_profile.kind != "legacy"),
            "cost_profile_id": cost_profile.id,
            "cost_profile_estimated": cost_profile.estimated,
            "entry_model": "next candle open",
            "timestamps": "naive UTC",
            "zone_source": "manual/static" if STRATEGY_SPECS[strategy_id]["requires_zones"] else "none",
            "result_units": "R-multiples",
            "timeframe": tf,
            "derived_timeframe": bool(frame.get("derived")),
        },
    }
    _save_run(run)
    return run


def _save_run(run: dict[str, Any]) -> None:
    directory = runs_root()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{run['id']}.json").write_text(
        json.dumps(run, indent=2), encoding="utf-8"
    )


def list_runs(limit: int = 25) -> list[dict[str, Any]]:
    directory = runs_root()
    if not directory.is_dir():
        return []
    runs: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        runs.append(
            {
                "id": payload.get("id", path.stem),
                "created_at": payload.get("created_at"),
                "dataset_id": payload.get("dataset", {}).get("id"),
                "timeframe": payload.get("request", {}).get("timeframe", "M1"),
                "range": payload.get("range", {}),
                "strategy": payload.get("strategy", {}),
                "metrics": payload.get("metrics", {}),
                "bar_count": payload.get("bar_count"),
                "simulated": payload.get("simulated"),
                "warning_count": len(payload.get("warnings", [])),
            }
        )
    runs.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return runs[:limit]


def get_run(run_id: str) -> dict[str, Any]:
    if not _RUN_ID_RE.fullmatch(run_id):
        raise DatasetNotFoundError("Invalid run id")
    path = runs_root() / f"{run_id}.json"
    if not path.is_file():
        raise DatasetNotFoundError("Run not found")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Bounded synchronous downloads
# ---------------------------------------------------------------------------


def _download_config_path(provider: str) -> Path:
    if provider == "twelve_data":
        return ROOT / "config" / "historical_data_twelve_data.json"
    return ROOT / "config" / "historical_data.json"


def download_dataset(
    *,
    provider: str,
    symbol: str,
    timeframe: str,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    if provider not in {"twelve_data", "dukascopy"}:
        raise ValueError("provider must be twelve_data or dukascopy")
    symbol = symbol.strip().upper()
    timeframe = timeframe.strip().upper()
    if symbol not in DOWNLOAD_SYMBOLS:
        raise ValueError("UI downloads currently support EURUSD and GBPUSD")
    if timeframe not in DOWNLOAD_TIMEFRAMES:
        raise ValueError("UI downloads currently support M1 only")
    if start > end:
        raise ValueError("start_date cannot be after end_date")
    if (end - start).days > MAX_DOWNLOAD_DAYS:
        raise ValueError(f"UI downloads are limited to {MAX_DOWNLOAD_DAYS} days")
    if end > date.today():
        raise ValueError("end_date cannot be in the future")

    # Never merge a new provider into a legacy partition whose provenance is
    # unknown, and never silently cross providers in the same yearly file.
    storage = HistoricalStorage(data_root())
    for year in range(start.year, end.year + 1):
        path = storage.year_path(symbol, timeframe, year)
        if not path.is_file():
            continue
        metadata = storage.read_metadata(symbol, timeframe, year)
        if metadata is None:
            raise ValueError(
                f"Existing partition {path.name} has no provenance metadata. "
                "Use a separate REX_DATA_DIR for this provider, or overwrite it "
                "deliberately with the CLI."
            )
        existing_provider = metadata.get("provider")
        if existing_provider and existing_provider != provider:
            raise ValueError(
                f"Existing partition {path.name} was written by {existing_provider}, "
                f"not {provider}. Use a separate REX_DATA_DIR or overwrite it deliberately."
            )

    # Resolve the provider credential once and pass it to the adapter.  The
    # environment is never mutated, and Dukascopy ignores any optional key.
    api_key = get_provider_key(provider)
    if provider == "twelve_data" and not api_key:
        raise HistoricalConfigurationError(
            "Twelve Data API key is not configured; add it in "
            "System → Key handling."
        )

    if not _download_lock.acquire(blocking=False):
        raise DownloadBusyError("A download is already running")
    try:
        base = load_historical_config(_download_config_path(provider))
        config = replace(
            base,
            provider=provider,
            symbols=(symbol,),
            timeframe="M1",
            start_date=start,
            end_date=end,
            data_directory=data_root(),
            overwrite_existing_files=False,
            retries=2,
            retry_delay_seconds=2,
        )
        source = build_source(config, api_key=api_key)
        paths = HistoricalDownloader(config, adapter=source).download()
    finally:
        _download_lock.release()

    summaries: list[dict[str, Any]] = []
    for path in paths:
        try:
            year = int(path.stem)
        except ValueError:
            continue
        summaries.append(_dataset_summary(symbol, timeframe, year))
    return summaries


def overview() -> dict[str, Any]:
    datasets = list_datasets()
    strategies = list_strategies()
    runs = list_runs(limit=5)
    warnings: list[str] = []
    if not has_twelve_data_key():
        warnings.append(
            "Twelve Data API key is not configured; add it in "
            "System → Key handling."
        )
    for dataset in datasets:
        for warning in dataset.get("warnings", []):
            warnings.append(f"{dataset['id']}: {warning}")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_root": str(data_root()),
        "instruments": list_instruments(),
        "datasets": datasets,
        "strategies": strategies,
        "runs": runs,
        "warnings": warnings[:20],
        "capabilities": {
            "twelve_data": has_twelve_data_key(),
            "dukascopy": True,
            "trade_simulation": [
                item["id"] for item in strategies if item["trade_simulation"]
            ],
            "download_max_days": MAX_DOWNLOAD_DAYS,
        },
    }
