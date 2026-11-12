# P2 Data Model

## 1. Strategy additions

```json
{
  "trading_concept": "The trading concept in plain language",
  "risk_assumptions": "Fixed-risk research assumptions",
  "zone_ids": ["zone_..."]
}
```

`zone_ids` belongs to a variation, not to executable strategy code.

## 2. Experiment extension

```json
{
  "status": "Planned|Running|Completed|Failed|Archived",
  "strategy_id": "sw_...",
  "variation_id": "var_...",
  "dataset_id": "EURUSD/M1/2026",
  "dataset_hash": "sha256...",
  "instrument": "EURUSD",
  "timeframe": "M1",
  "start_date": "2026-06-01",
  "end_date": "2026-06-30",
  "configuration": {
    "parameters": {},
    "zone_ids": [],
    "zone_snapshots": [{"id": "zone_...", "version": 3, "low": 1.1, "high": 1.2}]
  },
  "execution_configuration": {"entry_model": "next candle open", "costs_applied": true},
  "risk_configuration": {"equity": 100000, "risk_fraction": 0.01, "r_multiple": 2},
  "cost_profile": {"id": "proxy_forex_v1", "...": "..."},
  "gross_results": {"expectancy": -0.26, "...": "..."},
  "net_results": {"expectancy": -2.86, "...": "..."},
  "validation_status": "passed|failed|not_run",
  "run_id": "...",
  "research_objective": "...",
  "expected_outcome": "...",
  "actual_outcome": "...",
  "hypothesis_supported": false,
  "next_steps": "...",
  "created_at": "...",
  "completed_at": "..."
}
```

## 3. Manual zone

```json
{
  "id": "zone_eurusd-m1-2026_ab12cd34",
  "dataset_id": "EURUSD/M1/2026",
  "instrument": "EURUSD",
  "source_timeframe": "H1",
  "zone_type": "supply|demand|neutral",
  "low": 1.10,
  "high": 1.11,
  "start_timestamp": "2026-01-01T00:00:00+00:00",
  "effective_timestamp": "2026-01-01T00:00:00+00:00",
  "invalidation_timestamp": null,
  "status": "active|invalidated|archived",
  "strength": 7,
  "notes": "",
  "strategy_id": null,
  "variation_id": null,
  "provenance": "manual",
  "version": 1,
  "created_at": "...",
  "updated_at": "...",
  "versions": []
}
```

Every `PATCH` appends the previous record to `versions`, increments `version`, and never overwrites a historical snapshot. `DELETE` archives.

## 4. Persistence

| Store | Path | Override | Mode |
|---|---|---|---|
| Strategy workspace | `data/workspace/strategy_workspace.json` | `REX_WORKSPACE_FILE` | 0600 atomic |
| Manual zones | `data/workspace/manual_zones.json` | `REX_ZONES_FILE` | 0600 atomic |
| Runs | `research/outputs/ui_runs/*.json` | `REX_RUNS_DIR` | existing immutable |

No migration rewrites existing run artifacts or CSV data. Old experiments without P2 fields return empty/default values (`Completed`, `not_run`, no hash).

## 5. Invariants

- one baseline per strategy;
- baseline locked after first experiment;
- completed experiment results cannot be reopened; archive only;
- zone versions append-only;
- experiment configuration snapshots immutable after completion;
- selected zone versions retained in experiment snapshots;
- zone temporal availability is filtered before execution.

## P2.1 Snapshot and Integrity Extensions

### Zone provenance

```json
{
  "created_at": "server-generated",
  "historical_import": true,
  "import_source": "source reference",
  "import_operator": "operator",
  "imported_at": "server timestamp",
  "provenance": "historical_import"
}
```

Ordinary zones have `historical_import=false` and require `effective_timestamp >= created_at`. Backdated ordinary creation is rejected.

### Experiment snapshot additions

```json
{
  "snapshot_version": 1,
  "strategy_snapshot": {"id": "...", "rules": "...", "variations": []},
  "variation_snapshot": {"id": "...", "parameters": {}, "zone_ids": []},
  "dataset_snapshot": {"dataset_id": "...", "hash": "...", "metadata": {}},
  "zone_snapshots": [{"id": "...", "version": 1, "low": 1.1, "high": 1.2}],
  "backtest_parameters": {},
  "model_versions": {},
  "validation_reference": {"status": "passed"},
  "reproductions": [],
  "amendments": []
}
```

Completed results and snapshots are immutable. `reproductions` and `amendments` are append-only.

### Recovery files

- `*.json.bak` — last successful known-good state.
- `*.json.corrupt-<timestamp>` — preserved corrupt file.
- `*.json.lock` — POSIX cross-process lock.
