"""Independent trade and run validation.

This module deliberately re-implements the arithmetic from trade-level fields
instead of calling the engine's PnL/cost/metric functions. It is a second,
read-only check: it never modifies a run artifact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import fsum, isclose, isfinite
from typing import Any


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    component: str
    message: str
    correction: str
    trade_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "component": self.component,
            "message": self.message,
            "correction": self.correction,
            "trade_key": self.trade_key,
        }


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if isfinite(number) else None


def _trade_key(trade: dict[str, Any], index: int) -> str:
    return f"{trade.get('entry_time', index)}|{trade.get('signal_id', index)}"


def _add(
    findings: list[Finding],
    code: str,
    component: str,
    message: str,
    correction: str,
    *,
    severity: str = "error",
    trade_key: str | None = None,
) -> None:
    findings.append(
        Finding(
            code=code,
            severity=severity,
            component=component,
            message=message,
            correction=correction,
            trade_key=trade_key,
        )
    )


def _independent_metrics(pnl: list[float]) -> dict[str, float | int | None]:
    wins = [value for value in pnl if value > 0]
    losses = [value for value in pnl if value < 0]
    decided = len(wins) + len(losses)
    gross_profit = fsum(wins)
    gross_loss = abs(fsum(losses))
    equity = 0.0
    peak = 0.0
    drawdown = 0.0
    for value in pnl:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {
        "total_trades": len(pnl),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / decided * 100.0) if decided else 0.0,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else None,
        "expectancy": (fsum(pnl) / len(pnl)) if pnl else 0.0,
        "max_drawdown": drawdown,
        "largest_win": max(wins, default=0.0),
        "largest_loss": min(losses, default=0.0),
        "total_r": fsum(pnl),
    }


def _close(
    a: float | None,
    b: float | None,
    *,
    rel: float = 1e-8,
    abs_tol: float = 1e-8,
) -> bool:
    if a is None or b is None:
        return False
    return isclose(a, b, rel_tol=rel, abs_tol=abs_tol)


def _profile_cost(
    profile: dict[str, Any],
    symbol: str,
    risk_distance: float,
    risk_amount: float,
    holding_days: int,
) -> tuple[float, float, float, float]:
    values = {
        "spread_price": float(profile.get("spread_price", 0.0)),
        "slippage_price_per_side": float(
            profile.get("slippage_price_per_side", 0.0)
        ),
        "commission_per_round_trip": float(
            profile.get("commission_per_round_trip", 0.0)
        ),
        "swap_per_night_r": float(profile.get("swap_per_night_r", 0.0)),
    }
    overrides = profile.get("instrument_overrides") or {}
    if isinstance(overrides, dict) and isinstance(overrides.get(symbol), dict):
        for key, value in overrides[symbol].items():
            if key in values and isinstance(value, (int, float)):
                values[key] = float(value)
    spread = values["spread_price"] / risk_distance
    slippage = 2.0 * values["slippage_price_per_side"] / risk_distance
    commission = (
        values["commission_per_round_trip"] / risk_amount
        if risk_amount > 0
        else 0.0
    )
    swap = max(0, int(holding_days)) * values["swap_per_night_r"]
    return spread, slippage, commission, swap


def validate_run(run: dict[str, Any]) -> dict[str, Any]:
    """Validate a stored ui_run_v1 payload from its immutable trade records."""
    findings: list[Finding] = []
    trades = run.get("trades")
    if not isinstance(trades, list):
        _add(
            findings,
            "TRADES_MISSING",
            "run",
            "Run has no trade list.",
            "Regenerate the run with the current engine.",
        )
        trades = []

    profile = run.get("cost_profile") if isinstance(run.get("cost_profile"), dict) else None
    pnl: list[float] = []
    net_pnl: list[float] = []
    previous_exit: str | None = None

    for index, trade in enumerate(trades):
        if not isinstance(trade, dict):
            _add(
                findings,
                "TRADE_NOT_OBJECT",
                "trade",
                f"Trade {index} is not an object.",
                "Inspect the run artifact.",
                trade_key=str(index),
            )
            continue
        key = _trade_key(trade, index)
        direction = trade.get("direction")
        entry = _number(trade.get("entry_price"))
        exit_price = _number(trade.get("exit_price"))
        stop = _number(trade.get("sl_price"))
        target = _number(trade.get("tp_price"))
        recorded_r = _number(trade.get("pnl_r"))
        if direction not in {"LONG", "SHORT"}:
            _add(findings, "DIRECTION_INVALID", "trade", "Direction is not LONG/SHORT.", "Inspect the trade record.", trade_key=key)
            continue
        if entry is None or exit_price is None or stop is None or target is None:
            _add(findings, "PRICE_INVALID", "trade", "Entry/exit/SL/TP is missing or non-finite.", "Inspect the trade record.", trade_key=key)
            continue
        risk_distance = abs(entry - stop)
        if risk_distance <= 0 or not isfinite(risk_distance):
            _add(findings, "RISK_DISTANCE_INVALID", "trade", f"Risk distance is {risk_distance}.", "Reject trades with entry at the stop.", trade_key=key)
            continue
        if direction == "LONG":
            independent_r = (exit_price - entry) / risk_distance
        else:
            independent_r = (entry - exit_price) / risk_distance
        # Run artifacts round pnl_r to four decimals; compare with artifact precision.
        if recorded_r is None or not _close(recorded_r, independent_r, abs_tol=5e-4):
            _add(
                findings,
                "PNL_FORMULA_MISMATCH",
                "trade",
                f"Recorded {recorded_r}R; independent {independent_r}R.",
                "Inspect the fill and R calculation.",
                trade_key=key,
            )
        pnl.append(recorded_r if recorded_r is not None else independent_r)

        close_reason = str(trade.get("close_reason") or "")
        if close_reason == "SL":
            if direction == "LONG" and exit_price > stop + 1e-10:
                _add(findings, "SL_PRICE_INVALID", "trade", "Long SL exit is above the stop.", "Inspect gap fill handling.", trade_key=key)
            if direction == "SHORT" and exit_price < stop - 1e-10:
                _add(findings, "SL_PRICE_INVALID", "trade", "Short SL exit is below the stop.", "Inspect gap fill handling.", trade_key=key)
        elif close_reason == "TP":
            if direction == "LONG" and exit_price < target - 1e-10:
                _add(findings, "TP_PRICE_INVALID", "trade", "Long TP exit is below the target.", "Inspect target fill handling.", trade_key=key)
            if direction == "SHORT" and exit_price > target + 1e-10:
                _add(findings, "TP_PRICE_INVALID", "trade", "Short TP exit is above the target.", "Inspect target fill handling.", trade_key=key)
        elif close_reason == "AMBIGUITY":
            if independent_r > 0:
                _add(findings, "AMBIGUITY_FAVOURABLE", "trade", "Ambiguous exit has positive R.", "Inspect ambiguity resolution.", trade_key=key)
        elif close_reason not in {
            "TIMEOUT",
            "FORCE_CLOSE_END_OF_DATA",
        }:
            _add(findings, "CLOSE_REASON_UNKNOWN", "trade", f"Unknown close reason {close_reason!r}.", "Inspect the simulator.", trade_key=key, severity="warning")

        planned_risk = _number(trade.get("planned_risk_amount"))
        planned_size = _number(trade.get("planned_position_size"))
        planned_entry = _number(trade.get("planned_entry_price"))
        realized_risk = _number(trade.get("realized_risk_amount"))
        position_size = _number(trade.get("position_size"))
        if all(value is not None for value in (planned_risk, planned_size, planned_entry)):
            independent_planned = abs(planned_size * (planned_entry - stop))
            if not _close(planned_risk, independent_planned):
                _add(findings, "PLANNED_RISK_MISMATCH", "trade", f"Planned risk {planned_risk} vs {independent_planned} from planned size/entry.", "Inspect planning fields.", trade_key=key, severity="warning")
        if realized_risk is not None and position_size is not None:
            independent_realized = position_size * risk_distance
            if not _close(realized_risk, independent_realized):
                _add(findings, "REALISED_RISK_MISMATCH", "trade", f"Realised risk {realized_risk} vs {independent_realized} from size/stop.", "Inspect fill-time sizing.", trade_key=key, severity="warning")

        if profile is not None:
            risk_amount = realized_risk or planned_risk or 0.0
            holding_days = 0
            try:
                entry_dt = datetime.fromisoformat(str(trade.get("entry_time")))
                exit_dt = datetime.fromisoformat(str(trade.get("exit_time")))
                holding_days = max(0, (exit_dt.date() - entry_dt.date()).days)
            except (TypeError, ValueError):
                pass
            spread, slippage, commission, swap = _profile_cost(
                profile,
                str(trade.get("symbol", "")),
                risk_distance,
                risk_amount,
                holding_days,
            )
            expected_total = spread + slippage + commission + swap
            total = _number(trade.get("total_cost_r"))
            net = _number(trade.get("net_pnl_r"))
            if total is None or not _close(total, expected_total, rel=1e-6, abs_tol=5e-4):
                _add(findings, "COST_TOTAL_MISMATCH", "cost", f"Recorded total cost {total} vs independent {expected_total}.", "Inspect the selected cost profile.", trade_key=key)
            if net is None or not _close(net, independent_r - expected_total, rel=1e-6, abs_tol=5e-4):
                _add(findings, "NET_PNL_MISMATCH", "cost", f"Recorded net {net} vs independent {independent_r - expected_total}.", "Inspect gross/net separation.", trade_key=key)
            net_pnl.append(net if net is not None else independent_r - expected_total)

        exit_time = trade.get("exit_time")
        if isinstance(exit_time, str):
            if previous_exit is not None and exit_time < previous_exit:
                _add(findings, "TRADE_ORDER_INVALID", "run", "Trades are not ordered by exit time.", "Sort the trade ledger deterministically.", trade_key=key)
            previous_exit = exit_time

    metrics = run.get("metrics") if isinstance(run.get("metrics"), dict) else {}
    independent = _independent_metrics(pnl)
    comparisons = (
        ("total_trades", "TOTAL_TRADES"),
        ("wins", "WINS"),
        ("losses", "LOSSES"),
        ("win_rate", "WIN_RATE"),
        ("profit_factor", "PROFIT_FACTOR"),
        ("expectancy", "EXPECTANCY"),
        ("max_drawdown", "MAX_DRAWDOWN"),
        ("largest_win", "LARGEST_WIN"),
        ("largest_loss", "LARGEST_LOSS"),
    )
    for metric, code in comparisons:
        reported = metrics.get(metric)
        if reported is None:
            continue
        if not _close(_number(reported), _number(independent[metric]), rel=1e-4, abs_tol=1e-3):
            _add(findings, f"METRIC_{code}", "metrics", f"{metric} reported {reported} vs independent {independent[metric]}.", "Inspect metric calculation.", severity="error")

    net_metrics = run.get("net_metrics") if isinstance(run.get("net_metrics"), dict) else None
    if net_metrics is not None and net_pnl:
        independent_net = _independent_metrics(net_pnl)
        for metric in ("expectancy", "max_drawdown", "profit_factor"):
            reported = net_metrics.get(metric)
            if reported is None:
                continue
            if not _close(_number(reported), _number(independent_net[metric]), rel=1e-4, abs_tol=1e-3):
                _add(findings, f"NET_METRIC_{metric.upper()}", "metrics", f"Net {metric} reported {reported} vs independent {independent_net[metric]}.", "Inspect net metric calculation.", severity="error")

    errors = [item for item in findings if item.severity == "error"]
    warnings = [item for item in findings if item.severity == "warning"]
    return {
        "run_id": run.get("id"),
        "checked_trades": len(trades),
        "valid": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "findings": [item.to_dict() for item in findings],
        "independent_metrics": independent,
    }
