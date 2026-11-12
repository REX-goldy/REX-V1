"""Minimal FX weekly calendar rules shared by ingest and resampling."""

from __future__ import annotations

from datetime import datetime


def is_fx_market_open_minute_utc(timestamp: datetime) -> bool:
    """Return True when a naive-UTC minute is inside the FX weekly session.

    The heuristic mirrors ``fx_open_minutes_v1``: closed Saturday all day,
    Friday from 22:00, and Sunday before 22:00. It does not model DST or
    exchange holidays.
    """
    if timestamp.tzinfo is not None:
        raise ValueError("expected naive UTC timestamp")
    weekday = timestamp.weekday()  # Monday=0 ... Sunday=6
    if weekday == 5:
        return False
    if weekday == 4 and timestamp.hour >= 22:
        return False
    if weekday == 6 and timestamp.hour < 22:
        return False
    return True
