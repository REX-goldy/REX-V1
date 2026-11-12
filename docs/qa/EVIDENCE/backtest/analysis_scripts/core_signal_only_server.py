import os, sys, json
from datetime import date
from pathlib import Path
ROOT=Path("/home/user/workspaces/7de05e41da33")
os.environ["REX_RUNS_DIR"]="/tmp/opencode/qa-backtest/runs"
os.environ["REX_DATA_DIR"]=str(ROOT/"data/historical")
sys.path.insert(0,str(ROOT))
from server import research_service as service
run=service.run_backtest(dataset_id="EURUSD/M1/2026",strategy_id="CORE_ZONE_BREAKOUT",parameters={},start=date(2026,2,1),end=date(2026,2,7))
out=ROOT/"docs/qa/EVIDENCE/backtest/core_signal_only_server_run.json"
out.write_text(json.dumps(run,indent=2)+"\n")
print(json.dumps({"id":run["id"],"simulated":run["simulated"],"metrics":run["metrics"],"reconciliation":run["reconciliation"],"signals":run["signals"],"warnings":run["warnings"]},indent=2))
