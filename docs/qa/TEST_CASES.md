# REX QA Test Case Catalog

- **Date:** 2026-11-03
- **Commit:** `95f8aaa998f1ce1539c65777b5dd10ac063cbd34`
- **Total documented checks:** 305 (284 PASS, 9 FAIL, 5 BLOCKED, 2 NOT TESTED, 5 NOT APPLICABLE)
- **Full per-case matrices:** `E2E_TEST_REPORT.md`, `API_TEST_REPORT.md`, `DATA_VALIDATION_REPORT.md`, `FEATURE_VALIDATION_REPORT.md`, `STRATEGY_VALIDATION_REPORT.md`, `BACKTEST_VALIDATION_REPORT.md`, `SECURITY_TEST_REPORT.md`.
- **Machine-readable evidence:** `docs/qa/EVIDENCE/`.

This catalog is the QA Lead index. Each area report carries the complete test-ID table with test data, expected result, actual result, status and evidence path. Test IDs are stable; no duplicate IDs are used across areas. Test steps are the scenario steps described in the area reports; reproductions are included for every confirmed defect.

## 1. Test inventory by area

| Area | IDs | Range | Executed | Pass | Fail | Blocked | N/T | N/A | Report |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| Frontend / E2E | E2E-001…E2E-010d | 21 | 19 | 19 | 0 | 0 | 0 | 2 | `E2E_TEST_REPORT.md` |
| API | API-001…API-051 | 51 | 51 | 51 | 0 | 0 | 0 | 0 | `API_TEST_REPORT.md` |
| Historical data | DATA-001…DATA-075 | 75 | 75 | 74 | 1 | 0 | 0 | 0 | `DATA_VALIDATION_REPORT.md` |
| Features / structure | FEAT-001…FEAT-058 | 59 | 56 | 54 | 2 | 2 | 1 | 0 | `FEATURE_VALIDATION_REPORT.md` |
| Strategies | STRAT-001…STRAT-045 | 45 | 41 | 41 | 0 | 2 | 0 | 2 | `STRATEGY_VALIDATION_REPORT.md` |
| Backtesting / execution | BT-001…BT-023 | 23 | 23 | 18 | 5 | 0 | 0 | 0 | `BACKTEST_VALIDATION_REPORT.md` |
| Security / config | SEC-001…SEC-031 | 31 | 28 | 27 | 1 | 1 | 1 | 1 | `SECURITY_TEST_REPORT.md` |

## 2. Critical and representative cases

The following cases are the highest-value evidence. They are not the whole suite; the complete matrices are in the area reports.

### E2E — browser workflows

| ID | Component | Objective and steps | Preconditions / data | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| E2E-001 | Navigation | Open each of six modules; verify heading/topbar; collect console/page/network errors | Local UI 16900, API 16901, 1440×900 | Six modules render, no uncaught errors | All six correct; 0 page errors; 0 failed requests | PASS | `EVIDENCE/e2e/logs/console.json`, screens |
| E2E-003 | Market Data | Select each dataset; compare rows/coverage to API; inspect chart | Five real datasets | UI = API = stored metadata; chart populated | 5/5 match; 7 canvases; EURUSD warning shown | PASS | `screens/1440-data.png`, API truth logs |
| E2E-003c | Strategy Lab | Select M5/M15/H1/H4 derived timeframe | EURUSD real M1 | Derived frame loads without error | Derived selector works; counts consistent | PASS | E2E report, `logs/timeframe-checks.json` |
| E2E-005 | Strategy Lab | Run S008 EURUSD June 2026; inspect metrics/trades; repeat | Real data, defaults | Valid run, archived artifact, deterministic repeat | 200; metrics/UI match; repeat byte-identical metrics | PASS | `screens/1440-research-s008-result.png`, run logs |
| E2E-006 | Missing configuration | Select AUDUSD + S002 and run | AUDUSD data, no zone book | Understandable 400; no crash | 400 `No zone book is configured for AUDUSD…`; inline error | PASS | `screens/research-AUDUSD-S002-no-zones.png` |
| E2E-008 | System keys | Save dummy, reload, update, delete | Empty vault; dummy keys only | Masked display; no full key in DOM/network/storage; delete restores env | Masked `1234`/`5678`; secret absent from DOM/storage/responses; vault empty | PASS | `screens/system-key-saved.png, screens/system-key-updated.png, screens/system-key-removed.png`, E2E logs |
| E2E-009 | Responsive | Navigate all modules at 1440×900 and 390×844 | Playwright | No horizontal overflow; nav usable | 12/12 combinations no overflow; nav reachable | PASS | `screens/responsive-*.png` |
| E2E-010d | Error state | Abort `/api/datasets` request | Playwright route abort | Visible error state, no crash | Error state displayed; header retained | PASS | `screens/data-error-state.png` |

### API — routes and validation

| ID | Component | Objective and steps | Test data | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| API-005 | Overview | GET overview; cross-check 5 datasets/strategy IDs | Live API | 5 datasets, exact counts, 3 strategies | Match | PASS | `API-005_overview.json` |
| API-023 | Backtests | POST AUDUSD + S002 | AUDUSD M1 | 400 missing zone book; no invented zone | 400 exact message | PASS | `API-023_missing_zone_book.json` |
| API-026 | Backtests | POST valid S008 EURUSD | 2026-03-02..06, defaults | 200, full schema, reconciliation 0 | 51 signals/51 trades; WR 35.29%; PF 1.0909 | PASS | `API-026_bt_eurusd.json` |
| API-031 | Provider vault | PUT dummy, verify masked response/store mode | Isolated key file | 200, hint last 4, no full key, 0600 | Match | PASS | `API-031_provider_put.json` |
| API-039 | Downloads | POST unsupported symbol | `XXXYYY` | 400; accurate accepted-symbol message | 400 but message says only EURUSD/GBPUSD (D-001) | PASS (defect D-001) | `API-039_download_invalid_symbol.json` |
| API-043 | Downloads | POST Twelve Data without key | Isolated no-key instance | 503 before network | 503; 3.5 ms; no network | PASS | `API-043_download_missing_key.json` |

### DATA — historical integrity

| ID | Component | Objective and steps | Test data | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| DATA-001…004 | EURUSD M1 | Inventory, ordering, OHLC, parser | Real CSV | Count/order/OHLC valid | 184,963; 0 dup/order/invalid; 0 closure bars | PASS | `inventory.json`, `timestamp_integrity.json` |
| DATA-005 | EURUSD completeness | Gap audit | Real M1 | 0 unexpected gaps | 10 gaps / 17 missing FX-open minutes (documented) | FAIL | `gaps.csv`, `session_gaps.json` |
| DATA-008 | Derived M5 | Independent aggregate vs resampler | EURUSD M1 | OHLC match, complete buckets only | 36,987/36,987; 0 mismatch; 9 incomplete skipped | PASS | `resampled_summary.json` |
| DATA-012/014 | Derived H1/H4 | Same for H1/H4 | EURUSD | No future bars; OHLC match | 3,079 / 792; 0 mismatch | PASS | `resampled_summary.json` |
| DATA-015 | Causal H4 | `aggregate_completed_bars` vs resampler | EURUSD as-of | Documented FX-boundary differences; no future leak | Causal 741, resampler 792; 51 resampler-only closure buckets; 0 OHLC mismatch | PASS | `causal_htf.json` |
| DATA-016…030 | GBPUSD | Full M1 + derived validation | Real M1 | Same integrity | 93,600; 0 unexpected; 20/20 derived pass | PASS | data evidence |
| DATA-031…075 | AUDUSD/USDJPY/USDCAD | Full M1 + derived validation | Real M1 | Same integrity | All counts 93,600; 0 unexpected; derived pass | PASS | data evidence |

### FEAT — features and structure

| ID | Component | Objective and steps | Test data | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| FEAT-002/003 | FeatureRepository | Materialize real context; repeat | EURUSD/GBPUSD M1 | Valid packs; deterministic | PASS | PASS | `FEAT-002*`, `FEAT-003*` |
| FEAT-046 | MTF | Compare causal aggregator and resampler | EURUSD week | Intraday OHLC match; documented closure differences | M15/M30/H1 exact; H4/D1 boundary differences only | PASS | `FEAT-046*` |
| FEAT-048 | Causality | Truncate/mutate future bars | EURUSD week | No effect on past outputs | Equal; no leak | PASS | `FEAT-048*` |
| FEAT-044 | MarketState/ZoneEngine | Build with `zone_engine=None` | Real context | zones unavailable | `available` with empty zones (D-004) | FAIL | `FEAT-044*` |
| FEAT-054 | FeatureRepository | Inject duplicate timestamp | Real EURUSD | Explicit rejection/consistent de-dup | M1 retains duplicate; M15 silently drops; ambiguous error (D-003) | FAIL | `FEAT-054*` |
| FEAT-019 | CHoCH | Search implementation | Static | Implemented if claimed | No CHoCH; BOS only | BLOCKED | `FEAT-001_inventory.json` |
| FEAT-026 | Liquidity | Project view | Real context | Implemented if claimed | Raises unsupported; no pack | BLOCKED | `FEAT-004*` |

### STRAT — strategies

| ID | Strategy | Objective and steps | Test data | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| STRAT-004 | Registry | Discover strategies | Code | Only actual strategies | CORE, S002, S008; no extras | PASS | `inventory.json` |
| STRAT-005 | S008 | Valid EURUSD run, both directions | 2026-05-04..08 | Complete, counts reconcile | 303 signals / 272 trades; both directions | PASS | `runs/STRAT-005*` |
| STRAT-007 | S002 | Valid EURUSD with 8 zones | 2026-03-23..27 | Complete, counts reconcile | 516 signals / 223 trades; 65 policy rejects | PASS | `runs/STRAT-007*` |
| STRAT-009 | CORE | Signal study EURUSD | 2026-03-24..25 | No trades, signals only | 21,920 signals / 0 trades | PASS | `runs/STRAT-009*` |
| STRAT-017 | S002 | Missing AUDUSD zones | AUDUSD | Explicit error, no invented zones | Exact error; 400 over HTTP | PASS | `invalid/STRAT-017*` |
| STRAT-030/031/032 | All | Determinism | Real data | Identical repeat, no input mutation | All true | PASS | `determinism/*` |
| STRAT-039 | AUDUSD | HTTP reproduction S002/CORE/S008 | Temporary API | Zone-required 400; S008 200 | 400/400/200; S008 46/40 | PASS | `audusd/STRAT-039*` |

### BT — backtest/execution

| ID | Component | Objective and steps | Test data | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| BT-002 | S008 EURUSD | Valid run + metrics | 15,720 M1 | Full simulation | 657 signals / 606 trades; WR 18.48%; PF 0.4324; exp −0.4796R | PASS | `EURUSD_*server_run.json` |
| BT-003 | S008 GBPUSD | Valid run + metrics | 15,720 M1 | Full simulation | 500 signals / 468 trades; WR 15.17%; PF 0.3465; exp −0.5593R | PASS | `GBPUSD_*server_run.json` |
| BT-004 | Metrics | Independent recalculation | Both runs | All metrics match | Match to 1e-12 | PASS | `valid_runs_analysis.json` |
| BT-006 | Sizing | Compare planned vs realised risk | Both runs | 1% risk preserved | 543/606 and 441/468 differ; max 5.5×/6.25× (D-009) | FAIL | `valid_runs_analysis.json` |
| BT-008 | Reproducibility | Repeat identical config | Both runs | Byte-stable | Identical fingerprints | PASS | `valid_runs_analysis.json` |
| BT-016 | Ambiguity gap | Gap through SL while TP touched | Synthetic labelled | Loss at actual fill | Raw −5R recorded −1R (D-010) | FAIL | `ambiguity_gap_probe.json` |
| BT-021 | Multi-symbol curve | Duplicate exit timestamps | Combined actual data | One point per trade | 55/1,074 dropped (D-011) | FAIL | `valid_runs_analysis.json` |
| BT-022 | Signal-only reconciliation | CORE signal-only server run | Real data | Reconciliation N/A/null | Reports difference 56,818 (D-013) | FAIL | `core_signal_only_server_run.json` |

### SEC — security/config

| ID | Component | Objective and steps | Test data | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| SEC-009 | Masking | 4/5/long key hints | Dummy keys | Never full key | `••••`, `bcde`, `1234` | PASS | `sec-009-hints.txt` |
| SEC-010 | API | PUT/GET/DELETE and inspect bodies | Isolated store | No full key/no api_key | Match | PASS | `sec-010-http-responses.txt` |
| SEC-013 | CORS | Preflight and actual headers | Local API | Wildcard, no credentials | Match | PASS | `sec-013-*` |
| SEC-018/019 | Redaction | Provider error contains dummy key | Offline injected errors | Secret replaced with `***` | Match | PASS | `sec-018*`, `sec-019*` |
| SEC-024 | Frontend | Password input/state/bundle scan | Source + build | No storage/console/full key | Match | PASS | `sec-024-frontend-security.txt` |
| SEC-031 | Repo hygiene | Check ignore for `houseofapps_creds.env` | Git | Tracked `.gitignore` coverage | Local exclude only (D-014) | FAIL | `finding-01-gitignore-houseofapps.txt` |

## 3. Case design notes

- **Normal and abnormal workflows:** valid runs; invalid dates/parameters; unknown datasets/strategies; missing zones; network-abort UI; empty/no-signal ranges; invalid run IDs; malformed/oversized keys; corrupt credential store.
- **Causality:** future-bar mutation and truncated-history comparisons, as-of checks, and no-future-bucket checks.
- **Real-data first:** every strategy/backtest/feature check used stored M1 data unless explicitly labelled synthetic. Synthetic cases are marked in the area reports.
- **No fabrication:** no prices, signals, trades, counts or metrics were synthesized for real-data results.
- **Evidence:** each area report's evidence paths resolve to files under `docs/qa/EVIDENCE/`; QA Lead re-ran the regression/lint/build and key API reproductions.
