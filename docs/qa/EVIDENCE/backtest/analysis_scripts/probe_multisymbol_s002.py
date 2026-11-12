import sys, json
from collections import Counter
from datetime import date
from pathlib import Path
ROOT=Path("/home/user/workspaces/7de05e41da33"); sys.path.insert(0,str(ROOT))
from historical.provider import HistoricalDataProvider
from backtests.backtest_runner import BacktestRunner
from core.zone_loader import load_zones
from strategies.breakout_retest import S002_BreakoutRetest
p=HistoricalDataProvider(); z=load_zones(ROOT/"config/zones.json")
s,e=date(2026,5,1),date(2026,5,7)
bars={sym:p.get_bars(sym,"M1",s,e) for sym in ("EURUSD","GBPUSD")}
individual={}
for sym,bs in bars.items():
    r=BacktestRunner().run(S002_BreakoutRetest(z[sym]),bs)
    individual[sym]={"signals":r.total_signals,"by_symbol":dict(Counter(o.symbol for o in r.signal_outcomes)),"by_type":dict(Counter(o.signal_type for o in r.signal_outcomes))}
combined=sorted(bars["EURUSD"]+bars["GBPUSD"], key=lambda b:(b.timestamp,b.symbol))
# A single S002 instance can only hold one zone book; this probe uses EURUSD's book.
r=BacktestRunner().run(S002_BreakoutRetest(z["EURUSD"]),combined)
combined_out={"signals":r.total_signals,"by_symbol":dict(Counter(o.symbol for o in r.signal_outcomes)),"by_type":dict(Counter(o.signal_type for o in r.signal_outcomes))}
out={"range":[s.isoformat(),e.isoformat()],"individual":individual,"combined_with_EURUSD_book":combined_out,"sum_individual":sum(v["signals"] for v in individual.values())}
Path(ROOT/"docs/qa/EVIDENCE/backtest/multisymbol_s002_probe.json").write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out,indent=2))
