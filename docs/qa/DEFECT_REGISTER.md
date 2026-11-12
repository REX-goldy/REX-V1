# REX QA Defect Register

- **Date:** 2026-11-03
- **Commit:** `95f8aaa998f1ce1539c65777b5dd10ac063cbd34`
- **Total defects:** 15 — **0 Critical, 0 High, 5 Medium, 9 Low, 1 Info**
- **Policy:** a defect is listed only after reproduction or direct code/evidence confirmation. No application logic was changed to fix it during QA.
- **P0 follow-up (2026-11-03):** QA-D-003 (duplicate timestamps), QA-D-005 (CORE close-outside), QA-D-009 (realised risk) and QA-D-010 (ambiguity gap) were fixed and verified in `docs/p0-execution-integrity/`. This register remains the pre-P0 snapshot for the remaining findings.

## Severity summary

| Severity | Count | IDs |
|---|---:|---|
| Critical | 0 | — |
| High | 0 | — |
| Medium | 5 | QA-D-002, QA-D-003, QA-D-005, QA-D-009, QA-D-010 |
| Low | 9 | QA-D-001, QA-D-004, QA-D-006, QA-D-007, QA-D-011, QA-D-012, QA-D-013, QA-D-014, QA-D-015 |
| Info | 1 | QA-D-008 |

---

## QA-D-001 — Unsupported download-symbol message lists only two of seven accepted symbols

- **Severity:** Low
- **Component:** `POST /api/downloads` validation (`server/research_service.py`)
- **Summary:** The API accepts seven UI download symbols but the error text names only EURUSD and GBPUSD.
- **Preconditions:** API reachable; no provider request needed.
- **Reproduction:**
  ```bash
  curl -s -X POST http://127.0.0.1:16901/api/downloads \
    -H 'Content-Type: application/json' \
    -d '{"provider":"dukascopy","symbol":"XXXYYY","timeframe":"M1","start_date":"2025-01-01","end_date":"2025-01-02"}'
  ```
- **Expected:** Error reflects the actual accepted set (`DOWNLOAD_SYMBOLS`) or avoids an incomplete enumeration.
- **Actual:** `400 {"detail":"UI downloads currently support EURUSD and GBPUSD"}` while seven symbols are accepted.
- **Evidence:** `docs/qa/EVIDENCE/api/API-039_download_invalid_symbol.json`; code lines around `server/research_service.py:53-61` and `:1022-1023`.
- **Root cause:** stale user-facing message; confirmed.
- **Recommended resolution:** derive the message from `DOWNLOAD_SYMBOLS` or say “this symbol is not supported by UI downloads.”

## QA-D-002 — EURUSD M1 has 10 unexpected source gaps / 17 missing FX-open minutes

- **Severity:** Medium (data quality; not an application calculation defect)
- **Component:** historical data / provider ingestion
- **Summary:** EURUSD is the only dataset with gaps inside the FX-open session; derived M5/M15/H1/H4 omit the affected buckets.
- **Preconditions:** read-only `data/historical/EURUSD/M1/2026.csv`.
- **Reproduction:** parse CSV; compare consecutive timestamps using `is_fx_market_open_minute_utc`; 10 gaps contain at least one open minute.
- **Expected:** no missing FX-open minutes (or an explicit, documented provider limitation).
- **Actual:** 184,963 bars; 35 raw gaps, 10 unexpected gaps, 17 missing FX-open minutes. Nine short intraday holes plus a weekend-crossing gap `2026-02-06 21:59 → 2026-02-08 22:02` (2,880 closure minutes + 2 open minutes). No interpolation.
- **Evidence:** `docs/qa/EVIDENCE/data/gaps.csv`, `session_gaps.json`, `DATA_VALIDATION_REPORT.md`; README already documents 10 gaps.
- **Root cause:** provider source coverage; confirmed present in the pre-filter raw data and on re-query (prior investigation), not a parser/filter defect.
- **Recommended resolution:** retain the documented warning; do not fabricate bars. If complete EURUSD is required, re-download from a provider/period that covers the missing minutes and record provenance.

## QA-D-003 — Duplicate entry-timestamp bars are silently retained; HTF path fails with an unrelated error

- **Severity:** Medium
- **Component:** `core/features/repository.py::_normalize_bars`, `core/features/timeframes.py`
- **Summary:** Entry-timeframe materialization accepts duplicate timestamps; HTF materialization silently drops the bucket and reports a missing entry timeframe; the canonical resampler correctly rejects duplicates.
- **Preconditions:** real EURUSD bars with one injected duplicate timestamp.
- **Reproduction:** call `FeatureRepository.materialize` with an M1 sequence containing a duplicate; compare with `aggregate_completed_bars` and `resample_bars`.
- **Expected:** explicit duplicate rejection or deterministic de-duplication at every entry point.
- **Actual:** M1 materializes 3 bars with duplicate retained; M15 returns `ValueError: Missing entry timeframe candles: M15...`; direct aggregator emits 0 bars; resampler raises `ResampleError: duplicate source timestamp`.
- **Evidence:** `docs/qa/EVIDENCE/features/FEAT-054_boundary_duplicates.json`.
- **Root cause:** `_normalize_bars` sorts but does not validate duplicate timestamps; confirmed.
- **Recommended resolution:** reject duplicates with a clear error (or document and implement deterministic de-dup) before aggregation. Add regression tests.

## QA-D-004 — Missing `ZoneEngine` is reported as “available with no zones”

- **Severity:** Low
- **Component:** `build_zone_pack` / `MarketStateBuilder._build_zones`
- **Summary:** A repository created with `zone_engine=None` yields `zones.status=available`, `active=[]`, indistinguishable from a genuine empty zone book.
- **Preconditions:** real EURUSD context; `zone_engine=None`.
- **Reproduction:** materialize default packs without a ZoneEngine; build MarketState.
- **Expected:** zones section unavailable/unsupported when the dependency is absent.
- **Actual:** `{"status":"available","active_zones":[],"nearest":null,"inside_zone":false,"reason":null}`.
- **Evidence:** `docs/qa/EVIDENCE/features/FEAT-044_market_state_missing_zone_engine.json`.
- **Root cause:** `ZonePack` has no availability/source flag; empty pack is treated as valid. Confirmed.
- **Recommended resolution:** add explicit availability/source status or mark the section unavailable when no engine is configured.

## QA-D-005 — CORE_ZONE_BREAKOUT emits `CLOSE_OUTSIDE` on every bar for every untouched zone

- **Severity:** Medium (signal semantics; materially inflates signal counts)
- **Component:** `strategies/breakout.py`
- **Summary:** `CLOSE_OUTSIDE` is emitted whenever close is outside a zone, even when the zone was never interacted with; it dominates signal counts.
- **Preconditions:** real EURUSD/GBPUSD data with configured zones.
- **Reproduction:** run CORE_ZONE_BREAKOUT signal study:
  - EURUSD 2026-03-24..25: 21,920 signals, 21,848 `close_outside` (99.7%).
  - GBPUSD 2026-04-01..02: 2,880 signals, 100% `close_outside`; zone never reached (price 1.314–1.366 vs zone 1.260–1.2625).
- **Expected:** a signal should represent a zone interaction or state change; an untouched zone far away should not emit one signal per bar.
- **Actual:** `_detect_close_outside` returns `not zone.contains_price(close)` unconditionally; `_evaluate_zone` emits it each bar.
- **Evidence:** `docs/qa/EVIDENCE/strategy/runs/STRAT-009*`, `STRAT-010*`, `audusd/defects.json`.
- **Root cause:** confirmed strategy semantics/design; changing it alters documented behavior, so it was not changed.
- **Recommended resolution:** require a prior in-zone/break state or drop `CLOSE_OUTSIDE` from actionable signals; clearly label it as context if retained. Requires product authorization because it changes strategy output.

## QA-D-006 — S002 zero-risk retests are silently rejected at the policy boundary

- **Severity:** Low
- **Component:** `execution/factories.py`, `execution/policies.py`, `BacktestRunner` accounting
- **Summary:** When the retest candle closes at its low/high, the S002 factory sets stop == entry; the policy rejects zero risk and the runner only increments a generic boundary counter without a per-setup reason.
- **Preconditions:** real EURUSD S002 run 2026-03-23..27, defaults.
- **Reproduction:** run S002; inspect 65 of 516 signals; `stop_hint == entry_hint`; `planner.plan()` returns `None`.
- **Expected:** a structural non-zero stop or an explicit per-setup rejection reason visible to research users.
- **Actual:** 65 policy-boundary rejections; only 7 invalid-entry rejects have a termination record; 65 are silent counters.
- **Evidence:** `docs/qa/EVIDENCE/strategy/runs/STRAT-007*`, `STRAT-033*`, `S002_zero_risk_rejects.json`.
- **Root cause:** stop construction uses the retest bar extreme; policy rejects `risk_distance <= 1e-12`; confirmed.
- **Recommended resolution:** use the broken level/ATR as a fallback stop or record a structured rejection reason; add tests.

## QA-D-007 — UI cannot pre-validate zone availability for zone-requiring strategies

- **Severity:** Low (UX/integration gap; validation itself is correct)
- **Component:** Strategy Lab ↔ API
- **Summary:** AUDUSD + S002/CORE reaches `POST /api/backtests` and returns a 400; there is no API/UI zone catalog to disable or warn beforehand.
- **Preconditions:** AUDUSD dataset; no AUDUSD zone book.
- **Reproduction:** select AUDUSD + S002 in Strategy Lab; press Run.
- **Expected:** pre-submit warning/disable for known incompatible dataset+strategy, or a zone availability endpoint.
- **Actual:** clear backend error appears after submit; app remains usable. The error is correct, not a crash.
- **Evidence:** `docs/qa/EVIDENCE/strategy/audusd/STRAT-040_ui_path.json`; E2E-006.
- **Root cause:** no zone-availability API; confirmed.
- **Recommended resolution:** expose zone-book symbols/strategy requirements and gate the form. Do not invent AUDUSD zones.

## QA-D-008 — `BacktestRunner` defaults to `SweepTradeSetupFactory` for any strategy

- **Severity:** Info (API footgun)
- **Component:** `backtests/backtest_runner.py`
- **Summary:** With `simulate_trades=True` and no explicit factory, the runner uses the sweep factory for any strategy; non-sweep signals are silently rejected.
- **Preconditions:** direct runner call, e.g. S002, no `setup_factory`.
- **Reproduction:** `BacktestRunner().run(S002_BreakoutRetest(zone_book), bars, simulate_trades=True)`.
- **Expected:** require an explicit/inferred strategy-specific factory or fail clearly.
- **Actual:** 0 trades; signals counted as boundary rejects. The service avoids this by passing the correct factory, so HTTP behavior is not affected.
- **Evidence:** `docs/qa/EVIDENCE/strategy/audusd/defects.json`.
- **Root cause:** default factory in runner; confirmed.
- **Recommended resolution:** require a factory when simulating or infer from strategy; document in the public API.

## QA-D-009 — Realised position risk does not match planned risk

- **Severity:** Medium
- **Component:** `execution/sizers.py`, `backtests/trade_simulator.py`
- **Summary:** Sizing uses the planned entry (signal close) and stop, but fills at the next candle open; size/risk are not recalculated, so realised risk differs from the fixed 1% target.
- **Preconditions:** real S008 EURUSD/GBPUSD runs 2026-05-01..15.
- **Reproduction:** compare `plan.position_size * |actual_entry - stop|` with `plan.risk_amount` per trade.
- **Expected:** realised currency risk equals planned `equity × risk_fraction` (1,000 on 100k/1%).
- **Actual:** EURUSD 543/606 differ (max 5.50×); GBPUSD 441/468 differ (max 6.25×). R-multiple metrics are normalized by actual risk and therefore remain internally consistent, but the fixed-risk contract is violated.
- **Evidence:** `docs/qa/EVIDENCE/backtest/valid_runs_analysis.json` → `lifecycle.risk`.
- **Root cause:** no re-size at fill; confirmed.
- **Recommended resolution:** re-size at fill or explicitly define risk as approximate. Fix before currency-risk, portfolio, paper or live claims.

## QA-D-010 — AMBIGUITY can understate a gap loss

- **Severity:** Medium
- **Component:** `backtests/trade_simulator.py` / fill model
- **Summary:** If a bar opens through SL while also spanning TP, the fill is at the gapped open but PnL is overwritten to −1R, understating a worse-than-1R loss.
- **Preconditions:** labelled synthetic OHLC: LONG entry 1.1500, SL 1.1400, TP 1.1700; next bar opens 1.1000 and spans 1.0900–1.1800.
- **Reproduction:** run the probe in `ambiguity_gap_probe.json`.
- **Expected:** record the actual adverse fill or at least the worse of −1R and the gap formula.
- **Actual:** exit price 1.1000; raw −5.0R; recorded −1.0R.
- **Evidence:** `docs/qa/EVIDENCE/backtest/ambiguity_gap_probe.json`.
- **Root cause:** unconditional `AMBIGUITY → -1R` in simulator; confirmed.
- **Recommended resolution:** use the actual fill R for gap-through cases; keep the conservative ambiguity rule only when fill is inside the bar. Add regression test.

## QA-D-011 — Multi-symbol equity curve drops trades with duplicate exit timestamps

- **Severity:** Low
- **Component:** `server/research_service.py::_equity_curve`
- **Summary:** Curve points are keyed by epoch seconds; multiple trades exiting on the same second overwrite one another.
- **Preconditions:** combined actual EURUSD + GBPUSD trades (1,074).
- **Reproduction:** replicate `_equity_curve` with duplicate exits.
- **Expected:** one lossless point per trade (or explicitly aggregated).
- **Actual:** 55 duplicate exit timestamps; 1,019 curve points instead of 1,074. Final R/max DD happened to match in this sample.
- **Evidence:** `docs/qa/EVIDENCE/backtest/valid_runs_analysis.json` → `multi_symbol_curve_probe`.
- **Root cause:** dict keyed by int timestamp; confirmed.
- **Recommended resolution:** aggregate explicitly and document, or include trade id/sequence in curve points.

## QA-D-012 — `max_hold_candles=1` closes after two candles

- **Severity:** Low
- **Component:** `TradeSimulator`
- **Summary:** With a one-candle max hold, timeout is checked on the following bar, producing a two-candle holding duration.
- **Preconditions:** synthetic no-exit fixture; `max_hold_candles=1`.
- **Reproduction:** `edge_case_analysis.json → open_timeout_max_hold_1`.
- **Expected:** timeout after one candle.
- **Actual:** closed after two candles; `holding_duration_candles=2`. Default 60 unaffected.
- **Evidence:** `docs/qa/EVIDENCE/backtest/edge_case_analysis.json`.
- **Root cause:** entry-bar timeout not evaluated; confirmed.
- **Recommended resolution:** define inclusive semantics and fix the check; add boundary tests.

## QA-D-013 — Signal-only reconciliation looks like an unexplained imbalance

- **Severity:** Low
- **Component:** `BacktestResult.reconcile_signals()`, server run payload
- **Summary:** In signal-study mode (`simulate_trades=False`), reconciliation reports generated signals vs zero execution counters as a large difference.
- **Preconditions:** CORE_ZONE_BREAKOUT signal-only server run, 56,818 signals.
- **Reproduction:** `core_signal_only_server_run.json`.
- **Expected:** reconciliation marked N/A/null for signal-only runs, or execution counters explained.
- **Actual:** `difference=56818` with `accepted=ignored=rejected=0`.
- **Evidence:** `docs/qa/EVIDENCE/backtest/core_signal_only_server_run.json`.
- **Root cause:** signal-only mode does not populate execution counters; confirmed.
- **Recommended resolution:** expose `null`/`not_applicable` for execution reconciliation in signal-only mode.

## QA-D-014 — `houseofapps_creds.env` is ignored only by `.git/info/exclude`

- **Severity:** Low
- **Component:** repository configuration
- **Summary:** The local credential file is not tracked and is currently ignored, but the rule exists only in local `.git/info/exclude`, not in tracked `.gitignore`.
- **Preconditions:** clean checkout clone.
- **Reproduction:** `git check-ignore -v houseofapps_creds.env`; `git ls-files houseofapps_creds.env`.
- **Expected:** tracked `.gitignore` rule for the credential filename (or `*.env`).
- **Actual:** `.git/info/exclude:15` only; no tracked rule. File is untracked.
- **Evidence:** `docs/qa/EVIDENCE/security/finding-01-gitignore-houseofapps.txt`.
- **Root cause:** local-only ignore; confirmed.
- **Recommended resolution:** add `houseofapps_creds.env` (or a safe pattern) to `.gitignore`; do not add the file.

## QA-D-015 — Documentation still references old ports 8000/5173

- **Severity:** Low
- **Component:** `README.md`, `PROJECT_CONTEXT.md`
- **Summary:** The current runtime uses frontend 16900 and API 16901, but documentation still instructs 5173/8000.
- **Preconditions:** current HEAD.
- **Reproduction:** `grep -n "8000\|5173" README.md PROJECT_CONTEXT.md`.
- **Expected:** documentation matches current reserved ports and proxy.
- **Actual:** README lines 64–75 and PROJECT_CONTEXT line 174 reference 8000/5173; the System page and delivery config use 16900/16901.
- **Evidence:** `docs/qa/EVIDENCE/lead/docs-port-check.txt`.
- **Root cause:** stale documentation; confirmed.
- **Recommended resolution:** update README/PROJECT_CONTEXT to 16900/16901 and describe the key vault behavior.

---

## Defect-to-test map

| Defect | Failing/confirming test | Area report |
|---|---|---|
| QA-D-001 | API-039 | `API_TEST_REPORT.md` |
| QA-D-002 | DATA-005 | `DATA_VALIDATION_REPORT.md` |
| QA-D-003 | FEAT-054 | `FEATURE_VALIDATION_REPORT.md` |
| QA-D-004 | FEAT-044 | `FEATURE_VALIDATION_REPORT.md` |
| QA-D-005 | STRAT-009/010 | `STRATEGY_VALIDATION_REPORT.md` |
| QA-D-006 | STRAT-007/033 | `STRATEGY_VALIDATION_REPORT.md` |
| QA-D-007 | STRAT-040 / E2E-006 | `STRATEGY_VALIDATION_REPORT.md`, `E2E_TEST_REPORT.md` |
| QA-D-008 | STRAT defects | `STRATEGY_VALIDATION_REPORT.md` |
| QA-D-009 | BT-006 | `BACKTEST_VALIDATION_REPORT.md` |
| QA-D-010 | BT-016 | `BACKTEST_VALIDATION_REPORT.md` |
| QA-D-011 | BT-021 | `BACKTEST_VALIDATION_REPORT.md` |
| QA-D-012 | BT-014 | `BACKTEST_VALIDATION_REPORT.md` |
| QA-D-013 | BT-022 | `BACKTEST_VALIDATION_REPORT.md` |
| QA-D-014 | SEC-031 | `SECURITY_TEST_REPORT.md` |
| QA-D-015 | QA Lead review | `EVIDENCE/lead/docs-port-check.txt` |
