"""Agent 7 independent QA analysis for REX backtesting/execution.

Read-only: loads existing datasets and code. Writes only under the QA evidence dir.
No strategy/config/test/data modifications.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path("/home/user/workspaces/7de05e41da33")
EVIDENCE = ROOT / "docs/qa/EVIDENCE/backtest"
TMP = Path("/tmp/opencode/qa-backtest")
EVIDENCE.mkdir(parents=True, exist_ok=True)
TMP.mkdir(parents=True, exist_ok=True)
RUNS = TMP / "runs"
RUNS.mkdir(parents=True, exist_ok=True)
os.environ["REX_RUNS_DIR"] = str(RUNS)
os.environ["REX_DATA_DIR"] = str(ROOT / "data/historical")

sys.path.insert(0, str(ROOT))

from backtests.backtest_runner import BacktestRunner
from backtests.metrics import calculate_max_drawdown
from execution.planner import TradePlanner
from execution.policies import FixedRiskRewardPolicy
from execution.sizers import FixedRiskSizer
from historical.provider import HistoricalDataProvider
from models.account_context import AccountContext
from models.entry_model import EntryModel
from models.trade_plan import TradePlanStatus
from server import research_service as service
from strategies.liquidity_sweep import LiquiditySweepStrategy

ZERO = 1e-12


def f(x: float, n: int = 10) -> float:
    return round(float(x), n)


def isclose(a, b, tol=1e-12) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=tol)


def finite_tree(obj: Any, path: str = "$") -> list[str]:
    problems: list[str] = []
    if isinstance(obj, float):
        if not math.isfinite(obj):
            problems.append(f"{path}={obj!r}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            problems.extend(finite_tree(v, f"{path}.{k}"))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            problems.extend(finite_tree(v, f"{path}[{i}]"))
    return problems


def load_bars(symbol: str, start: date, end: date):
    return HistoricalDataProvider().get_bars(symbol, "M1", start, end)


def make_planner(equity: float = 100_000.0, risk_fraction: float = 0.01, r_multiple: float = 2.0):
    return RecordingPlanner(
        policy=FixedRiskRewardPolicy(r_multiple=r_multiple),
        sizer=FixedRiskSizer(),
        account=AccountContext(equity=equity, risk_fraction=risk_fraction),
    )


class RecordingPlanner(TradePlanner):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.plans: list[Any] = []

    def plan(self, setup, candles):
        plan = super().plan(setup, candles)
        if plan is not None:
            self.plans.append(plan)
        return plan


def independent_metrics(trades):
    pnl = [t.pnl_r for t in trades]
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p < 0]
    zeros = [p for p in pnl if p == 0]
    decided = len(wins) + len(losses)
    gross_profit = math.fsum(wins)
    gross_loss = abs(math.fsum(losses))
    pf = (gross_profit / gross_loss) if gross_loss > 0 else None
    n = len(pnl)
    return {
        "total_trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "zeros": len(zeros),
        "decided": decided,
        "win_rate": (len(wins) / decided * 100.0) if decided else 0.0,
        "profit_factor": pf,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "total_r": math.fsum(pnl),
        "expectancy": (math.fsum(pnl) / n) if n else 0.0,
        "average_win": (gross_profit / len(wins)) if wins else 0.0,
        "average_loss": (math.fsum(losses) / len(losses)) if losses else 0.0,
        "max_drawdown": calculate_max_drawdown(pnl),
        "largest_win": max(wins, default=0.0),
        "largest_loss": min(losses, default=0.0),
        "ambiguous_exits": sum(1 for t in trades if t.close_reason == "AMBIGUITY"),
        "avg_holding_duration": (sum(t.holding_duration_candles for t in trades) / n) if n else 0.0,
    }


def curve_from_trades(trades):
    eq = 0.0
    peak = 0.0
    points = []
    max_dd = 0.0
    for t in trades:
        eq += t.pnl_r
        peak = max(peak, eq)
        dd = peak - eq
        max_dd = max(max_dd, dd)
        points.append({
            "exit_time": t.exit_time.isoformat(),
            "symbol": t.symbol,
            "pnl_r": t.pnl_r,
            "cumulative_r": eq,
            "drawdown_r": dd,
        })
    return {"points": points, "final_r": eq, "max_drawdown": max_dd}


def compare_metrics(reported, independent):
    mapping = {
        "wins": "wins",
        "losses": "losses",
        "win_rate": "win_rate",
        "profit_factor": "profit_factor",
        "expectancy": "expectancy",
        "max_drawdown": "max_drawdown",
        "largest_win": "largest_win",
        "largest_loss": "largest_loss",
        "average_win": "average_win",
        "average_loss": "average_loss",
        "total_trades": "total_trades",
        "ambiguous_exits": "ambiguous_exits",
        "avg_holding_duration": "avg_holding_duration",
    }
    out = {}
    for field, key in mapping.items():
        a = getattr(reported, field)
        b = independent[key]
        out[field] = {
            "reported": a,
            "independent": b,
            "delta": None if a is None or b is None else float(a) - float(b),
            "match": isclose(a, b),
        }
    return out


def run_direct(symbol: str, start: date, end: date):
    bars = load_bars(symbol, start, end)
    planner = make_planner()
    strategy = LiquiditySweepStrategy(lookback=10, min_wick_ratio=0.60, tolerance=0.0)
    result = BacktestRunner().run(
        strategy, bars, simulate_trades=True, trade_planner=planner
    )
    return bars, planner, result


def signal_id_for(outcome):
    return f"{outcome.symbol}_{outcome.timestamp.isoformat()}_{outcome.signal_type}"


def validate_lifecycle(symbol, bars, planner, result):
    by_ts = {b.timestamp: b for b in bars}
    idx = {b.timestamp: i for i, b in enumerate(bars)}
    signal_by_id = {signal_id_for(s): s for s in result.signal_outcomes}
    plan_by_id = {p.setup_id: p for p in planner.plans}
    checks = Counter()
    failures: list[str] = []
    holding_by_reason = defaultdict(Counter)
    risk_diffs = []
    ambiguous_raw = []

    for t in result.closed_trades:
        sig = signal_by_id.get(t.signal_id)
        plan = plan_by_id.get(t.signal_id)
        if sig is None:
            failures.append(f"missing signal for trade {t.signal_id}")
            continue
        if plan is None:
            failures.append(f"missing plan for trade {t.signal_id}")
            continue
        checks["trades_checked"] += 1

        if t.entry_time > sig.timestamp:
            checks["entry_after_signal"] += 1
        else:
            failures.append(f"entry not after signal {t.signal_id}")

        if plan.status == TradePlanStatus.PLANNED:
            checks["plan_status_planned"] += 1
        else:
            failures.append(f"unexpected plan status {plan.status}")

        if plan.planned_at == sig.timestamp:
            checks["planned_at_signal_time"] += 1
        else:
            failures.append(f"planned_at mismatch {t.signal_id}")

        if plan.entry_model == EntryModel.NEXT_CANDLE_OPEN:
            checks["entry_model_next_open"] += 1
        else:
            failures.append(f"unexpected entry model {plan.entry_model}")

        for field in ("estimated_fees", "estimated_spread", "estimated_slippage"):
            if getattr(plan, field) == 0.0:
                checks[f"{field}_zero"] += 1
            else:
                failures.append(f"{field} nonzero for {t.signal_id}: {getattr(plan, field)}")

        ebar = by_ts.get(t.entry_time)
        if ebar is None:
            failures.append(f"entry bar missing {t.signal_id}")
            continue
        if ebar.open == t.entry_price:
            checks["entry_at_bar_open"] += 1
        else:
            failures.append(f"entry price != bar open {t.signal_id}")

        sigbar = by_ts.get(sig.timestamp)
        expected_sl = sigbar.low if t.direction.value == "LONG" else sigbar.high
        if t.sl_price == expected_sl:
            checks["sl_matches_signal_bar_extreme"] += 1
        else:
            failures.append(f"SL mismatch {t.signal_id}: {t.sl_price} vs {expected_sl}")

        risk = abs(t.entry_price - t.sl_price)
        sign = 1.0 if t.direction.value == "LONG" else -1.0
        expected_tp = t.entry_price + sign * risk * 2.0
        if isclose(t.tp_price, expected_tp):
            checks["tp_matches_r_multiple"] += 1
        else:
            failures.append(f"TP mismatch {t.signal_id}: {t.tp_price} vs {expected_tp}")

        if t.close_reason == "AMBIGUITY":
            ambiguous_raw.append({
                "signal_id": t.signal_id,
                "entry_price": t.entry_price,
                "sl_price": t.sl_price,
                "tp_price": t.tp_price,
                "exit_price": t.exit_price,
                "forced_pnl_r": t.pnl_r,
                "raw_formula_pnl_r": sign * (t.exit_price - t.entry_price) / risk if risk else None,
            })
            if t.pnl_r == -1.0:
                checks["ambiguity_forced_minus_1R"] += 1
        else:
            expected_r = sign * (t.exit_price - t.entry_price) / risk if risk else 0.0
            if isclose(t.pnl_r, expected_r):
                checks["pnl_r_matches_formula"] += 1
            else:
                failures.append(f"pnl_r mismatch {t.signal_id}: {t.pnl_r} vs {expected_r}")

        if t.close_reason in {"SL", "TP", "TIMEOUT", "AMBIGUITY", "FORCE_CLOSE_END_OF_DATA"}:
            checks["known_close_reason"] += 1
        else:
            failures.append(f"unknown close reason {t.close_reason}")

        if t.exit_time in idx and t.entry_time in idx:
            entry_i = idx[t.entry_time]
            exit_i = idx[t.exit_time]
            span = exit_i - entry_i + 1
            holding = t.holding_duration_candles
            same_bar = exit_i == entry_i
            if t.close_reason in {"TIMEOUT", "FORCE_CLOSE_END_OF_DATA"}:
                expected_holding = span
            else:
                expected_holding = 1 if same_bar else (exit_i - entry_i)
            holding_by_reason[t.close_reason][f"holding={holding},span={span}"] += 1
            if holding == expected_holding:
                checks["holding_duration_code_convention"] += 1
            else:
                failures.append(
                    f"holding mismatch {t.signal_id} {t.close_reason}: {holding} vs expected {expected_holding} (span {span})"
                )

        planned_risk = abs(plan.entry_price - plan.sl_price)
        expected_size = plan.risk_amount / planned_risk if planned_risk else None
        if expected_size is not None and isclose(plan.position_size, expected_size):
            checks["position_size_from_planned_risk"] += 1
        else:
            failures.append(f"position size mismatch {t.signal_id}")

        realized_risk_currency = risk * plan.position_size
        risk_diffs.append({
            "signal_id": t.signal_id,
            "planned_entry": plan.entry_price,
            "actual_entry": t.entry_price,
            "planned_risk_amount": plan.risk_amount,
            "realized_risk_amount": realized_risk_currency,
            "realized_vs_planned_ratio": realized_risk_currency / plan.risk_amount if plan.risk_amount else None,
        })

    # Ordering / overlap for each symbol
    by_symbol = defaultdict(list)
    for t in result.closed_trades:
        by_symbol[t.symbol].append(t)
    for sym, trades in by_symbol.items():
        ordered = sorted(trades, key=lambda t: (t.entry_time, t.exit_time))
        for prev, nxt in zip(ordered, ordered[1:]):
            if nxt.entry_time >= prev.exit_time:
                checks["no_same_symbol_overlap"] += 1
            else:
                failures.append(f"overlap {sym}: {prev.signal_id} -> {nxt.signal_id}")
        for t in trades:
            if t.entry_time <= t.exit_time:
                checks["entry_before_or_at_exit"] += 1
            else:
                failures.append(f"exit before entry {t.signal_id}")

    exit_times = [t.exit_time for t in result.closed_trades]
    if exit_times == sorted(exit_times):
        checks["trades_sorted_by_exit_time"] += 1
    else:
        failures.append("closed trades not sorted by exit_time")

    significant = [d for d in risk_diffs if abs(d["realized_vs_planned_ratio"] - 1.0) > 1e-9]
    max_risk_dev = max((abs(d["realized_vs_planned_ratio"] - 1.0) for d in risk_diffs), default=0.0)
    return {
        "checks": dict(checks),
        "failures": failures[:50],
        "failure_count": len(failures),
        "holding_distribution_by_reason": {k: dict(v) for k, v in holding_by_reason.items()},
        "risk": {
            "trades": len(risk_diffs),
            "realized_risk_differs_from_planned_count": len(significant),
            "max_abs_relative_deviation": max_risk_dev,
            "examples": significant[:10],
        },
        "ambiguity_examples": ambiguous_raw[:10],
    }


def main():
    report: dict[str, Any] = {"generated_at": datetime.utcnow().isoformat() + "Z", "runs": {}}
    configs = [
        ("EURUSD", date(2026, 5, 1), date(2026, 5, 15)),
        ("GBPUSD", date(2026, 5, 1), date(2026, 5, 15)),
    ]
    params = {"lookback": 10, "min_wick_ratio": 0.6, "tolerance": 0.0}

    for symbol, start, end in configs:
        key = f"{symbol}_S008_{start.isoformat()}_{end.isoformat()}"
        print(f"\n=== {key} ===", flush=True)
        dataset_id = f"{symbol}/M1/2026"
        server_run = service.run_backtest(
            dataset_id=dataset_id,
            strategy_id="S008",
            parameters=params,
            start=start,
            end=end,
        )
        (EVIDENCE / f"{key}_server_run.json").write_text(json.dumps(server_run, indent=2) + "\n")

        bars, planner, result = run_direct(symbol, start, end)
        (EVIDENCE / f"{key}_direct_result.json").write_text(
            json.dumps(result.to_dict(), indent=2, allow_nan=False) + "\n"
        )
        trades_csv = EVIDENCE / f"{key}_trades.csv"
        with trades_csv.open("w", newline="", encoding="utf-8") as fh:
            fields = list(asdict(result.closed_trades[0]).keys()) if result.closed_trades else [
                "symbol","direction","entry_price","entry_time","exit_price","exit_time",
                "sl_price","tp_price","pnl_r","close_reason","holding_duration_candles","signal_id","strategy_id",
            ]
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for t in result.closed_trades:
                row = asdict(t)
                row["direction"] = t.direction.value
                row["entry_time"] = t.entry_time.isoformat()
                row["exit_time"] = t.exit_time.isoformat()
                w.writerow(row)

        indep = independent_metrics(result.closed_trades)
        comparison = compare_metrics(result, indep)
        indep_train = independent_metrics(list(reversed(result.closed_trades)))
        lifecycle = validate_lifecycle(symbol, bars, planner, result)
        curve = curve_from_trades(result.closed_trades)
        ui_curve = service._equity_curve(result)

        # signal-only / simulate_trades=False behavior
        solo = BacktestRunner().run(
            LiquiditySweepStrategy(lookback=10, min_wick_ratio=0.60, tolerance=0.0),
            bars,
            simulate_trades=False,
        )

        # reproducibility: fresh strategy + planner, identical bars
        _, planner2, result2 = run_direct(symbol, start, end)
        def fingerprint(res):
            return tuple(
                (t.symbol, t.direction.value, t.entry_time.isoformat(), t.exit_time.isoformat(),
                 repr(t.entry_price), repr(t.exit_price), repr(t.sl_price), repr(t.tp_price),
                 repr(t.pnl_r), t.close_reason, t.holding_duration_candles, t.signal_id)
                for t in res.closed_trades
            )
        snap1 = {"metrics": result.summary_dict(), "trades": fingerprint(result),
                 "signals": tuple((s.symbol, s.timestamp.isoformat(), s.signal_type, s.zone_id, repr(s.price)) for s in result.signal_outcomes)}
        snap2 = {"metrics": result2.summary_dict(), "trades": fingerprint(result2),
                 "signals": tuple((s.symbol, s.timestamp.isoformat(), s.signal_type, s.zone_id, repr(s.price)) for s in result2.signal_outcomes)}
        repro_digest_1 = hashlib.sha256(repr(snap1).encode()).hexdigest()
        repro_digest_2 = hashlib.sha256(repr(snap2).encode()).hexdigest()

        # server reproducibility
        server_run2 = service.run_backtest(
            dataset_id=dataset_id, strategy_id="S008", parameters=params, start=start, end=end
        )
        server_comparable_1 = {k: server_run[k] for k in ("metrics","reconciliation","signals","equity_curve","trades","warnings")}
        server_comparable_2 = {k: server_run2[k] for k in ("metrics","reconciliation","signals","equity_curve","trades","warnings")}

        server_vs_direct_metrics = {}
        for sk, dk in [
            ("total_signals","total_signals"),("total_trades","total_trades"),("wins","wins"),
            ("losses","losses"),("win_rate","win_rate"),("profit_factor","profit_factor"),
            ("expectancy","expectancy"),("max_drawdown_r","max_drawdown"),("largest_win","largest_win"),
            ("largest_loss","largest_loss"),("ambiguous_exits","ambiguous_exits"),
            ("avg_holding_duration","avg_holding_duration"),
        ]:
            a = server_run["metrics"][sk]; b = getattr(result, dk)
            server_vs_direct_metrics[dk] = {"server": a, "direct": b, "match": isclose(a,b)}

        entry = {
            "symbol": symbol,
            "range": {"start": start.isoformat(), "end": end.isoformat()},
            "bars": len(bars),
            "server_run_id": server_run["id"],
            "server_metrics": server_run["metrics"],
            "server_warnings": server_run["warnings"],
            "server_assumptions": server_run["assumptions"],
            "server_reconciliation_signals": server_run["reconciliation"],
            "direct_reconciliation_signals": result.reconcile_signals(),
            "direct_reconciliation_execution": result.reconcile_execution(),
            "independent_metrics": indep,
            "metric_comparison": comparison,
            "metric_all_match": all(v["match"] for v in comparison.values()),
            "reverse_order_max_drawdown": indep_train["max_drawdown"],
            "server_vs_direct_metrics": server_vs_direct_metrics,
            "server_vs_direct_all_match": all(v["match"] for v in server_vs_direct_metrics.values()),
            "lifecycle": lifecycle,
            "equity_curve": {
                "independent_points": len(curve["points"]),
                "independent_final_r": curve["final_r"],
                "independent_max_drawdown": curve["max_drawdown"],
                "server_curve_points": len(ui_curve["equity"]),
                "server_curve_final_r": ui_curve["equity"][-1]["value"] if ui_curve["equity"] else None,
                "server_curve_max_drawdown": max((p["value"] for p in ui_curve["drawdown"]), default=0.0),
                "duplicate_exit_timestamps": len(result.closed_trades) - len({t.exit_time for t in result.closed_trades}),
            },
            "signal_only": {
                "simulate_trades": False,
                "total_signals": solo.total_signals,
                "total_trades": solo.total_trades,
                "closed_trades_len": len(solo.closed_trades),
                "wins": solo.wins,
                "losses": solo.losses,
                "win_rate": solo.win_rate,
                "profit_factor": solo.profit_factor,
            },
            "signal_simulation_match": solo.total_signals == result.total_signals,
            "reproducibility": {
                "direct_digest_1": repro_digest_1,
                "direct_digest_2": repro_digest_2,
                "direct_identical": repro_digest_1 == repro_digest_2,
                "server_second_run_id": server_run2["id"],
                "server_comparable_identical": server_comparable_1 == server_comparable_2,
            },
            "finite_problems_direct": finite_tree(result.to_dict()),
            "finite_problems_server": finite_tree(server_run),
        }
        report["runs"][key] = entry
        print(json.dumps({k: entry[k] for k in ("bars","server_metrics","server_warnings")}, indent=2, default=str), flush=True)
        print("metric_all_match", entry["metric_all_match"], "server_vs_direct_all_match", entry["server_vs_direct_all_match"], flush=True)
        print("lifecycle_failures", lifecycle["failure_count"], lifecycle["failures"][:5], flush=True)
        print("curve", entry["equity_curve"], flush=True)

    # Multi-symbol equity curve duplicate-timestamp probe
    print("\n=== multi-symbol equity curve probe ===", flush=True)
    eur = load_bars("EURUSD", date(2026,5,1), date(2026,5,15))
    gbp = load_bars("GBPUSD", date(2026,5,1), date(2026,5,15))
    combined = sorted(eur + gbp, key=lambda b: (b.timestamp, b.symbol))
    planner = make_planner()
    result = BacktestRunner().run(
        LiquiditySweepStrategy(lookback=10, min_wick_ratio=0.60, tolerance=0.0),
        combined, simulate_trades=True, trade_planner=planner,
    )
    ui_curve = service._equity_curve(result)
    exit_times = [t.exit_time for t in result.closed_trades]
    dupes = Counter(exit_times)
    duplicate_groups = {k.isoformat(): v for k, v in dupes.items() if v > 1}
    indep = independent_metrics(result.closed_trades)
    curve = curve_from_trades(result.closed_trades)
    report["multi_symbol_curve_probe"] = {
        "bars": len(combined),
        "trades": result.total_trades,
        "duplicate_exit_timestamp_count": len(exit_times) - len(set(exit_times)),
        "duplicate_exit_groups": dict(list(duplicate_groups.items())[:20]),
        "independent_curve_points": len(curve["points"]),
        "server_curve_points": len(ui_curve["equity"]),
        "independent_final_r": curve["final_r"],
        "server_curve_final_r": ui_curve["equity"][-1]["value"] if ui_curve["equity"] else None,
        "metrics_max_drawdown": indep["max_drawdown"],
        "independent_curve_max_drawdown": curve["max_drawdown"],
        "server_curve_max_drawdown": max((p["value"] for p in ui_curve["drawdown"]), default=0.0),
        "lossless_curve": len(ui_curve["equity"]) == result.total_trades,
    }
    print(json.dumps(report["multi_symbol_curve_probe"], indent=2), flush=True)

    (EVIDENCE / "valid_runs_analysis.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print("\nwrote", EVIDENCE / "valid_runs_analysis.json")


if __name__ == "__main__":
    main()
