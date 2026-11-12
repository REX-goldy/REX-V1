# P1 Test Report

- **Date:** 2026-11-03
- **Environment:** Python 3.11.6, Node 20.9.0, Vite 5.4.21
- **Full suite:** **628 / 628 PASS**
- **P1-specific tests:** 24
- **Lint:** PASS
- **Frontend build:** PASS (chunk-size advisory only)
- **P0 regression:** PASS (11 P0 tests remain in the suite)
- **No commit, push, deploy, data modification or run rewrite.**

## 1. Test matrix

| Area | Tests | Result |
|---|---|---|
| P0 execution integrity (retained) | 11 | PASS |
| P1 cost profiles/simulator | 5 | PASS |
| P1 independent validation | 7 | PASS |
| P1 preflight | 5 | PASS |
| P1 dataset quality | 3 | PASS |
| P1 cost/quality/preflight/validation API | 4 | PASS |
| Existing repository regression | remainder | PASS |
| **Total** | **628** | **PASS** |

New files:
- `tests/test_p1_costs.py`
- `tests/test_p1_validation.py`
- `tests/test_p1_preflight.py`
- `tests/test_p1_data_quality.py`
- `tests/test_p1_api.py`

Commands:
```bash
python -m unittest discover -s tests
make lint
cd frontend && npm run build
```

Evidence: `EVIDENCE/tests-full.log`, `EVIDENCE/lint.log`, `EVIDENCE/frontend-build.log`.

## 2. Cost verification

Selected profile: `proxy_forex_v1` (estimated proxy, 1.2 pips spread, 0.2 pips adverse slippage/side; USDJPY override).

API run `20261103T170348Z_3cff7597` (EURUSD S008 2026-05-01..03):
- gross expectancy: **−0.262746R**
- net expectancy: **−2.865300R**
- 54 trades
- first trade: total cost **3.2R**, net **−1.2R** (gross +2R)
- profile and assumptions recorded in the run
- independent validation: **valid, 0 errors, 0 warnings**

Evidence: `EVIDENCE/costed-run.json`, `EVIDENCE/independent-validation.json`.

The large cost ratio is real for the proxy assumptions on a tight-stop sample; it is not hidden or normalized away. This is why gross and net are separate and why the proxy is labelled estimated.

## 3. Independent validation

`backtests/validation.py` independently recalculates from trade fields:

- gross R by direction;
- planned/realised risk from size × stop distance;
- SL/TP exit side and ambiguity sign;
- independent cost components and net R;
- gross and net metrics, including drawdown;
- trade ordering and missing fields.

The validator does not call the engine's PnL or cost functions. Artifact rounding is handled with explicit 4-decimal tolerances. Synthetic fixtures test valid, PnL mismatch, risk mismatch, cost mismatch, net-metric mismatch, favourable ambiguity and missing-field cases.

## 4. Dataset quality

`GET /api/dataset-quality?dataset_id=EURUSD/M1/2026`:

- 184,963 bars
- 0 duplicates / 0 ordering violations / 0 invalid bars
- 35 raw gaps
- **10 unexpected gaps**
- **17 missing FX-open minutes**
- 74,880 closure minutes; 0 bars inside closure
- M5: 36,987 emitted, 9 incomplete buckets skipped
- M15/H1/H4 also audited
- status: `warning`
- source hash unchanged; no interpolation

GBPUSD check: 93,600 bars, 0 unexpected gaps, 0 missing open minutes, status `ok`.

Evidence: `EVIDENCE/eurusd-quality.json`, UI `EVIDENCE/quality-panel.png`.

## 5. Preflight

`POST /api/validation/backtest` returns structured issues. Verified:

- valid S008 EURUSD configuration → no blocking errors;
- AUDUSD + S002 → `ZONE_BOOK_MISSING` error;
- unknown dataset/strategy/cost profile → explicit errors;
- invalid range/R/risk → explicit errors;
- estimated proxy profile → warning;
- EURUSD quality warning propagated.

Evidence: `EVIDENCE/preflight.json`.

## 6. Frontend verification

Chromium run against local UI and API:

```
quality_panel=1
has_10=true
preflight=1
net_panel=true
net_expectancy=true
validation_panel=true
console_errors=0
```

Screenshots:
- `EVIDENCE/quality-panel.png`
- `EVIDENCE/cost-net-validation.png`
- `EVIDENCE/ui-e2e.log`

The Strategy Lab disables execution until preflight returns valid; cost profile is selectable; net/cost/validation panels and Net R trade column are populated from backend data.

## 7. Preserved assets

- Historical dataset hashes unchanged from the P0 baseline.
- Existing run artifacts not rewritten.
- P0 execution semantics and tests retained.
- No new dependency or database.

## 8. Known limitations

- Cost profiles are deterministic assumptions, not observed historical bid/ask.
- Swap is R-per-night; no account-currency conversion exists.
- The proxy cost run can show large cost-to-R ratios on tight stops; that is an honest result, not an engine error.
- Dataset-quality reports recompute full data on demand and are relatively expensive; caching is future work.
- Preflight is integrated into Strategy Lab; the service's final guards remain.
- The frontend build emits a non-fatal >500 kB chunk advisory.
- P2–P6 are not implemented in this phase.
