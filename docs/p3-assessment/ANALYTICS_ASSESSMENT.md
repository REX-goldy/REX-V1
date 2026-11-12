# Strategy Performance Analytics Assessment

## 1. Current run-artifact contents

Each `ui_run_v1` artifact currently includes:

- `schema_version`, `id`, `created_at`;
- `dataset_id` and dataset summary;
- strategy id/name/description;
- `parameters`;
- `request` (date range, timeframe, R multiple, equity, risk fraction);
- `range` and `bar_count`;
- `simulated`;
- gross `metrics` and independently validated `net_metrics`;
- signal counts, reconciliation counts and signal distribution;
- `equity_curve` (R) and drawdown;
- `trade_distribution` by date;
- closed `trades` with entry/exit, direction, prices, PnL R, exit reason, holding
  duration, planned/actual risk, costs, net PnL, execution assumption;
- warnings, cost profile, zone IDs and dataset-quality summary.

P2.1 experiments add immutable snapshots, validation status, cost/risk/execution
configuration, strategy/variation snapshots and reproduction records.

## 2. Reliably calculable today

These can be calculated from current closed trades/run metrics without inventing data:

| Metric | Source |
|---|---|
| Total trades | `metrics.total_trades` / `trades` |
| Gross win rate | `metrics.win_rate` / `pnl_r` |
| Net win rate | `net_metrics.win_rate` / `net_pnl_r` |
| Gross profit factor | `metrics.profit_factor` |
| Net profit factor | `net_metrics.profit_factor` |
| Gross/net expectancy | `metrics` / `net_metrics` |
| Average win/loss | `metrics.average_win`, `average_loss` |
| Largest win/loss | `metrics.largest_win`, `largest_loss` |
| Maximum drawdown in R | `metrics.max_drawdown_r` / `net_metrics.max_drawdown` |
| Consecutive wins/losses | current metrics; independently recomputable |
| Ambiguous exits | `metrics.ambiguous_exits` / trade reasons |
| Average holding duration | `metrics.avg_holding_duration` / trade records |
| R-multiple distribution | trade `pnl_r` or `net_pnl_r` |
| Long/short performance | trade `direction` + PnL fields |
| Cost contribution | `spread_cost_r`, `slippage_cost_r`, `commission_cost_r`, `swap_cost_r` |
| Trade ordering | sorted by exit time in run artifacts |
| Gross/net comparison | `metrics` vs `net_metrics` |

## 3. Requires new read-only analytics infrastructure

| Capability | Requirement |
|---|---|
| Monthly/weekly/daily breakdowns | Derive from trade entry/exit timestamps; define whether trade is attributed to entry or exit date |
| Session breakdowns | Use `SessionManager`; document fixed UTC windows/IST reporting and lack of DST/holiday modeling |
| Rolling performance | Rolling window over trade sequence and/or time; must handle gaps and small samples |
| Rolling drawdown | Compute from trade-level R curve; portfolio equity not available |
| R-multiple histogram | Aggregate closed trade R values; no fabricated bins |
| Long/short metrics | Counts/win rate/expectancy/PF separately; no account currency |
| Exposure | Per-trade size and risk are available; portfolio exposure is not available |
| Regime-conditioned results | Join trades to causal regime snapshots; requires P3 regime pack/versioning |
| Statistical uncertainty | Bootstrap/analytic intervals require explicit methodology; not yet implemented |
| Multiple-testing diagnostics | Requires trial counts from robustness infrastructure |

## 4. Gross versus net

- `pnl_r` is **gross** and remains unchanged by cost profiles.
- `net_pnl_r = pnl_r − total_cost_r`.
- `metrics` reports gross; `net_metrics` reports net when a costed run is available.
- Cost profiles are assumptions/proxies when `estimated=true`; they are not observed
  historical bid/ask.
- Any analytics must report both sets where costs exist, or explicitly mark net unavailable.

## 5. Account-currency and portfolio limitations

REX currently reports R-multiples only. It cannot claim:

- account-currency P&L;
- portfolio equity, margin, leverage or currency conversion;
- portfolio-level exposure or correlation;
- net returns after financing in currency;
- combined multi-strategy equity.

Per-trade `planned_position_size`, `position_size`, `planned_risk_amount` and
`realized_risk_amount` exist, but aggregate portfolio exposure and account currency are not
modeled. A future phase would need explicit contract sizes, conversion rates and portfolio
accounting.

## 6. Analysis semantics that must be documented

1. **Trade attribution date:** entry date vs exit date changes monthly/session totals.
2. **Ambiguity:** ambiguous exits are conservatively resolved; net metrics inherit this.
3. **Small samples:** no metric should be presented as edge without sample size and context.
4. **Missing trades:** truncated ledgers (`trades_truncated`) mean distributions may be partial.
5. **R units:** R is normalized by actual risk; it is not currency return.
6. **Time zones:** session analytics use UTC/IST conventions; no DST holiday model.
7. **Comparable experiments:** analytics must group only equal dataset/instrument/timeframe/
   date-range and compatible cost profiles.

## 7. Proposed analytics output

A read-only `RunAnalytics` service should be additive:

- reads an immutable run artifact or P2.1 experiment;
- does not rewrite the run;
- computes aggregates from trade records;
- returns gross and net sections separately;
- declares missing/insufficient data explicitly;
- carries the source run id, experiment id, cost profile and validation status.

No account-currency fields should exist until currency conversion is implemented.

## Related documents

[README](README.md) · [Current state](CURRENT_STATE.md) · [Feature catalogue](FEATURE_CATALOGUE.md) · [Analytics](ANALYTICS_ASSESSMENT.md) · [Regime](REGIME_RESEARCH.md) · [Robustness](ROBUSTNESS_ASSESSMENT.md) · [Architecture](ARCHITECTURE_PROPOSAL.md) · [Roadmap](P3_ROADMAP.md) · [Risks](RISKS_AND_OPEN_QUESTIONS.md)
