# REX Research Terminal — End-to-End UI QA Report

**Report owner:** Agent 2 — Frontend UI QA  
**Execution date/time (UTC):** 2026-11-03, final main pass 13:36:39–13:37:40; supplementary timeframe pass ~13:39  
**Application:** REX Research Terminal, latest working tree at `/home/user/workspaces/7de05e41da33`  
**Scope:** Browser-level end-to-end UI verification only. No application code, tests, config, datasets, or strategy logic were modified. No credentials were used and no paid data requests were made.

## Verdict

| Metric | Result |
|---|---|
| Test cases executed and passed | 19 |
| Failed | 0 |
| Blocked | 0 |
| Not applicable (UI does not expose the capability) | 2 |
| Confirmed UI defects | **None** |
| Confirmed backend defects | **None** |
| Unhandled console errors / page errors / failed requests | 0 (two browser console resource errors were expected HTTP 400 responses from intentional invalid submissions) |

All PASS results below were verified against live API responses (`/api/overview`, `/api/datasets`, `/api/frame`, `/api/range`, `/api/runs`, `/api/settings/providers`) and real local datasets. No synthetic or fabricated results are included.

## Environment

| Item | Value |
|---|---|
| Frontend | `http://127.0.0.1:16900` (Vite dev server) |
| Backend API | `http://127.0.0.1:16901` (FastAPI) |
| Browser automation | `@playwright/test` 1.64.1 |
| Browser binary | Chromium 131.0.6778.33 (`chromium_headless_shell-1148`) |
| OS / runtime | Linux, Node 20.9.0 |
| Viewports | 1440×900 and 390×844 |
| Test harness | `/tmp/opencode/qa-ui/run-qa.cjs`, `/tmp/opencode/qa-ui/timeframes.cjs`, `/tmp/opencode/qa-ui/error-states.cjs` |

### Commands used

```bash
cd /home/user/workspaces/7de05e41da33
curl -sf --max-time 3 http://127.0.0.1:16900
curl -s --max-time 5 http://127.0.0.1:16901/api/overview
NODE_PATH=/tmp/opencode/pwcheck/node_modules node /tmp/opencode/qa-ui/run-qa.cjs
NODE_PATH=/tmp/opencode/pwcheck/node_modules node /tmp/opencode/qa-ui/timeframes.cjs
NODE_PATH=/tmp/opencode/pwcheck/node_modules node /tmp/opencode/qa-ui/error-states.cjs
```

## Data under test (real)

| Dataset | M1 bars | Coverage | API status | Warnings |
|---|---:|---|---|---|
| EURUSD/M1/2026 | 184,963 | 2026-01-01 13:00 → 2026-06-30 23:59 | warning | 10 unexpected timestamp gaps (beyond FX closures) |
| AUDUSD/M1/2026 | 93,600 | 2026-04-01 00:00 → 2026-06-30 23:59 | ok | none |
| GBPUSD/M1/2026 | 93,600 | 2026-04-01 00:00 → 2026-06-30 23:59 | ok | none |
| USDJPY/M1/2026 | 93,600 | 2026-04-01 00:00 → 2026-06-30 23:59 | ok | none |
| USDCAD/M1/2026 | 93,600 | 2026-04-01 00:00 → 2026-06-30 23:59 | ok | none |

At the start of the final pass, the archive contained 3 runs: the pre-existing `20261030T105941Z_1684076e` plus two S008 runs created during the preliminary pass. That preliminary pass exposed two test-harness locator/case-sensitivity bugs, which were fixed before the final pass; the preliminary raw results are retained at `docs/qa/EVIDENCE/e2e/logs/run1/results.json`.

## Results table

| Test ID | Component | Scenario | Test data | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| E2E-001 | AppShell / navigation | Navigate all six modules; verify h1 and topbar route | 1440×900, default app | All six modules render with correct titles; no console/page/network errors | Overview: “Evidence before conviction.” / RESEARCH OVERVIEW; Market Data: “The record, before the model.” / HISTORICAL DATA; Strategy Lab: “Ask a falsifiable question.” / STRATEGY LAB; Run Archive: “Every result leaves a trace.” / RUN ARCHIVE; Help & Handbook: “Learn the language before trusting the number.” / HELP & HANDBOOK; System: “Precision includes limits.” / SYSTEM & LIMITS. Console errors 0, page errors 0, failed requests 0. | PASS | `EVIDENCE/e2e/screens/1440-*.png`; `EVIDENCE/e2e/logs/console.json`, `network-failures.json` |
| E2E-001b | AppShell / document title | Browser tab title across modules | All modules | Stable product title | `document.title = "REX — Research Terminal"` for every module | PASS | In-page assertion; `EVIDENCE/e2e/screens/1440-*.png` |
| E2E-002 | Overview | Cross-check metrics and lists against GET /api/overview | State at final-pass start | Instruments 8, Datasets 5, Strategies 3, Recent runs 3; dataset rows 5; recent-run rows 3; warning text matches API | UI: Instruments 8; Datasets 5; Strategies 3 (“2 trade-simulated”); Recent runs 3; dataset rows 5; recent-run rows 3. API: instruments 8, datasets 5, strategies 3, runs 3; warning “EURUSD/M1/2026: 10 unexpected timestamp gaps (beyond FX closures).” matched in UI. | PASS | `EVIDENCE/e2e/screens/1440-overview-data-crosscheck.png`; `EVIDENCE/e2e/logs/api-truth-overview.json` |
| E2E-002b | Overview | Loading state | `/api/overview` delayed 2.5 s via Playwright route | Loading message visible, no crash | “Assembling research state” observed | PASS | `EVIDENCE/e2e/screens/overview-loading-state.png` |
| E2E-002c | Overview | Error state when `/api/overview` fails | Request aborted via Playwright route | Error state with explanatory message | “The research service did not answer” / “Failed to fetch” rendered in the error state; header/nav remained usable | PASS | `EVIDENCE/e2e/screens/overview-error-state.png`; `EVIDENCE/e2e/logs/error-state-text.json` |
| E2E-003 | Market Data | Discover all datasets, select each, compare metadata/bar counts/date ranges, warnings, chart | 5 real datasets | 5 rows; every selection matches API bar count and coverage; EURUSD warning visible; chart canvas rendered | 5 dataset rows. AUDUSD 93,600; EURUSD 184,963; GBPUSD 93,600; USDCAD 93,600; USDJPY 93,600 — all UI values matched API. First/last bar text matched API coverage for all five. EURUSD showed warning “10 unexpected timestamp gaps (beyond FX closures).” 7 chart canvases rendered (price chart + chart internals). | PASS | `EVIDENCE/e2e/screens/1440-data.png`, `1440-data-EURUSD.png`; `EVIDENCE/e2e/logs/api-truth-datasets.json` |
| E2E-003b | Market Data | M5/M15/H1/H4 selection availability | Market Data page | UI exposes timeframe selection if supported | Market Data page exposes no timeframe selector (M1 source is shown read-only). Backend derived frames are available: M5 18,720; M15 6,240; H1 1,560; H4 403. | NOT APPLICABLE | `EVIDENCE/e2e/results.json`; source inspection `frontend/src/pages/DataPage.tsx` |
| E2E-003c | Strategy Lab / timeframe | Select M5/M15/H1/H4 derived timeframes in the UI | AUDUSD/M1/2026; Strategy Lab selector | Selector offers M1/M5/M15/H1/H4; frame facts and range update; totals match `/api/frame` | Options exactly `M1, M5, M15, H1, H4`. UI frame totals matched API: M5 18,720 (range 6,360 M5 bars); M15 6,240 (2,120); H1 1,560 (530); H4 403 (137). | PASS | `EVIDENCE/e2e/screens/1440-research-timeframe-H4.png`; `EVIDENCE/e2e/logs/timeframe-checks.json` |
| E2E-004 | Strategy Lab | Valid S008 run on EURUSD with a real date range | EURUSD/M1/2026, M1, 2026-06-01→2026-06-30, S008 defaults (lookback 10, min_wick_ratio 0.6, tolerance 0) | Range validates; run completes; UI metrics match archived run; warnings shown | Range summary: 31,680 M1 bars, 4 gaps, 01 Jan 2026 → 30 Jun 2026 (API bar_count 31,680, valid true). Result: signals 1,387; closed trades 1,310; win rate 11.8%; expectancy −0.652R; profit factor 0.26; max drawdown 853.75R; ambiguous exits 22; avg hold 3.0 bars. UI matched archived run `20261103T133655Z_0d7426ea` (API win_rate 11.83206106870229, expectancy −0.6517210786489162, PF 0.2618383521235236, max DD 853.7546130300801, ambiguous 22, avg hold 2.9625954198473283, 4 warnings). Warnings displayed: costs not applied; R-multiples/no compounding; 22 ambiguous intrabar exits scored at −1R; 4 timestamp gaps larger than one M1 bar. | PASS | `EVIDENCE/e2e/screens/1440-research-s008-result.png`; `EVIDENCE/e2e/logs/api-runs-after.json` |
| E2E-004b | Strategy Lab | Deterministic repeat of identical S008 configuration | Same dataset/range/parameters submitted twice | Two distinct run IDs with identical metrics | Run A `20261103T133657Z_5249e0f7` and Run B `20261103T133655Z_0d7426ea` are distinct IDs but have identical metrics: signals 1,387; trades 1,310; wins 155; losses 1,155; win rate 11.83206106870229; PF 0.2618383521235236; expectancy −0.6517210786489162; max DD 853.7546130300801; ambiguous 22; avg hold 2.9625954198473283. UI repeated the same displayed values. | PASS | `EVIDENCE/e2e/logs/api-runs-after.json` |
| E2E-005 | Missing configuration workflow | AUDUSD + S002 (requires static zones, none configured) | AUDUSD/M1/2026, M1, 2026-06-01→2026-06-30, S002 defaults | Understandable no-zone error, no crash, HTTP 400 | UI range 31,680 bars, 4 gaps. POST `/api/backtests` returned HTTP 400 with body `{"detail":"No zone book is configured for AUDUSD in config/zones.json"}`. UI inline error displayed exactly “No zone book is configured for AUDUSD in config/zones.json”; page remained rendered. | PASS | `EVIDENCE/e2e/screens/research-AUDUSD-S002-no-zones.png`; `EVIDENCE/e2e/logs/api-errors.json` |
| E2E-006 | Run Archive | Open generated run; compare metrics to archived JSON | Newest run `20261103T133657Z_5249e0f7` | Row list contains new run; detail metrics match `/api/runs/{id}` | Archive listed 5 runs. Detail showed Trades 1,310, Expectancy −0.652R, Warnings 4; dataset EURUSD/M1/2026; strategy “Liquidity Sweep V1”; API values 1,310 / −0.6517210786489162 / 4 matched. | PASS | `EVIDENCE/e2e/screens/1440-runs-detail.png`; `EVIDENCE/e2e/logs/api-runs-after.json` |
| E2E-006b | Run Archive | Side-by-side comparison | Latest two runs | Two selectors populated; comparison metrics rendered | Run A `20261103T133657Z_5249e0f7`; Run B `20261103T133655Z_0d7426ea`; comparison showed Trades, Win rate, Expectancy, Profit factor, Max drawdown and Signals. | PASS | `EVIDENCE/e2e/screens/1440-runs-detail.png` |
| E2E-006c | Run Archive | Invalid run ID handling | `GET /api/runs/does-not-exist` | HTTP 404 with clear detail; no UI run-ID input | HTTP 404 `{"detail":"Run not found"}`. UI exposes row selection only, so no invalid-ID entry path exists in the UI. | PASS | `EVIDENCE/e2e/logs/api-runs-after.json` |
| E2E-007 | System / provider credentials | Save, persist, update, delete dummy key; masking and non-exposure | `ui-dummy-key-1234`, then `ui-dummy-key-5678` (no real key) | Masked hints; key not in DOM/responses/storage; reload persists; delete returns to environment; vault empty | Save: 200, feedback “Twelve Data key stored server-side.”, masked key `1234`, source `stored`, input cleared. Reload persisted hint `1234` with no input value. Update: 200, hint `5678`. Delete: 200, hint returned to environment-masked `cdf7`, source `environment`. Full keys absent from DOM, PUT/DELETE response bodies, localStorage and sessionStorage. `data/provider_keys.json` ended as `{"providers": {},"version": 1}`. | PASS | `EVIDENCE/e2e/screens/system-key-saved.png`, `system-key-updated.png`, `system-key-removed.png`; `EVIDENCE/e2e/logs/api-providers-after.json` |
| E2E-008 | Help & Handbook | Categories, search, related links, glossary, all article bodies | 71 articles; search “slippage”; empty search; all articles | Counts match; search/related/glossary work; no broken/missing content | Category counts matched rendered lists: All 71; Getting Started 8; Trading Fundamentals 8; Technical Analysis 8; Risk Management 9; Backtesting & Statistics 18; REX Research Engine 11; Troubleshooting 9; Glossary 20. Search “slippage” returned 4 results; first opened “Running a backtest” with 3 related links; clicking related navigated to “Reading a result”. No-result state displayed for “zzzznotfound”. Glossary opened article “Bid, ask and spread”. All 71 articles rendered a title, ≥5 sections, and substantial body text; 0 broken articles. | PASS | `EVIDENCE/e2e/screens/1440-handbook.png`, `handbook-search-related.png`, `handbook-no-results.png`; `EVIDENCE/e2e/logs/handbook-article-checks.json` |
| E2E-009 | AppShell / responsive | No horizontal overflow; navigation usable at desktop and mobile widths | 1440×900 and 390×844; all six modules | `scrollWidth <= viewport + 1`; six nav items visible/clickable | For all 12 viewport/module combinations, document and body scrollWidth equaled the viewport width (1440 or 390); 0 overflow rows. Six nav items were present; Playwright clicked every item at 390 px (the mobile nav scrolls horizontally as designed). | PASS | `EVIDENCE/e2e/screens/responsive-*.png` |
| E2E-010a | Market Data / download modal | Malformed date ranges and disabled submit | Local-only validation; no download request | Each case shows inline error and disabled Download | End before start: “Start date must be before end date.” (disabled). 181-day window: “UI downloads are limited to 31 days per request.” (disabled). Future end: “End date cannot be in the future.” (disabled). Missing start: “Choose both a start and end date.” (disabled). No download request was sent. | PASS | `EVIDENCE/e2e/screens/data-download-validation.png` |
| E2E-010b | Strategy Lab / validation | Bad date range, out-of-range parameter, invalid risk fraction | EURUSD June 2026; lookback 1; risk fraction 0.5 | Inline validation; run disabled for invalid range; backend rejects parameter; risk fraction rejected client-side | Bad range: “Start date is after the end date. The selected range contains no bars.”; Run button disabled. Lookback 1: POST `/api/backtests` HTTP 400 `{"detail":"lookback must be >= 2"}` and UI showed same error. Risk fraction 0.5: “Risk fraction must be between 0 and 0.1.” | PASS | `EVIDENCE/e2e/screens/research-bad-date-range.png`, `research-bad-parameter.png`, `research-bad-risk-fraction.png` |
| E2E-010c | Strategy Lab / validation | Missing dataset or strategy selection | UI selects are always populated | Validation for missing selection if reachable | NOT APPLICABLE — both selects default to the first available dataset/strategy and expose no empty option. | NOT APPLICABLE | Source inspection `frontend/src/pages/ResearchPage.tsx` |
| E2E-010d | Market Data | Network failure on `/api/datasets` | Request aborted via Playwright route | Error banner/state shown; no crash | Error state “The research service did not answer” / “Failed to fetch” displayed; page header remained. | PASS | `EVIDENCE/e2e/screens/data-error-state.png`; `EVIDENCE/e2e/logs/error-state-text.json` |

## Key observations

### Overview and navigation
- The six module titles and topbar route labels are internally consistent. `document.title` is intentionally the global product title (`REX — Research Terminal`) and does not change per module; this is a global-title design, not a broken page title.
- On the final-pass start state, Overview matched the API exactly: 8 instruments, 5 datasets, 3 strategies, 3 runs, 5 dataset rows, 3 recent-run rows.
- Both the loading state and the API-failure state are user-visible and understandable.

### Market Data
- All five stored datasets are discoverable and selectable. UI bar counts and first/last bar timestamps matched API metadata for every dataset.
- EURUSD correctly surfaces its single warning and “warning” state; the other four are “Verified”.
- The price chart renders (7 canvases) and is populated from real M1 bars.
- The Market Data page does not expose a timeframe selector; derived timeframe selection is exercised in Strategy Lab instead (E2E-003c).
- Download validation prevents malformed/oversized/future requests before any provider call. A real download was deliberately not triggered.

### Strategy Lab
- A real S008 run over EURUSD June 2026 completed and produced an archived artifact whose metrics matched the UI exactly.
- Repeating the identical configuration produced a second, distinct run ID with byte-identical metrics, supporting deterministic replay for this case.
- Invalid date ranges are blocked before submission; invalid parameters are rejected by the backend with a clear 400 and surfaced inline.
- AUDUSD + S002 fails gracefully with the exact no-zone configuration message and does not crash the app.

### Run Archive
- The archive reflects newly generated runs immediately (5 rows after the QA passes).
- Detail metrics match the archived JSON; comparison controls populate from real runs.
- There is no UI input for arbitrary run IDs, so invalid-ID handling was verified at the API boundary (`404 Run not found`).

### System / credentials
- The dummy-key lifecycle worked end to end: save → masked hint `1234`; reload persists; update → `5678`; delete → environment fallback `cdf7`; stored vault empty.
- The submitted secret appears only in the expected PUT request body; it was never found in the DOM, response bodies, `localStorage`, or `sessionStorage`.
- No real provider credential was read, changed, or used.

### Handbook
- All 71 articles rendered complete content; category counts, search, related navigation, glossary, and no-result state all worked. No broken or missing articles were found.

### Responsive
- No horizontal page overflow at either 1440×900 or 390×844. At mobile width the sidebar becomes a horizontally scrollable top bar; all six nav items were still reachable and clickable.

## Confirmed defects

**None.** No reproducible UI defects were found in this run.

For clarity, the following are expected backend-returned errors, not UI defects:

| HTTP | Endpoint | Detail | UI handling |
|---|---|---|---|
| 400 | `POST /api/backtests` | `No zone book is configured for AUDUSD in config/zones.json` | Clear inline error; app remains usable |
| 400 | `POST /api/backtests` | `lookback must be >= 2` | Clear inline error; no run archived |
| 404 | `GET /api/runs/does-not-exist` | `Run not found` | UI does not expose arbitrary-ID lookup; API behaves correctly |

Two browser console entries of type `error` were recorded during E2E-010b and E2E-005. Both are Chromium’s automatic “Failed to load resource: 400 (Bad Request)” log for the intentional invalid submissions; the UI handled those responses with inline messages and no page exception. No unhandled console errors, page errors, or failed network requests occurred during navigation.

## Not run / limitations

| Item | Reason |
|---|---|
| Real provider download | Prohibited from using real provider credentials or triggering paid data requests. Only local download-form validation was exercised. |
| Empty dataset / empty run archive states | Would require deleting or hiding datasets/artifacts; preserving existing data and run artifacts was required. The no-result Handbook empty state was exercised instead. |
| Missing dataset/strategy selection in Strategy Lab | Selects always contain defaults; no empty option exists in the UI. |
| Arbitrary invalid run ID via UI | Run Archive has no free-text run-ID input; the API 404 path was verified directly. |
| Market Data timeframe selection | Not exposed on Market Data. The same derived timeframes were verified through the Strategy Lab selector. |

## Artifacts and side effects

- New real S008 run artifacts created by QA (local data only):
  - `20261103T133520Z_8fb5df13` (preliminary pass)
  - `20261103T133522Z_0dacd4dc` (preliminary pass)
  - `20261103T133655Z_0d7426ea` (final pass)
  - `20261103T133657Z_5249e0f7` (final pass)
- Pre-existing run `20261030T105941Z_1684076e` was preserved untouched.
- The provider key vault was left empty (`data/provider_keys.json` contains `"providers": {}`); the pre-existing environment fallback remains untouched.
- `git status --short` shows only the new `docs/qa/` evidence tree as untracked. No application code, tests, config, datasets, or strategy logic changed.

## Evidence index

All raw evidence is under `docs/qa/EVIDENCE/e2e/`:

- `results.json` — machine-readable result set (21 cases)
- `logs/console.json` — all browser console messages
- `logs/page-errors.json` — uncaught page errors (0)
- `logs/network-failures.json` — failed requests (0)
- `logs/api-calls.json`, `logs/api-errors.json` — API request log and HTTP errors
- `logs/api-truth-*.json` — API snapshots used as truth
- `logs/api-runs-after.json` — run archive snapshot after the test
- `logs/timeframe-checks.json`, `logs/handbook-article-checks.json`, `logs/error-state-text.json`
- `logs/run1/` — retained preliminary-pass evidence (before test-harness correction)
- `screens/` — 36 screenshots covering every module, key results, failures/validation states, and both viewports
