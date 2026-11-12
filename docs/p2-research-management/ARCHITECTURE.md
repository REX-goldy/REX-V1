# P2 Architecture

```
Strategy Workspace (JSON)
  ├─ Strategy metadata / rules / notes
  ├─ Variations (versioned configuration snapshots, baseline)
  ├─ Experiments (planned/running/completed/failed/archived)
  │    └─ immutable run reference + gross/net/validation/cost snapshots
  └─ Zone IDs
Manual Zone Store (JSON)
  ├─ versioned zone snapshots
  └─ temporal availability

Strategy Lab
  → preflight (P1)
  → BacktestRunner (single execution path)
  → run archive
  → workspace experiment link

Zone Manager
  → lightweight-charts candles + rectangle overlays
  → versioned zone store
  → temporal ZoneBooks for BacktestRunner
```

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/workspace/dashboard` | Real research summary |
| GET/POST | `/api/workspace/strategies` | List/create strategies |
| GET/PATCH/DELETE | `/api/workspace/strategies/{id}` | Detail/update/archive |
| POST/PATCH/DELETE | `/api/workspace/strategies/{id}/notes...` | Notes |
| POST/PATCH/DELETE | `/api/workspace/strategies/{id}/variations...` | Variations |
| POST | `.../experiments` | Link completed run |
| POST | `.../experiments/plan` | Planned experiment |
| PATCH/DELETE | `.../experiments/{experiment_id}` | Status/notes/archive |
| GET | `/api/zones` | Manual + legacy zones |
| POST | `/api/zones` | Create manual zone |
| GET/PATCH/DELETE | `/api/zones/{id}` | Detail/new version/archive |

## Zone temporal rule

`build_zone_books(start, end, zone_ids)` includes manual zones only when:

- status is `active`;
- `effective_timestamp <= run_start`;
- `invalidation_timestamp` is absent or after run end.

Legacy `config/zones.json` zones remain static and available. Selected zone IDs restrict the run to those manual zones. This is conservative and prevents future/invalidated zones from leaking into a run.

## Experiment traceability

A completed experiment records:

- exact run ID and dataset hash;
- variation ID and configuration version;
- parameter, risk and execution snapshots;
- cost profile and assumptions;
- gross metrics, net metrics, validation status/findings summary;
- hypothesis, objective, expected/actual outcome, supported flag, next steps;
- timestamps and status.

Zone versions used by an experiment are snapshotted in its configuration (`zone_snapshots`). Updating a zone appends a new version rather than overwriting history.

## P2.1 Remediation Additions

- Ordinary zones are server-timestamped and cannot be effective before creation. Historical imports are a distinct provenance path with source/operator/import timestamp.
- `build_zone_books` excludes legacy/backdated ordinary annotations from historical runs; imports remain available.
- Completed experiment snapshots include strategy rules, variation definition, dataset hash/metadata, zone versions/data, cost profile, execution/risk assumptions, model versions and validation reference.
- Reproduction is a new endpoint that resolves the snapshot, verifies dataset hash/model compatibility, builds zone books from snapshot data, runs the existing `BacktestRunner`, appends a reproduction record and compares outputs.
- Completed experiment records are immutable; narrative corrections use append-only amendments.
- JSON stores use a POSIX cross-process file lock plus `.bak`/`.corrupt-*` recovery.
