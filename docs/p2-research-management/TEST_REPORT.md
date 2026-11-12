# P2 Test Report

- **Date:** 2026-11-03
- **Full backend suite:** **650 / 650 PASS** (637 at P2 delivery; P2.1 remediation added 13 tests)
- **P2-specific tests:** 22
- **P0/P1 regression:** PASS
- **Lint:** PASS
- **Frontend build:** PASS
- **No commit, push or deploy; historical data unchanged.**

## 1. Tests

| Area | Tests | Result |
|---|---|---|
| Zone store: CRUD, versioning, archive, temporal filtering | 6 | PASS |
| Experiment persistence: traceability, statuses, dashboard | 6 | PASS |
| P2 API: zone CRUD, dashboard, planned experiment | 2 | PASS |
| Reproduction: zone/variation pinning, hash/model failures | 5 | PASS |
| Persistence: backup/recovery, multi-process locking | 3 | PASS |
| P0/P1 and existing regression | remainder | PASS |
| **Total** | **650** | **PASS** |

Commands:

```bash
python -m unittest discover -s tests
make lint
cd frontend && npm run build
```

Evidence: `EVIDENCE/remediation/tests-full.log`, `EVIDENCE/remediation/ui-reproduce-amend.log`, `EVIDENCE/remediation/ui-zone-draw.log`.

## 2. Zone tests

- create zone → version 1;
- edit → version 2, previous snapshot retained;
- archive → version 3, history retained;
- future-effective zone excluded from an earlier run;
- invalidated-before-end zone excluded;
- legacy config zones preserved;
- selected zone IDs isolate a run to the selected manual zones;
- API CRUD and version increments verified.

## 3. Experiment tests

- completed run link stores strategy/variation, dataset hash, cost profile, gross/net results, validation status and research fields;
- planned → running → archived transitions;
- completed result cannot be reopened;
- dashboard reads actual strategy/experiment counts;
- route contract includes all additive P2 endpoints.

## 4. UI verification

`EVIDENCE/ui-verify.log`:

```
dashboard=1
experiment_rows=2
status_completed=true
gross_net=true/true
validation_passed=true
console_errors=0
zone_chart=1
zone_rows=12
```

`EVIDENCE/zone-draw.log`:

```
heading=Draw the area, keep the version.
chart=1
zone_rows=11
modal=1
dialog_title=Create zone
zone_rows_after=12
console_errors=0
```

Screenshots:
- `EVIDENCE/workspace-experiments.png`
- `EVIDENCE/zone-manager.png`

The browser flow verified dashboard, experiment status/gross/net/validation, zone chart, drag-created zone and persisted zone list.

## 5. Data integrity

- `data/historical` SHA-256 unchanged.
- Existing run artifacts untouched.
- Zones and workspace state stored separately under `data/workspace/`.
- No fabricated zones or metrics; test zones are real records created through the UI/API.

## 6. Known limitations

- Conservative temporal zone availability; no mid-run dynamic activation.
- Drag creates new rectangles; resizing uses exact boundary editing rather than handles.
- Planned experiments are API/model-supported; primary UI flow records completed runs.
- JSON single-process persistence.
- P3–P6 not started.

## P2.1 Remediation Test Update

- Full suite after remediation: **650 / 650 PASS**.
- P0/P1 regression: **35 / 35 PASS**.
- P2 remediation/regression: **22 / 22 PASS**.
- Lint and frontend build: PASS.
- Browser reproduction/amendment and zone-draw checks: PASS, 0 console errors.
- Historical hashes unchanged; existing run artifacts unchanged.

Remediation evidence is in `EVIDENCE/remediation/`. Original audit evidence remains in `EVIDENCE/audit/` and `AUDIT.md` is unchanged.
