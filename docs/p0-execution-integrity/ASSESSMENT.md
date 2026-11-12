# P0 Execution Integrity — Assessment

- **Date:** 2026-11-03
- **Base commit:** `95f8aaa998f1ce1539c65777b5dd10ac063cbd34` plus additive working tree
- **Scope:** P0 only. P1–P6 are not started.
- **Constraints:** no data modification, no commit/push/deploy, no strategy redesign without documenting the approved P0.3 behavior change.

## 1. Repository path inspected

The existing research path is:

```
HistoricalDataParser / storage
  → Bar[] (causal replay)
  → Strategy.generate_signals
  → TradeSetupFactory
  → TradeSetupValidator
  → TradePlanner
      FixedRiskRewardPolicy
      FixedRiskSizer
  → TradePlan
  → TradeSimulator + ConservativeOHLCFillModel
  → ClosedTrade[]
  → PerformanceMetrics / BacktestResult
  → server/research_service
  → Strategy Lab / Run Archive / Strategy Workspace
```

`BacktestRunner` remains the only backtest execution path. The Strategy Workspace added earlier is documentation/experiment metadata around existing runs; it is not a second engine.

## 2. Existing components reused

| Component | Reuse |
|---|---|
| `BacktestRunner` | Unchanged orchestration; no second pipeline |
| `FixedRiskRewardPolicy` | Unchanged entry/target policy |
| `FixedRiskSizer` | Extended with contract size and min/max bounds |
| `TradeSimulator` | Extended to re-size at actual fill and retain execution evidence |
| `ConservativeOHLCFillModel` | Kept; ambiguity/gap semantics corrected downstream |
| `ClosedTrade` / `Position` | Extended with planned/actual risk and execution assumption fields |
| `PerformanceMetrics` | Unchanged formulas; no metric hiding |
| `FeatureRepository` | Added duplicate rejection; no feature redesign |
| `BreakoutStrategy` | One narrow signal-transition fix, documented in P0.3 |
| `server/research_service` | Exposes new trade fields and corrected ambiguity warning |
| Existing tests | Preserved; two fixtures/tests updated because they encoded the defects |

No new dependency and no database/infrastructure change was introduced.

## 3. Confirmed defects addressed

### P0.1 Realised risk ≠ planned risk

**Before:** the sizer used `entry_hint` (signal close) and stop, while the simulator filled at the next candle open and kept the planned units. Actual risk therefore depended on entry slippage.

Observed baseline (EURUSD S008, 2026-05-01..15):
- 543 / 606 trades had realised risk different from planned.
- maximum deviation: 6.50× (QA had observed 5.50× on a different sample; both are real).
- examples: planned 1,000 → realised 333.33 or 1,599.99.

**Root cause:** sizing at plan time using an estimated entry; no fill-time re-sizing.

### P0.2 Gap/ambiguity PnL

**Before:** any `AMBIGUITY` was overwritten to `-1.0R`, even when the bar opened through the stop and the actual fill loss was worse.

**Evidence:** synthetic LONG entry 1.1500, SL 1.1400, TP 1.1700; next bar opens 1.1000, ranges 1.0900–1.1800. Actual fill −5.0R; recorded −1.0R.

### P0.3 CORE CLOSE_OUTSIDE

**Before:** `CLOSE_OUTSIDE` was emitted for every zone on every bar whose close was outside, with no state change.

Observed:
- EURUSD 2026-03-24..25: 21,920 signals, 21,848 close-outside (99.7%).
- GBPUSD 2026-04-01..02: 2,880 signals, all close-outside; zone never interacted.

**Root cause:** `_detect_close_outside` returned `not zone.contains_price(close)` unconditionally.

### P0.4 Duplicate timestamps

**Before:**
- `FeatureRepository._normalize_bars` sorted but retained duplicate timestamps.
- HTF aggregation silently dropped the affected bucket and raised a misleading “missing entry timeframe” error.
- Direct causal aggregation silently emitted zero bars.
- The canonical resampler already rejected duplicates.

**Root cause:** no duplicate validation in feature ingress/aggregation.

## 4. P0 decisions

| Decision | Rationale |
|---|---|
| Re-size at actual fill, not at plan time | Avoids look-ahead and preserves the fixed-risk contract |
| Keep R-multiple metrics unchanged | Metrics are normalised by actual risk; changing reported metrics would hide the defect |
| Preserve planned risk/size on the plan and actual on the trade | Clear evidence and audit trail |
| Conservative SL-first ambiguity inside a bar | OHLC cannot establish order; never assume favourable path |
| Use actual gapped open when price traded beyond SL | The market did not trade at the stop; using the stop would understate loss |
| No favourable gap-through-TP assumption | Current model fills TP at the target; documented as conservative |
| Close-outside only on inside→outside transition | Prevents per-bar duplication; breaks remain separate signals |
| Reject duplicate timestamps | Ambiguous history cannot be safely aggregated; fail closed |
| Keep JSON/file persistence | No need for a database in P0 |

## 5. Explicit limitations / conflicts

- The engine is **R-multiple research**, not currency P&L. There is no account-currency conversion rate source. `contract_size` is now an explicit sizer/instrument input, but automatic FX conversion is intentionally not invented. Account-currency portfolio/live work is deferred to the phase that introduces actual currency-valued P&L.
- Partial exits, variable spread/slippage, commissions and swap are not part of P0; they are P1 work.
- Ambiguity is still determined from OHLC; without tick data, the SL-first assumption is deterministic and documented.
- The selected P0.3 change alters CORE signal counts; that is intended and recorded before/after. It does not affect S008 execution.
