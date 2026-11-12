# P2 Implementation

## Strategy workspace

`server/strategy_workspace.py` now exposes:

- strategy metadata: `trading_concept`, `risk_assumptions`;
- variations with `zone_ids` and immutable configuration versions;
- experiment statuses and traceability fields;
- planned experiment creation and status/notes updates;
- dashboard aggregation.

Existing CRUD, notes, baseline lock, clone/version and run association remain.

## Experiments

`POST .../experiments` links a real run and records:

- `dataset_hash` (SHA-256 of the source CSV);
- `status=Completed`, `created_at`, `completed_at`;
- gross `metrics`, `net_metrics`, cost profile and validation result;
- risk/execution configuration;
- research objective, expected/actual outcome, hypothesis supported, next steps;
- zone IDs and zone version snapshots.

`POST .../experiments/plan` creates a planned experiment without inventing a run.
`PATCH .../experiments/{id}` supports Planned/Running/Completed/Failed/Archived and notes/outcome fields. Completed results cannot be reopened; archive is allowed.
`DELETE .../experiments/{id}` archives.

Run association still goes through the existing UI workflow and BacktestRunner. No synthetic run is created.

## Zone Manager

`server/zone_store.py`:

- atomic JSON store, mode 0600, process lock;
- create/list/get/update/archive;
- append-only version history;
- validation of dataset ID, timeframe, bounds, type, status, strength, timestamps;
- legacy `config/zones.json` entries exposed read-only;
- temporal `build_zone_books(start, end, zone_ids)` used by `research_service`.

The frontend `ZoneManagerPage.tsx`:

- dataset selector and last 1,500-bar candlestick chart;
- draw mode with pointer-drag rectangles and a click-to-create fallback;
- overlay zones by type and time;
- create/edit form with exact bounds, effective/invalidation timestamps, strength, notes, strategy/variation association;
- archive and version display.

## Backtest integration

`service.run_backtest(..., zone_ids=...)` builds a `ZoneBook` from the temporal zone store. Variation preset passes `zone_ids` through Strategy Lab; preflight validates the zone requirement using selected/all available zones.

## Dashboard and comparison

- `/api/workspace/dashboard` reads strategies, variations, experiment statuses, recent experiments/runs and dataset warnings.
- Workspace list displays the real dashboard.
- Comparison groups exact dataset/instrument/timeframe/start/end and adds net expectancy, net total R, cost R and validation status.

## API additions

See `ARCHITECTURE.md` for the endpoint table.

## Files changed

Backend:
- `server/strategy_workspace.py`
- `server/zone_store.py` (new)
- `server/main.py`
- `server/research_service.py`
- `server/preflight.py`
- `config/zones.json` remains unchanged.

Frontend:
- `frontend/src/pages/ZoneManagerPage.tsx` (new)
- `StrategyWorkspacePage.tsx`, `ResearchPage.tsx`
- `App.tsx`, `components/AppShell.tsx`
- `types.ts`, `api.ts`, `styles/global.css`

Tests:
- `tests/test_p2_zones.py`
- `tests/test_p2_experiments.py`
- `tests/test_p2_api.py`
- route contract updates.

## Dependencies / database

- No new third-party dependencies.
- No database migration.
- New runtime JSON file for manual zones; volume-backed through the existing workspace data path.

## Limitations

- Zone temporal behavior is conservative: effective before start and not invalidated before end. Per-bar activation/invalidation is not dynamically fed into strategies.
- Drag creates; editing uses boundary fields. Resize handles are not implemented.
- Normal UI workflow creates completed experiments; planned/running states are available through API and model.
- Account-currency P&L remains unsupported.
- No P3–P6 functionality.

## P2.1 Integrity Remediation

- `server/file_lock.py` — fcntl-backed cross-process locking with re-entrant nested calls.
- `server/zone_store.py` — server `created_at`, backdate rejection, audited historical imports, strict zone references, `.bak`/corrupt recovery.
- `server/strategy_workspace.py` — immutable experiment snapshots, version-pinned reproduction, completion invariant, append-only amendments, strict zone validation, repaired legacy fields.
- `server/research_service.py` — accepts preserved zone-book and cost-profile overrides from reproduction; still the sole BacktestRunner path.
- `server/main.py` — reproduction/amendment endpoints and zone import fields.
- `frontend/src/pages/ZoneManagerPage.tsx` — historical import controls; draw workflow.
- `frontend/src/pages/StrategyWorkspacePage.tsx` — Reproduce/Amend actions.
- `frontend/src/api.ts`, `types.ts` — reproduction/amendment/zone provenance contracts.

No new dependencies, no database.
