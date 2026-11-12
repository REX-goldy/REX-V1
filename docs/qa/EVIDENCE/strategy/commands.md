# Strategy QA - commands and environment

All generated run artifacts used temporary directories (never the project's
`research/outputs/ui_runs`):

- Service/harness runs: `/tmp/opencode/qa-strategy/runs-harness`
- Probe runs: `/tmp/opencode/qa-strategy/runs-probe`
- HTTP runs: `/tmp/opencode/qa-strategy/http-runs`
- Short-data fixture: `/tmp/opencode/qa-strategy/fixture-data`
- Harness scripts: `/tmp/opencode/qa-strategy/`

## Baseline (no code changes)

```bash
CI=1 timeout 300 python3 -m unittest \
  tests.test_strategy_registry tests.test_strategy_interface \
  tests.test_liquidity_sweep tests.test_breakout_retest \
  tests.test_backtesting tests.test_trade_simulation \
  tests.test_ui_service tests.test_api_routes
```

Result: `Ran 93 tests in 0.315s / OK` (saved in `baseline_tests.txt`).

## Main strategy harness

```bash
cd /home/user/workspaces/7de05e41da33
REX_RUNS_DIR=/tmp/opencode/qa-strategy/runs-harness PYTHONPATH=. \
  python3 /tmp/opencode/qa-strategy/harness.py
```

The harness wrote `results.json`, `inventory.json`, `runs/`, `raw_runs/`,
`determinism/`, `invalid/`, and `audusd/` under this evidence directory.

## HTTP reproduction

A temporary uvicorn instance was started on port 16904 (16900-16903 were
already bound by other processes; no other process was touched):

```bash
REX_RUNS_DIR=/tmp/opencode/qa-strategy/http-runs PYTHONPATH=. \
  setsid nohup python3 -m uvicorn server.main:app \
  --host 0.0.0.0 --port 16904 > /tmp/opencode/qa-strategy/http-server.log 2>&1 &
```

Representative requests (full transcript in `audusd/http_transcript.txt`):

```bash
curl -sS --max-time 5 -w '\nHTTP_STATUS:%{http_code}\n' \
  http://localhost:16904/api/health
curl -sS --max-time 5 -w '\nHTTP_STATUS:%{http_code}\n' \
  http://localhost:16904/api/strategies
curl -sS --max-time 120 -w '\nHTTP_STATUS:%{http_code}\n' \
  http://localhost:16904/api/datasets
curl -sS --max-time 30 -w '\nHTTP_STATUS:%{http_code}\n' \
  -X POST http://localhost:16904/api/backtests \
  -H 'Content-Type: application/json' \
  -d '{"dataset_id":"AUDUSD/M1/2026","strategy_id":"S002","start_date":"2026-05-04","end_date":"2026-05-05"}'
curl -sS --max-time 30 -w '\nHTTP_STATUS:%{http_code}\n' \
  -X POST http://localhost:16904/api/backtests \
  -H 'Content-Type: application/json' \
  -d '{"dataset_id":"AUDUSD/M1/2026","strategy_id":"CORE_ZONE_BREAKOUT","start_date":"2026-05-04","end_date":"2026-05-05"}'
curl -sS --max-time 60 -w '\nHTTP_STATUS:%{http_code}\n' \
  -X POST http://localhost:16904/api/backtests \
  -H 'Content-Type: application/json' \
  -d '{"dataset_id":"AUDUSD/M1/2026","strategy_id":"S008","start_date":"2026-05-04","end_date":"2026-05-05"}'
```

The temporary server was stopped by PID after the transcript was captured.
Port 16904 was verified free afterwards.

## Determinism / mutation checks

The harness reran the same configuration on the same strategy instance and on a
fresh instance, hashed every signal/trade record, and hashed the input bars and
zone book before/after each run. Service-level runs were also repeated and
compared on metrics, reconciliation, signal counts, range, bar count, simulated
flag, parameters, and assumptions.
