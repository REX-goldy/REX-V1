# REX Project Status — Evidence-Based Audit

- **Audit date:** 2026-11-10 (UTC)
- **Repository:** `/home/user/workspaces/7de05e41da33`
- **Git state:** base commit `95f8aaa` plus uncommitted P0–P3.1 Stage 2A working-tree changes
- **Primary source:** the local working tree, not GitHub
- **Mode:** read-only assessment. No source, dataset, experiment or run artifact was changed.

## 1. Headline assessment

REX is a **functional, single-user quantitative research platform** for FX backtesting and
experiment management. It is **not** a paper-trading system and **not** a production
automated trading platform.

The platform has a coherent research workflow: ingest and validate M1 data, derive
timeframes, define manual zones, run three strategies through one `BacktestRunner`, record
runs and experiments, independently validate trade arithmetic, compare results, and
reproduce snapshotted experiments.

The central strategic gap is research evidence, not UI polish: **no archived run currently
demonstrates positive expectancy**, and the strategy set is small. The current results are
R-multiple research results, not account-currency returns and not a claim about future
profitability.

## 2. Verified snapshot

| Item | Verified state |
|---|---|
| Backend test suite | **674 / 674 PASS** (81.1 s) |
| Lint | PASS (`make lint`) |
| Frontend typecheck + production build | PASS; chunk-size warning |
| API surface | 46 FastAPI route decorators in `server/main.py` |
| Frontend pages | 8 primary pages in `frontend/src/App.tsx` |
| Stored datasets | 5 EURUSD/GBPUSD/AUDUSD/USDJPY/USDCAD M1 datasets, 559,363 bars total |
| Registered instruments | 8 in the instrument registry; 5 have stored data |
| Strategies | 3 registered; 2 trade-simulated, 1 signal-only |
| Archived runs | 24 JSON artifacts; all 24 independently validate with zero errors |
| Archived experiment results | No run artifact shows positive gross expectancy |
| Workspace | 3 strategies, 4 variations, 3 experiments; 1 has a full reproducible snapshot |
| Historical data hashes | 10/10 files unchanged against the QA reference |
| Latest implemented phase | P3.1 Stage 2A (WMA/HMA/DEMA/TEMA), self-verified |
| Active development | None in progress at audit time; Stage 2A awaits review |
| Deployment | Preview/deploy config exists; Docker unavailable; no production deployment verified |

## 3. Documents

1. [FUNCTIONALITY_INVENTORY.md](FUNCTIONALITY_INVENTORY.md) — capability-by-capability
   inventory across the research engine, strategy research, data, UI, infrastructure and
   quality, with exact status labels.
2. [PHASE_STATUS.md](PHASE_STATUS.md) — QA, P0, P1, P2, P2.1, P3.0 and P3.1 status,
   including Stage 1/2A/2B, caching and feature-provenance persistence.
3. [PRIORITY_GAPS.md](PRIORITY_GAPS.md) — the ten most important outstanding items,
   with impact, dependencies, priority and recommended next action.
4. [EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md) — one-page CEO brief and maturity
   classification.
5. [REX_CEO_PRESENTATION.pptx](REX_CEO_PRESENTATION.pptx) — six-slide executive
   presentation with speaker notes.
6. [EVIDENCE/](EVIDENCE/) — current test, lint, build, run-validation, dataset-hash and
   test-distribution records.

## 4. Status vocabulary

| Status | Meaning in this audit |
|---|---|
| COMPLETED | Implemented and supported by code plus verification evidence |
| PARTIALLY COMPLETED | Core exists, but important capabilities or integrations are missing |
| IN PROGRESS | Actively being implemented at audit time |
| PLANNED | Documented/approved, but no meaningful implementation |
| BLOCKED | Cannot progress without a specific unresolved dependency |
| NOT STARTED | No meaningful implementation exists |

A documentation claim alone is never treated as evidence of implementation. **P3.1 Stage 2A**
is COMPLETED in code and self-tested, but it has **not** received an independent audit or
formal acceptance; the report distinguishes that review status separately.

## 5. Evidence basis

- Source inspection: `core/`, `strategies/`, `execution/`, `backtests/`, `historical/`,
  `server/`, `frontend/src/`, `config/`, `.appforge/`.
- Test execution: `python -m unittest discover -s tests` → 674 PASS.
- Lint: `make lint` → PASS.
- Frontend: `cd frontend && npm run build` → PASS.
- Run-artifact validation: all 24 `research/outputs/ui_runs/*.json` checked with the
  independent `backtests.validation.validate_run`; 24 valid, 0 errors, 0 warnings.
- Dataset hashes: 10/10 match `docs/qa/EVIDENCE/lead/data_sha256_after.txt`.
- Workspace state: `data/workspace/strategy_workspace.json` inspected read-only.
- Data/quality: `historical.quality` / existing metadata inspected.

## 6. Important boundaries

- The latest P3.1 Stage 2A changes are **uncommitted**; GitHub does not represent current
  progress.
- The current environment has no Docker binary, so the Compose/Docker deployment path was
  reviewed statically, not run.
- At audit time only the API port `16901` was listening; the frontend preview port `16900`
  was not listening. The preview configuration exists, but live preview availability was
  not asserted.
- No line-coverage percentage is claimed. The suite is verified by test count and execution,
  not by an enforced coverage threshold.
- No historical result is extrapolated into a claim of future profitability.

## 7. One-line verdict

**Strong research foundation and unusually good traceability for its stage; no validated
trading edge yet, and not ready for paper or live execution.**
