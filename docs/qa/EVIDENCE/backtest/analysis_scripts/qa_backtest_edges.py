"""Agent 7 edge-case, export, archive and serialization checks (read-only)."""
from __future__ import annotations

import csv
import json
import math
import os
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path("/home/user/workspaces/7de05e41da33")
EVIDENCE = ROOT / "docs/qa/EVIDENCE/backtest"
TMP = Path("/tmp/opencode/qa-backtest")
RUNS = TMP / "runs"
os.environ["REX_RUNS_DIR"] = str(RUNS)
os.environ["REX_DATA_DIR"] = str(ROOT / "data/historical")
sys.path.insert(0, str(ROOT))

from backtests.backtest_runner import BacktestRunner
from backtests.trade_simulator import TradeSimulator, calculate_pnl_r
from core.zone_loader import load_zones
from execution.factories import SweepTradeSetupFactory
from execution.planner import TradePlanner
from execution.policies import FixedRiskRewardPolicy
from execution.sizers import FixedRiskSizer
from historical.provider import HistoricalDataProvider
from models.account_context import AccountContext
from models.bar import Bar
from models.entry_model import EntryModel
from models.signal import Signal, SignalType
from models.trade_direction import TradeDirection
from models.trade_plan import TradePlan, TradePlanStatus
from models.trade_setup import TradeSetup
from models.zone import ZoneBook
from server import research_service as service
from strategies.base_strategy import BaseStrategy
from strategies.breakout import BreakoutStrategy
from strategies.breakout_retest import S002_BreakoutRetest
from strategies.liquidity_sweep import LiquiditySweepStrategy

provider = HistoricalDataProvider()
report: dict[str, Any] = {"generated_at": datetime.utcnow().isoformat() + "Z", "edge_cases": {}}


def finite_problems(obj, path="$"):
    out = []
    if isinstance(obj, float):
        if not math.isfinite(obj):
            out.append(f"{path}={obj!r}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(finite_problems(v, f"{path}.{k}"))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.extend(finite_problems(v, f"{path}[{i}]"))
    return out


class MockSignalStrategy(BaseStrategy):
    strategy_id = "QA_EDGE"
    strategy_name = "QA Edge Mock"
    description = "Edge-case signal injector for QA."
    def __init__(self, signal_map, max_hold_candles=None):
        self.signal_map = signal_map
        if max_hold_candles is not None:
            self.max_hold_candles = max_hold_candles
    def generate_signals(self, candles):
        cur = candles[-1]
        return [s for s in self.signal_map.get(cur.timestamp, []) if s.symbol == cur.symbol]


class NeverExitFillModel:
    def check_entry(self, plan, bar):
        return bar.open
    def check_exit(self, position, bar):
        return None


# --- S002 / CORE_ZONE_BREAKOUT signal studies on actual EURUSD data ---
start, end = date(2026, 2, 1), date(2026, 2, 7)
bars = provider.get_bars("EURUSD", "M1", start, end)
zone_book = load_zones(ROOT / "config/zones.json")["EURUSD"]
for name, strategy in [
    ("CORE_ZONE_BREAKOUT", BreakoutStrategy(zone_book)),
    ("S002", S002_BreakoutRetest(zone_book)),
]:
    res = BacktestRunner().run(strategy, bars)
    entry = {
        "bars": len(bars),
        "range": [start.isoformat(), end.isoformat()],
        "total_signals": res.total_signals,
        "by_type": dict(sorted(Counter(s.signal_type for s in res.signal_outcomes).items())),
        "total_trades": res.total_trades,
        "closed_trades_len": len(res.closed_trades),
        "wins": res.wins,
        "losses": res.losses,
        "profit_factor": res.profit_factor,
        "reconciliation_signals": res.reconcile_signals(),
        "no_crash": True,
    }
    report["edge_cases"][f"signal_study_{name}"] = entry

# CORE with simulate_trades=True (no breakout factory) should reject all signals, no trades.
core_sim = BacktestRunner().run(
    BreakoutStrategy(zone_book), bars, simulate_trades=True,
    trade_planner=TradePlanner(FixedRiskRewardPolicy(2.0), FixedRiskSizer(), AccountContext(100000.0, 0.01)),
    setup_factory=SweepTradeSetupFactory(),
)
report["edge_cases"]["core_simulate_true_no_factory"] = {
    "total_signals": core_sim.total_signals,
    "accepted": core_sim.accepted_setups_count,
    "ignored": core_sim.ignored_active_lifecycle_count,
    "rejected_policy_boundary": core_sim.rejected_policy_boundary_count,
    "trades": core_sim.total_trades,
    "reconciliation_signals": core_sim.reconcile_signals(),
    "note": "Breakout signals are outside SweepTradeSetupFactory; server marks CORE simulate_trades False.",
}

# --- Missing zones: empty ZoneBook on actual data ---
empty_book = ZoneBook(symbol="EURUSD", zones=())
small_bars = bars[:500]
for name, strat in [("CORE_ZONE_BREAKOUT", BreakoutStrategy(empty_book)), ("S002", S002_BreakoutRetest(empty_book))]:
    res = BacktestRunner().run(strat, small_bars)
    report["edge_cases"][f"missing_zones_{name}"] = {
        "bars": len(small_bars), "total_signals": res.total_signals,
        "total_trades": res.total_trades, "no_crash": True,
        "reconciliation_signals": res.reconcile_signals(),
    }

# --- Empty / insufficient / no-signal with actual data ---
empty = BacktestRunner().run(LiquiditySweepStrategy(), [], simulate_trades=True)
report["edge_cases"]["empty_dataset_sim_true"] = {
    "bars": 0, "total_signals": empty.total_signals, "total_trades": empty.total_trades,
    "started_at": None, "ended_at": None, "no_crash": True,
    "reconciliation_signals": empty.reconcile_signals(),
    "reconciliation_execution": empty.reconcile_execution(),
}
insufficient_bars = provider.get_bars("EURUSD", "M1", date(2026, 5, 1), date(2026, 5, 1))[:5]
ins = BacktestRunner().run(LiquiditySweepStrategy(), insufficient_bars, simulate_trades=True)
report["edge_cases"]["insufficient_bars"] = {
    "bars": len(insufficient_bars), "lookback_required": 11,
    "total_signals": ins.total_signals, "total_trades": ins.total_trades,
    "no_crash": True, "reconciliation_signals": ins.reconcile_signals(),
}

# Find a bounded actual window with zero S008 signals (for no-signal edge case).
day_bars = provider.get_bars("EURUSD", "M1", date(2026, 1, 1), date(2026, 1, 2))
zero_window = None
window_size = 120
# Actual first two hours of the EURUSD 2026 dataset happen to contain no sweep.
window = day_bars[:window_size]
res = BacktestRunner().run(LiquiditySweepStrategy(), window, simulate_trades=True)
if res.total_signals == 0:
    zero_window = {
        "start": window[0].timestamp.isoformat(),
        "end": window[-1].timestamp.isoformat(),
        "bars": len(window), "total_signals": res.total_signals,
        "total_trades": res.total_trades, "no_crash": True,
        "reconciliation_signals": res.reconcile_signals(),
        "reconciliation_execution": res.reconcile_execution(),
    }
report["edge_cases"]["no_signal_actual_window"] = zero_window

# --- Timeout of pending plan (LIMIT never fills) using actual bars ---
ts0 = bars[0].timestamp
setup = TradeSetup(
    setup_id="QA_PENDING_TIMEOUT", symbol="EURUSD", direction=TradeDirection.LONG,
    strategy_id="QA_EDGE", timestamp=ts0, reason="pending timeout",
    stop_hint=bars[0].low, entry_hint=bars[0].close,
    entry_model_hint=EntryModel.LIMIT, timeout_candles=3,
)
plan = TradePlan(
    setup=setup, entry_model=EntryModel.LIMIT, entry_price=setup.entry_hint,
    sl_price=setup.stop_hint, tp_price=setup.entry_hint + 0.001,
    r_multiple=2.0, position_size=1.0, risk_amount=100.0,
    timeout_candles=3, planned_at=ts0,
)
sim = TradeSimulator()
sim.add_plan(plan)
updates = []
for b in bars[1:4]:
    sim.update(b)
    updates.append({"bar": b.timestamp.isoformat(), "active": sim.get_currently_active_count(),
                    "terminated": [t.reason for t in sim.terminated_setups]})
report["edge_cases"]["pending_plan_expiry"] = {
    "timeout_candles": 3, "updates": updates,
    "final_active": sim.get_currently_active_count(),
    "terminated_reason": sim.terminated_setups[0].reason if sim.terminated_setups else None,
    "termination_time": sim.terminated_setups[0].termination_time.isoformat() if sim.terminated_setups else None,
}

# --- Open-position timeout + max_hold=1 off-by-one probe ---
base = datetime(2026, 5, 1, 0, 0)
synth = [Bar("EURUSD", base + timedelta(minutes=i), 1.1000, 1.1005, 1.0995, 1.1000) for i in range(5)]
sig = Signal("EURUSD", SignalType.BULLISH_SWEEP, 0, 1.1000, base, "timeout probe")
for max_hold in (1, 2, 3):
    strat = MockSignalStrategy({base: [sig]}, max_hold_candles=max_hold)
    res = BacktestRunner().run(strat, synth, simulate_trades=True, fill_model=NeverExitFillModel())
    t = res.closed_trades[0]
    report["edge_cases"][f"open_timeout_max_hold_{max_hold}"] = {
        "max_hold_candles": max_hold, "close_reason": t.close_reason,
        "holding_duration_candles": t.holding_duration_candles,
        "entry_time": t.entry_time.isoformat(), "exit_time": t.exit_time.isoformat(),
        "expected_if_max_hold_is_upper_bound": max_hold,
        "exceeds_max_hold": t.holding_duration_candles > max_hold,
    }

# --- Ambiguous intrabar exits from actual EURUSD run ---
amb_bars = provider.get_bars("EURUSD", "M1", date(2026, 5, 1), date(2026, 5, 15))
planner = TradePlanner(FixedRiskRewardPolicy(2.0), FixedRiskSizer(), AccountContext(100000.0, 0.01))
amb_res = BacktestRunner().run(
    LiquiditySweepStrategy(), amb_bars, simulate_trades=True, trade_planner=planner
)
bar_by_ts = {b.timestamp: b for b in amb_bars}
examples = []
for t in amb_res.closed_trades:
    if t.close_reason != "AMBIGUITY":
        continue
    b = bar_by_ts[t.exit_time]
    sign = 1.0 if t.direction == TradeDirection.LONG else -1.0
    raw = sign * (t.exit_price - t.entry_price) / abs(t.entry_price - t.sl_price)
    examples.append({
        "signal_id": t.signal_id, "direction": t.direction.value,
        "entry_price": t.entry_price, "sl": t.sl_price, "tp": t.tp_price,
        "exit_price": t.exit_price, "bar_open": b.open, "bar_high": b.high, "bar_low": b.low,
        "both_levels_touched": (b.low <= t.sl_price and b.high >= t.tp_price) if t.direction == TradeDirection.LONG else (b.high >= t.sl_price and b.low <= t.tp_price),
        "recorded_pnl_r": t.pnl_r, "raw_formula_pnl_r": raw,
        "worse_than_minus_1R_raw": raw < -1.0,
    })
    if len(examples) >= 5:
        break
report["edge_cases"]["ambiguous_intrabar_actual"] = {
    "ambiguous_count": amb_res.ambiguous_exits,
    "examples": examples,
    "all_recorded_minus_1R": all(t.pnl_r == -1.0 for t in amb_res.closed_trades if t.close_reason == "AMBIGUITY"),
}

# --- End-of-data force close and cancelled setups on actual data ---
eod_bars = provider.get_bars("EURUSD", "M1", date(2026, 5, 4), date(2026, 5, 8))
planner = TradePlanner(FixedRiskRewardPolicy(2.0), FixedRiskSizer(), AccountContext(100000.0, 0.01))
eod_res = BacktestRunner().run(LiquiditySweepStrategy(), eod_bars, simulate_trades=True, trade_planner=planner)
last_bar = eod_bars[-1]
force = [t for t in eod_res.closed_trades if t.close_reason == "FORCE_CLOSE_END_OF_DATA"]
report["edge_cases"]["end_of_data_force_close"] = {
    "bars": len(eod_bars), "last_bar": last_bar.timestamp.isoformat(),
    "last_bar_close": last_bar.close, "force_close_count": len(force),
    "examples": [
        {"signal_id": t.signal_id, "exit_time": t.exit_time.isoformat(),
         "exit_price": t.exit_price, "at_last_bar": t.exit_time == last_bar.timestamp,
         "price_equals_last_close": t.exit_price == last_bar.close}
        for t in force[:5]
    ],
}
gbp_bars = provider.get_bars("GBPUSD", "M1", date(2026, 5, 1), date(2026, 5, 15))
canc_res = BacktestRunner().run(LiquiditySweepStrategy(), gbp_bars, simulate_trades=True, trade_planner=planner)
cancelled = [s for s in canc_res.terminated_setups if s.reason == "CANCELLED_END_OF_DATA"]
report["edge_cases"]["end_of_data_cancelled_plan"] = {
    "cancelled_count": len(cancelled),
    "examples": [
        {"signal_id": s.signal_id, "setup_time": s.timestamp.isoformat(),
         "termination_time": s.termination_time.isoformat(),
         "at_last_bar": s.termination_time == gbp_bars[-1].timestamp}
        for s in cancelled[:5]
    ],
    "last_bar": gbp_bars[-1].timestamp.isoformat(),
}

# --- Export / serialization / archive compatibility ---
exp_res = amb_res
exp_dir = EVIDENCE / "exports"
exp_dir.mkdir(parents=True, exist_ok=True)
json_path = exp_res.export_json(exp_dir / "EURUSD_S008_2026-05-01_2026-05-15_result.json")
csv_path = exp_res.export_csv(exp_dir / "EURUSD_S008_2026-05-01_2026-05-15_summary.csv")
xlsx_path = exp_res.export_excel(exp_dir / "EURUSD_S008_2026-05-01_2026-05-15_result.xlsx")

payload_text = json_path.read_text()
payload = json.loads(payload_text)
forbidden = [tok for tok in ("NaN", "Infinity", "-Infinity") if tok in payload_text]
payload_roundtrip = json.loads(json.dumps(exp_res.to_dict(), allow_nan=False))
with csv_path.open(newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
import openpyxl
wb = openpyxl.load_workbook(xlsx_path, read_only=True)
sheet_names = wb.sheetnames
sheet_rows = {name: wb[name].max_row for name in sheet_names}
wb.close()
report["export"] = {
    "json_path": str(json_path.relative_to(ROOT)),
    "json_parse_ok": isinstance(payload, dict),
    "forbidden_tokens": forbidden,
    "finite_problems": finite_problems(payload),
    "roundtrip_keyset_equal": set(payload_roundtrip) == set(payload),
    "roundtrip_trade_count_equal": len(payload_roundtrip["closed_trades"]) == len(payload["closed_trades"]),
    "csv_path": str(csv_path.relative_to(ROOT)),
    "csv_rows": len(rows),
    "csv_header": list(rows[0].keys()) if rows else [],
    "csv_total_signals": rows[0].get("total_signals") if rows else None,
    "csv_contains_only_summary": "closed_trades" not in (rows[0] if rows else {}),
    "xlsx_path": str(xlsx_path.relative_to(ROOT)),
    "xlsx_sheets": sheet_names,
    "xlsx_sheet_max_rows": sheet_rows,
}

# Run archive / id compatibility from the saved valid-run artifact.
valid = json.loads((EVIDENCE / "valid_runs_analysis.json").read_text())
run_id = valid["runs"]["EURUSD_S008_2026-05-01_2026-05-15"]["server_run_id"]
loaded = service.get_run(run_id)
archive_run = json.loads((EVIDENCE / "EURUSD_S008_2026-05-01_2026-05-15_server_run.json").read_text())
report["run_archive"] = {
    "run_id": run_id,
    "run_id_matches_regex": bool(re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id)),
    "get_run_returns_same_id": loaded.get("id") == run_id,
    "schema_version": loaded.get("schema_version"),
    "has_metrics": "metrics" in loaded,
    "has_trades": "trades" in loaded,
    "has_equity_curve": "equity_curve" in loaded,
    "list_runs_contains_id": any(r["id"] == run_id for r in service.list_runs(limit=100)),
    "saved_artifact_matches_loaded": loaded == archive_run,
    "finite_problems": finite_problems(loaded),
    "forbidden_tokens_in_saved_json": [tok for tok in ("NaN", "Infinity", "-Infinity") if tok in json.dumps(loaded)],
    "direct_result_has_no_result_id_field": "id" not in exp_res.to_dict(),
}

# --- PnL helper sanity on actual examples ---
if exp_res.closed_trades:
    t = exp_res.closed_trades[0]
    report["pnl_helper_sanity"] = {
        "example_signal_id": t.signal_id,
        "direction": t.direction.value,
        "entry": t.entry_price, "sl": t.sl_price, "exit": t.exit_price,
        "closed_trade_pnl_r": t.pnl_r,
        "calculate_pnl_r_output": calculate_pnl_r(t.direction, t.entry_price, t.sl_price, t.exit_price),
        "match": abs(t.pnl_r - calculate_pnl_r(t.direction, t.entry_price, t.sl_price, t.exit_price)) < 1e-12 or t.close_reason == "AMBIGUITY",
    }

(EVIDENCE / "edge_case_analysis.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
print(json.dumps(report, indent=2, default=str))
print("\nwrote", EVIDENCE / "edge_case_analysis.json")
