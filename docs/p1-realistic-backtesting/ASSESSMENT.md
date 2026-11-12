# P1 Assessment

## 1. P0 re-validation

Before adding P1:

- `python -m unittest discover -s tests` → **604 tests, OK**.
- `make lint` → PASS.
- `cd frontend && npm run build` → PASS.
- Existing P0 evidence and dataset hashes re-checked.
- No P0 regression was found. The P0 contracts remain:
  - fill-time sizing preserves planned risk;
  - ambiguous inside-bar exits use stop-first;
  - gap-through-stop records the actual fill loss;
  - CORE close-outside is transition-only;
  - duplicate timestamps fail closed.
- P1 does not change P0 strategy logic, historical data or existing run artifacts.

## 2. Extension points found

| Area | Existing component | P1 extension |
|---|---|---|
| Cost | `TradeSimulator`, `TradePlan`, `ClosedTrade` | `TradeSimulator(cost_model=...)`, cost fields on closed trades |
| Gross/net metrics | `BacktestResult`, `PerformanceMetrics` | `BacktestResult.net_metrics`; run-level `net_metrics` |
| Run persistence | `server/research_service.run_backtest` | cost profile + net metrics + dataset quality recorded in run |
| Validation | no independent validator | `backtests/validation.py` |
| Data quality | `assess_dataset_quality`, resampler stats | `historical/quality.py` reusable report |
| Preflight | service-level validation inside run | `server/preflight.py` structured checks |
| UI | Strategy Lab, Run Archive, Market Data | cost selector, preflight, gross/net/cost, validation and quality panels |

## 3. Reused components

`BacktestRunner`, `FixedRiskRewardPolicy`, `FixedRiskSizer` + P0 fill-time resizing, `ConservativeOHLCFillModel`, `TradeSimulator`, `PerformanceMetrics`, `HistoricalDataParser`, `research.free_ohlc.resampler`, `historical.calendar`, FastAPI service and existing UI primitives.

No second backtest engine, database, or new third-party dependency was introduced.

## 4. Key limitations identified before implementation

- No historical bid/ask data; spread/slippage must be labelled proxies.
- No account-currency conversion feed; results remain R-multiples.
- No partial exits.
- No tick-level ambiguity resolution.
- Dataset quality is expensive to recompute; reports are read-only and can be recomputed/cached later.
- The preflight service is additive; the existing service still performs its own final guard checks.
