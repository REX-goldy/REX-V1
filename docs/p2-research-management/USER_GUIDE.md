# P2 User Guide

## Strategy Workspace

1. Open **Strategy Workspace**.
2. The dashboard shows strategy/variation/experiment inventory, statuses, dataset warnings and validation failures.
3. Create a strategy with hypothesis, trading concept, risk assumptions, rules and notes.
4. Open a strategy to edit metadata/rules or add notes.
5. Variations preserve their own parameter/zone configuration and version. Clone the baseline for a versioned change.
6. **Run** opens Strategy Lab with the selected variation.

## Experiment workflow

1. Open an executable variation and select **Run** (or **Run experiment** in the context bar).
2. Strategy Lab preselects the strategy and parameters.
3. Choose instrument/timeframe/dataset/date range.
4. Choose a cost profile.
5. Review preflight errors/warnings. Execution is disabled on blocking errors.
6. Run the existing backtest.
7. The run is linked to the variation and an experiment is recorded with gross/net metrics, costs, validation, dataset hash and configuration.
8. Return to **Experiments** to inspect status and traceability; use **Comparison** for equivalent conditions.

Experiment statuses are Planned/Running/Completed/Failed/Archived. Completed results are immutable; archive instead of deleting.

## Zone Manager

1. Open **Zone Manager**.
2. Select a dataset.
3. Click **Draw on chart**, drag a rectangle (click-to-create is also available), then set exact prices, effective/invalidation timestamps, strength, type and notes.
4. Save. Every edit appends a version.
5. Link zones to a strategy/variation where appropriate.
6. Use status filters to inspect active/invalidated/archived zones.

Zones are stored separately from candles. A run uses manual zones effective before the run start and not invalidated before the run end; legacy `config/zones.json` zones remain static. This conservative rule prevents future-zone leakage.

## Traceability

Each completed experiment records the linked run, dataset hash, exact configuration, cost/risk/execution assumptions, gross/net results, validation status, hypothesis, expected/actual outcome, supported flag and next steps. Zone versions are snapshotted.

## Limits

- No P3–P6 features.
- No account-currency P&L.
- JSON single-process persistence.
- Mid-run zone activation/invalidation is conservative rather than dynamic.

## P2.1 Reproduction and Amendments

- A completed experiment with a full snapshot has **Reproduce** in the Experiments table. Reproduction creates a new run and appends a reproduction record; it never overwrites the original.
- If the dataset hash, model versions, strategy rules, cost profile or zone snapshot is missing/incompatible, the API returns a structured failure instead of using current state.
- **Amend** appends a narrative correction (author, field, previous/new value, reason). The original completed values remain unchanged.
- Historical experiments created before snapshots exist cannot be reproduced exactly; they return `SNAPSHOT_MISSING`.

### Historical zone imports

Ordinary drawn zones use server creation time and cannot backdate. For historical annotations, check **Audited historical import** and provide source/operator. Historical-import zones are distinct from ordinary manual zones. Legacy `config/zones.json` remains static/read-only.

### Recovery

The stores maintain `.bak` and `.corrupt-*` files under `data/workspace/`. A corrupt file is preserved and a valid backup is restored only after JSON/version/structure validation. Manual recovery instructions remain in this directory.
