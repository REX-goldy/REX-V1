"""Deterministic transaction-cost profiles and per-trade cost accounting.

The REX research engine is R-multiple based. Cost profiles therefore expose:

- spread in price units (full bid/ask spread, applied once per round trip);
- slippage in price units per side (applied to entry and exit);
- commission in account-currency units per round trip;
- optional financing/swap in R per overnight holding period.

No historical bid/ask is fabricated. Every profile is either the explicit
zero-cost legacy profile or labelled as an estimated/proxy assumption.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "config" / "cost_profiles.json"
PROFILE_VERSION = 1


class CostProfileError(ValueError):
    """Invalid cost-profile configuration."""


class CostModelError(ValueError):
    """A trade cannot be costed under the selected profile."""


@dataclass(frozen=True)
class CostProfile:
    id: str
    name: str
    description: str
    kind: str
    estimated: bool
    spread_price: float
    slippage_price_per_side: float
    commission_per_round_trip: float
    swap_per_night_r: float
    instrument_overrides: dict[str, dict[str, float]]
    source_note: str = ""

    def values_for(self, symbol: str) -> dict[str, float]:
        values = {
            "spread_price": self.spread_price,
            "slippage_price_per_side": self.slippage_price_per_side,
            "commission_per_round_trip": self.commission_per_round_trip,
            "swap_per_night_r": self.swap_per_night_r,
        }
        values.update(self.instrument_overrides.get(symbol.upper(), {}))
        return values

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> "CostProfile":
        return _profile(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "kind": self.kind,
            "estimated": self.estimated,
            "spread_price": self.spread_price,
            "slippage_price_per_side": self.slippage_price_per_side,
            "commission_per_round_trip": self.commission_per_round_trip,
            "swap_per_night_r": self.swap_per_night_r,
            "instrument_overrides": self.instrument_overrides,
            "source_note": self.source_note,
        }


@dataclass(frozen=True)
class CostBreakdown:
    spread_r: float
    slippage_r: float
    commission_r: float
    swap_r: float
    total_r: float
    gross_pnl_r: float
    net_pnl_r: float
    profile_id: str
    estimated: bool
    assumptions: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "spread_r": self.spread_r,
            "slippage_r": self.slippage_r,
            "commission_r": self.commission_r,
            "swap_r": self.swap_r,
            "total_r": self.total_r,
            "gross_pnl_r": self.gross_pnl_r,
            "net_pnl_r": self.net_pnl_r,
            "profile_id": self.profile_id,
            "estimated": self.estimated,
            "assumptions": self.assumptions,
        }


def _profile(raw: dict[str, Any]) -> CostProfile:
    def number(key: str, default: float = 0.0) -> float:
        value = raw.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CostProfileError(f"{key} must be a number")
        value = float(value)
        if value < 0:
            raise CostProfileError(f"{key} cannot be negative")
        return value

    overrides = raw.get("instrument_overrides", {})
    if not isinstance(overrides, dict):
        raise CostProfileError("instrument_overrides must be an object")
    clean_overrides: dict[str, dict[str, float]] = {}
    for symbol, values in overrides.items():
        if not isinstance(symbol, str) or not symbol.strip():
            raise CostProfileError("instrument override symbols must be non-empty")
        if not isinstance(values, dict):
            raise CostProfileError("instrument overrides must be objects")
        clean: dict[str, float] = {}
        for key, value in values.items():
            if key not in {
                "spread_price",
                "slippage_price_per_side",
                "commission_per_round_trip",
                "swap_per_night_r",
            }:
                raise CostProfileError(f"unknown instrument cost field: {key}")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise CostProfileError(f"instrument cost {key} must be a number")
            if float(value) < 0:
                raise CostProfileError(f"instrument cost {key} cannot be negative")
            clean[key] = float(value)
        clean_overrides[symbol.strip().upper()] = clean

    return CostProfile(
        id=str(raw.get("id", "")).strip(),
        name=str(raw.get("name", "")).strip(),
        description=str(raw.get("description", "")).strip(),
        kind=str(raw.get("kind", "estimated_proxy")).strip(),
        estimated=bool(raw.get("estimated", True)),
        spread_price=number("spread_price"),
        slippage_price_per_side=number("slippage_price_per_side"),
        commission_per_round_trip=number("commission_per_round_trip"),
        swap_per_night_r=number("swap_per_night_r"),
        instrument_overrides=clean_overrides,
        source_note=str(raw.get("source_note", "")).strip(),
    )


def load_cost_profiles(path: Path = DEFAULT_PATH) -> tuple[CostProfile, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CostProfileError(f"Unable to load cost profiles: {path}") from exc
    if not isinstance(payload, dict) or payload.get("version") != PROFILE_VERSION:
        raise CostProfileError("Unsupported cost-profile version")
    raw_profiles = payload.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise CostProfileError("Cost profiles must be a non-empty list")
    profiles = tuple(_profile(item) for item in raw_profiles if isinstance(item, dict))
    if len(profiles) != len(raw_profiles):
        raise CostProfileError("Every cost profile must be an object")
    ids = [profile.id for profile in profiles]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise CostProfileError("Cost-profile ids must be non-empty and unique")
    return profiles


_PROFILES: tuple[CostProfile, ...] | None = None


def get_cost_profiles() -> tuple[CostProfile, ...]:
    global _PROFILES
    if _PROFILES is None:
        _PROFILES = load_cost_profiles()
    return _PROFILES


def get_cost_profile(profile_id: str) -> CostProfile:
    for profile in get_cost_profiles():
        if profile.id == profile_id:
            return profile
    raise CostProfileError(f"Unknown cost profile: {profile_id}")


def zero_profile() -> CostProfile:
    return get_cost_profile("zero_costs")


class TransactionCostModel:
    """Apply a deterministic cost profile to a closed trade's gross R."""

    def __init__(self, profile: CostProfile | None = None) -> None:
        self.profile = profile or zero_profile()

    def calculate(
        self,
        *,
        symbol: str,
        entry_price: float,
        exit_price: float,
        risk_distance: float,
        risk_amount: float,
        gross_pnl_r: float,
        holding_days: int = 0,
    ) -> CostBreakdown:
        values = self.profile.values_for(symbol)
        if risk_distance <= 0 or risk_amount < 0:
            raise CostModelError("risk distance/amount is invalid")
        spread_price = values["spread_price"]
        slippage_price = values["slippage_price_per_side"]
        commission = values["commission_per_round_trip"]
        swap_per_night = values["swap_per_night_r"]

        spread_r = spread_price / risk_distance if risk_distance else 0.0
        slippage_r = (2.0 * slippage_price) / risk_distance if risk_distance else 0.0
        commission_r = commission / risk_amount if risk_amount > 0 else 0.0
        swap_r = max(0, int(holding_days)) * swap_per_night
        total_r = spread_r + slippage_r + commission_r + swap_r
        net_pnl_r = gross_pnl_r - total_r
        return CostBreakdown(
            spread_r=spread_r,
            slippage_r=slippage_r,
            commission_r=commission_r,
            swap_r=swap_r,
            total_r=total_r,
            gross_pnl_r=gross_pnl_r,
            net_pnl_r=net_pnl_r,
            profile_id=self.profile.id,
            estimated=self.profile.estimated,
            assumptions={
                "kind": self.profile.kind,
                "estimated": self.profile.estimated,
                "spread_price": spread_price,
                "slippage_price_per_side": slippage_price,
                "commission_per_round_trip": commission,
                "swap_per_night_r": swap_per_night,
                "spread_application": "full spread once per round trip",
                "slippage_application": "per side, twice per round trip",
                "commission_units": "account currency",
                "swap_units": "R per overnight period",
                "source_note": self.profile.source_note,
            },
        )
