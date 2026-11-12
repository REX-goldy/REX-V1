# REX QA Test Execution Report

- **Execution date:** 2026-11-03 (UTC)
- **Commit:** `95f8aaa998f1ce1539c65777b5dd10ac063cbd34`
- **Workspace:** `/home/user/workspaces/7de05e41da33`
- **QA Lead:** Agent 1
- **Overall result:** 305 documented QA checks — **284 PASS, 9 FAIL, 5 BLOCKED, 2 NOT TESTED, 5 NOT APPLICABLE**. No Critical or High severity defect. Full regression suite **581/581 PASS**.
- **Working tree:** only `docs/qa/` added; no application/test/config/dataset/strategy changes.

## 1. Environment

| Item | Observed |
|---|---|
| Python | 3.11.6 |
| Node / npm | 20.9.0 / 10.1.0 |
| Backend | FastAPI 0.162.0, uvicorn 0.54.0 |
| Frontend | Vite 5.4.21, React 18 |
| Browser | Playwright 1.64.1 + Chromium (E2E agent) |
| Local API | `http://127.0.0.1:16901` |
| Local UI | `http://127.0.0.1:16900` |
| Datasets | five M1 2026 partitions, unchanged |

## 2. Commands and results

| # | Command | Result | Duration | Evidence |
|---|---|---|---|---|
| 1 | `python -m unittest discover -s tests` | **581 tests, OK, exit 0** | 5 s wall | `EVIDENCE/lead/full-suite.log` |
| 2 | `make lint` (compileall + pyflakes) | **exit 0** | 1 s | `EVIDENCE/lead/lint.log` |
| 3 | `cd frontend && npm run build` | **tsc + vite build, exit 0**; 455.82 kB JS / 36.86 kB CSS | 8 s | `EVIDENCE/lead/frontend-build.log` |
| 4 | Frontend E2E (Playwright, six modules, desktop/mobile) | **19 executed / 19 PASS / 2 N/A** | see E2E report | `EVIDENCE/e2e/` |
| 5 | Backend API matrix | **51/51 PASS**; 1 low defect (message only) | 13:35–13:39 UTC | `EVIDENCE/api/` |
| 6 | Historical data matrix | **74 PASS / 1 FAIL** (EURUSD source gaps) | 13:47 UTC | `EVIDENCE/data/` |
| 7 | Feature/structure matrix | **54 PASS / 2 FAIL / 2 BLOCKED / 1 NOT TESTED** | — | `EVIDENCE/features/` |
| 8 | Strategy matrix | **41 PASS / 0 FAIL / 2 BLOCKED / 2 N/A**; 4 confirmed defects | — | `EVIDENCE/strategy/` |
| 9 | Backtest/execution matrix | **18 PASS / 5 FAIL** | 13:35 UTC | `EVIDENCE/backtest/` |
| 10 | Security/config matrix | **27 PASS / 1 FAIL / 1 BLOCKED / 1 NOT TESTED / 1 N/A** | — | `EVIDENCE/security/` |
| 11 | `cd frontend && npm audit --omit=dev` | **0 vulnerabilities, exit 0** | — | `EVIDENCE/lead/frontend-audit.log` |
| 12 | `python -m pip check` | **No broken requirements, exit 0** | — | `EVIDENCE/lead/pip-check.log` |

The 581 unit tests are the repository regression suite. The 305 QA checks include browser, API, data, feature, strategy, backtest and security scenarios; they are not the same tests and are not added together to inflate the unit-test count.

## 3. Per-agent execution summary

| Agent | Total | PASS | FAIL | BLOCKED | NOT TESTED | N/A |
|---|---:|---:|---:|---:|---:|---:|
| Frontend UI | 21 | 19 | 0 | 0 | 0 | 2 |
| Backend API | 51 | 51 | 0 | 0 | 0 | 0 |
| Historical Data | 75 | 74 | 1 | 0 | 0 | 0 |
| Features/Structure | 59 | 54 | 2 | 2 | 1 | 0 |
| Strategies | 45 | 41 | 0 | 2 | 0 | 2 |
| Backtesting/Execution | 23 | 18 | 5 | 0 | 0 | 0 |
| Security/Config | 31 | 27 | 1 | 1 | 1 | 1 |
| **Total** | **305** | **284** | **9** | **5** | **2** | **5** |

## 4. FAIL records

| Test ID | Area | Reason | Evidence |
|---|---|---|---|
| DATA-005 | Data | EURUSD has 10 unexpected provider gaps / 17 unfilled FX-open minutes. Documented data-quality warning, not invented. | `EVIDENCE/data/test_results.json` |
| FEAT-044 | Features | `ZoneEngine=None` yields `zones.status=available` with empty zones instead of unavailable. | `FEAT-044_market_state_missing_zone_engine.json` |
| FEAT-054 | Features | Duplicate entry timestamps are retained at M1; HTF aggregation silently drops the bucket and raises an unrelated missing-timeframe error. | `FEAT-054_boundary_duplicates.json` |
| BT-006 | Backtest | Realised risk differs from planned risk on 543/606 EURUSD and 441/468 GBPUSD trades (max 5.50× / 6.25×). | `valid_runs_analysis.json` |
| BT-014 | Backtest | `max_hold_candles=1` closes after 2 candles. | `edge_case_analysis.json` |
| BT-016 | Backtest | Ambiguous gap through SL and TP records −1R while raw fill implies −5R. | `ambiguity_gap_probe.json` |
| BT-021 | Backtest | Multi-symbol equity curve drops 55 of 1,074 trades sharing exit timestamps. | `valid_runs_analysis.json` |
| BT-022 | Backtest | Signal-only reconciliation reports `difference=56818` with no execution path. | `core_signal_only_server_run.json` |
| SEC-031 | Security | `houseofapps_creds.env` is ignored only by local `.git/info/exclude`, not tracked `.gitignore`. | `finding-01-gitignore-houseofapps.txt` |

## 5. Blocked / not tested

| Item | Status | Reason |
|---|---|---|
| Successful real provider download | BLOCKED | Requires real credentials and incurs provider/paid usage. |
| CHoCH implementation | BLOCKED | No CHoCH implementation exists in the working tree; BOS is the only structural break primitive. |
| Liquidity pack/view | BLOCKED | Phase 1 has no liquidity pack; view raises `UnsupportedMethodError` rather than fabricating. |
| Live provider redaction test | BLOCKED | No real key/provider request permitted. |
| MarketState runtime integration | NOT TESTED | No runtime references; only builder/serialization exists. |
| Real-browser vault inspection | NOT TESTED (security)/covered by E2E | Security agent used static/bundle checks; E2E agent exercised the UI vault with a dummy key. |
| Authentication/multi-user isolation | N/A | Not implemented by design; local single-user terminal. |
| Cost-adjusted PnL | N/A/BLOCKED | OHLCV only; no bid/ask; costs are intentionally off. |
| Docker image build / compose up | N/A | Docker unavailable; compose YAML statically validated. |
| Empty dataset/run archive | NOT TESTED | Would require hiding/deleting real data/artifacts; preservation constraint. |

## 6. Evidence verification by QA Lead

Independently checked by the QA Lead after agent completion:

- Full suite re-run: **581 tests, OK**, 3.488 s.
- Lint: exit 0.
- Frontend build: exit 0.
- API D-01 reproduced: `POST /api/downloads` invalid symbol returns 400 with `"UI downloads currently support EURUSD and GBPUSD"` while seven symbols are accepted.
- Dataset counts and metadata read from disk: EURUSD 184,963; GBPUSD/AUDUSD/USDJPY/USDCAD 93,600 each.
- `houseofapps_creds.env` ignored only by `.git/info/exclude`; not tracked.
- Backtest risk deviation, ambiguity gap, duplicate timestamp, and missing-zone-engine evidence inspected in `docs/qa/EVIDENCE/`.
- Data files' SHA-256 values unchanged; `git status` shows only `docs/qa/`.

## 7. Artifacts and side effects

- Reports: `docs/qa/*.md`.
- Evidence: `docs/qa/EVIDENCE/` (API 2.5 MB, backtest 2.1 MB, data 220 KB, E2E 11 MB, features 1.3 MB, security 136 KB, strategy 645 KB).
- New real UI run artifacts created during E2E (4) and strategy/backtest agents used temp `REX_RUNS_DIR`; pre-existing run `20261030T105941Z_1684076e` preserved.
- `data/provider_keys.json` left empty; no real key stored.
- No application code, tests, config, strategy, dataset or git history changed.
- No deploy, commit or push.

## 8. Execution conclusion

The regression suite, lint, and frontend build are green. The backend/API and browser layers behaved correctly in the tested matrix. Failures are concentrated in execution sizing/ambiguity edge cases, feature dependency/duplicate handling, one source-data gap warning, and two low operational/security/documentation gaps. No failure was hidden or converted into a pass.
