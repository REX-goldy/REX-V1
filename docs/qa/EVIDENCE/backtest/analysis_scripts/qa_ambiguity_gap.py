"""Probe AMBIGUITY PnL when a gap opens beyond the stop and the bar also spans TP."""
import json, sys
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path("/home/user/workspaces/7de05e41da33"); sys.path.insert(0,str(ROOT))
from backtests.backtest_runner import BacktestRunner
from backtests.trade_simulator import calculate_pnl_r
from models.bar import Bar
from models.signal import Signal, SignalType
from strategies.base_strategy import BaseStrategy

class OneSignal(BaseStrategy):
    strategy_id="QA_AMBIG_GAP"; strategy_name="QA Ambiguity Gap"; description="Ambiguity gap probe"
    def __init__(self, ts, signal): self.ts=ts; self.signal=signal
    def generate_signals(self,candles):
        return [self.signal] if candles[-1].timestamp==self.ts else []

ts=datetime(2026,1,1,12,0)
bars=[
    Bar("EURUSD",ts,1.1500,1.1510,1.1400,1.1500),
    Bar("EURUSD",ts+timedelta(minutes=1),1.1500,1.1550,1.1450,1.1500),
    Bar("EURUSD",ts+timedelta(minutes=2),1.1000,1.1800,1.0900,1.1500),
]
sig=Signal("EURUSD",SignalType.BULLISH_SWEEP,0,1.1500,ts,"gap beyond SL and through TP")
res=BacktestRunner().run(OneSignal(ts,sig),bars,simulate_trades=True)
t=res.closed_trades[0]
raw=calculate_pnl_r(t.direction,t.entry_price,t.sl_price,t.exit_price)
out={
 "bars":[{"timestamp":b.timestamp.isoformat(),"open":b.open,"high":b.high,"low":b.low,"close":b.close} for b in bars],
 "entry_price":t.entry_price,"sl":t.sl_price,"tp":t.tp_price,"exit_price":t.exit_price,
 "close_reason":t.close_reason,"recorded_pnl_r":t.pnl_r,"raw_formula_pnl_r":raw,
 "understates_loss": raw < t.pnl_r,
 "explanation":"Bar open gaps below SL while bar also spans TP; fill model returns bar.open with AMBIGUITY, simulator overwrites PnL to -1R.",
}
Path(ROOT/"docs/qa/EVIDENCE/backtest/ambiguity_gap_probe.json").write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out,indent=2))
