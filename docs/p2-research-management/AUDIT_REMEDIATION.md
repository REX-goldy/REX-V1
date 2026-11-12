# P2.1 — Audit Remediation Report

- **Date:** 2026-11-03
- **Audit source:** `AUDIT.md` (kept intact; verdict at audit time was FAIL)
- **Scope:** remediation of AUD-001 through AUD-009. No P3–P6 work.
- **Safety:** historical CSVs/meta, existing run artifacts and existing completed experiment records were not rewritten. No commit, push or deploy.

## Gate A — Historical Integrity and Reproducibility

### A1 — Zone provenance (AUD-001): PASS

Implemented:

- ordinary zone creation uses server-generated `created_at`;
- supplying `created_at` is rejected;
- ordinary zones cannot have `effective_timestamp < created_at`;
- backdated ordinary zones are rejected;
- a distinct audited historical-import path requires `historical_import`, `import_source`, `import_operator`, and stores server `imported_at` plus original effective timestamp;
- historical imports are marked `provenance=historical_import` and are distinguishable;
- `build_zone_books` excludes ordinary manual zones whose effective time predates their creation;
- legacy config zones remain static/read-only.

Affected files: `server/zone_store.py`, `server/main.py`, `frontend/src/pages/ZoneManagerPage.tsx`, `frontend/src/types.ts`.

Regression tests: `tests/test_p2_zones.py` — backdated rejection, `created_at` rejection, historical import, temporal filtering.

### A2 — Immutable experiment snapshots (AUD-002/AUD-005/AUD-009): PASS

Completed experiments now snapshot:

- strategy ID and full strategy definition/rules;
- variation ID and full variation snapshot;
- strategy/variation configuration versions;
- dataset ID, SHA-256, provider, symbol, timeframe, coverage, metadata and quality;
- exact zone IDs, zone versions and full zone snapshot data;
- cost profile ID and resolved parameters;
- execution policy/sizing assumptions;
- risk configuration;
- backtest parameters;
- model/schema versions;
- run ID and independent validation reference.

Affected files: `server/strategy_workspace.py`.

### A3 — Version-pinned reproduction (AUD-002/AUD-009): PASS

New endpoint:

```text
POST /api/workspace/strategies/{strategy_id}/experiments/{experiment_id}/reproduce
```

Flow:

1. load the immutable snapshot;
2. verify dataset SHA-256;
3. resolve zone IDs/versions from snapshot data;
4. resolve the strategy/variation snapshot and verify strategy rules/registry compatibility;
5. resolve saved cost profile and execution/risk assumptions;
6. check model versions;
7. execute through the existing `BacktestRunner` (`run_backtest` with zone/cost overrides);
8. write a new run and append a reproduction record;
9. compare original/reproduced metrics.

Structured failures include `SNAPSHOT_MISSING`, `MODEL_VERSION_INCOMPATIBLE`, `DATASET_HASH_MISMATCH`, `ZONE_SNAPSHOT_INCOMPLETE`, `COST_SNAPSHOT_INVALID`, `STRATEGY_DEFINITION_CHANGED`, `REPRODUCTION_EXECUTION_FAILED`.

The original experiment/run is not modified; reproduction records are append-only.

Regression tests: `tests/test_p2_reproduction.py` — reproduction after zone edit, reproduction after variation edit, dataset hash mismatch, model-version mismatch.

**Legacy limitation:** experiments created before this remediation do not have snapshots. They are preserved but reproduction returns structured `SNAPSHOT_MISSING`; they cannot be made exactly reproducible without inventing historical data.

## Gate B — Experiment Integrity

### B1 — Completion requirements (AUD-003): PASS

`Completed` requires a run ID, result reference and `validation_status=passed`. `update_experiment` rejects invalid transitions at service/API level. `record_experiment` records `Failed` if independent validation fails, not `Completed`.

Tests: `test_completed_requires_run_and_validation`.

### B2 — Completed immutability and amendments (AUD-004): PASS

Direct mutation of completed narrative fields is rejected. Append-only amendments are implemented:

```text
POST /api/workspace/strategies/{strategy_id}/experiments/{experiment_id}/amendments
```

Amendments include ID, experiment ID, timestamp, author/source, field, previous value, new value and reason. Original completed values remain unchanged.

Tests: `test_completed_narrative_requires_amendment`.

### B3 — Referential integrity (AUD-006): PASS

`_zone_snapshots` now validates every selected zone ID, rejects archived zones and raises structured `WorkspaceValidationError` for missing zones. Planned experiments use the same check.

Tests: `test_missing_zone_reference_is_rejected`.

## Gate C — Persistence Reliability

### C1 — Multi-process safety (AUD-007): PASS

Added `server/file_lock.py` using `fcntl.flock`; workspace and zone public read-modify-write operations are guarded. Nested calls are re-entrant. The model is documented as single JSON-store, multi-process-safe on POSIX; Windows/non-fcntl falls back to process-local locking.

Tests: `tests/test_p2_persistence.py::test_two_processes_do_not_lose_zone_updates`.

### C2 — Backup and recovery (AUD-008): PASS

JSON writes now:

- keep a last-known-good `.bak` copy after each successful write;
- preserve a corrupt file as `.corrupt-<timestamp>` before recovery;
- validate a backup's JSON/version/structure before restoring it;
- never replace corrupt data with an empty default;
- fail closed if no valid backup exists.

Tests: `test_zone_backup_recovers_corrupt_file`, `test_workspace_backup_recovers_corrupt_file`.

## AUD finding mapping

| Finding | Status | Implementation | Regression test |
|---|---|---|---|
| AUD-001 | Resolved | `server/zone_store.py` created_at/import rules; ZoneManager import fields | `test_p2_zones.py` |
| AUD-002 | Resolved | snapshot + version-pinned reproduction | `test_p2_reproduction.py` |
| AUD-003 | Resolved | completion invariant | `test_p2_experiments.py` |
| AUD-004 | Resolved | completed lock + amendments | `test_p2_experiments.py` |
| AUD-005 | Resolved | strategy/variation/dataset/model snapshots | `test_p2_reproduction.py`, `test_p2_experiments.py` |
| AUD-006 | Resolved | strict zone reference validation | `test_p2_experiments.py` |
| AUD-007 | Resolved | `server/file_lock.py` | `test_p2_persistence.py` |
| AUD-008 | Resolved | backup/corrupt-recovery | `test_p2_persistence.py` |
| AUD-009 | Resolved | dataset hash verification in reproduction | `test_p2_reproduction.py` |
| AUD-010 | Accepted limitation | legacy config zones static/read-only; external edits unversioned | documented |
| AUD-011 | Accepted limitation | Planned/Running API support; primary UI records completed runs | documented |
| AUD-012 | Accepted limitation | draw + exact boundary edit; no resize handles | documented |

## Test results

| Check | Result |
|---|---|
| Full backend suite | **650 / 650 PASS** |
| P0/P1 regression | **35 / 35 PASS** |
| P2 remediation/regression | **22 / 22 PASS** |
| Lint | PASS |
| Frontend build | PASS |
| Browser | reproduction and amendment actions exercised; zone draw verified; 0 console errors |
| Dataset hashes | unchanged |
| Existing run artifacts | not rewritten |

Evidence: `EVIDENCE/remediation/` and `EVIDENCE/audit/`.

## Known limitations

- Pre-remediation experiments have no snapshots and return a structured failure rather than being silently reproduced against current state.
- Historical imports require explicit source/operator provenance; legacy backdated manual zones are excluded from historical runs.
- The JSON store remains a single-file design; cross-process locking is POSIX-only.
- No P3–P6 features.

## Final verdict

**PASS WITH LEGACY LIMITATION** for P2.1 remediation: all High/Medium audit findings are addressed for new experiments; legacy pre-remediation records are preserved but explicitly non-reproducible. The original P2 audit verdict remains recorded in `AUDIT.md`.
