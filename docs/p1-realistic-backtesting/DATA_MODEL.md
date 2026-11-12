# P1 Data Model

## 1. Cost profile

`config/cost_profiles.json` (version 1):

```json
{
  "version": 1,
  "profiles": [
    {
      "id": "proxy_forex_v1",
      "name": "Estimated FX proxy v1",
      "description": "Illustrative proxy costs, not observed historical bid/ask.",
      "kind": "estimated_proxy",
      "estimated": true,
      "spread_price": 0.00012,
      "slippage_price_per_side": 0.00002,
      "commission_per_round_trip": 0.0,
      "swap_per_night_r": 0.0,
      "instrument_overrides": {
        "USDJPY": {"spread_price": 0.012, "slippage_price_per_side": 0.002}
      },
      "source_note": "..."
    }
  ]
}
```

- **zero_costs** is the explicit legacy gross baseline.
- **proxy_forex_v1** is an estimated proxy; it is never described as observed bid/ask.
- Spread is full spread per round trip.
- Slippage is adverse per side, twice per round trip.
- Commission is account-currency per round trip.
- Swap is R per overnight period (explicitly not currency conversion).
- Instrument overrides replace individual values for the symbol.

## 2. Trade cost fields

`ClosedTrade` / run trade rows:

```text
spread_cost_r
slippage_cost_r
commission_cost_r
swap_cost_r
total_cost_r
net_pnl_r
cost_profile_id
```

`pnl_r` remains the **gross** R. `net_pnl_r = pnl_r − total_cost_r`.

## 3. Run payload additions

```json
{
  "metrics": { "...": "gross metrics" },
  "net_metrics": { "...": "net metrics" },
  "cost_profile": { "...": "complete selected profile and assumptions" },
  "dataset_quality": {
    "status": "warning",
    "counts": { "...": "..." },
    "quality": { "...": "..." },
    "gaps": [],
    "derived": {},
    "provenance": {}
  },
  "assumptions": {
    "costs_applied": true,
    "cost_profile_id": "proxy_forex_v1",
    "cost_profile_estimated": true
  }
}
```

Old run artifacts without these fields remain readable; consumers show unavailable/legacy.

## 4. Dataset quality report

Returned by `GET /api/dataset-quality?dataset_id=SYMBOL/TF/YEAR`:

```json
{
  "dataset_id": "EURUSD/M1/2026",
  "provider": "twelve_data",
  "coverage": {"requested_start": "...", "actual_start": "...", "...": "..."},
  "counts": {
    "bar_count": 184963,
    "duplicate_timestamp_count": 0,
    "order_violation_count": 0,
    "invalid_bar_count": 0,
    "raw_gap_count": 35,
    "unexpected_gap_count": 10,
    "missing_open_minutes": 17,
    "missing_closure_minutes": 74880,
    "bars_in_closure": 0
  },
  "gaps": [{"before": "...", "after": "...", "missing_open_minutes": 3, "unexpected": true}],
  "derived": {"M5": {"status": "ok", "emitted_bar_count": 36987, "skipped_incomplete_buckets": 9}},
  "quality": {"status": "warning", "errors": [], "warnings": ["..."], "notes": []},
  "provenance": {"provider": "twelve_data", "...": "..."}
}
```

No report writes to source data.

## 5. Preflight response

```json
{
  "valid": false,
  "errors": [{
    "code": "ZONE_BOOK_MISSING",
    "severity": "error",
    "component": "zones",
    "message": "No zone book is configured for AUDUSD.",
    "suggestion": "..."
  }],
  "warnings": [],
  "info": [],
  "details": {}
}
```

## 6. Independent validation response

`GET /api/runs/{run_id}/validation`:

```json
{
  "run_id": "...",
  "checked_trades": 54,
  "valid": true,
  "error_count": 0,
  "warning_count": 0,
  "findings": [],
  "independent_metrics": {"expectancy": -0.2627, "max_drawdown": 12.3, "total_r": -14.2}
}
```

Findings are structured `code/severity/component/message/suggestion`; they never mutate the run.

## 7. Migration

Schema version remains additive:

- cost profiles are a new versioned config file;
- run fields are optional for old artifacts;
- no historical dataset or run artifact is rewritten;
- a future database migration would need to import cost/quality/validation fields while preserving IDs and files.
