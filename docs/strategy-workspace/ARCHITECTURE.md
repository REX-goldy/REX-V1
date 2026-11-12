# Strategy Workspace — Architecture

- **Feature:** additive strategy research management
- **Status:** implemented locally; no deploy/commit performed
- **Runtime:** FastAPI + React/Vite, one JSON workspace store
- **Existing execution path:** unchanged (`BacktestRunner`)

## 1. Why this layer exists

REX already had:

- a strategy registry (`CORE_ZONE_BREAKOUT`, `S002`, `S008`);
- Strategy Lab for one-off causal replay;
- a Run Archive of immutable `ui_run_v1` JSON artifacts.

It did **not** have a durable research-management layer between the registry and the lab. Registry IDs identify **implemented code**, not user research projects, hypotheses or variations. This feature adds that layer without turning documentation into execution.

```
Registry implementation  ──►  Strategy record  ──►  Variation  ──►  Experiment  ──►  immutable run artifact
      (code)                  (research identity)     (config)        (link)            (BacktestRunner output)
```

A strategy record may be:

- **implemented**: linked to a registry strategy and able to launch the lab;
- **documentation-only**: no executable implementation, no Run Experiment action.

A documentation-only record cannot become executable by merely creating text fields.

## 2. Layers

| Layer | Location | Responsibility |
|---|---|---|
| Domain/store | `server/strategy_workspace.py` | Model, validation, seeding, atomic persistence, experiment linking |
| HTTP API | `server/main.py` | `/api/workspace/*` additive routes and error mapping |
| Frontend API | `frontend/src/api.ts` | Typed workspace calls |
| Frontend page | `frontend/src/pages/StrategyWorkspacePage.tsx` | List, detail, rules, notes, variations, experiments, comparison |
| Navigation | `frontend/src/components/AppShell.tsx`, `frontend/src/App.tsx` | New Strategy Workspace section and lab preset handoff |
| Lab integration | `frontend/src/pages/ResearchPage.tsx` | Preselection banner, preset parameters, post-run experiment link |
| Persistence | `data/workspace/strategy_workspace.json` | Versioned JSON store, 0600, atomic replace |

## 3. Request flow

### Workspace list

1. `GET /api/workspace/strategies` loads the store.
2. If the store is absent, the service writes `WORKSPACE_VERSION = 1` and seeds the three **actual** registered strategies with one baseline variation each.
3. The response is a summary (card fields only). Experiment metrics are only from real linked runs.

### Detail

`GET /api/workspace/strategies/{id}` returns the strategy plus:

- implemented/proposed/experimental rules;
- persistent notes;
- variations with parameter snapshots and versions;
- experiments with run references and actual result snapshots;
- comparable comparison groups.

### Run Experiment

```
Workspace variation
  → App stores WorkspaceRunPreset
  → page = research
  → ResearchPage preselects registry strategy + parameter snapshot
  → user chooses dataset/instrument/timeframe/date range
  → existing POST /api/backtests
  → BacktestRunner archives run
  → POST /api/workspace/strategies/{id}/experiments {variation_id, run_id}
  → workspace validates the run's strategy and variation constraints
  → experiment stores the run reference and actual metrics snapshot
```

The workspace **never** calls `BacktestRunner` itself and **never** creates a `ui_run` artifact. It only links an existing run after the normal API path succeeds.

### Comparison

`GET /api/workspace/strategies/{id}/comparison` groups experiments by:

```
(dataset_id, instrument, timeframe, start_date, end_date)
```

A group is returned only when at least two distinct variations have experiments in it. The UI shows the group header and does not rank rows. Missing metrics remain `null`/unavailable. Sample-size warnings are derived from actual trade counts.

## 4. Baseline and immutability rules

- Every strategy has exactly one `is_baseline: true` variation.
- A baseline can be edited before its first experiment.
- After its first experiment, `PATCH /variations/{id}` returns **409** and the UI disables Edit.
- The explicit versioned path is **Clone**: create a new variation with its own ID and `cloned_from` reference. The baseline is never overwritten.
- The baseline cannot be archived.
- Experiments are append-only. There is no delete endpoint; the `delete_experiment` implementation intentionally raises a conflict.
- Strategy and variation removal is archival (`status=Archived`), never hard deletion of run history.

## 5. Integration guarantees

- Existing Strategy Lab remains available and unchanged when no workspace preset is present.
- Strategy selection change clears the workspace context so a run cannot be linked accidentally to a different strategy.
- The workspace validates:
  - `run.strategy.id == strategy.registry_strategy_id`;
  - variation is `implemented`, not `Archived`;
  - run instrument/timeframe are allowed by the variation when those lists are non-empty;
  - the same run is not linked twice.
- Run archive files remain the source of truth; the workspace stores a reference plus a snapshot of actual metrics.
- No existing strategy logic, `BacktestRunner`, execution/risk code or historical data was modified.

## 6. API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/workspace/strategies` | Search/filter/sort summaries |
| POST | `/api/workspace/strategies` | Create record + baseline variation |
| GET | `/api/workspace/strategies/{id}` | Full detail |
| PATCH | `/api/workspace/strategies/{id}` | Edit documentation/status/rules |
| DELETE | `/api/workspace/strategies/{id}` | Archive |
| POST | `/api/workspace/strategies/{id}/notes` | Add note |
| PATCH | `/api/workspace/strategies/{id}/notes/{note_id}` | Edit note |
| DELETE | `/api/workspace/strategies/{id}/notes/{note_id}` | Delete note |
| POST | `/api/workspace/strategies/{id}/variations` | Create variation |
| PATCH | `/api/workspace/strategies/{id}/variations/{vid}` | Edit variation |
| DELETE | `/api/workspace/strategies/{id}/variations/{vid}` | Archive variation |
| POST | `/api/workspace/strategies/{id}/variations/{vid}/clone` | Versioned copy |
| POST | `/api/workspace/strategies/{id}/experiments` | Link existing run |
| GET | `/api/workspace/strategies/{id}/comparison` | Comparable groups |

## 7. Failure and safety behavior

- Duplicate non-archived title → **409**.
- Unknown strategy/variation/note → **404**.
- Invalid status/parameter/timeframe/date/run → **400**.
- Baseline edit after experiments → **409**.
- Documentation-only variation run/link → **409**.
- Missing or wrong-strategy run → **400**.
- Corrupt/unsupported workspace JSON → **500** with no silent reset.
- Atomic write via temp file + `os.replace`; store mode `0600`; process `RLock`.
- The workspace file is gitignored and excluded from Docker build context; a compose volume preserves it at `/app/data/workspace`.

## 8. Known limitations

- Single-user local terminal: no authentication or multi-user ownership.
- JSON storage, not a database; writes are serialized in-process. Multi-process writers beyond one uvicorn process are not coordinated.
- No automatic migration beyond version validation; a future schema version must add an explicit migration.
- Comparison does not infer comparability from date overlap; it requires exact dataset/instrument/timeframe/start/end equality.
- Out-of-sample marking is user-declared, not statistically detected.
- A strategy's “latest experiment” is a reference summary, not a freshness guarantee; the linked run's availability is checked.
- No real provider downloads or paid requests were used.
