# Strategy Workspace — Data Model

## 1. Storage

| Item | Value |
|---|---|
| Default file | `data/workspace/strategy_workspace.json` |
| Override | `REX_WORKSPACE_FILE` |
| Format | Versioned JSON, pretty-printed |
| Version | `1` |
| Mode | `0600` on POSIX |
| Write | temp file + `fsync` + `os.replace` |
| Lock | process-wide `RLock` |
| Git | `data/workspace/` ignored |
| Docker | `rex_workspace:/app/data/workspace` volume |

The store is intentionally a JSON document, not a database. It is small, local, inspectable and needs no new infrastructure.

## 2. Root schema

```json
{
  "version": 1,
  "strategies": [Strategy]
}
```

## 3. Strategy

```json
{
  "id": "sw_liquidity-sweep_ab12cd34",
  "title": "Liquidity Sweep",
  "registry_strategy_id": "S008",
  "short_description": "Sweep of a prior swing high/low with a close back inside.",
  "description": "Detailed research description.",
  "hypothesis": "A falsifiable hypothesis; never presented as proven.",
  "research_objective": "What the research programme is trying to establish.",
  "category": "Liquidity",
  "status": "Research",
  "tags": ["liquidity", "sweeps"],
  "created_at": "2026-11-03T14:44:22+00:00",
  "updated_at": "2026-11-03T14:44:22+00:00",
  "archived_at": null,
  "rules": {
    "implemented": { "entry_conditions": [], "...": "..." },
    "proposed": ["Documentation-only proposal."],
    "experimental": ["Documentation-only experiment."]
  },
  "notes": [ResearchNote],
  "variations": [StrategyVariation],
  "experiments": [Experiment]
}
```

### Strategy statuses

`Draft`, `Research`, `Experimental`, `Validated`, `Archived`.

These represent research maturity only. They do not imply profitability, trading readiness or risk approval.

### Strategy/registry rule

`registry_strategy_id` may be `null` for a user-created documentation-only strategy. A non-null value is validated against the existing registry. The workspace never changes the registered implementation.

## 4. StrategyVariation

```json
{
  "id": "var_liquidity-sweep-baseline_ab12cd34",
  "title": "V1 — Original baseline",
  "description": "What this variation changes.",
  "hypothesis": "Variation-specific hypothesis.",
  "changes_from_parent": "Changes from parent or previous version.",
  "entry_rule_differences": "",
  "exit_rule_differences": "",
  "filter_differences": "",
  "parameter_config": {
    "lookback": 10,
    "min_wick_ratio": 0.6,
    "tolerance": 0.0
  },
  "instruments": ["EURUSD"],
  "timeframes": ["M1", "M5"],
  "status": "Research",
  "notes": "",
  "is_baseline": true,
  "implementation_status": "implemented",
  "registry_strategy_id": "S008",
  "configuration_version": 1,
  "cloned_from": null,
  "created_at": "2026-11-03T14:44:22+00:00",
  "updated_at": "2026-11-03T14:44:22+00:00",
  "archived_at": null
}
```

Invariants:

- Exactly **one** variation per strategy has `is_baseline: true`.
- `implementation_status` is `implemented` only when the strategy is linked to a registry implementation; otherwise `documentation_only`.
- Executable variations validate parameter names/types/ranges against the registry spec.
- `configuration_version` increments on a `parameter_config` change.
- `cloned_from` records the source variation for explicit versioned copies.
- A baseline with any experiment is locked; a clone is the versioned path.
- A baseline cannot be archived.
- Variations are archived, not hard-deleted.

## 5. ResearchNote

```json
{
  "id": "note_ab12cd34",
  "body": "Observation / problem / decision.",
  "created_at": "2026-11-03T14:45:00+00:00",
  "updated_at": "2026-11-03T14:45:00+00:00"
}
```

Notes are ordered by creation and returned newest-last in storage; the UI displays newest first. Note deletion does not touch experiments or runs.

## 6. Experiment

```json
{
  "id": "exp_ab12cd34",
  "strategy_id": "sw_liquidity-sweep_ab12cd34",
  "name": "V2 · EURUSD/M1/2026 · M1",
  "variation_id": "var_...",
  "variation_version": 1,
  "hypothesis": "Why this experiment was run.",
  "experiment_kind": "experiment",
  "kind": "experiment",
  "dataset_id": "EURUSD/M1/2026",
  "instrument": "EURUSD",
  "timeframe": "M1",
  "start_date": "2026-06-01",
  "end_date": "2026-06-30",
  "configuration": {
    "registry_strategy_id": "S008",
    "variation_id": "var_...",
    "variation_version": 1,
    "parameters": {"lookback": 10, "min_wick_ratio": 0.6, "tolerance": 0.0},
    "r_multiple": 2.0,
    "equity": 100000.0,
    "risk_fraction": 0.01,
    "entry_model": "next candle open"
  },
  "executed_at": "2026-11-03T14:46:26+00:00",
  "run_id": "20261103T144626Z_57dd08ff",
  "result_reference": {
    "run_id": "20261103T144626Z_57dd08ff",
    "run_created_at": "2026-11-03T14:46:26+00:00",
    "dataset_id": "EURUSD/M1/2026",
    "bar_count": 31800,
    "metrics": {
      "total_signals": 1393,
      "total_trades": 1316,
      "win_rate": 11.778115501519757,
      "profit_factor": 0.2604870396538276,
      "expectancy": -0.6533089764666262,
      "max_drawdown_r": 859.7546130300801
    },
    "warnings": [],
    "assumptions": {"costs_applied": false},
    "total_r": -859.7546130300801,
    "trades_truncated": false
  },
  "notes": "",
  "created_at": "2026-11-03T14:46:27+00:00"
}
```

### Experiment kinds

- `baseline` — first experiment on the baseline variation (auto).
- `experiment` — normal experimental variation run (auto when no prior experiment).
- `repeat` — repeated run (auto when prior experiments exist; user may override).
- `out_of_sample` — user-declared validation run.

The backend never infers out-of-sample status from dates.

### Run relationship

The run archive remains the source of truth. The experiment stores:

- `run_id`;
- a compact result reference with actual metrics/warnings/assumptions;
- the configuration snapshot;
- variation/version.

The `run_available` flag on reads checks the run archive file but does not mutate or recreate a missing run.

## 7. Comparison group

Comparison is computed from experiments, not persisted separately:

```
(dataset_id, instrument, timeframe, start_date, end_date)
```

A group requires at least two distinct variations. Each row includes actual metrics or `null` when unavailable. `sample_size_warning` is true below 100 trades. No ranking is calculated.

## 8. Relationships

```
Strategy 1 ─── * StrategyVariation
Strategy 1 ─── * ResearchNote
Strategy 1 ─── * Experiment
StrategyVariation 1 ─── * Experiment
Experiment * ─── 1 immutable backtest run (by run_id)
Strategy 1 ─── 0..1 registry implementation (by registry_strategy_id)
```

Stable IDs:

- strategy: `sw_<slug>_<8hex>`
- variation: `var_<slug>_<8hex>`
- note: `note_<slug>_<8hex>`
- experiment: `exp_<slug>_<8hex>`
- run: existing `ui_run_v1` ID.

## 9. Validation and conflicts

| Case | Behavior |
|---|---|
| Duplicate strategy title | 409 |
| Unknown strategy/variation/note | 404 |
| Invalid status/timeframe/key/parameter | 400 |
| Baseline edit after experiment | 409 |
| Baseline archive | 409 |
| Documentation-only variation run | 409 |
| Wrong-strategy run | 400 |
| Run instrument/timeframe not allowed by variation | 400 |
| Duplicate run link | 409 |
| Missing run file | 400 |
| Corrupt/unsupported workspace version | 500, fail closed |

## 10. Migration strategy

- Current schema version is `1`.
- Reads reject any unknown version instead of silently rewriting.
- A future migration must:
  1. add a new version constant;
  2. migrate read data in memory;
  3. write atomically only after full validation;
  4. keep the original file as a timestamped backup outside `data/workspace`;
  5. add tests for old-to-new shape.
- No automatic destructive migration is performed now.
- Existing run artifacts are never migrated or rewritten.

## 11. Seeding

When the workspace file does not exist, the service seeds the three **actual** registry strategies:

- `CORE_ZONE_BREAKOUT` → “Zone Breakout”
- `S002` → “Breakout Retest”
- `S008` → “Liquidity Sweep”

Each gets one baseline variation with default registry parameters. Seed rules are transcribed from the current implementation and existing Strategy Lab descriptions. No performance result is seeded; `latest_experiment` is `null` until a real run is linked.

The seed is written only when the file is absent. An existing empty/corrupt file is not silently replaced.

## 12. Persistence and deployment

- Local: default `data/workspace/strategy_workspace.json`.
- Docker Compose: `rex_workspace` volume at `/app/data/workspace`; `data/workspace/` is excluded from the build context.
- The file is not committed; no credentials are stored in it.
- Concurrent reads/writes within one process are serialized. Multi-process concurrent writers are outside the current single-user design.
