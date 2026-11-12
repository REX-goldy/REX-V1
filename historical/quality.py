"""Reusable, read-only historical dataset quality reporting.

Quality reports never modify source CSVs. They distinguish FX closures from
unexpected gaps and expose incomplete derived buckets using the existing
resampler rather than a second aggregation path.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from historical.bar_contract import assess_dataset_quality, normalize_provider_timestamp
from historical.calendar import is_fx_market_open_minute_utc
from historical.exceptions import HistoricalParseError
from historical.parser import HistoricalDataParser
from research.free_ohlc.resampler import ResampleError, resample_bars

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data" / "historical"
DERIVED = ("M5", "M15", "H1", "H4")


class DatasetQualityError(ValueError):
    """Dataset quality report cannot be produced."""


def _dataset_parts(dataset_id: str) -> tuple[str, str, int]:
    parts = dataset_id.split("/")
    if len(parts) != 3:
        raise DatasetQualityError("Dataset id must be SYMBOL/TIMEFRAME/YEAR")
    symbol, timeframe, year_text = parts
    symbol = symbol.strip().upper()
    timeframe = timeframe.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{3,12}", symbol):
        raise DatasetQualityError("Invalid dataset symbol")
    if not re.fullmatch(r"[A-Z0-9]{1,8}", timeframe):
        raise DatasetQualityError("Invalid dataset timeframe")
    try:
        year = int(year_text)
    except ValueError as exc:
        raise DatasetQualityError("Invalid dataset year") from exc
    return symbol, timeframe, year


def _raw_integrity(path: Path) -> dict[str, int]:
    """Scan raw CSV timestamps for duplicate/order issues even if the parser rejects."""
    seen: set[datetime] = set()
    duplicates = 0
    order_violations = 0
    malformed = 0
    previous: datetime | None = None
    try:
        with path.open("r", encoding="utf-8", newline="") as source:
            first_line = source.readline()
            source.seek(0)
            has_header = any(name in first_line.lower() for name in ("time", "open", "close"))
            reader = (
                csv.DictReader(source)
                if has_header
                else csv.DictReader(
                    source,
                    delimiter=";",
                    fieldnames=("time", "open", "high", "low", "close", "volume"),
                )
            )
            for row in reader:
                raw = row.get("timestamp") or row.get("time")
                try:
                    stamp = normalize_provider_timestamp(str(raw or ""))
                except HistoricalParseError:
                    malformed += 1
                    continue
                if stamp in seen:
                    duplicates += 1
                seen.add(stamp)
                if previous is not None and stamp <= previous:
                    order_violations += 1
                previous = stamp
    except OSError as exc:
        raise DatasetQualityError(f"Unable to read dataset: {path}") from exc
    return {
        "duplicate_timestamp_count": duplicates,
        "order_violation_count": order_violations,
        "malformed_timestamp_count": malformed,
    }


def build_dataset_quality_report(
    dataset_id: str,
    *,
    data_root: Path | None = None,
) -> dict[str, Any]:
    symbol, timeframe, year = _dataset_parts(dataset_id)
    root = data_root or Path(DEFAULT_DATA_DIR)
    path = root / symbol / timeframe / f"{year}.csv"
    meta_path = path.with_suffix(".meta.json")
    if not path.is_file():
        raise DatasetQualityError(f"Dataset not found: {dataset_id}")
    meta: dict[str, Any] = {}
    if meta_path.is_file():
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                meta = payload
        except (OSError, ValueError):
            meta = {}

    raw = _raw_integrity(path)
    parse_error: str | None = None
    bars: list = []
    try:
        bars = HistoricalDataParser().parse_file(path, symbol)
    except HistoricalParseError as exc:
        parse_error = str(exc)

    quality = assess_dataset_quality(
        bars,
        instrument=symbol,
        timeframe=timeframe,
        provider=str(meta.get("provider") or "unknown"),
        coverage_start=meta.get("start_date"),
        coverage_end=meta.get("end_date"),
        expected_step_minutes=1 if timeframe == "M1" else None,
    )

    gaps: list[dict[str, Any]] = []
    missing_open = 0
    missing_closed = 0
    bars_in_closure = 0
    if bars:
        for left, right in zip(bars, bars[1:]):
            if right.timestamp <= left.timestamp:
                continue
            if (right.timestamp - left.timestamp) > timedelta(minutes=1):
                open_missing = 0
                closed_missing = 0
                cursor = left.timestamp + timedelta(minutes=1)
                while cursor < right.timestamp:
                    if is_fx_market_open_minute_utc(cursor):
                        open_missing += 1
                    else:
                        closed_missing += 1
                    cursor += timedelta(minutes=1)
                missing_open += open_missing
                missing_closed += closed_missing
                gaps.append(
                    {
                        "before": left.timestamp.isoformat(),
                        "after": right.timestamp.isoformat(),
                        "duration_minutes": int(
                            (right.timestamp - left.timestamp).total_seconds() // 60
                        ),
                        "missing_open_minutes": open_missing,
                        "missing_closed_minutes": closed_missing,
                        "unexpected": open_missing > 0,
                    }
                )
        bars_in_closure = sum(
            1 for bar in bars if not is_fx_market_open_minute_utc(bar.timestamp)
        )

    derived: dict[str, Any] = {}
    if bars and timeframe == "M1":
        for target in DERIVED:
            try:
                result = resample_bars(bars, target_timeframe=target)
                derived[target] = {
                    "status": "ok",
                    "emitted_bar_count": result.stats.emitted_bar_count,
                    "skipped_incomplete_buckets": result.stats.skipped_incomplete_buckets,
                    "skipped_closed_buckets": result.stats.skipped_closed_buckets,
                    "completeness_rule": result.stats.completeness_rule,
                    "first_timestamp": (
                        result.stats.first_timestamp.isoformat()
                        if result.stats.first_timestamp
                        else None
                    ),
                    "last_timestamp": (
                        result.stats.last_timestamp.isoformat()
                        if result.stats.last_timestamp
                        else None
                    ),
                }
            except (ResampleError, ValueError) as exc:
                derived[target] = {"status": "error", "error": str(exc)}

    unexpected = sum(1 for gap in gaps if gap["unexpected"])
    warnings: list[str] = []
    errors: list[str] = []
    if parse_error:
        errors.append(f"Parser rejected dataset: {parse_error}")
    if raw["duplicate_timestamp_count"]:
        errors.append(f"{raw['duplicate_timestamp_count']} duplicate timestamp(s).")
    if raw["order_violation_count"]:
        errors.append(f"{raw['order_violation_count']} ordering violation(s).")
    if quality.invalid_bar_count:
        errors.append(f"{quality.invalid_bar_count} invalid OHLC bar(s).")
    if unexpected:
        warnings.append(
            f"{unexpected} unexpected gap(s) remove {missing_open} FX-open minute(s)."
        )
    if bars_in_closure:
        warnings.append(
            f"{bars_in_closure} bar(s) are inside the FX weekly closure."
        )
    for target, item in derived.items():
        if item.get("status") == "error":
            warnings.append(f"{target} derivation failed: {item.get('error')}")
        elif item.get("skipped_incomplete_buckets"):
            warnings.append(
                f"{target} skips {item['skipped_incomplete_buckets']} incomplete bucket(s)."
            )
    status = "error" if errors else ("warning" if warnings else "ok")

    return {
        "dataset_id": dataset_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "year": year,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "provider": str(meta.get("provider") or "unknown"),
        "metadata": meta,
        "coverage": {
            "requested_start": meta.get("requested_start_date") or meta.get("start_date"),
            "requested_end": meta.get("requested_end_date") or meta.get("end_date"),
            "actual_start": quality.first_timestamp.isoformat()
            if quality.first_timestamp
            else None,
            "actual_end": quality.last_timestamp.isoformat()
            if quality.last_timestamp
            else None,
        },
        "counts": {
            "bar_count": len(bars),
            "duplicate_timestamp_count": raw["duplicate_timestamp_count"],
            "order_violation_count": raw["order_violation_count"],
            "malformed_timestamp_count": raw["malformed_timestamp_count"],
            "invalid_bar_count": quality.invalid_bar_count,
            "raw_gap_count": quality.timestamp_gap_count,
            "unexpected_gap_count": unexpected,
            "missing_open_minutes": missing_open,
            "missing_closure_minutes": missing_closed,
            "bars_in_closure": bars_in_closure,
        },
        "gaps": gaps,
        "derived": derived,
        "quality": {
            "status": status,
            "errors": errors,
            "warnings": warnings,
            "notes": list(quality.notes),
        },
        "provenance": {
            "provider": str(meta.get("provider") or "unknown"),
            "retrieved_at": meta.get("retrieved_at"),
            "closure_filtered_count": meta.get("closure_filtered_count"),
            "requested_start": meta.get("requested_start_date"),
            "requested_end": meta.get("requested_end_date"),
        },
        "parse_error": parse_error,
    }
