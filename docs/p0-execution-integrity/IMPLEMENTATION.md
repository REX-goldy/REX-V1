# P0 Execution Integrity — Implementation

## 1. P0.1 Position sizing and realised risk

### New sizing behavior

`execution/sizers.py`:
- `FixedRiskSizer` now supports:
  - `contract_size: float | None` — explicit contract value per price unit; `None` resolves `Instrument.contract_size` (default `1.0`).
  - `min_position_size` / `max_position_size` bounds.
  - finite/positive validation; out-of-bounds returns `None` (fail closed).
- Formula:
  ```
  risk_amount = equity × risk_fraction
  position_size = risk_amount / (|entry − stop| × contract_size)
  ```

`backtests/trade_simulator.py`:
- At the actual fill, `_size_at_fill` recomputes units from the **actual** entry and stop.
- If a sizer is supplied by the planner, it is reused; otherwise the plan's risk amount is preserved with `plan.risk_amount / risk_distance`.
- The plan's `position_size` remains the planned estimate; the position/closed trade stores the actual units.
- Rejections are explicit:
  - invalid stop/entry (`REJECTED_INVALID_ENTRY`)
  - non-finite/zero/out-of-bounds size (`REJECTED_SIZE_INVALID`).
- `BacktestRunner` passes the planner's sizer/account into the simulator; there is still one execution path.

### New audit fields

`Position` and `ClosedTrade`:
- `planned_entry_price`
- `planned_position_size`
- `planned_risk_amount`
- `position_size` (actual)
- `realized_risk_amount`
- `entry_slippage`
- `execution_assumption`

The server trade payload exposes the same fields. Strategy Lab shows planned → realised risk per trade and exposes the execution assumption as the exit tag tooltip.

### Account currency

No currency conversion feed or account-currency P&L exists in the current R-multiple research engine. `contract_size` provides the explicit hook for a future account-currency model; no exchange rate is fabricated. This limitation is recorded in `ASSESSMENT.md`.

## 2. P0.2 Gap and ambiguity execution

`ConservativeOHLCFillModel` remains the deterministic OHLC model.

| Scenario | Fill | Reason | PnL |
|---|---|---|---|
| Normal SL | SL level | `SL` | formula |
| Gap through SL (SL only) | bar open, worse than SL | `SL` | actual adverse R |
| Normal TP | TP level | `TP` | +R |
| Gap through TP | TP level (no favourable assumption) | `TP` | +R |
| Both SL and TP touched, open inside | SL level (conservative) | `AMBIGUITY` | −1R |
| Both touched, open through SL | bar open | `AMBIGUITY` | actual adverse R (e.g. −5R) |
| Entry and exit same candle | next open → same bar exit | `TP`/`SL`/`AMBIGUITY` | determined by fill |
| Missing next candle | pending plan cancelled at end of data | `CANCELLED_END_OF_DATA` | no trade |

`TradeSimulator._close_position` no longer overwrites ambiguity PnL with −1R. `execution_assumption` records:
- `both_levels_touched_stop_first_conservative`
- `both_levels_touched_gap_through_stop_at_open`
- `gap_through_stop_at_open`
- `stop_at_level`
- `target_at_level`
- `timeout_at_close`
- `force_close_at_final_close`

Server warning text no longer claims all ambiguity is −1R.

## 3. P0.3 CORE_ZONE_BREAKOUT signal lifecycle

`strategies/breakout.py`:
- `CLOSE_OUTSIDE` is now emitted only when the previous zone position was `INSIDE` and the current position is outside.
- First observation does not emit `CLOSE_OUTSIDE` (no state transition).
- Repeated closes on the same side do not re-emit.
- `BREAK_ABOVE` / `BREAK_BELOW` remain separate breakout transitions.
- `ENTER_ZONE` remains an interaction signal.
- Existing intended rule semantics are otherwise unchanged.

**Before → after on real data:**

| Dataset/range | Before signals | After signals | Before close-outside | After close-outside |
|---|---:|---:|---:|---:|
| EURUSD 2026-03-24..25 | 21,920 | 108 | 21,848 | 36 |
| GBPUSD 2026-04-01..02 | 2,880 | 0 | 2,880 | 0 |

The GBPUSD case has no zone interaction, so after P0 it emits no signals. This is the intended consequence of removing unconditional per-bar close-outside events. No zone levels were invented.

## 4. P0.4 Duplicate timestamp handling

- `core/features/repository.py::_normalize_bars`:
  - explicit deterministic sorting remains (documented);
  - duplicates are now rejected with `Duplicate timestamps in <TF> for <symbol>: ...`.
- `core/features/timeframes.py::validate_unique_timestamps`:
  - called by `aggregate_completed_bars` and `prepare_causal_bars`;
  - rejects duplicate source timestamps before bucketing.
- `research.free_ohlc.resampler` already rejected duplicates; behavior is now consistent.
- The previous silent drop/misleading missing-timeframe error is replaced by a precise validation error.
- Existing test fixture that multiplied identical-timestamp bars was updated to shift timestamps; this was a test fixture defect, not an application relaxation.

## 5. Files changed

| File | Change |
|---|---|
| `execution/sizers.py` | Contract size, bounds, finite validation |
| `core/market/instrument.py` | Optional `contract_size` with validation |
| `models/position.py` | Planned/actual risk fields |
| `models/closed_trade.py` | Planned/actual risk, execution assumption |
| `backtests/trade_simulator.py` | Fill-time re-sizing, actual ambiguity PnL, audit fields |
| `backtests/backtest_runner.py` | Passes planner sizer/account to simulator |
| `backtests/results.py` | Counts `REJECTED_SIZE_INVALID` |
| `server/research_service.py` | New trade fields and corrected warning |
| `strategies/breakout.py` | Close-outside transition semantics |
| `core/features/repository.py` | Duplicate validation |
| `core/features/timeframes.py` | Duplicate validation in causal paths |
| `frontend/src/pages/ResearchPage.tsx` | Planned → realised risk column |
| `frontend/src/types.ts` | Optional trade audit fields |
| `tests/test_p0_execution_integrity.py` | 11 regression tests |
| `tests/test_strategy_interface.py` | Updated expected CORE signal lifecycle |
| `tests/test_market_engine_verification.py` | Removed duplicate-timestamp test fixture |

No schema/DB migration was introduced. Existing run artifacts remain readable; new fields are optional on old records. `ClosedTrade`/`Position` defaults preserve old construction compatibility.

## 6. P0 completion gate

| Gate | Status |
|---|---|
| P0.1 risk mismatch fixed | **PASS** — 0/606 EURUSD, 0/468 GBPUSD mismatches; planned risk 1,000 equals realised risk |
| P0.2 gap semantics fixed | **PASS** — gap-through-stop records actual −5R; conservative inside-bar ambiguity remains −1R |
| P0.3 repeated CLOSE_OUTSIDE fixed | **PASS** — transition-only; before/after documented |
| P0.4 duplicate timestamps | **PASS** — explicit rejection in repo and causal paths |
| Regression suite | **604 / 604 PASS** |
| Datasets unchanged | **PASS** — no writes to `data/historical` |
| Independent metric reproducibility | **PASS** — S008 before/after R metrics reproduced; changes explained by two ambiguous gap fills |
| Strategy behavior changes documented | **PASS** — CORE counts and one test expectation updated deliberately |

P0 gate is **PASS for the scoped fixes**. P1–P6 remain unstarted; costs, data-quality reporting, pre-backtest validation, portfolio, agents, paper/live are not implemented in this phase.
