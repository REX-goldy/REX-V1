# P0 Execution Integrity — Test & Verification Report

- **Date:** 2026-11-03
- **Environment:** Python 3.11.6, Node 20.9.0, Vite 5.4.21
- **Commands:** `python -m unittest discover -s tests`; `make lint`; `cd frontend && npm run build`
- **Result:** **604 / 604 tests PASS**, lint PASS, frontend typecheck/build PASS.
- **No commit, push or deploy. No historical dataset writes.**

## 1. Test count

| Item | Count |
|---|---:|
| Full repository suite | 604 |
| New P0 regression tests (`tests/test_p0_execution_integrity.py`) | 11 |
| Existing strategy interface test updated | 1 |
| Existing duplicate-timestamp fixture corrected | 1 fixture |
| Lint | PASS |
| Frontend build | PASS |

Evidence: `EVIDENCE/tests_full_after.log`, `EVIDENCE/tests_p0.log`, `EVIDENCE/lint.log`, `EVIDENCE/frontend_build.log`.

## 2. P0.1 — realised risk

### Before (EURUSD S008, 2026-05-01..15)

`EVIDENCE/before/risk_eurusd.json`:

```json
{"trades": 606, "mismatches": 543, "max_ratio": 6.499999999991673,
 "min_ratio": 0.14285714285487708}
```

Examples: planned risk 1,000 realised as 333.33, 624.99, 1,499.99, 857.14, 1,333.33. QA separately observed GBPUSD 441/468 mismatches, max 6.25×.

### After (same bars, same planner defaults)

`EVIDENCE/after/risk_both.json`:

```json
{"EURUSD": {"trades": 606, "mismatches": 0, "max_abs_deviation": 0.0},
 "GBPUSD": {"trades": 468, "mismatches": 0, "max_abs_deviation": 0.0}}
```

New tests:
- fill-time re-size preserves 100 risk after entry slippage;
- contract-size and min/max bounds;
- out-of-bounds rejection produces `REJECTED_SIZE_INVALID`;
- R metrics are not hidden/changed to force the expected risk.

**Conclusion: PASS.**

## 3. P0.2 — gap and ambiguity

Synthetic fixture (labelled in test source):

- LONG entry 1.1500, SL 1.1400, TP 1.1700.
- Next bar opens 1.1000 and spans 1.0900–1.1800.
- Before: QA evidence `before/ambiguity_gap.json` recorded −1.0R despite a −5.0R fill.
- After: `after/ambiguity_gap.json` records exit 1.1000, `pnl_r=-4.999999999999978`, `execution_assumption=both_levels_touched_gap_through_stop_at_open`.

Other tests:
- Both levels inside one bar → conservative SL fill → −1R.
- Gap through TP → TP level, no favourable gap assumption.
- Entry and exit same candle → one closed trade, correct timestamps.
- Missing next candle → pending plan cancelled.
- Normal SL/TP tests from the existing suite remain green.

**Conclusion: PASS.**

## 4. P0.3 — CORE close-outside

Real data before/after (`EVIDENCE/before/metrics.json`, `after/metrics.json`):

| Dataset | Before total | After total | Before close_outside | After close_outside |
|---|---:|---:|---:|---:|
| EURUSD 2026-03-24..25 | 21,920 | 108 | 21,848 | 36 |
| GBPUSD 2026-04-01..02 | 2,880 | 0 | 2,880 | 0 |

The after counts preserve entry/break signals (EURUSD: 36 enter, 9 break-above, 27 break-below) and emit close-outside only on transitions. GBPUSD has no zone interaction and therefore emits no signals after removing unconditional close-outside events.

Updated `tests/test_strategy_interface.py` expectation:
- first observation outside → no close-outside;
- enter zone;
- break above + one close-outside confirmation.

**Conclusion: PASS with documented, approved behavior change.**

## 5. P0.4 — duplicate timestamps

Before (`EVIDENCE/before/duplicate_feature.json` from QA):
- M1 entry materialization retained a duplicate;
- M15 dropped the bucket with `Missing entry timeframe candles`;
- direct aggregation emitted 0 bars; resampler raised duplicate error.

After:
- `FeatureRepository` rejects duplicates with a precise error.
- `aggregate_completed_bars` and `prepare_causal_bars` reject duplicates before bucketing.
- `research.free_ohlc.resampler` retains its existing explicit rejection.
- Existing test fixture that repeated identical timestamps was corrected to use shifted timestamps.

Tests:
- `test_feature_repository_rejects_duplicate_entry_timestamp`
- `test_causal_aggregation_rejects_duplicate_source_timestamp`

**Conclusion: PASS.**

## 6. S008 metric change explanation

No metric formula changed. The only S008 numerical changes came from **two actual ambiguous gap fills**, one per pair, that were previously overwritten to −1R:

| Run | Metric | Before | After |
|---|---|---:|---:|
| S008 EURUSD | profit factor | 0.4323941185 | 0.4321830921 |
| S008 EURUSD | expectancy | −0.4795624652R | −0.4799750065R |
| S008 EURUSD | max drawdown | 297.4898539402R | 297.7398539402R |
| S008 GBPUSD | profit factor | 0.3464678513 | 0.3454329844 |
| S008 GBPUSD | expectancy | −0.5593474299R | −0.5619115325R |
| S008 GBPUSD | max drawdown | 272.4732349678R | 272.4732349678R |

Evidence from the new runs:
- EURUSD ambiguous gap trade `2026-05-05T02:59`: −1.25R (39 ambiguous: 38 stop-first, 1 gap).
- GBPUSD ambiguous gap trade `2026-05-04T20:43`: −2.20R (14 ambiguous: 13 stop-first, 1 gap).

All other S008 signals/trades and metrics are unchanged. This is an explained execution correction, not an unexplained strategy change. Results remain gross/cost-free.

## 7. UI verification

Strategy Lab was exercised in Chromium against the local API after the P0 changes:

```
risk_header=true
first_trade=SHORT 01 Jun 2026, 16:01 ... 1,000 → 1,000 SL -1.000R 1 bar
console_errors=0
```

The trade ledger now shows **Risk planned → realised**; an actual run with the new fields displays identical planned/realised amounts. Evidence: `EVIDENCE/ui-risk.log`, `EVIDENCE/trade-risk.png`.

## 8. Compatibility and migration

- Existing run artifacts remain readable.
- New trade fields are optional; old artifacts show `null`/empty values in the UI.
- No database migration.
- No historical data or run artifact was rewritten.
- `FixedRiskSizer` default behavior is unchanged except that a supplied/registered `contract_size` is now used; default instrument contract size is `1.0`.

## 9. P0 completion gate

| Gate | Status |
|---|---|
| P0.1 sizing/realised risk | PASS |
| P0.2 gap/stop semantics | PASS |
| P0.3 repeated CORE signals | PASS |
| P0.4 duplicate timestamps | PASS |
| Regression tests | 604 PASS |
| Lint | PASS |
| Frontend build | PASS |
| Data unchanged | PASS |
| Before/after documented | PASS |
| No unexplained behavior changes | PASS |

## 10. Remaining known issues (not P0)

- P1: no spread/slippage/commission/swap model; results are gross.
- P1: EURUSD 10 provider gaps remain and are currently surfaced in data quality; no interpolation.
- P1: no pre-backtest validation service integrated in Strategy Lab.
- Account-currency conversion is not modeled; R-multiples only.
- Partial exits, variable execution delay, paper/live are not implemented.
- Existing QA findings not in P0 scope (e.g. multi-symbol curve duplicate timestamps) remain.
