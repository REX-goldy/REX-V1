# P2 Independent Audit — Strategy Workspace, Experiments and Zones

- **Date:** 2026-11-03
- **Scope:** read-only audit of the completed P2 implementation
- **Commit/worktree:** `95f8aaa` plus the uncommitted P0/P1/P2 working tree
- **Constraints:** no code, dataset, run-artifact or completed-experiment changes made during this audit. No commit, push or deploy.
- **Verdict:** **FAIL** for the stated P2 completion criteria. Two High findings affect temporal integrity and reproducibility. The implementation is functional, but it is not yet safe to treat historical experiments as fully reproducible.

## 1. Audit Scope

Reviewed:

- `server/zone_store.py`
- `server/strategy_workspace.py`
- `server/research_service.py`
- `server/preflight.py`
- `server/main.py`
- `server/zone_store.py` / `config/zones.json` legacy path
- Strategy Lab and Strategy Workspace / Zone Manager UI
- P0/P1 execution and cost contracts
- JSON persistence and run archive integration

Reproduction harnesses and logs are in `docs/p2-research-management/EVIDENCE/audit/`.

## 2. Findings

| ID | Severity | Finding | Affected area |
|---|---|---|---|
| AUD-001 | **High** | A zone created after a historical period can still influence that backtest via a backdated `effective_timestamp`. | `server/zone_store.py::build_zone_books` |
| AUD-002 | **High** | Historical zone versions are snapshotted but not used for reproduction; re-runs use the current/latest zone record. | `strategy_workspace`, `research_service`, `zone_store` |
| AUD-003 | Medium | A planned experiment can be marked Completed with no linked run. | `strategy_workspace.update_experiment` |
| AUD-004 | Medium | Completed experiment narrative fields can be modified through the update API. | `strategy_workspace.update_experiment` |
| AUD-005 | Medium | Experiment snapshots do not contain strategy/variation rule definitions, code/fill-model versions, or a reproduce endpoint. | `strategy_workspace`, `research_service` |
| AUD-006 | Low | Missing zone IDs are silently dropped from experiment snapshots; referential integrity is not enforced. | `strategy_workspace._zone_snapshots` |
| AUD-007 | Low | JSON read-modify-write is only process-locked; multi-process/uvicorn workers can lose updates. | `strategy_workspace`, `zone_store` |
| AUD-008 | Low | Corrupt stores fail closed, but there is no backup/automatic recovery. | JSON stores |
| AUD-009 | Low | Dataset hash is recorded but not verified on reproduction; dataset metadata is not snapshotted. | experiments / datasets |
| AUD-010 | Informational | Legacy `config/zones.json` zones remain static/read-only; external edits to that file change future runs without zone-store versioning. | legacy zone path |
| AUD-011 | Informational | Planned/Running statuses are API/model-supported, but the primary UI workflow records Completed experiments. | UI |
| AUD-012 | Informational | Zone rectangle creation and exact boundary editing work; resize handles are not implemented. | Zone Manager UI |

No Critical credential or data-corruption defect was found. The High findings are research-integrity defects, not execution-engine crashes.

## 3. Evidence and Reproduction

### AUD-001 — Created-after-period zone included

**Evidence:** `EVIDENCE/audit/zone-temporal.log`

```text
created_after_period_included current_created=2026-11-03T17:40:14Z run_start=2026-01-15
```

A zone created now with `effective_timestamp=2026-01-01` was included in a synthetic January 2026 run. `build_zone_books` checks `effective_timestamp`, status and invalidation, but never compares `created_at` with the simulated range.

**Reproduction:**

```bash
PYTHONPATH=. python docs/p2-research-management/EVIDENCE/audit/zone_audit.py
```

**Expected:** a zone created after the historical period cannot influence that backtest unless an explicit, audited historical-import process overrides it.

**Actual:** the user can backdate `effective_timestamp` in the Zone Manager and the zone is included.

**Affected files:** `server/zone_store.py`, `frontend/src/pages/ZoneManagerPage.tsx`.

**Recommended remediation:** distinguish imported historical zones from newly created annotations; require a provenance/approval flag for backdated zones, or enforce `created_at <= run_start` (and document the import workflow). Do not fix in this audit.

### AUD-002 — Historical zone versions not used for reproduction

**Evidence:** `EVIDENCE/audit/experiment-immutability.log`

```text
ZONE_SNAPSHOTS [{"id": "...", "version": 1, "low": 1.1, "high": 1.11, ...}]
ZONE_VERSION_AFTER_EDIT 2 1.12 1.13
EXPERIMENT_ZONE_AFTER_EDIT [{"version": 1, "low": 1.1, "high": 1.11, ...}]
ZONE_SNAPSHOT_USED_BY_RUN False
HAS_REPRODUCE_ENDPOINT False
```

The experiment preserves the old zone snapshot, but `run_backtest` accepts only `zone_ids` and rebuilds from the current zone store. There is no reproduction endpoint or zone-version-pinned path. After editing or archiving a zone, an old experiment cannot be recreated with its exact zone geometry.

**Affected files:** `server/strategy_workspace.py::_zone_snapshots`, `server/research_service.py::_zone_books` / `run_backtest`, `server/zone_store.py::build_zone_books`, Strategy Lab preset.

**Recommended remediation:** add an explicit experiment reproduction API that accepts the stored snapshot (zone IDs + versions), validates dataset hash, and runs the existing engine with pinned zone records. Or mark experiments as non-reproducible until this exists.

### AUD-003 — Completed without a run

**Evidence:** `EVIDENCE/audit/completed-without-run.log`

```text
completed_without_run Completed None None
```

`update_experiment` accepts `status: Completed` for a Planned experiment without `run_id`, result reference or validation.

**Expected:** Completed requires a linked run and completed result; otherwise use Failed/Archived or remain Planned/Running.

**Affected files:** `server/strategy_workspace.py::update_experiment`, `server/main.py` PATCH route.

**Recommended remediation:** enforce invariant `status == Completed => run_id and result_reference and validation_status present`; reject API transitions that violate it.

### AUD-004 — Completed narrative mutable

**Evidence:** `EVIDENCE/audit/experiment-immutability.log`

```text
COMPLETED_MUTABLE_FIELDS AUDIT mutation AUDIT outcome True
```

The PATCH API allows `notes`, `actual_outcome`, `hypothesis_supported` and `next_steps` after Completed. The run/result/config snapshot is unchanged, but research traceability is mutable without an amendment history.

**Expected:** completed experiment results and traceability are immutable; corrections should be append-only/versioned.

**Actual:** narrative fields can be changed directly.

**Recommended remediation:** lock completed experiments, or add an explicit amendment record with timestamp/author/reason rather than mutating the original.

### AUD-005 — Snapshot insufficient for full reproduction

The experiment stores IDs, parameters, cost profile, risk config, zone snapshots, result metrics and run ID. It does **not** store:

- strategy rule definitions (only `registry_strategy_id`);
- full variation definition (only ID/version/parameters/zone IDs; hypothesis/rule differences/description are not snapshotted);
- code commit/version, fill-model version, or cost-model code version;
- dataset metadata snapshot (hash is stored, but metadata is not);
- a reproduction endpoint.

The `configuration` fields from the audit are:

```text
registry_strategy_id, variation_id, variation_version, parameters, zone_ids,
zone_snapshots, r_multiple, equity, risk_fraction, entry_model
```

`HAS_REPRODUCE_ENDPOINT False`; `ZONE_SNAPSHOT_USED_BY_RUN False`.

**Recommendation:** snapshot strategy/variation definitions and code/model versions, validate dataset hash and zone versions, and add one reproduce endpoint that uses the existing `BacktestRunner`.

### AUD-006 — Missing zone references silently dropped

**Evidence:** `EVIDENCE/audit/persistence.log`

```text
missing_zone_snapshot_result []
```

`_zone_snapshots` catches missing/read-only zone IDs and continues. A completed experiment can therefore have fewer zone snapshots than requested, without an error.

**Recommendation:** validate every selected zone ID/version before recording an experiment; fail with a structured error.

### AUD-007 — Multi-process write risk

Both workspace and zone stores use a process-local `RLock`, atomic temp-file + `os.replace`, and `0600`. A single-process write is safe. Two uvicorn workers can read the same JSON, modify, and replace, losing the other update.

**Evidence:** `EVIDENCE/audit/persistence.log` shows single-process thread writes are valid JSON and clean; no multi-process coordination exists.

**Recommendation:** run one worker or add a filesystem lock/relational store before multi-worker operation. This is a documented single-user limitation, not a crash.

### AUD-008 — Corrupt/partial file recovery

`EVIDENCE/audit/persistence.log` shows corrupt workspace fails closed (`WorkspaceStoreError`). Existing files are not overwritten by a failed read, but there is no backup, recovery journal or automatic restore. A partially written temp file is cleaned; the atomic replace protects against torn final files. Manual recovery is required.

**Recommendation:** document backup/restore; add timestamped backups before migrations; consider a startup validation/recovery command.

### AUD-009 — Dataset hash not verified on reproduction

`dataset_hash` is recorded from the current CSV, but no reproduction path compares it with the file and dataset metadata is not snapshotted. If a data file changes, an experiment cannot be safely reconstructed.

**Recommendation:** validate dataset hash and metadata before any reproduce action; block or explicitly flag changed data.

### AUD-010 — Legacy config zones

`config/zones.json` is loaded as static legacy zones; it is intentionally read-only through the API/UI. External edits to the file change future runs without zone-store versioning. This is documented behavior, but it is not a complete migration for historical reproducibility.

### AUD-011 / AUD-012 — Coverage notes

- Planned/Running statuses are represented and API-supported; the primary UI flow records completed runs. A dedicated planned-experiment UI is not implemented.
- Zone drawing and exact-boundary editing work; resize handles are not implemented. This is a UX limitation, not a data-integrity failure.

## 4. Baseline / Variation / Experiment Integrity

Verified PASS:

- baseline cannot be edited after its first experiment (`BASELINE_UPDATE_ALLOWED False`, `WorkspaceConflict`);
- baseline cannot be archived;
- clone creates a separate variation with `cloned_from` and independent config;
- variation edit does not mutate an existing experiment configuration (`variation_edit_mutated_experiment False`);
- archiving a variation preserves its experiment/run reference;
- strategy edits do not mutate experiment configuration snapshots;
- duplicate run links and missing/wrong-strategy runs are rejected;
- completed experiment `run_id`, gross/net, cost, validation and configuration fields are not modified by narrative PATCH.

Failed/partial:

- completed can be marked without run (AUD-003);
- completed narrative mutable (AUD-004);
- full strategy/variation/code snapshot missing (AUD-005).

## 5. Temporal Zone Checks

Verified PASS:

- future-effective zone excluded from an earlier run;
- zone invalidated during a run excluded under conservative policy;
- selected future zone ID cannot bypass temporal filtering;
- legacy config zones remain available when no zone selection is made;
- aware/naive UTC comparisons behaved consistently in synthetic checks.

Failed:

- zone created after the period but backdated effective date included (AUD-001).
- exact historical zone versions not used on reproduction (AUD-002).

## 6. Persistence

Verified PASS:

- JSON writes use temp file + `fsync` + `os.replace`;
- workspace/zone files are `0600`;
- corrupt store fails closed instead of being silently overwritten;
- IDs are stable; zone versions increment; history appended;
- eight concurrent threads produced valid JSON under the process lock.

Limitations/failures:

- multi-process lost-update risk;
- no automatic backup/recovery;
- missing-zone snapshot references are silently skipped;
- legacy config is outside the versioned zone store.

## 7. Test Results

| Check | Result | Evidence |
|---|---|---|
| Full backend suite | **637 / 637 PASS** | `EVIDENCE/audit/tests-full.log` |
| P0/P1 targeted regression | **35 / 35 PASS** | `EVIDENCE/audit/p0-p1-regression.log` |
| P2 targeted tests | **9 / 9 PASS** | `EVIDENCE/audit/p2-tests.log` |
| Lint | PASS | `EVIDENCE/audit/lint.log` |
| Frontend typecheck/build | PASS (non-fatal chunk-size advisory) | `EVIDENCE/audit/frontend-build.log` |
| Browser workflow | Dashboard, experiments, gross/net, validation, zone chart, 12 zone rows; 0 console errors | `EVIDENCE/audit/ui.log` |
| Historical hashes | unchanged | P0 hash baseline |
| Run artifacts | not rewritten | audit constraint |

Tests currently do not cover AUD-001/AUD-002/AUD-003/AUD-004/AUD-005; passing tests do not prove P2 completion criteria.

## 8. Recommended Remediation (no changes made)

1. **High:** enforce zone creation/provenance time against the run period or add an audited historical-import workflow.
2. **High:** pin and use exact zone version snapshots in an experiment reproduction API.
3. **Medium:** enforce Completed ⇒ valid run/result/validation invariant.
4. **Medium:** make completed experiment narrative immutable or amendment-based.
5. **Medium:** snapshot strategy/variation definitions, code/fill/cost model versions and dataset metadata; add reproduce endpoint.
6. **Low:** validate all selected zone IDs and snapshots before completion.
7. **Low:** single-worker or file-lock coordination; add JSON backup/recovery.
8. **Low:** verify dataset hash and metadata before reproduction.

## 9. Data Integrity

- No historical CSV/meta was modified.
- No existing run artifact was rewritten.
- Audit scripts used temporary workspace/zone/run roots except for read-only UI checks.
- The live workspace was only read/verified; no completed experiment was changed by the audit.

## 10. Final Verdict

# FAIL

P2 is functionally implemented and test-covered, but it does not meet two explicit P2 integrity criteria:

1. a zone created after a historical period can influence that backtest via a backdated effective timestamp;
2. historical zone versions are stored but cannot be used to reproduce an experiment because the run path uses current zone state.

Completed experiments can also be marked Completed without a run and their narrative fields can be mutated. These are research-traceability defects, not P0/P1 execution regressions.

**P0/P1 remain stable: 637 tests pass, lint and frontend build pass, and historical data hashes are unchanged.**
