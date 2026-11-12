# REX Quant Research Terminal — QA Assessment

- **Assessment date:** 2026-11-03 (UTC)
- **Repository:** `/home/user/workspaces/7de05e41da33`
- **Commit under test:** `95f8aaa998f1ce1539c65777b5dd10ac063cbd34`
- **Scope:** current implementation, local UI/API, stored M1 datasets, feature/strategy/backtest/security paths
- **Mode:** read-only QA; no deploy, commit, push, strategy change, data change, or config change made to make tests pass.
- **QA Lead:** Agent 1. Specialized evidence: E2E, API, data, features, strategies, backtest/execution, security.

---

## Executive Summary

REX is **functionally coherent and substantially test-covered**, but its **execution-layer assumptions are not yet trustworthy enough for paper/live use**. The core research arithmetic is strong: all reported backtest metrics matched independent recomputation to `1e-12`, the five historical datasets are internally consistent apart from known provider gaps, the API/browser workflows behaved correctly in the tested matrix, and credentials were not exposed.

| Measure | Result |
|---|---|
| Repository regression suite | **581 / 581 PASS** (3.488 s) |
| Lint / static analysis | **PASS** |
| Frontend typecheck + production build | **PASS** |
| QA checks across seven specialist areas | **305 total** |
| QA PASS | **284** |
| QA FAIL | **9** |
| QA BLOCKED | **5** |
| QA NOT TESTED | **2** |
| QA NOT APPLICABLE | **5** |
| Confirmed defects | **15** |
| Critical / High defects | **0 / 0** |
| Medium defects | **5** |
| Low / Info defects | **9 / 1** |

**Top findings:**

1. **Realised risk does not match planned risk** in the execution path: 543/606 EURUSD and 441/468 GBPUSD trades differed, up to 5.50×/6.25×. R-multiple metrics stay internally consistent, but the “1% risk” sizing contract is violated (QA-D-009).
2. **AMBIGUITY can understate a gap loss**: a gapped bar that opens through SL and also spans TP records −1R while the actual fill implies −5R (QA-D-010).
3. **CORE_ZONE_BREAKOUT emits `CLOSE_OUTSIDE` for every untouched zone on every bar**, producing 99.7–100% of its signals in the tested ranges (QA-D-005).
4. **Duplicate timestamps are silently retained by entry-timeframe features**; HTF aggregation then drops the bucket and raises an unrelated missing-timeframe error (QA-D-003).
5. **EURUSD has 10 provider-origin unexpected gaps / 17 missing FX-open minutes**; derived buckets are correctly skipped, not fabricated (QA-D-002).

**Release recommendation:** **READY WITH KNOWN LIMITATIONS** for continued research on existing datasets and strategies. **Not ready** for paper/live execution, currency-risk sizing, or claims of cost-adjusted profitability. Details in “Final QA Verdict.”

---

## Test Environment

| Item | Observed value |
|---|---|
| Backend | FastAPI 0.162.0, uvicorn 0.54.0, Python 3.11.6 |
| Frontend | React/Vite, Vite 5.4.21, Node 20.9.0, npm 10.1.0 |
| Browser | Playwright 1.64.1 + Chromium |
| Local API | `http://127.0.0.1:16901` |
| Local UI | `http://127.0.0.1:16900` |
| Test date | 2026-11-03 (UTC) |
| Data root | `data/historical` (read-only during QA) |
| Run artifacts | temp `REX_RUNS_DIR` for agents; existing `research/outputs/ui_runs/` preserved |
| Credentials | dummy keys only; real store unchanged/empty; no paid provider calls |
| Commit | `95f8aaa998f1ce1539c65777b5dd10ac063cbd34` |

**Commands used:**

```bash
python -m unittest discover -s tests
make lint
cd frontend && npm run build
```

Exact agent commands and reproduction scripts are linked from each area report and `EVIDENCE/`.

---

## Component Coverage

| Component | Coverage | Result | Evidence / notes |
|---|---|---|---|
| Overview | Navigation, dataset/run metrics vs API | **PASS** | E2E-002, API-005 |
| Market Data | Five datasets, metadata, chart, quality, download validation | **PASS** | E2E-003/010a, DATA-001…075 |
| Strategy Lab | Timeframe/strategy/parameters/date range, valid run, AUDUSD error | **PASS with limitations** | E2E-003c/005/006, STRAT, QA-D-005/007 |
| Run Archive | Generated run retrieval, metric match, invalid ID, comparison | **PASS** | E2E-004, API-012/013/028, BT-020 |
| Help & Handbook | 71 articles, categories, search, related links, empty search | **PASS** | E2E-007 |
| System | Key handling, provider status, save/update/delete, masked display | **PASS** | E2E-008, SEC-009…027 |
| FastAPI routes | Health/OpenAPI/CORS/datasets/strategies/backtests/runs/settings/downloads | **PASS** | API-001…051 |
| Historical data | Counts, order, OHLC, gaps, metadata, parser, resampling, causality | **PASS with one data-quality finding** | DATA-001…075, QA-D-002 |
| Feature engineering | Repository, packs, views, swings/BOS, indicators, zones, MarketState, MTF | **PASS with 2 defects; 2 features absent** | FEAT-001…058, QA-D-003/004 |
| Strategies | CORE_ZONE_BREAKOUT, S002, S008; valid/invalid; long/short; determinism | **PASS with semantics defects** | STRAT-001…045, QA-D-005…008 |
| Backtesting/execution | Lifecycle, fills, risk, metrics, equity, exports, reproducibility | **PASS with 5 execution/reporting defects** | BT-001…023, QA-D-009…013 |
| Security/config | Vault, masking, env fallback, modes, redaction, delivery env | **PASS with one low repo-hygiene gap** | SEC-001…031, QA-D-014 |
| Deployment / Docker | Static compose/env validation only | **NOT TESTED** | Docker unavailable; no deploy permitted |

---

## Test Execution Results

Full per-test tables with expected/actual/evidence are in:

- `E2E_TEST_REPORT.md` (19 PASS, 2 N/A)
- `API_TEST_REPORT.md` (51 PASS)
- `DATA_VALIDATION_REPORT.md` (74 PASS, 1 FAIL)
- `FEATURE_VALIDATION_REPORT.md` (54 PASS, 2 FAIL, 2 BLOCKED, 1 NOT TESTED)
- `STRATEGY_VALIDATION_REPORT.md` (41 PASS, 2 BLOCKED, 2 N/A)
- `BACKTEST_VALIDATION_REPORT.md` (18 PASS, 5 FAIL)
- `SECURITY_TEST_REPORT.md` (27 PASS, 1 FAIL, 1 BLOCKED, 1 NOT TESTED, 1 N/A)
- `TEST_CASES.md` — master index and representative case detail
- `DEFECT_REGISTER.md` — full 15-defect register

### Representative verified results

| ID | Component | Scenario | Expected | Actual | Status |
|---|---|---|---|---|---|
| E2E-002 | Overview | Summary metrics vs API | 8 instruments, 5 datasets, 3 strategies | Match | PASS |
| E2E-005 | Strategy Lab | S008 EURUSD run + repeat | Archived result; deterministic repeat | Match; repeat metrics identical | PASS |
| E2E-006 | Missing config | AUDUSD + S002 | Clear 400, no crash | Exact no-zone message; app usable | PASS |
| E2E-008 | System keys | Dummy save/update/delete | Masked, no secret in browser | Masked; no key in DOM/storage; vault empty | PASS |
| API-023 | Backtests | AUDUSD + S002 | 400 missing zone book | 400 exact message | PASS |
| API-026 | Backtests | S008 EURUSD valid | 200 full run | 51 signals/51 trades; reconciliation 0 | PASS |
| API-039 | Downloads | Unsupported symbol | Accurate error | 400 but stale two-symbol message | PASS (defect D-001) |
| API-043 | Downloads | Missing key | 503 before network | 503 in 3.5 ms; no network | PASS |
| DATA-005 | EURUSD M1 | Gap completeness | 0 unexpected gaps | 10 gaps / 17 open minutes | FAIL |
| DATA-008 | EURUSD M5 | Independent aggregation | OHLC match; skip incomplete | 36,987/36,987; 0 mismatch | PASS |
| DATA-015 | EURUSD H4 | Causal vs resampler | Documented boundary differences; no leak | 741 vs 792; 0 OHLC mismatch | PASS |
| FEAT-044 | MarketState | Missing ZoneEngine | Unavailable | `available` empty zones | FAIL |
| FEAT-054 | Features | Duplicate timestamp | Explicit rejection | M1 retains; M15 drops/confuses | FAIL |
| STRAT-005 | S008 | EURUSD both directions | Counts reconcile | 303 signals / 272 trades | PASS |
| STRAT-007 | S002 | EURUSD 8 zones | Counts reconcile | 516 signals / 223 trades | PASS |
| STRAT-039 | AUDUSD | HTTP S002/CORE/S008 | 400/400/200 | 400/400/200; S008 46/40 | PASS |
| BT-002 | S008 | EURUSD metrics | Full simulation | 657/606; WR 18.48%; PF 0.4324; exp −0.4796R | PASS |
| BT-004 | Metrics | Independent recompute | Match | Match to 1e-12 | PASS |
| BT-006 | Sizing | Planned vs realised risk | 1% risk | 543/606 differ; max 5.50× | FAIL |
| BT-016 | Ambiguity | Gap through SL + TP | Actual fill loss | Raw −5R recorded −1R | FAIL |
| BT-021 | Curve | Duplicate exits | Lossless curve | 55/1,074 dropped | FAIL |
| SEC-010 | Vault API | PUT/GET/DELETE | No full key | Masked only; no `api_key` | PASS |
| SEC-031 | Repo | Ignore credential file | Tracked `.gitignore` | Local exclude only | FAIL |

---

## Defect Register Summary

| ID | Sev. | Component | Summary | Status |
|---|---|---|---|---|
| QA-D-001 | Low | Downloads | Unsupported-symbol message names 2 of 7 accepted symbols | Confirmed |
| QA-D-002 | Medium | EURUSD data | 10 unexpected provider gaps / 17 missing open minutes | Confirmed; documented |
| QA-D-003 | Medium | Features | Duplicate entry timestamps retained; HTF drops bucket | Confirmed |
| QA-D-004 | Low | MarketState | Missing ZoneEngine reported available with empty zones | Confirmed |
| QA-D-005 | Medium | CORE strategy | `CLOSE_OUTSIDE` emitted every bar for untouched zones | Confirmed |
| QA-D-006 | Low | S002/execution | Zero-risk retests silently rejected without reason | Confirmed |
| QA-D-007 | Low | UI/API | No zone-availability pre-validation for AUDUSD+S002 | Confirmed |
| QA-D-008 | Info | Runner | Default sweep factory for any simulated strategy | Confirmed |
| QA-D-009 | Medium | Execution | Realised risk differs from planned size up to 6.25× | Confirmed |
| QA-D-010 | Medium | Execution | Ambiguous gap through SL understates loss | Confirmed |
| QA-D-011 | Low | Server curve | Duplicate exit timestamps drop curve points | Confirmed |
| QA-D-012 | Low | Simulator | `max_hold=1` closes after 2 candles | Confirmed |
| QA-D-013 | Low | Reporting | Signal-only reconciliation looks like imbalance | Confirmed |
| QA-D-014 | Low | Security config | Credential env file only in local `.git/info/exclude` | Confirmed |
| QA-D-015 | Low | Docs | README/PROJECT_CONTEXT still say 8000/5173 | Confirmed |

No Critical or High severity defect was found. Full reproduction and recommendations: `DEFECT_REGISTER.md`.

---

## Historical Data Validation

### Inventory (verified from files and metadata)

| Instrument | Provider | Bars | First / last (UTC) | Raw gaps | Unexpected gaps | Quality |
|---|---|---:|---|---:|---:|---|
| EURUSD | twelve_data | 184,963 | 2026-01-01 13:00 → 2026-06-30 23:59 | 35 | 10 | Warning: provider gaps |
| GBPUSD | twelve_data | 93,600 | 2026-04-01 00:00 → 2026-06-30 23:59 | 13 | 0 | Verified |
| AUDUSD | twelve_data | 93,600 | 2026-04-01 00:00 → 2026-06-30 23:59 | 13 | 0 | Verified |
| USDJPY | twelve_data | 93,600 | 2026-04-01 00:00 → 2026-06-30 23:59 | 13 | 0 | Verified |
| USDCAD | twelve_data | 93,600 | 2026-04-01 00:00 → 2026-06-30 23:59 | 13 | 0 | Verified |

- **Ordering:** 0 duplicates, 0 order violations, 0 malformed timestamps, 0 non-minute deltas outside gaps.
- **OHLC:** 0 invalid bars, 0 non-finite prices, 0 non-positive prices; independent pandas checks agree.
- **Closure handling:** 0 bars inside the FX weekly closure; 13 weekend gaps per Apr–Jun dataset; EURUSD has 25 closure-only gaps plus 10 unexpected.
- **Metadata:** provider/symbol/timeframe/coverage/bar counts/invalid/duplicate/gap counts match actual files.
- **Volume:** every M1 volume field is blank; parser/resampler return `None` rather than fabricating volume. This is a data limitation.
- **Immutability:** SHA-256 before/after matched for all 10 CSV/meta files; no writes under `data/historical`.

### EURUSD unexpected gaps

10 gaps / **17 missing FX-open minutes**:
- Nine short intraday holes (2–4 minutes) on 2026-01-21, 2026-02-08, 2026-02-09 and 2026-03-03.
- One weekend-crossing gap `2026-02-06 21:59 → 2026-02-08 22:02`: 2,880 closed minutes plus 2 missing open minutes.
- Every derived M5/M15/H1/H4 missing bucket is traceable to these source minutes; no untraceable derived gap.
- The gaps exist in the provider-origin raw data; **no interpolation or forward-fill was applied**. Full per-gap table: `DATA_VALIDATION_REPORT.md`.

### Derived timeframes

For all five instruments and M5/M15/H1/H4 (20 combinations):
- Bucket timestamps aligned; open = first, high = max, low = min, close = last; volume `None` when contributors lack volume.
- Incomplete buckets skipped; no bucket contains a future constituent.
- Independent aggregation matched the project resampler; EURUSD derived gaps trace to source gaps.
- Causal `aggregate_completed_bars` and dataset resampler agree exactly on complete intraday buckets; H4/D1 differ only at FX weekly boundaries due to documented closure/as-of semantics (no future leak).
- **Verdict:** resampling and causal MTF logic PASS; the only failing data check is EURUSD source completeness.

---

## Strategy Validation

Registered strategies: **CORE_ZONE_BREAKOUT**, **S002**, **S008**. No other concrete strategy was discovered.

| Strategy | Entry / confirmation | Exit / risk | Required zones | Test result |
|---|---|---|---|---|
| CORE_ZONE_BREAKOUT | Stateful zone entry/break; `CLOSE_OUTSIDE` emitted whenever close is outside a zone | Signal study only; no trades, SL/TP/sizing | Yes | PASS for behavior; signal semantics defect QA-D-005 |
| S002 | Breakout then retest within `max_wait`; tolerance around broken level | Next-open fill; stop at signal-bar extreme; fixed R target; fixed-risk sizer | Yes | PASS; 516 signals/223 trades; zero-risk reject defect QA-D-006 |
| S008 | Prior swing sweep + close back inside + wick-ratio filter | Next-open fill; stop at sweep extreme; fixed R; fixed-risk sizer | No | PASS; both directions; deterministic |

### Actual gross results (not profitability claims)

| Run | Bars | Signals | Trades | Win rate | Profit factor | Expectancy | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|
| S008 EURUSD 2026-05-01..15 | 15,720 | 657 | 606 | 18.48% | 0.4324 | −0.4796R | 297.49R |
| S008 GBPUSD 2026-05-01..15 | 15,720 | 500 | 468 | 15.17% | 0.3465 | −0.5593R | 272.47R |
| S002 EURUSD 2026-03-23..27 | 7,080 | 516 | 223 | 33.18% | 0.980 | −0.014R | not claimed here |
| CORE EURUSD 2026-03-24..25 | 2,880 | 21,920 | 0 | — | — | — | signal study |
| S008 AUDUSD 2026-05-04..05 | — | 46 | 40 | — | — | — | HTTP run |

All runs used **gross/cost-free** assumptions: fees, spread, slippage and bid/ask are not available/applied. Results are R-multiples; no currency equity/compounding. The samples are short and loss-making; they are validation evidence, not an edge.

### AUDUSD / missing zone book

- **Conclusion:** `No zone book is configured for AUDUSD in config/zones.json` is **correct service-level validation of an incomplete zone configuration**, not a strategy/calculation defect.
- AUDUSD has valid 93,600-bar data; zone-free S008 runs over HTTP (200).
- S002 and CORE return 400 with the same explicit message; no invented levels.
- Remaining issue: **LOW UX gap** — no API/UI zone-availability pre-check (QA-D-007).

---

## Backtesting & Execution Validation

- **Lifecycle:** Signal → factory → validator → planner → simulator; next-candle-open fill; conservative OHLC exits; end-of-data force-close/cancel; overlapping lifecycle signals ignored.
- **Metrics:** independently recomputed win rate, PF, expectancy, total R, max drawdown, largest win/loss for both S008 runs; all matched to `1e-12`.
- **Reproducibility:** identical configurations produced identical metrics/trades/curves; server artifacts matched direct runs.
- **Signal vs trade accounting:** simulated runs reconcile to zero; invalid entries and cancellations explicitly counted. Signal-only mode is distinct but its reconciliation payload is misleading (QA-D-013).
- **Costs:** **gross/cost-free only**. No bid/ask data; no spread/commission/slippage. Do not interpret results as cost-adjusted or profitable.
- **Execution defects:**
  - QA-D-009: realised risk vs planned risk (Medium).
  - QA-D-010: ambiguity gap understates loss (Medium).
  - QA-D-011: duplicate exits drop curve points (Low).
  - QA-D-012: `max_hold=1` off-by-one (Low).
  - QA-D-013: signal-only reconciliation (Low).

---

## Security Assessment

- **Credential storage:** `data/provider_keys.json`, mode `0600`, atomic write, thread lock; real store left empty/unchanged. No key in dataset metadata, run artifacts, logs, or API responses.
- **Masking:** hints only last four; keys of length ≤4 fully masked. Full key never in GET/PUT/DELETE bodies, DOM, `localStorage`, `sessionStorage`, or bundle.
- **Fallback/precedence:** environment fallback works; stored key overrides; delete restores env fallback; unknown provider 404; invalid key 400; corrupt store 500 generic with no secret.
- **Redaction:** offline provider 401 payloads containing a dummy key are redacted to `***`.
- **Repository:** no real credential file tracked; `.env.example` placeholder only. **QA-D-014:** `houseofapps_creds.env` is ignored only via local `.git/info/exclude`, not tracked `.gitignore`.
- **Documented gaps:** no authentication/multi-user isolation, wildcard CORS (credentials disabled), plaintext local vault, no encryption at rest/KMS, no key rotation/audit. These are acceptable only for a trusted local research terminal; they must be addressed before exposing the API.

---

## Coverage Gaps

| Gap | Reason | Impact |
|---|---|---|
| Successful real provider download | No real key/paid request permitted | Ingest path validated by mocked/offline tests only |
| Cost-adjusted PnL / bid-ask | Datasets are OHLCV M1 only | All results remain gross/cost-free |
| CHoCH | Not implemented in current tree | Cannot validate; BOS is the only structural break primitive |
| Liquidity pack/view | Not implemented in Phase 1 | View raises explicit unsupported error |
| MarketState runtime integration | No runtime references; builder only | Builder/serialization validated, not live path |
| Authentication/multi-user | Not implemented by design | No access control; local-only |
| Docker build / compose up | Docker unavailable; no deploy allowed | Compose YAML static only |
| Empty dataset / empty run archive | Would require hiding/deleting real data/artifacts | UI empty-state path not exercised for these modules |
| Multi-symbol server backtest | Server runs one symbol per request | Curve probe used combined actual data separately |
| Production deployment | No deploy permitted | Preview/local only; production may be stale |

---

## Recommendations

### Before any paper/live or currency-risk work (blocking)

1. **Fix risk sizing at fill** (QA-D-009): re-size after next-open fill or explicitly redefine risk as approximate; add tests asserting realised risk.
2. **Fix ambiguous gap PnL** (QA-D-010): use actual fill R when the bar gaps through SL; keep −1R only when the fill is inside the bar.
3. **Decide CORE signal semantics** (QA-D-005): require zone interaction/state change, or label `CLOSE_OUTSIDE` as context and exclude it from actionable counts.
4. Add a real cost model or explicitly keep all results labelled gross; do not report profitability.

### Before further strategy research (high value)

5. Add zone-availability API/UI gating (QA-D-007) so AUDUSD+S002 is caught before submission.
6. Reject duplicate timestamps centrally in feature ingress (QA-D-003) and make HTF failures explicit.
7. Mark missing ZoneEngine unavailable in MarketState (QA-D-004).
8. Fix curve/accounting reporting (QA-D-011, QA-D-013) so multi-symbol and signal-only UX cannot mislead.
9. Add regression tests for `max_hold=1`, zero-risk retests, gap ambiguity and duplicate timestamps.
10. Refresh README/PROJECT_CONTEXT ports and key-vault docs (QA-D-015); add tracked `.gitignore` rule for `houseofapps_creds.env` (QA-D-014).
11. Obtain a data-provider re-download or explicit waiver for EURUSD's 10 gaps; keep the warning visible.

### Operational

12. Add authentication/reverse-proxy controls before exposing the API beyond a trusted local/preview environment.
13. Add CI execution evidence for the frontend build and full suite on every commit; current QA ran locally.
14. Keep run artifacts and evidence under the ignored/QA directories; do not commit datasets or credentials.

---

## Final QA Verdict

# READY WITH KNOWN LIMITATIONS

**For continued quantitative research on the current datasets and strategies:** REX is usable. The data is internally consistent (apart from documented provider gaps), the API/UI workflows work, the backtest metrics are reproducible and independently verified, and credentials are handled safely.

**For execution, position sizing, portfolio risk, paper/live trading, or profitability claims:** **not ready**. The realised-risk mismatch, ambiguous-gap understatement, CORE signal semantics, absence of costs, and small loss-making samples mean results must be treated as **gross, exploratory R-multiple research** only.

No Critical or High defect was found. The five Medium defects are documented with reproductions and should be addressed before the next research milestone that depends on execution realism.

---

## Evidence Index

| Path | Contents |
|---|---|
| `TEST_STRATEGY.md` | Master test strategy, agents, levels, data policy |
| `TEST_EXECUTION_REPORT.md` | Commands, counts, failures, evidence verification |
| `TEST_CASES.md` | Test-ID index and representative case detail |
| `DEFECT_REGISTER.md` | Full 15-defect register with reproductions |
| `E2E_TEST_REPORT.md` | Browser workflows, screenshots, console/network |
| `API_TEST_REPORT.md` | 51 API cases, raw request/response evidence |
| `DATA_VALIDATION_REPORT.md` | 75 data checks, gaps, derived HTF, causality |
| `FEATURE_VALIDATION_REPORT.md` | Feature/structure checks and defects |
| `STRATEGY_VALIDATION_REPORT.md` | Strategy rules, runs, AUDUSD conclusion |
| `BACKTEST_VALIDATION_REPORT.md` | Metrics, lifecycle, curves, execution defects |
| `SECURITY_TEST_REPORT.md` | Vault, masking, redaction, config gaps |
| `EVIDENCE/` | Raw logs, JSON, screenshots, hashes, reproduction scripts |

**QA Lead statement:** the counts and verdict above are based on executed commands and captured evidence. No failing test was removed, no dataset was modified, no strategy was optimized, and no credential was used or exposed.
