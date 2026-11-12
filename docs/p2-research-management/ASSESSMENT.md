# P2 Assessment

## 1. Existing architecture reused

P0 and P1 were re-checked before implementation: 604 tests, lint, build and data hashes. No P0/P1 regression was found.

P2 reuses:

- the three existing registry strategies and `BacktestRunner`;
- the existing Strategy Lab/preflight/cost/validation pipeline;
- the existing run archive (`ui_runs`) as the immutable result source;
- the existing Strategy Workspace JSON store and UI patterns;
- the existing `Zone`, `ZoneBook`, `ZoneEngine`, loader and chart components;
- FastAPI, React/Vite and the house design system.

No duplicate strategy registry, execution engine, metrics engine or run archive was introduced.

## 2. P2 extension points

| Gap | Extension |
|---|---|
| Strategy metadata needed more research fields | `trading_concept`, `risk_assumptions` |
| Variations needed zone references | `zone_ids` on variation and run/lab request |
| Experiments needed traceability and lifecycle | extended experiment model, planned/update/archive APIs |
| Manual zones were config-only | new `server/zone_store.py` persistent versioned zone store and Zone Manager |
| Backtests used static config zones | service builds a temporal zone book; selected IDs are honoured |
| No research overview | `/api/workspace/dashboard` and workspace dashboard panel |

## 3. Persistence decision

JSON remains sufficient for this single-user research phase:

- workspace: `data/workspace/strategy_workspace.json`
- manual zones: `data/workspace/manual_zones.json`
- run artifacts: `research/outputs/ui_runs/*.json`

No database or ClickHouse migration was introduced. The volume-backed data directory handles Docker persistence; all writes are atomic JSON with process locks.

## 4. Protected contracts

Unchanged: P0 execution semantics, P1 cost calculations, historical CSVs/meta, existing run files, strategy logic. Strategy execution still goes through `BacktestRunner`; zones are passed to existing strategies using the existing `ZoneBook` contract.

## 5. Known architecture limitations

- Temporal zone handling is conservative at run construction, not a per-bar mutable zone feed.
- JSON is single-process; multi-process coordination is not implemented.
- The UI supports planned/experiment status display and API status updates; the normal user flow records completed runs.
- No P3 robustness, portfolio, agents, paper or live features.
