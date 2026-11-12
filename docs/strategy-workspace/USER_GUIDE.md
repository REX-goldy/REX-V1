# Strategy Workspace — User Guide

## 1. Open the workspace

Use the sidebar item **Strategy Workspace** (section 04). It sits beside Strategy Lab and Run Archive.

- The list is the research catalogue.
- Clicking a card opens that strategy’s dedicated workspace.
- **All strategies** returns to the list.
- The search/filter bar searches title, registry ID, tags and descriptions, and filters by research status.

The three registered strategies are seeded on first use:

- Zone Breakout (`CORE_ZONE_BREAKOUT`)
- Breakout Retest (`S002`)
- Liquidity Sweep (`S008`)

The seed contains documentation and one baseline variation. It contains **no fabricated performance**.

## 2. Create a strategy record

Click **New strategy**.

Fill in:

- title and short description (required),
- optional registry implementation,
- category, status, tags,
- instruments and timeframes,
- hypothesis, research objective and detailed description.

If you choose a **registry implementation**, the baseline is executable and its defaults come from the actual Strategy Lab strategy. If you leave it empty, the record is **documentation only** and cannot be run.

Duplicate titles (case-insensitive) are rejected. Strategies are archived, not hard-deleted.

## 3. Read the detail workspace

The context bar stays visible while you work and shows:

- strategy name and registry ID,
- selected variation,
- research status,
- last experiment,
- linked run count,
- **Run experiment** for an executable variation.

Sections:

### Overview

Identity, hypothesis, objective, category, status, dates, tags, instruments, timeframes and descriptions.

### Rules

Three explicit groups:

- **Implemented** — what the current code does.
- **Proposed** — documentation only.
- **Experimental** — documentation only.

Use **Edit rules** to maintain the record. Proposed/experimental rules never become executable because they are typed into this page.

### Notes

Add observations, hypotheses, problems, decisions and future experiment ideas. Notes are timestamped. Notes can be edited or deleted; deleting a note does not delete experiments or runs.

### Variations

Every variation has its own ID, title, description, hypothesis, changes, rule differences, parameter snapshot, instruments, timeframes, status, notes, creation date and linked experiment count.

- **V1 — Original baseline** is locked after its first experiment.
- **Clone** is the explicit versioned-change path. A clone is a new variation with its own ID and `cloned_from` reference.
- **Edit** a non-baseline variation to change its configuration. Changing `parameter_config` increments its configuration version.
- **Archive** hides a variation from active work without deleting its experiments or runs.
- **Run** opens Strategy Lab with the correct strategy/parameters preselected.

Documentation-only variations show that they have no executable implementation; their Run button is disabled.

### Experiments

Shows actual linked runs with:

- experiment name and run ID,
- variation,
- dataset/timeframe/date range,
- baseline/experiment/repeat/out-of-sample kind,
- actual trade count and expectancy.

No row is inferred from documentation. Missing run files are marked `missing`.

### Comparison

Only experiments with the **same dataset, instrument, timeframe, start date and end date** are grouped. The table shows:

- trade count, win rate, profit factor, expectancy,
- max drawdown, total R, average holding time,
- run availability and a <100-trade sample warning.

No superiority ranking is applied. Gross results are labelled; costs are not applied. Missing values show as `—`.

## 4. Run an experiment

1. Open an executable variation.
2. Click **Run experiment** in the context bar or **Run** on the variation.
3. Strategy Lab opens with the strategy and parameter configuration preselected.
4. Choose instrument, timeframe, dataset and date range.
5. Select the **Experiment kind**:
   - Auto (baseline/repeat/experiment)
   - Baseline
   - Experimental variation
   - Repeated experiment
   - Out-of-sample validation
6. Execute the existing backtest.
7. REX archives the run, then links the run ID to the selected variation.
8. Return to **Strategy Workspace → Experiments** to see it.

If the workspace link fails, the run is still archived and the error is shown; the system never fakes an association.

Changing the strategy in Strategy Lab clears the workspace context, preventing a link to the wrong variation.

## 5. Status meanings

| Status | Meaning |
|---|---|
| Draft | Record is being assembled |
| Research | Active research documentation |
| Experimental | Research is testing a defined variation |
| Validated | Research process has reached a documented validation state |
| Archived | Retained, out of active view |

These are **research-maturity labels**, not profitability or trading-readiness labels.

## 6. Persistence and safety

- Data is stored server-side at `data/workspace/strategy_workspace.json` (override: `REX_WORKSPACE_FILE`).
- The file is local, versioned, atomic and `0600`; it is gitignored.
- Docker Compose uses a dedicated `rex_workspace` volume.
- The workspace never modifies:
  - `strategies/` or `execution/` logic,
  - `BacktestRunner`,
  - risk calculations,
  - historical data,
  - existing run artifacts.
- Experiments are append-only. There is no delete action.
- Baseline protection is server-enforced, not just hidden in the UI.

## 7. Current limitations

- Single-user local terminal; no authentication.
- JSON storage; no multi-process write coordination.
- Comparisons require exact dataset/instrument/timeframe/start/end equality.
- Out-of-sample is a user declaration, not an automatic statistical test.
- No cost-adjusted results; current runs are gross R-multiples with costs disabled.
- The workspace intentionally does not create a second backtest engine.
