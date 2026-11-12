# REX QA Test Strategy

- **Date:** 2026-11-03
- **Commit under test:** `95f8aaa998f1ce1539c65777b5dd10ac063cbd34`
- **Scope:** current working tree, local API/UI, actual stored M1 datasets
- **Mode:** read-only validation; no deploy, no commit, no strategy/data/app changes.
- **Primary rule:** evidence over assertion. A page loading is not a passing test.

## 1. Quality objectives

1. Establish whether the **research numbers** are correct, reproducible and causally computed.
2. Establish whether the **historical data** is internally consistent and honestly described.
3. Establish whether the **UI and API** behave correctly for normal and abnormal workflows.
4. Establish whether **credentials and provider configuration** are handled safely.
5. Identify the defects that block or constrain quantitative research, without optimizing strategies or fabricating outcomes.

## 2. Architecture inspected

| Layer | Actual implementation reviewed |
|---|---|
| Data ingestion/storage | `historical/` (Twelve Data, Dukascopy, parser, storage, metadata, FX calendar) |
| Data derivation | `research/free_ohlc/resampler.py`; causal path in `core/features/timeframes.py` |
| Features/structure | `core/features/`, `core/indicators/`, `core/zones/`, `core/market_state/` |
| Strategy layer | `strategies/` registry, `CORE_ZONE_BREAKOUT`, `S002`, `S008` |
| Execution/backtest | `execution/`, `backtests/` (`BacktestRunner`, simulator, fills, metrics, results) |
| API | `server/main.py`, `server/research_service.py`, `server/provider_keys.py` |
| Frontend | React/Vite in `frontend/src`; six module pages |
| Delivery/config | `.appforge/*`, `docker-compose.yml`, Dockerfiles (static checks only) |

## 3. QA team model

| Agent | Responsibility | Output |
|---|---|---|
| Agent 1 — QA Lead | Architecture inspection, plan, consolidation, evidence verification, final verdict | `README.md`, this strategy, execution report, test cases, defect register |
| Agent 2 — Frontend UI | Playwright E2E, all six modules, validation, responsive, console/network | `E2E_TEST_REPORT.md` |
| Agent 3 — Backend API | Routes, schemas, invalid requests, runs, credentials, download validation | `API_TEST_REPORT.md` |
| Agent 4 — Historical Data | Counts, timestamps, OHLC, closures, gaps, metadata, derived HTF, causality | `DATA_VALIDATION_REPORT.md` |
| Agent 5 — Features/Structure | Repository, packs, views, swings/BOS, indicators, zones, MarketState, MTF | `FEATURE_VALIDATION_REPORT.md` |
| Agent 6 — Strategies | Rule documentation, valid/invalid runs, directions, determinism, AUDUSD | `STRATEGY_VALIDATION_REPORT.md` |
| Agent 7 — Backtest/Execution | Lifecycle, fills, sizing, metrics, equity, costs, exports, reproducibility | `BACKTEST_VALIDATION_REPORT.md` |
| Agent 8 — Security/Config | Vault, masking, env fallback, file modes, redaction, delivery env | `SECURITY_TEST_REPORT.md` |

The QA Lead retained ownership of the consolidated verdict and independently re-ran the full suite, lint, frontend build and key defect reproductions.

## 4. Test levels

| Level | Purpose |
|---|---|
| Static inspection | Confirm actual implementation, missing features, contracts and citations |
| Unit/regression | Existing `unittest` suite and focused agent subsets |
| Data integrity | Independent CSV/pandas checks, parser round-trip, resampling, causal comparison |
| API integration | Direct HTTP requests against local and isolated instances |
| Browser E2E | Playwright against the real Vite UI and API |
| Workflow E2E | Market Data, Strategy Lab, Missing Config, Run Archive, Provider Config, Handbook, Overview |
| Security | Isolated dummy vault, credential lifecycle, redaction, repository hygiene |
| Reproducibility | Repeat runs, deterministic fingerprints, run archive round-trip |

## 5. Test data policy

Priority:
1. Actual stored datasets: EURUSD, GBPUSD, AUDUSD, USDJPY, USDCAD M1 2026.
2. Authorized provider data only if explicitly needed — **not used** (no real key / no paid request).
3. Deterministic synthetic fixtures only for isolated edge cases; every such case is labelled **SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA**.

No historical file, metadata, config or strategy was modified. Dataset SHA-256 values were captured before/after by the data agent and matched.

## 6. Environments

| Item | Value |
|---|---|
| Python | 3.11.6 |
| Node | 20.9.0 |
| npm | 10.1.0 |
| Backend | FastAPI 0.162.0, uvicorn 0.54.0 |
| Frontend | React/Vite, Vite 5.4.21 |
| Browser | Playwright 1.64.1, Chromium |
| API | `http://127.0.0.1:16901`; isolated 16902/16903/16904 for tests |
| UI | `http://127.0.0.1:16900` |
| Data root | `data/historical` |
| Run root | temp `REX_RUNS_DIR` for agents; existing UI runs preserved |
| Credentials | real store untouched; dummy keys only; no provider calls |

## 7. Status definitions

- **PASS** — expected behavior observed and evidence captured.
- **FAIL** — reproducible mismatch between expected and actual behavior.
- **BLOCKED** — cannot execute because required capability/data/infrastructure is absent or prohibited.
- **NOT TESTED** — in scope but not executed; reason documented.
- **NOT APPLICABLE** — feature/claim does not exist or is explicitly out of scope.

Severity:
- **Critical** — data corruption, credential leakage, major financial-calculation failure, research-integrity failure.
- **High** — core function unavailable, materially wrong backtest results, major API failure.
- **Medium** — incorrect calculation/workflow with workaround, significant execution/configuration defect.
- **Low** — minor UI, message, formatting or documentation defect.
- **Info** — design footgun/observation with no immediate failure.

## 8. Test ID scheme

| Prefix | Area |
|---|---|
| E2E-### | Browser/frontend workflows |
| API-### | HTTP/API/service behavior |
| DATA-### | Historical data and resampling |
| FEAT-### | Feature engineering and market structure |
| STRAT-### | Strategies |
| BT-### | Backtesting/execution |
| SEC-### | Security/configuration |
| D-### | Consolidated defect register |

## 9. Entry / exit criteria

**Entry:** repository inspected; local API/UI reachable; real datasets present; isolated run/key roots available.

**Exit:**
- full backend suite executed on current HEAD;
- lint and frontend build executed;
- every module and required workflow exercised or explicitly blocked;
- every confirmed defect reproduced and evidence-linked;
- data files byte-identical after testing;
- no secrets used or exposed;
- all results consolidated with a release verdict.

## 10. Constraints and non-negotiable rules

- No deploy, commit, push or git history change.
- No strategy logic, data, config or application changes to make tests pass.
- No real credentials, no paid/provider requests.
- No fabricated candles, signals, trades, metrics or counts.
- No deletion of existing runs or artifacts.
- All temporary scripts live outside the repository; only reports/evidence are added under `docs/qa/`.
- Gaps and blockers are reported, not hidden.
