"""Structured pre-backtest validation.

This is a preflight layer over the existing research service. It returns
explicit error/warning records for the UI and does not execute a backtest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from backtests.costs import CostProfileError, get_cost_profile
from core.market import research_symbols
from historical.quality import DatasetQualityError, build_dataset_quality_report
from server import research_service as service


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str  # error | warning | info
    component: str
    message: str
    suggestion: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "component": self.component,
            "message": self.message,
            "suggestion": self.suggestion,
        }


def _issues(issues: list[Issue], **kwargs: str) -> None:
    issues.append(Issue(**kwargs))


def validate_backtest(
    *,
    dataset_id: str,
    strategy_id: str,
    timeframe: str,
    parameters: dict[str, Any] | None = None,
    start: date | None = None,
    end: date | None = None,
    r_multiple: float = 2.0,
    equity: float = 100_000.0,
    risk_fraction: float = 0.01,
    cost_profile_id: str = "zero_costs",
    zone_ids: list[str] | None = None,
) -> dict[str, Any]:
    errors: list[Issue] = []
    warnings: list[Issue] = []
    info: list[Issue] = []
    details: dict[str, Any] = {}

    strategies = {item["id"]: item for item in service.list_strategies()}
    strategy = strategies.get(strategy_id)
    if strategy is None:
        _issues(
            errors,
            code="STRATEGY_NOT_AVAILABLE",
            severity="error",
            component="strategy",
            message=f"Strategy {strategy_id!r} is not exposed by the research registry.",
            suggestion="Choose one of: " + ", ".join(sorted(strategies)),
        )
    elif not strategy.get("trade_simulation"):
        _issues(
            info,
            code="SIGNAL_STUDY_ONLY",
            severity="info",
            component="execution",
            message=(
                "This strategy is a signal study; no simulated trades will be produced."
            ),
            suggestion="Use a trade-simulated strategy for execution analysis.",
        )
    if timeframe.upper() not in service.UI_TIMEFRAMES:
        _issues(
            errors,
            code="TIMEFRAME_UNSUPPORTED",
            severity="error",
            component="timeframe",
            message=f"Unsupported timeframe: {timeframe}",
            suggestion="Use one of: " + ", ".join(service.UI_TIMEFRAMES),
        )

    try:
        profile = get_cost_profile(cost_profile_id)
        details["cost_profile"] = profile.to_dict()
        if profile.estimated:
            _issues(
                warnings,
                code="ESTIMATED_COSTS",
                severity="warning",
                component="costs",
                message=f"Cost profile {profile.name!r} is an estimated/proxy assumption.",
                suggestion="Do not treat net results as observed historical execution costs.",
            )
        elif profile.kind == "legacy":
            _issues(
                info,
                code="COST_FREE_LEGACY",
                severity="info",
                component="costs",
                message="The selected profile is the explicit cost-free legacy baseline.",
                suggestion="Select a proxy profile to inspect cost sensitivity.",
            )
    except CostProfileError as exc:
        _issues(
            errors,
            code="COST_PROFILE_INVALID",
            severity="error",
            component="costs",
            message=str(exc),
            suggestion="Choose a registered cost profile.",
        )
        profile = None

    if r_multiple <= 0:
        _issues(errors, code="R_MULTIPLE_INVALID", severity="error", component="risk", message="R multiple must be positive.", suggestion="Use a positive target multiple.")
    if equity <= 0:
        _issues(errors, code="EQUITY_INVALID", severity="error", component="risk", message="Equity must be positive.", suggestion="Set a positive account equity.")
    if not 0 < risk_fraction <= 0.1:
        _issues(errors, code="RISK_FRACTION_INVALID", severity="error", component="risk", message="Risk fraction must be between 0 and 0.1.", suggestion="Use the fixed-risk research range.")

    if strategy is not None:
        try:
            service._coerce_parameters(strategy_id, parameters or {})
        except ValueError as exc:
            _issues(
                errors,
                code="PARAMETERS_INVALID",
                severity="error",
                component="parameters",
                message=str(exc),
                suggestion="Correct the strategy parameters before execution.",
            )

    dataset = None
    quality = None
    try:
        dataset = service.dataset_detail(dataset_id, timeframe=timeframe)
        details["dataset"] = {
            "id": dataset.get("id"),
            "symbol": dataset.get("symbol"),
            "timeframe": dataset.get("timeframe"),
            "bar_count": dataset.get("bar_count"),
        }
        symbol = str(dataset.get("symbol") or "")
        if symbol and symbol not in research_symbols():
            _issues(
                errors,
                code="INSTRUMENT_UNSUPPORTED",
                severity="error",
                component="instrument",
                message=f"{symbol} is not a research-enabled instrument.",
                suggestion="Use a research-enabled instrument.",
            )
        required_features = list(strategy.get("required_features", [])) if strategy else []
        if required_features:
            _issues(
                info,
                code="FEATURE_REQUIREMENTS_DECLARED",
                severity="info",
                component="features",
                message="Required features: " + ", ".join(map(str, required_features)),
                suggestion="Feature availability is resolved by the existing feature layer.",
            )
        else:
            _issues(
                info,
                code="FEATURE_REQUIREMENTS_NONE",
                severity="info",
                component="features",
                message="This strategy declares no required feature packs; OHLC/zone inputs are sufficient.",
                suggestion="Add feature requirements to the strategy spec when a strategy depends on them.",
            )
        if strategy is not None and strategy.get("requires_zones"):
            zones = (
                service._zone_books(zone_ids=zone_ids)
                if zone_ids
                else service._zone_books()
            )
            if symbol not in zones:
                _issues(
                    errors,
                    code="ZONE_BOOK_MISSING",
                    severity="error",
                    component="zones",
                    message=f"No zone book is configured for {symbol}.",
                    suggestion=f"Add a verified {symbol} zone book or choose a zone-free strategy.",
                )
    except Exception as exc:
        _issues(
            errors,
            code="DATASET_NOT_FOUND",
            severity="error",
            component="dataset",
            message=str(exc),
            suggestion="Choose an available stored dataset.",
        )

    if dataset is not None:
        try:
            quality = build_dataset_quality_report(dataset_id)
            details["dataset_quality"] = {
                "status": quality["quality"]["status"],
                "counts": quality["counts"],
                "quality": quality["quality"],
            }
            if quality["quality"]["status"] == "error":
                _issues(
                    errors,
                    code="DATASET_QUALITY_ERROR",
                    severity="error",
                    component="dataset_quality",
                    message="; ".join(quality["quality"]["errors"]),
                    suggestion="Repair or replace the dataset before executing research.",
                )
            for warning in quality["quality"]["warnings"]:
                _issues(
                    warnings,
                    code="DATASET_QUALITY_WARNING",
                    severity="warning",
                    component="dataset_quality",
                    message=warning,
                    suggestion="Review the dataset quality report before interpreting results.",
                )
        except DatasetQualityError as exc:
            _issues(
                warnings,
                code="DATASET_QUALITY_UNAVAILABLE",
                severity="warning",
                component="dataset_quality",
                message=str(exc),
                suggestion="Inspect the dataset metadata and quality report.",
            )
        try:
            range_info = service.range_summary(dataset_id, timeframe=timeframe, start=start, end=end)
            details["range"] = range_info
            if not range_info.get("valid"):
                _issues(
                    errors,
                    code="RANGE_INVALID",
                    severity="error",
                    component="range",
                    message=str(range_info.get("error") or "The selected range is invalid."),
                    suggestion="Choose a range covered by the dataset with at least two bars.",
                )
        except Exception as exc:
            _issues(
                errors,
                code="RANGE_INVALID",
                severity="error",
                component="range",
                message=str(exc),
                suggestion="Choose a valid dataset range.",
            )

    if profile is not None:
        details["cost_assumptions"] = {
            "profile_id": profile.id,
            "estimated": profile.estimated,
            "kind": profile.kind,
            "source_note": profile.source_note,
        }

    return {
        "valid": not errors,
        "errors": [item.to_dict() for item in errors],
        "warnings": [item.to_dict() for item in warnings],
        "info": [item.to_dict() for item in info],
        "details": details,
    }
