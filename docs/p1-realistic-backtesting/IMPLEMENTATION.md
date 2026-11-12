# P1 Implementation

## 1. P1.1 transaction costs

### Cost formula

For each closed trade:

```text
spread_r      = spread_price / risk_distance
slippage_r    = (2 × slippage_price_per_side) / risk_distance
commission_r  = commission_per_round_trip / realized_risk_amount
swap_r        = nights × swap_per_night_r
net_pnl_r     = gross_pnl_r − (spread_r + slippage_r + commission_r + swap_r)
```

- Gross `pnl_r` and metrics are untouched.
- Net metrics are independently calculated from `net_pnl_r`.
- The selected profile and complete assumptions are stored in the run.
- The zero-cost profile is explicitly marked legacy/gross.
- Proxy profiles are marked estimated; no historical bid/ask is fabricated.
- Cost application is centralised in `backtests/costs.py` and the existing simulator; no new pipeline.

## 2. P1.2 independent validation

`backtests/validation.py` re-implements arithmetic from trade fields:

- gross R formula by direction;
- position size × stop distance vs realised risk;
- planned size × planned entry-to-stop vs planned risk;
- SL/TP exit-side checks;
- ambiguity sign/favourable check;
- independent spread/slippage/commission/swap and net R;
- independent gross and net metrics, including drawdown;
- ordered trade ledger check;
- explicit findings with codes and corrections.

It does not call `calculate_pnl_r`, `calculate_trade_metrics`, or the cost model. Artifact rounding (4 decimals) is accounted for in comparison tolerances.

## 3. P1.3 dataset quality

`historical/quality.py` builds a read-only report from the actual CSV and metadata:

- raw duplicate/order scan even if the strict parser rejects a row;
- parser/OHLC validity;
- FX-open vs closure gap classification using the shared calendar;
- unexpected gaps (EURUSD 10 / 17 missing open minutes);
- normal closure counts;
- provider provenance;
- M5/M15/H1/H4 resampler completeness and skipped-bucket counts.

The report is exposed in Market Data and attached to new run artifacts. It never fills/interpolates data.

## 4. P1.4 preflight

`server/preflight.py` returns structured `error`/`warning`/`info` records for:

- strategy availability;
- timeframe;
- parameters;
- dataset existence and range;
- zone book requirement;
- dataset quality errors/warnings;
- R/equity/risk configuration;
- cost profile existence and estimated status.

Strategy Lab calls `POST /api/validation/backtest` before enabling execution. Existing service guards remain as the final boundary.

## 5. Frontend

- Strategy Lab: cost-profile selector, preflight panel, net/cost panel, independent validation summary, planned → realised risk and Net R trade columns.
- Market Data: source/derived quality panel with unexpected gaps, missing open minutes, closure minutes, derived bucket skip counts and warnings.
- Run Archive: cost profile, gross/net expectancy and independent validation summary in run detail.
- All values come from backend run/quality/validation payloads.

## 6. Files changed

- `backtests/costs.py`, `config/cost_profiles.json`
- `backtests/validation.py`
- `historical/quality.py`
- `server/preflight.py`
- `backtests/trade_simulator.py`, `backtests/backtest_runner.py`, `backtests/results.py`, `backtests/metrics.py`
- `models/closed_trade.py`
- `server/research_service.py`, `server/main.py`
- `frontend/src/types.ts`, `api.ts`, `ResearchPage.tsx`, `DataPage.tsx`, `RunsPage.tsx`
- tests: `tests/test_p1_costs.py`, `test_p1_validation.py`, `test_p1_preflight.py`, `test_p1_data_quality.py`, `test_p1_api.py`
- docs: this directory

## 7. Dependencies / database

- New dependencies: **none**.
- Database: **none**.
- New config file: `config/cost_profiles.json`.
- No migration of existing data or run artifacts.

## 8. Known limitations

- Costs are estimated/proxy unless a user supplies an explicit profile; no historical bid/ask.
- Swap is R-per-night, not account-currency conversion.
- No account-currency P&L or conversion feed.
- No partial exits, order rejection, execution delay or broker constraints.
- Dataset quality reports can be expensive; current implementation recomputes. A cache can be added after profiling.
- Preflight is advisory to the UI; the service retains final guard checks.
- P2 dashboard, P3 advanced research, P4 agents, P5 paper and P6 live are not started.
