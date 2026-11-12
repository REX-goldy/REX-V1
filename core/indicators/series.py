"""Timestamp-aligned historical indicator series models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class IndicatorSeries:
    """One indicator series aligned one-for-one with canonical source bars.

    ``values[i]`` corresponds to ``timestamps[i]``. Warm-up/unavailable values
    are represented by ``None`` rather than a fabricated zero. ``warmup_bars``
    is the number of leading unavailable observations (or the full length when
    no finite value exists).
    """

    indicator_id: str
    method_id: str
    timeframe: str
    timestamps: tuple[datetime, ...]
    values: tuple[float | None, ...]
    parameters: Mapping[str, object]
    implementation_version: str
    warmup_bars: int
    start_index: int = 0
    source_bar_count: int = 0

    def __post_init__(self) -> None:
        if len(self.timestamps) != len(self.values):
            raise ValueError("IndicatorSeries timestamps and values must align")
        object.__setattr__(
            self, "parameters", MappingProxyType(dict(self.parameters))
        )

    def value_at(self, index: int) -> float | None:
        return self.values[index]


def series_metadata(
    *,
    indicator_id: str,
    method_id: str,
    timeframe: str,
    timestamps: tuple[datetime, ...],
    parameters: Mapping[str, object],
    implementation_version: str,
    values: tuple[float | None, ...],
    start_index: int = 0,
    source_bar_count: int | None = None,
) -> IndicatorSeries:
    """Build a series with explicit warm-up count from leading None values."""
    warmup = 0
    for value in values:
        if value is not None:
            break
        warmup += 1
    return IndicatorSeries(
        indicator_id=indicator_id,
        method_id=method_id,
        timeframe=timeframe,
        timestamps=timestamps,
        values=values,
        parameters=parameters,
        implementation_version=implementation_version,
        warmup_bars=warmup,
        start_index=start_index,
        source_bar_count=source_bar_count if source_bar_count is not None else len(values),
    )
