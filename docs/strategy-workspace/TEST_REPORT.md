# Strategy Workspace — Test Report

- **Date:** 2026-11-03
- **Feature commit base:** `95f8aaa998f1ce1539c65777b5dd10ac063cbd34` plus this additive working tree
- **Environment:** Python 3.11.6, Node 20.9.0, FastAPI/uvicorn, Vite 5.4.21, Playwright 1.64.1 + Chromium
- **Scope:** persistence, API, workspace UI, Strategy Lab integration and regression compatibility
- **No deploy, commit, push, strategy change or historical-data change was performed.**

## 1. Result summary

| Check | Result |
|---|---|
| Full backend suite | **628 / 628 PASS** at current tree (593 at workspace delivery; P0/P1 added 35 tests) |
| New workspace tests | **12 / 12 PASS** (`tests.test_strategy_workspace`) |
| API route contract | **PASS**, including 9 additive workspace paths |
| Lint / static analysis | **PASS** (`compileall` + `pyflakes`) |
| Frontend typecheck | **PASS** |
| Frontend production build | **PASS** (Vite 5.4.21; 1,606 modules; 499.41 kB JS / 42.21 kB CSS) |
| Browser E2E | **PASS** — list/search/detail/tabs/notes/variation/create/run/link; 0 console/page errors |
| Real run linked | `20261103T144626Z_57dd08ff`; 31,800 bars, 1,393 signals, 1,316 trades, gross expectancy −0.653R |
| Persistence | workspace JSON created, mode `0600`, gitignored |
| Existing Strategy Lab | remains functional with no preset; existing tests pass |

## 2. Commands

```bash
python -m unittest discover -s tests
python -m unittest tests.test_strategy_workspace -v
make lint
cd frontend && npm run build
```

Playwright workflow was run against `http://127.0.0.1:16900` with API `http://127.0.0.1:16901`. Evidence:
`EVIDENCE/e2e-verify.log`, `EVIDENCE/workspace-list.png`, `EVIDENCE/run-result.png`,
`EVIDENCE/experiments.png`, `EVIDENCE/final-workspace.png`.

## 3. Automated test matrix

`tests/test_strategy_workspace.py`:

| Test | Scenario | Result |
|---|---|---|
| `test_seeded_real_strategies_and_documents` | Three actual registry strategies, baseline, implemented rules | PASS |
| `test_create_edit_archive_and_duplicate_title` | Create, edit, archive, duplicate-title conflict, docs-only baseline | PASS |
| `test_search_status_and_title_sort` | Search, status filter, title sort | PASS |
| `test_notes_are_timestamped_and_editable` | Add/update/delete note, timestamps | PASS |
| `test_multiple_variations_and_configuration_version` | Multiple variations, parameter validation, version increment | PASS |
| `test_invalid_parameters_and_docs_only_cannot_run` | Unknown parameter, docs-only run rejection | PASS |
| `test_record_experiment_links_real_run_and_keeps_metrics` | Correct variation, real run ID, actual metrics, baseline kind | PASS |
| `test_experiment_rejects_duplicate_missing_and_wrong_strategy` | Duplicate link, missing run, wrong strategy | PASS |
| `test_baseline_locks_after_experiment_and_clone_is_independent` | Baseline lock, clone isolation, baseline archive rejection | PASS |
| `test_comparison_requires_comparable_conditions` | Exact comparable group, two variations, metrics | PASS |
| `test_invalid_store_version_fails_closed` | Corrupt/unsupported version is not overwritten | PASS |
| `test_live_route_functions` | GET list/detail, note add, missing ID | PASS |

The API route contract now asserts the additive paths:

```
/api/workspace/strategies
/api/workspace/strategies/{strategy_id}
/api/workspace/strategies/{strategy_id}/notes
/api/workspace/strategies/{strategy_id}/notes/{note_id}
/api/workspace/strategies/{strategy_id}/variations
/api/workspace/strategies/{strategy_id}/variations/{variation_id}
/api/workspace/strategies/{strategy_id}/variations/{variation_id}/clone
/api/workspace/strategies/{strategy_id}/experiments
/api/workspace/strategies/{strategy_id}/comparison
```

## 4. Browser workflow evidence

Executed against the real local services:

1. Sidebar **Strategy Workspace** → list heading and 3 seeded cards.
2. Search `Liquidity` → 1 result; clear → 3.
3. Open **Liquidity Sweep** → context bar, baseline, six tabs.
4. Notes → add note; persisted.
5. Variations → create **V2 — E2E Variation** (EURUSD/M1); variation count 2.
6. Run on V2 → Strategy Lab opened with workspace banner, strategy `S008`, lookback `10`.
7. Existing kernel run completed; run archived.
8. Return to workspace → Experiments tab shows the V2 experiment with the actual run ID and metrics. No console/page/network errors.

E2E output:

```
list_heading=Keep the hypothesis, before the result.
cards=3
search_results=1
detail_heading=Liquidity Sweep
tab_Overview_visible=true ... tab_Comparison_visible=true
experiment_rows=1
has_run_link=true
console_errors=0
```

Empty/error states:

```
empty_search_cards=0
empty_title=Start with a hypothesis
empty_copy=Create a strategy record, document its rules, and add variations...
error_title=The research service did not answer
error_copy=Failed to fetch
```

Evidence: `EVIDENCE/e2e-states.log`, `EVIDENCE/empty-search.png`, `EVIDENCE/error-state.png`.

## 5. HTTP API smoke

A fresh isolated uvicorn instance (`REX_WORKSPACE_FILE` / `REX_RUNS_DIR` temp) verified:

- seeded list = 3 real strategies;
- create documentation-only strategy = `documentation_only`;
- GET detail = seeded S008 with one baseline;
- POST real existing run `20261103T144626Z_57dd08ff` → linked count 1, 1,316 actual trades;
- missing run → HTTP 400 `Backtest run is unavailable`;
- linked-run detail returns 1 experiment.

Evidence: `EVIDENCE/http-api-smoke.log`.

## 6. Integration and safety checks

- Run association uses the actual run artifact; no run is created by the workspace.
- Wrong-strategy run, missing run and duplicate run are rejected.
- Baseline edit after experiment returns a conflict; clone creates a separate variation.
- Documentation-only variations cannot run or receive experiments.
- Archived variations cannot receive new experiments.
- Parameter names/types/ranges are validated against the registered strategy.
- Experiment result snapshots contain actual metrics, warnings and assumptions; missing run files are flagged.
- Existing `BacktestRunner`, `execution/`, risk calculations, strategy logic and historical data were not modified.

## 7. Known gaps and limitations

- No authentication/multi-user ownership; local single-user terminal.
- JSON store is process-locked, not a multi-process database.
- No automated browser test was added to the repository test runner; Playwright evidence is retained under `EVIDENCE/` and the UI flows were executed manually by the QA harness. Backend behavior is covered by 12 automated tests.
- Comparison requires exact dataset/instrument/timeframe/start/end equality; no overlap inference.
- Out-of-sample is a user-declared kind, not an automatic statistical test.
- No cost-adjusted results; the linked example run is gross/cost-free.
- Existing QA findings (execution risk sizing, ambiguity gap, CORE signal semantics, etc.) remain outside this additive feature and were not changed.

## 8. Verdict

**Feature acceptance: PASS for the implemented scope.** The workspace is additive, backward-compatible, persists research data, supports isolated variations, links only real runs, and preserves the existing Strategy Lab/BacktestRunner path.
