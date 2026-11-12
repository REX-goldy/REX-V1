# REX Backtesting & Execution QA Report (Agent 7)

- **Date:** 2026-11-03
- **Workspace:** `/home/user/workspaces/7de05e41da33`
- **Git HEAD at test time:** `95f8aaa998f1ce1539c65777b5dd10ac063cbd34`
- **Python:** 3.11.6
- **Scope:** read-only validation of `backtests/*` and `execution/*`; S008 trade simulation on real EURUSD/GBPUSD M1 data; independent metric, lifecycle, curve, reproducibility, cost, edge-case, export and run-archive checks.
- **Constraints honoured:** no app code, strategy, config, dataset or existing test was modified. No commit/push/deploy. No paid requests. Only `docs/qa/BACKTEST_VALIDATION_REPORT.md` and `docs/qa/EVIDENCE/backtest/` were created.

## 1. Data and run configuration

| Dataset | Bars | Actual range (UTC) | Source metadata | Usage |
|---|---:|---|---|---|
| `EURUSD/M1/2026.csv` | 184,963 | 2026-01-01 13:00 → 2026-06-30 23:59 | `twelve_data`, 0 duplicates, 0 invalid, 35 raw gaps | valid S008 run, edge probes |
| `GBPUSD/M1/2026.csv` | 93,600 | 2026-04-01 00:00 → 2026-06-30 23:59 | `twelve_data`, 0 duplicates, 0 invalid, 13 raw gaps | second-pair S008 run |

Read-only hashes are in `docs/qa/EVIDENCE/backtest/data_sha256.txt`; `git status` showed no data changes.

Valid-run window for both pairs: **2026-05-01 → 2026-05-15 inclusive**, M1, **15,720 bars per symbol**. S008 defaults were used unchanged: `lookback=10`, `min_wick_ratio=0.60`, `tolerance=0.0`. Execution defaults: `FixedRiskRewardPolicy(r_multiple=2.0)`, `FixedRiskSizer`, `AccountContext(equity=100_000.0, risk_fraction=0.01)`, `TradeSimulator(max_hold_candles=60)`, `ConservativeOHLCFillModel`. Temporary run archive root: `/tmp/opencode/qa-backtest/runs` via `REX_RUNS_DIR`.

**No profitability claim is made.** Both samples are short, gross (cost-free), and materially loss-making in R terms. They are validation samples, not strategy optimisation or evidence of edge.

## 2. Architecture and lifecycle trace (BT-001)

Actual path in code:

```
Signal (bar N)
  → BacktestRunner loop (backtests/backtest_runner.py:87-139)
  → SweepTradeSetupFactory.create (execution/factories.py:29-63)
  → TradeSetupValidator.validate (execution/validators.py:29-48)
  → TradePlanner.plan (execution/planner.py:31-71)
      FixedRiskRewardPolicy.build (execution/policies.py:66-114)
      FixedRiskSizer.size (execution/sizers.py:35-50)
  → TradePlan(status=PLANNED, planned_at=N, entry_model=NEXT_CANDLE_OPEN)
  → TradeSimulator.add_plan (backtests/trade_simulator.py:79-84)
  → TradeSimulator.update on bar N+1 (trade_simulator.py:86-90)
  → fill at bar N+1 open → Position(entry_time=N+1)
  → same-bar exit check → open position
  → subsequent bars: SL / TP / AMBIGUITY / TIMEOUT
  → finalize_backtest: CANCELLED_END_OF_DATA / FORCE_CLOSE_END_OF_DATA
```

Actual semantics observed:

- **S008 signal:** `LiquiditySweepStrategy.generate_signals` evaluates only the last completed bar; `BULLISH_SWEEP` maps to `LONG` with `stop_hint = signal-bar low`, `BEARISH_SWEEP` maps to `SHORT` with `stop_hint = signal-bar high`; `entry_hint = signal close`.
- **Plan:** planned entry is the signal-bar close; TP is `entry ± abs(entry-stop) * 2.0`; plan timeout defaults to 5 candles; risk amount is `100,000 × 0.01 = 1,000`; size is `1,000 / abs(planned entry − stop)`. `status` is always `PLANNED`.
- **Fill:** `NEXT_CANDLE_OPEN` fills at the next bar's **open**. TP is recalculated from the **actual** fill and actual stop distance in `trade_simulator.py:216-220`; the plan's size and `risk_amount` are **not** recalculated (see D-BT-01).
- **Status transitions:** `TradePlanStatus` documents `planned/queued/active/closed/cancelled/expired`, but the backtest only ever persists `PLANNED`. `TradePlan` is frozen; the executor records lifecycle facts in `Position`, `ClosedTrade` and `TerminatedSetup` instead. This is an architectural gap, not a crash: the observable lifecycle is inferred from closed/terminated records.
- **Overlap:** while a plan is pending or a position is open for `(strategy_id, symbol)`, new signals are ignored and counted in `ignored_active_lifecycle_count` (`backtest_runner.py:100-103`, `trade_simulator.py:70-77`).
- **Timeout/expiry:** pending plans expire when `waited >= plan.timeout_candles` (`trade_simulator.py:235-242`). This branch is effectively dormant for S008 because `NEXT_CANDLE_OPEN` always fills on the next bar. Open positions time out at `max_hold_candles` (`trade_simulator.py:165-167`).
- **End of data:** pending plans become `CANCELLED_END_OF_DATA`; open positions are force-closed at the final bar close as `FORCE_CLOSE_END_OF_DATA` (`trade_simulator.py:92-121`).

## 3. Test matrix

Status values: PASS / FAIL / BLOCKED / NOT TESTED / NOT APPLICABLE.

| Test ID | Component | Scenario | Data | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| BT-001 | Runner / planner / simulator | Trace Signal → TradeSetup → TradePlan → Position → ClosedTrade/TerminatedSetup and timeout/expiry behaviour | Actual code + S008 runs | Documented causal lifecycle, no lookahead, no status mutation | Trace matches code; only `PLANNED` status persisted; expiry dormant under `NEXT_CANDLE_OPEN` | PASS | `valid_runs_analysis.json`; source lines above |
| BT-002 | S008 + trade simulation | Valid run, EURUSD | EURUSD M1 2026-05-01→15, 15,720 bars | Trades simulated with full accounting | 657 signals, 606 trades, 112 wins / 494 losses, WR 18.4818%, PF 0.432394, expectancy −0.479562 R, max DD 297.489854 R, 39 ambiguous | PASS | `EURUSD_S008_2026-05-01_2026-05-15_server_run.json`, `..._trades.csv` |
| BT-003 | S008 + trade simulation | Valid run, second pair | GBPUSD M1 2026-05-01→15, 15,720 bars | Trades simulated with full accounting | 500 signals, 468 trades, 71 wins / 397 losses, WR 15.1709%, PF 0.346468, expectancy −0.559347 R, max DD 272.473235 R, 14 ambiguous | PASS | `GBPUSD_S008_2026-05-01_2026-05-15_server_run.json`, `..._trades.csv` |
| BT-004 | `metrics.py` | Independently recompute win rate, PF, expectancy, total R, max DD, largest win/loss | Both valid runs | All reported metrics match recomputation | Every field matched to 1e-12; 0 discrepancies | PASS | `valid_runs_analysis.json → metric_comparison` |
| BT-005 | Runner / simulator | Entry after signal, next-open fill, SL/TP levels, exit reason, holding, ordering, overlap | Both valid runs | 606/468 trades satisfy all invariants | 0 lifecycle failures; 606 + 468 trades checked; no same-symbol overlap | PASS | `valid_runs_analysis.json → lifecycle` |
| BT-006 | Planner / sizer / simulator | Risk per trade and position size after actual fill | Both valid runs | Realised currency risk equals planned `risk_amount` | EURUSD 543/606 trades differ, max 5.50×; GBPUSD 441/468 differ, max 6.25× | FAIL (D-BT-01) | `valid_runs_analysis.json → lifecycle.risk` |
| BT-007 | Results / server curve | Reconstruct single-symbol cumulative R and drawdown from trades | Both valid runs | Curve points equal trade count; final R and max DD equal metrics | EURUSD 606/606 points, final −290.614854 R, max DD 297.489854 R; GBPUSD 468/468, final −261.774597 R, max DD 272.473235 R | PASS | `valid_runs_analysis.json → equity_curve` |
| BT-008 | Runner / simulator | Same config twice; compare metrics, trades, signals, server artifacts | Both valid runs | Byte-stable fingerprints and identical metrics/curves | Direct digests identical; server comparable payloads identical | PASS | `valid_runs_analysis.json → reproducibility` |
| BT-009 | Runner accounting | Signal vs trade counts; rejected/expired/cancelled; `simulate_trades=False` vs `True` | Both valid runs | Reconciliations zero; signal-only has signals but no trades | EURUSD signals 657 = 635 accepted + 22 ignored + 0 rejected; 635 = 606 closed + 29 invalid entries; GBPUSD 500 = 485 + 15; 485 = 468 + 16 + 1 cancelled; signal-only same signal counts, 0 trades | PASS | `valid_runs_analysis.json → reconciliation*, signal_only` |
| BT-010 | Costs / fills | Verify gross, cost-free classification | Both valid runs + plan records | No bid/ask; no fee/spread/slippage applied | OHLCV only; every plan `estimated_fees/spread/slippage = 0.0`; server assumptions `costs_applied=false` | PASS | `valid_runs_analysis.json → lifecycle.checks`, server run assumptions |
| BT-011 | S002 / CORE_ZONE_BREAKOUT | Signal study on real zoned data | EURUSD M1 2026-02-01→07, 7,200 bars | Signals recorded, no trades, no crash | CORE 56,818 signals (56,680 `close_outside`, 69 `enter_zone`, 39 `break_above`, 30 `break_below`); S002 659 signals (528 `retest_above`, 131 `retest_below`); 0 trades | PASS | `edge_case_analysis.json → signal_study_*` |
| BT-012 | Runner | Empty dataset, insufficient bars, no-signal window | Empty list; first 5 EURUSD bars; EURUSD 2026-01-01 13:00→14:59 (120 bars) | No crash; zeros | All returned 0 signals/trades; reconciliations zero | PASS | `edge_case_analysis.json → empty/insufficient/no_signal` |
| BT-013 | Simulator | Pending-plan expiry and open-position timeout | Actual EURUSD bars; synthetic no-exit fill | `EXPIRED` at configured count; `TIMEOUT` at `max_hold` | Pending active 1,1,0 → `EXPIRED` at third bar; max_hold 2/3 close at 2/3 bars | PASS | `edge_case_analysis.json → pending_plan_expiry`, `open_timeout_*` |
| BT-014 | Simulator | `max_hold_candles=1` boundary | Synthetic bars + no-exit fill model | Timeout at one candle | Closed after 2 candles (`holding_duration_candles=2`) | FAIL (D-BT-03) | `edge_case_analysis.json → open_timeout_max_hold_1` |
| BT-015 | Fill model / simulator | Ambiguous intrabar exits in actual data | EURUSD/GBPUSD valid runs | Both levels touched → conservative exit and `pnl_r=-1` | 39 EURUSD + 14 GBPUSD ambiguous exits; all exactly −1R; examples touch SL and TP in same bar | PASS | `valid_runs_analysis.json`, `edge_case_analysis.json → ambiguous_intrabar_actual` |
| BT-016 | Fill model / simulator | Gap opens through SL while bar also spans TP | Synthetic deterministic OHLC | Loss reflected at actual fill, i.e. worse than −1R | Exit at 1.1000 vs SL 1.1400, raw −5.0R, recorded −1.0R | FAIL (D-BT-05) | `ambiguity_gap_probe.json` |
| BT-017 | Simulator finalize | Open position at end of data; pending plan at end of data | EURUSD M1 2026-05-04→08; GBPUSD valid run | Force close at final close; pending cancelled at final time | EURUSD 1 force close at 21:59, price 1.17887 = last close; GBPUSD 1 cancelled at last bar 21:59 | PASS | `edge_case_analysis.json → end_of_data_*` |
| BT-018 | Strategies / zones | Missing zone book | Empty `ZoneBook` on actual EURUSD bars (500) | No crash, no signals | CORE and S002 both 0 signals, 0 trades | PASS | `edge_case_analysis.json → missing_zones_*` |
| BT-019 | `results.py` exports | JSON, CSV, Excel; finite values; round-trip fields | EURUSD valid run | Parseable, no NaN/Infinity, expected sheets/fields | JSON parses, no forbidden tokens, round-trip keyset/trade count equal; CSV = 1 summary row; XLSX sheets `Summary`, `Signal Outcomes`, `Closed Trades` (29/658/607 rows incl. headers) | PASS | `edge_case_analysis.json → export`; `exports/` |
| BT-020 | Run archive | Run ID and archive compatibility | Server EURUSD run | Valid ID, `get_run`/`list_runs`, schema, no non-finite values | ID matched regex; `get_run` returns same; `ui_run_v1`; artifact equals loaded; direct result has no result-id field | PASS | `edge_case_analysis.json → run_archive` |
| BT-021 | Server equity curve | Duplicate exit timestamps across symbols | Combined actual EURUSD+GBPUSD M1 2026-05-01→15, 1,074 trades | One curve point per trade, lossless | 55 duplicate exit timestamps; 1,074 trades collapsed to 1,019 curve points | FAIL (D-BT-02) | `valid_runs_analysis.json → multi_symbol_curve_probe` |
| BT-022 | `reconcile_signals()` / server | Signal-only run reconciliation | CORE on EURUSD 2026-02-01→07, 56,818 signals | Reconciliation not exposed as an execution imbalance, or difference N/A | Server reports `generated=56818`, `accepted=0`, `difference=56818` | FAIL (D-BT-04) | `core_signal_only_server_run.json` |
| BT-023 | Existing regression tests | Targeted unittest baseline | `test_backtesting`, `test_trade_simulation`, `test_execution_qa_adversarial` | All pass | 77 tests, OK, 0.212 s | PASS | `baseline_tests.log` |

## 4. Valid-run metrics and independent recomputation (BT-002–BT-004)

### 4.1 Reported server metrics

| Metric | EURUSD S008 | GBPUSD S008 |
|---|---:|---:|
| Bars | 15,720 | 15,720 |
| Signals | 657 | 500 |
| Accepted setups | 635 | 485 |
| Ignored (active lifecycle) | 22 | 15 |
| Rejected at policy/factory boundary | 0 | 0 |
| Invalid entries (`REJECTED_INVALID_ENTRY`) | 29 | 16 |
| Closed trades | 606 | 468 |
| Wins / losses / zero-PnL | 112 / 494 / 0 | 71 / 397 / 0 |
| Win rate | 18.4818481848% | 15.1709401709% |
| Profit factor | 0.4323941185 | 0.3464678513 |
| Gross profit / gross loss (R) | 221.3862781955 / 512.0011321357 | 138.7789145588 / 400.5535117586 |
| Expectancy | −0.4795624652 R | −0.5593474299 R |
| Total R | −290.6148539402 | −261.7745971998 |
| Max drawdown | 297.4898539402 R | 272.4732349678 R |
| Largest win / largest loss | 2.0 / −4.3255813953 | 2.0 / −2.6000000000 |
| Average win / average loss | 1.9766631982 / −1.0364395387 | 1.9546325994 / −1.0089509112 |
| Ambiguous exits | 39 | 14 |
| Average holding (candles) | 2.6221122112 | 3.0128205128 |
| TIMEOUT exits | 2 | 5 |
| Force-close / cancelled | 0 / 0 | 0 / 1 |
| Warnings | costs not applied; R units; 39 ambiguous at −1R; 2 range gaps | costs not applied; R units; 14 ambiguous at −1R; 2 range gaps |

### 4.2 Formula and source

Source: `backtests/metrics.py:103-155`; trade order comes from `TradeSimulator.get_all_closed_trades` sorted by `exit_time` (`backtests/trade_simulator.py:123-128`).

Let `p_i` be `pnl_r` for closed trade `i`, `N` the number of closed trades, and `C_k = Σ_{i≤k} p_i` in exit-time order.

- Wins = `count(p_i > 0)`; losses = `count(p_i < 0)`; zero-PnL trades are excluded from the win-rate denominator (`decided = wins + losses`).
- Win rate = `wins / decided × 100`.
- Profit factor = `Σ(p_i > 0) / |Σ(p_i < 0)|`; `None` if gross loss is zero.
- Expectancy = `Σ p_i / N` (all closed trades, including zeros).
- Max drawdown = `max_k( max_{j≤k} C_j − C_k )`, starting at 0.
- Largest win = max positive; largest loss = min (most negative) value.
- Total R = `Σ p_i`.
- R-multiple per trade = `sign × (exit − entry) / |entry − sl|`, where `sign = +1` for LONG and `−1` for SHORT (`trade_simulator.py:15-34`); AMBIGUITY is overwritten to `−1.0`.

### 4.3 Comparison result

All reported fields matched the independent recomputation for both pairs to `1e-12` (win rate, PF, expectancy, total R, max DD, largest win/loss, average win/loss, trade count, ambiguous count, average holding). The server run and direct `BacktestRunner` run also matched on all metrics. **No metric discrepancy was found.** The only caveat is the semantics of holding duration described in section 8.

## 5. Lifecycle checks (BT-005, BT-006)

For every closed trade, all of the following were verified against the actual bars and the recorded plans:

- **Entry timing:** `entry_time > signal.timestamp` for 606/606 EURUSD and 468/468 GBPUSD.
- **Plan timing:** `planned_at == signal.timestamp`; status `PLANNED`; entry model `NEXT_CANDLE_OPEN`.
- **Fill price:** entry price equals the entry bar `open` for every trade (the actual fill model).
- **Stop:** stop equals the signal bar low (LONG) or high (SHORT) for every trade.
- **Target:** `tp = entry ± |entry − sl| × 2.0` for every trade.
- **Exit reason:** only `SL`, `TP`, `AMBIGUITY`, `TIMEOUT`, `FORCE_CLOSE_END_OF_DATA` were observed.
- **PnL formula:** non-ambiguous trades matched the R formula for 567/567 EURUSD and 454/454 GBPUSD; all 53 ambiguous trades were exactly −1.0R.
- **Ordering:** closed trades are sorted by non-decreasing `exit_time`; `entry_time <= exit_time`; no same-symbol overlap (605/605 and 467/467 adjacent pairs non-overlapping).
- **Holding duration:** internally consistent with the code convention. For SL/TP/AMBIGUITY exits after the entry candle, the exit candle is not counted (span minus 1); entry-candle exits count 1; TIMEOUT and FORCE_CLOSE include the exit candle. This means `avg_holding_duration` is a completed-candle style measure, not an inclusive candle span.

### D-BT-01 — Realised position risk does not match planned risk (MEDIUM)

- **Repro:** `valid_runs_analysis.json → runs.*.lifecycle.risk`.
- **Cause:** the sizer uses the planned entry (signal close) and stop; the simulator fills at the next bar open and never re-sizes. `plan.position_size` and `plan.risk_amount` are carried unchanged while actual risk distance changes (`execution/sizers.py:42-50`, `backtests/trade_simulator.py:191-233`).
- **Observed:** EURUSD 543/606 trades (89.6%) had realised risk different from planned; max absolute deviation **5.50×** (e.g. planned entry 1.17275, actual 1.17285, realised 333.33 vs planned 1,000). GBPUSD 441/468 (94.2%) differed; max **6.25×** (e.g. planned entry 1.36028, actual 1.36023, realised 1,333.33 vs planned 1,000).
- **Impact:** R-multiple metrics are unaffected because they are normalised by actual risk, but the execution layer's "fixed 1% risk" contract is violated. This should be fixed before sizing/currency-risk claims or paper/live use.
- **Note:** no code was changed.

## 6. Equity curve, reproducibility, signal/trade accounting (BT-007–BT-010)

- **Single-symbol curve (PASS):** reconstructed from closed trades independently. EURUSD 606 curve points, final −290.6148539402 R, max DD 297.4898539402 R. GBPUSD 468 points, final −261.7745971998 R, max DD 272.4732349678 R. These match the metric outputs.
- **Multi-symbol curve (D-BT-02, LOW):** `server/research_service.py:702-721` keys curve points by integer epoch seconds. With combined actual EURUSD+GBPUSD data (1,074 trades) there were 55 duplicate exit timestamps; the server curve had only 1,019 points, so 55 trades were not represented. Final R and max DD happened to remain equal in this sample, but the curve is not lossless and can diverge in other samples. This is a UI/reporting defect, not a metric-engine defect.
- **Reproducibility (PASS):** direct runs produced identical SHA-256 fingerprints of metrics + signals + trades for both pairs; two server runs produced identical comparable JSON payloads (`metrics`, `reconciliation`, `signals`, `equity_curve`, `trades`, `warnings`).
- **Signal vs trade accounting (PASS):** all simulated-run reconciliations had `difference=0`. Rejected invalid entries (29 EURUSD, 16 GBPUSD) and end-of-data cancellations (1 GBPUSD) are explicitly accounted for. `simulate_trades=False` preserves the signal count but produces 0 trades and zero performance metrics; this is distinct from simulation mode.
- **Cost classification (PASS):** datasets contain OHLCV only, no bid/ask. All recorded plans have `estimated_fees=0.0`, `estimated_spread=0.0`, `estimated_slippage=0.0`. Server assumptions explicitly say `costs_applied=false`. Results are **gross/cost-free**, not cost-adjusted.

## 7. Edge cases (BT-011–BT-018, BT-022)

| Scenario | Result |
|---|---|
| CORE_ZONE_BREAKOUT signal study | 7,200 actual EURUSD bars, 56,818 signals: `close_outside` 56,680, `enter_zone` 69, `break_above` 39, `break_below` 30; 0 trades. The dominant `close_outside` count is the strategy's per-bar/per-zone behaviour, not trade candidates. |
| S002 signal study | Same 7,200 bars, 659 signals: `retest_above` 528, `retest_below` 131; 0 trades. |
| CORE with `simulate_trades=True` | All 56,818 signals rejected at the policy/factory boundary (`SweepTradeSetupFactory` does not handle breakout signals); 0 trades, reconciliation difference 0. Server correctly exposes CORE as signal-study only. |
| Empty dataset | 0 bars, 0 signals/trades, no crash, null start/end, reconciliations zero. |
| Insufficient bars | 5 actual bars vs required 11 for S008; 0 signals/trades, no crash. |
| No-signal window | Actual EURUSD 2026-01-01 13:00→14:59, 120 bars; 0 signals/trades, no crash. |
| Pending plan expiry | LIMIT plan, timeout 3, actual bars: active 1→1→0; `EXPIRED` at 2026-02-01 22:03. |
| Open-position timeout | `max_hold=2/3` closed at 2/3 candles. `max_hold=1` closed at 2 candles (D-BT-03). |
| Missing zones | Empty `ZoneBook` on 500 actual bars: CORE and S002 both 0 signals, no crash. |
| Ambiguous actual exits | 39 EURUSD + 14 GBPUSD; all recorded −1R; examples confirm both SL and TP touched in the exit bar. |
| End-of-data force close | EURUSD 2026-05-04→08: 1 force close at final bar 21:59, exit price 1.17887 equals final close. |
| End-of-data cancellation | GBPUSD valid run: 1 pending plan cancelled at final bar 21:59. |
| Signal-only reconciliation (D-BT-04, LOW) | CORE server run reports `generated=56818`, `difference=56818`; execution counters are not populated in signal-only mode, so this field looks like an unexplained imbalance. |

### D-BT-03 — `max_hold_candles=1` off-by-one (LOW)

- **Repro:** `edge_case_analysis.json → open_timeout_max_hold_1`.
- **Cause:** the entry candle is only checked for SL/TP in `_evaluate_new_positions`; timeout is checked on the following bar in `_update_open_positions`. With `max_hold_candles=1`, the position is closed on the second candle with `holding_duration_candles=2`.
- **Impact:** default S008 uses 60 and is unaffected; a configured 1-candle timeout is exceeded.

### D-BT-04 — Signal-only reconciliation looks like an imbalance (LOW)

- **Repro:** `core_signal_only_server_run.json`.
- **Observed:** `simulated=false`, `total_signals=56818`, `reconciliation={"generated":56818,"accepted":0,"ignored":0,"rejected":0,"difference":56818}`.
- **Cause:** `BacktestResult.reconcile_signals()` compares generated signals with execution-path counters that are not used when `simulate_trades=False`; `server/research_service.py:929` still exports it.
- **Impact:** reporting/UI confusion between signal study and execution accounting; no trade-engine error.

### D-BT-05 — AMBIGUITY can understate a gap loss (MEDIUM)

- **Repro:** `ambiguity_gap_probe.json`.
- **Setup:** LONG entry 1.1500, SL 1.1400, TP 1.1700; next bar opens at 1.1000 and ranges 1.0900–1.1800 (both SL and TP touched). Fill model returns `bar.open` = 1.1000 with reason `AMBIGUITY`; `_close_position` overwrites PnL to `−1.0R`.
- **Observed:** raw formula = **−5.0R**, recorded = **−1.0R**.
- **Impact:** in gap-through scenarios where both levels are touched, the "conservative −1R" rule is actually optimistic, understating losses and drawdown. Actual valid-run ambiguous examples all had raw = −1R, so this was not triggered in the sample, but the branch is reachable.

## 8. Other observations (not counted as failures)

- **Holding-duration semantics:** see section 5. The convention is internally consistent but not explicitly documented; SL/TP/AMBIGUITY exits exclude the exit candle while TIMEOUT/force-close include it, so `avg_holding_duration` is not a pure inclusive span.
- **CORE signal volume:** `CLOSE_OUTSIDE` is emitted on every bar for every zone whose close is outside; hence 56,680 such signals in 7,200 bars. This is strategy semantics, but consumers should not treat total signals as trade candidates.
- **TradePlan status surface:** only `PLANNED` is persisted in backtests; no per-plan status-transition history exists. This is documented in `models/trade_plan.py:12-25`.
- **Multi-symbol S002:** not part of the required S008 validation; a short probe is included in `multisymbol_s002_probe.json` but the server runs one symbol per backtest, so this is out of scope rather than a validated behaviour.

## 9. Export, serialization and run archive (BT-019, BT-020)

- **JSON:** exported and re-parsed; no `NaN`, `Infinity`, or `-Infinity`; recursive finiteness check passed; round-trip keyset and closed-trade count identical.
- **CSV:** one summary row, 29 summary columns; it intentionally does **not** contain the trade list or signal outcomes.
- **Excel:** sheets `Summary` (29 rows), `Signal Outcomes` (658 rows including header), `Closed Trades` (607 rows including header); opened successfully with `openpyxl`.
- **Run archive:** server run ID `20261103T133504Z_750fee2c` matched `[A-Za-z0-9_-]{1,80}`; `get_run` and `list_runs` returned it; schema `ui_run_v1`; saved artifact equals the loaded object; no forbidden non-finite tokens. A direct `BacktestResult` has no `id` field — run IDs belong to the server archive, not the core result object.

## 10. Blocked / not applicable

| Item | Status | Reason |
|---|---|---|
| Cost-adjusted PnL (spread, commission, slippage, bid/ask) | BLOCKED | Datasets are OHLCV M1 with no bid/ask or tick data; paid requests are forbidden. Results are explicitly gross. |
| Paper/live lifecycle status transitions (`QUEUED`/`ACTIVE`/`CLOSED`/`CANCELLED`/`EXPIRED`) | NOT APPLICABLE | No paper/live executor is part of this workspace; backtest only persists `PLANNED`. |
| Sub-candle / tick-level fill-path resolution | BLOCKED | No tick data; OHLC ambiguity is resolved conservatively (with the D-BT-05 exception). |
| Profitability / statistical significance | NOT TESTED | Out of scope by instruction; sample is short and loss-making. |
| Multi-symbol S002 full validation | NOT TESTED | Server runs one symbol per backtest; S002's shared processed-bar cursor is not exercised by the supported single-symbol path. |

## 11. Reproduction commands and evidence

Command log: `docs/qa/EVIDENCE/backtest/command_log.txt`.

```bash
# Valid runs, independent metrics, lifecycle, reproducibility, multi-symbol curve probe
REX_RUNS_DIR=/tmp/opencode/qa-backtest/runs \
REX_DATA_DIR=/home/user/workspaces/7de05e41da33/data/historical \
python /tmp/opencode/qa-backtest/qa_backtest_analysis.py

# Edge cases, exports, archive checks
REX_RUNS_DIR=/tmp/opencode/qa-backtest/runs \
REX_DATA_DIR=/home/user/workspaces/7de05e41da33/data/historical \
python /tmp/opencode/qa-backtest/qa_backtest_edges.py

# Gap-ambiguity and signal-only reconciliation probes
python /tmp/opencode/qa-backtest/qa_ambiguity_gap.py
REX_RUNS_DIR=/tmp/opencode/qa-backtest/runs \
python /tmp/opencode/qa-backtest/core_signal_only_server.py

# Baseline regression tests
CI=1 python -m unittest tests.test_backtesting tests.test_trade_simulation \
  tests.test_execution_qa_adversarial -v
```

Key evidence files (all under `docs/qa/EVIDENCE/backtest/`):

- `valid_runs_analysis.json` — server/direct metrics, independent recomputation, lifecycle, curves, reproducibility, multi-symbol probe.
- `EURUSD_S008_2026-05-01_2026-05-15_server_run.json`, `..._direct_result.json`, `..._trades.csv`.
- `GBPUSD_S008_2026-05-01_2026-05-15_server_run.json`, `..._direct_result.json`, `..._trades.csv`.
- `edge_case_analysis.json` — all edge, export and archive results.
- `core_signal_only_server_run.json` — BT-022 evidence.
- `ambiguity_gap_probe.json` — BT-016/D-BT-05 evidence.
- `multisymbol_s002_probe.json` — out-of-scope probe.
- `exports/` — JSON/CSV/XLSX export artifacts.
- `baseline_tests.log` — 77/77 targeted tests passing.
- `analysis_scripts/` — exact replication scripts used.
- `data_sha256.txt` — read-only dataset hashes.

## 12. Final summary

- **Runs executed:** S008 EURUSD (15,720 M1 bars, 657 signals, 606 trades); S008 GBPUSD (15,720 M1 bars, 500 signals, 468 trades); plus CORE/S002 signal studies, edge probes, export/archive checks, and 77 baseline regression tests.
- **Tests:** 18 PASS, 5 FAIL (BT-006, BT-014, BT-016, BT-021, BT-022); blocked/N/A items listed in section 10.
- **Metric discrepancies:** none. All reported metrics matched independent recomputation and direct-run recomputation to 1e-12.
- **Confirmed defects:** D-BT-01 realised risk vs planned size (MEDIUM); D-BT-05 AMBIGUITY gap understates loss (MEDIUM); D-BT-02 multi-symbol equity curve drops duplicate-timestamp trades (LOW); D-BT-03 `max_hold=1` off-by-one (LOW); D-BT-04 signal-only reconciliation imbalance (LOW).
- **Data integrity:** read-only; no app code, config, datasets or existing tests modified; no commit/push/deploy.
- **Report path:** `docs/qa/BACKTEST_VALIDATION_REPORT.md`.
