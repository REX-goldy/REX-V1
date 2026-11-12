# REX Strategy Validation Report

- **Agent:** Agent 6 - Strategy QA
- **Repository:** `/home/user/workspaces/7de05e41da33`
- **Revision:** `95f8aaa998f1ce1539c65777b5dd10ac063cbd34` (`main`)
- **Scope:** registered strategy catalog, valid/invalid configurations on the
  actual datasets, long/short direction coverage, determinism, signal/trade
  accounting, the AUDUSD missing-zone error, and gross/cost-free status.
- **Change policy:** no strategy logic, `config/zones.json`, datasets,
  application code, or existing tests were modified. Only this report and
  `docs/qa/EVIDENCE/strategy/` were created. All generated run artifacts went to
  temporary `REX_RUNS_DIR` values under `/tmp/opencode/qa-strategy/`.
- **Evidence root:** `docs/qa/EVIDENCE/strategy/` (machine-readable
  `results.json`, `inventory.json`, run summaries, raw run JSON, determinism,
  invalid-case, and AUDUSD evidence).

## 1. Executive summary

- **Strategies tested:** `CORE_ZONE_BREAKOUT`, `S002`, `S008`. Registry discovery
  found exactly these three; no additional concrete `BaseStrategy` classes exist
  in `strategies/`.
- **Test results:** 45 tests - 41 `PASS`, 2 `BLOCKED`, 2 `NOT APPLICABLE`,
  0 `FAIL`. The full matrix is in section 6.
- **AUDUSD conclusion:** the error
  `No zone book is configured for AUDUSD in config/zones.json` is **correct
  service-level validation** triggered by an **incomplete AUDUSD zone
  configuration**, not a strategy/engine/calculation bug. The dataset is present
  and zone-free `S008` runs on AUDUSD over HTTP. The remaining issue is a
  **LOW-severity UX/integration gap**: no API exposes which symbols have zone
  books, so the UI cannot disable/warn before submission.
- **Confirmed defects:** 4 (one MEDIUM, two LOW, one INFO). See section 8.
  They do not change the conclusion that the documented strategy rules are
  implemented as written; they concern signal semantics, silent zero-risk
  rejection, UI discoverability, and an API footgun.
- **Cost/profitability:** all simulated results are **gross R-multiples with
  transaction costs disabled**. No profitability claim is made. Signal study
  (`CORE_ZONE_BREAKOUT`) is kept separate from trade simulation (`S002`, `S008`).

## 2. Environment and actual inputs

| Item | Observed value | Evidence |
|---|---|---|
| Zone book: EURUSD | 8 manual zones, prices 1.1400-1.2050 | `config/zones.json:2-73`; `inventory.json` |
| Zone book: GBPUSD | 1 manual zone, 1.2600-1.2625 | `config/zones.json:75-87`; `inventory.json` |
| Zone book: AUDUSD | none | `config/zones.json`; `inventory.json` |
| EURUSD/M1/2026 | 184,963 bars, 2026-01-01 13:00 to 2026-06-30 23:59 UTC, provider twelve_data | `data/historical/EURUSD/M1/2026.meta.json` |
| GBPUSD/M1/2026 | 93,600 bars, 2026-04-01 to 2026-06-30 UTC | `data/historical/GBPUSD/M1/2026.meta.json` |
| AUDUSD/M1/2026 | 93,600 bars, 2026-04-01 to 2026-06-30 UTC | `data/historical/AUDUSD/M1/2026.meta.json` |
| USDJPY/M1/2026 | 93,600 bars, 2026-04-01 to 2026-06-30 UTC | `data/historical/USDJPY/M1/2026.meta.json` |
| USDCAD/M1/2026 | 93,600 bars, 2026-04-01 to 2026-06-30 UTC | `data/historical/USDCAD/M1/2026.meta.json` |

Zone loading is manual-only and validates ids, bounds, timeframes, strength,
kind, source, duplicates, and overlaps (`core/zone_loader.py:10-65`,
`core/validation.py:48-143`). No zone levels were invented in this QA.

## 3. Registry inventory

`StrategyRegistry.discover()` imports non-private modules in `strategies/` and
registers concrete `BaseStrategy` subclasses (`strategies/registry.py:39-56`).
`build_default_registry()` returns that registry (`strategies/registry.py:77-79`).
The observed IDs are exactly:

| Strategy ID | Class | Name | Module |
|---|---|---|---|
| `CORE_ZONE_BREAKOUT` | `BreakoutStrategy` | Existing Zone Breakout | `strategies/breakout.py:35-53` |
| `S002` | `S002_BreakoutRetest` | BreakoutRetest | `strategies/breakout_retest.py:58-65` |
| `S008` | `LiquiditySweepStrategy` | Liquidity Sweep V1 | `strategies/liquidity_sweep.py:12-19` |

`server/research_service.py:116-190` defines a UI spec for each of these three
and no others. `list_strategies()` merges registry metadata with those specs
(`server/research_service.py:193-208`). **No additional strategies were found.**
The legacy `LookbackBreakoutRule` is a rule, not a registered strategy
(`strategies/rules/lookback_breakout_rule.py:1-6`).

## 4. Strategy documentation (from code only)

The strategy layer emits `Signal` objects; it does not itself place orders.
Where a strategy has an execution mapping, entry/stop/target/sizing are supplied
by the shared execution layer. Rules below are quoted from the implementation,
not inferred.

### 4.1 `CORE_ZONE_BREAKOUT` (`BreakoutStrategy`)

| Field | Documented behavior and citation |
|---|---|
| Entry / confirmation | Stateful per-zone evaluation on each bar. `ENTER_ZONE` when the previous position was not inside and the current close is inside; on the first observation it also requires the bar range to overlap the zone (`strategies/breakout.py:92-107`, `:151-165`). `BREAK_ABOVE` / `BREAK_BELOW` use `BreakoutRule` (`strategies/breakout.py:167-181`, `strategies/rules/breakout_rule.py:16-36`): after the first bar, a break is any bar closing beyond the zone when the previous position was not already above/below; on the first bar it requires the bar to straddle the boundary. |
| Exit | No strategy exit. No trade is opened by this strategy. It is explicitly a signal study (`server/research_service.py:116-124`, `:818-821`, `:825-837`). |
| Invalidation | Per-zone `last_position` and `was_inside` are updated after evaluation (`strategies/breakout.py:139-140`); `reset()` clears all state and reinitializes one `ZoneState` per zone (`strategies/breakout.py:58-62`). `CLOSE_OUTSIDE` is emitted whenever the close is outside the zone (`strategies/breakout.py:129-137`, `:183-189`). |
| SL | Not applicable at strategy level; no setup factory or trade simulation is wired (`server/research_service.py:116-124`). |
| TP | Not applicable at strategy level. |
| Sizing | Not applicable at strategy level. |
| Required features | OHLC bars only (`models/bar.py:7-16`). No volume, indicators, or feature packs are read. |
| Required zones | A `ZoneBook` for the exact symbol (`models/zone.py:113-124`); service refuses a missing book (`server/research_service.py:807-809`). |
| Supported instruments | Any research-enabled symbol with a configured zone book. Actual books: EURUSD, GBPUSD. GBPUSD was run but its single zone is far above the observed price range. |
| Supported timeframes | Timeframe-agnostic over `Sequence[Bar]` (`strategies/base_strategy.py:10-21`). UI supports M1, M5, M15, H1, H4; M5+ are derived from stored M1 (`server/research_service.py:63`, `:266-304`, `:608-610`). |
| Limitations | (1) `CLOSE_OUTSIDE` is emitted for every zone on every bar whose close is outside that zone, even with no zone interaction; EURUSD 2 days produced 21,848 `close_outside` of 21,920 signals, and GBPUSD produced 2,880/2,880 `close_outside`. (2) Signal counts scale with the number of zones. (3) No trade simulation, SL/TP, or sizing. (4) Zones are static manual annotations without confirmation timestamps (`server/research_service.py:851-854`). (5) No state reconstruction before the first available bar. |

### 4.2 `S002` (`S002_BreakoutRetest`)

| Field | Documented behavior and citation |
|---|---|
| Entry / confirmation | Persistent per-zone breakout state. Bullish breakout: close > zone.high starts a wait at `broken_level=zone.high`; bearish breakout: close < zone.low starts a wait at `broken_level=zone.low` (`strategies/breakout_retest.py:122-139`). A retest signal is emitted only after the breakout bar and within `max_wait` bars (`strategies/breakout_retest.py:141-187`, `:189-231`): bullish = `low <= broken_level + tolerance` and `close > broken_level`; bearish = `high >= broken_level - tolerance` and `close < broken_level`. The breakout candle itself is never its own retest (`:151-153`, `:199-200`). |
| Exit | No strategy exit. Retest signals map to `TradeSetup` via `ZoneBreakoutRetestTradeSetupFactory` (`execution/factories.py:66-106`). Simulated exits are SL, TP, TIMEOUT, AMBIGUITY, or FORCE_CLOSE_END_OF_DATA (`backtests/trade_simulator.py:150-300`). |
| Invalidation | While waiting bullish, a close below `zone.low` switches to waiting bearish; while waiting bearish, a close above `zone.high` switches to waiting bullish (`strategies/breakout_retest.py:160-167`, `:206-211`). Expiry after `breakout_index + max_wait` clears the wait and re-evaluates the bar as idle (`:155-158`, `:202-204`). `reset()` clears all per-zone state and the processed-bar cursor (`:81-87`). |
| SL | Execution mapping: signal-bar low for a long, signal-bar high for a short (`execution/factories.py:80-86`), then `FixedRiskRewardPolicy` validates the stop relative to entry (`execution/policies.py:83-100`). |
| TP | Fixed R-multiple target, default 2.0R (`execution/policies.py:58-64`, `:87-100`). The simulator recalculates TP from the actual next-candle-open fill (`backtests/trade_simulator.py:216-220`). |
| Sizing | `FixedRiskSizer`: `risk_amount = equity * risk_fraction`; `position_size = risk_amount / abs(entry - stop)` (`execution/sizers.py:32-50`). Defaults: equity 100,000, risk 1%. |
| Required features | OHLC bars and a zone book only. No volume/indicators. |
| Required zones | Exact-symbol `ZoneBook` (`server/research_service.py:807-809`). Actual zones: EURUSD 8, GBPUSD 1. |
| Supported instruments | Any research-enabled symbol with a zone book. Actual EURUSD test produced both directions; GBPUSD has a zone outside its available price range. AUDUSD is blocked by the missing zone book. |
| Supported timeframes | Timeframe-agnostic over `Sequence[Bar]`; UI M1/M5/M15/H1/H4, with M5+ derived from M1 (`server/research_service.py:63`, `:275-304`). |
| Limitations | (1) `tolerance` is an absolute price (default 0.0005), not pip-scaled per instrument (`server/research_service.py:130-139`). (2) The stop hint can equal the entry when the retest bar closes at its extreme, producing zero risk and a silent policy-boundary rejection (DEF-02). (3) No requirement that price crossed the zone from the other side before a breakout; state starts idle, so a zone entirely above/below the data can enter a waiting state (GBPUSD probe). (4) One active lifecycle per strategy+symbol ignores signals while a plan/position is active (`backtests/backtest_runner.py:101-103`). (5) Static zones, costs off, fixed 2.0R default, plan timeout 5 bars, position max hold 60 bars. |

### 4.3 `S008` (`LiquiditySweepStrategy`)

| Field | Documented behavior and citation |
|---|---|
| Entry / confirmation | Bullish sweep: current low < prior swing low - tolerance, close > swing low, and lower-wick ratio >= `min_wick_ratio`; bearish sweep: current high > prior swing high + tolerance, close < swing high, and upper-wick ratio >= `min_wick_ratio` (`strategies/rules/liquidity_sweep_rule.py:38-49`, `:89-155`). The swing is the max high / min low of the prior `lookback` candles, excluding the current bar (`:73-78`). Defaults: lookback 10, min wick ratio 0.60, tolerance 0.0 (`strategies/liquidity_sweep.py:21-41`). The strategy passes a bounded `lookback+1` window to the rule and suppresses a duplicate signal at the same timestamp for the same symbol (`strategies/liquidity_sweep.py:47-85`). |
| Exit | No strategy exit. Sweep signals map via `SweepTradeSetupFactory` (`execution/factories.py:26-63`). Simulated exits are SL, TP, TIMEOUT, AMBIGUITY, or FORCE_CLOSE_END_OF_DATA (`backtests/trade_simulator.py:150-300`). |
| Invalidation | No persistent setup state beyond the per-symbol duplicate timestamp; `reset()` clears those timestamps (`strategies/liquidity_sweep.py:43-45`). A bar that fails the rule produces nothing. |
| SL | Signal-bar low for bullish sweeps, signal-bar high for bearish sweeps (`execution/factories.py:41-46`), validated by `FixedRiskRewardPolicy` (`execution/policies.py:83-100`). |
| TP | Fixed R-multiple, default 2.0R, recalculated at fill (`execution/policies.py:58-64`, `:87-100`; `backtests/trade_simulator.py:216-220`). |
| Sizing | `FixedRiskSizer` (`execution/sizers.py:32-50`); defaults equity 100,000 and 1% risk. |
| Required features | OHLC bars only; no volume/indicators; no zones (`zone_id=0` in `strategies/liquidity_sweep.py:80`). |
| Required zones | None (`server/research_service.py:153-189`). |
| Supported instruments | Any research-enabled symbol with a dataset. Tested EURUSD, GBPUSD, and AUDUSD. |
| Supported timeframes | Timeframe-agnostic over `Sequence[Bar]`; UI M1/M5/M15/H1/H4 with M5+ derived from M1. Tested M5. |
| Limitations | (1) Bullish is checked before bearish, so a bar that satisfies both is reported only as bullish (`strategies/rules/liquidity_sweep_rule.py:89-155`). (2) The wick ratio uses `abs(close-open)` as body; a zero denominator yields ratio 0 (`:97-101`, `:133-137`). (3) "Swing" means a simple lookback extremum, not fractal/BOS structure. (4) Duplicate suppression is only same-timestamp/same-symbol. (5) One active lifecycle per strategy+symbol; costs off; fixed default R and timeouts. |

### 4.4 Shared execution layer (applies to S002 and S008, not CORE)

- Entry model is `NEXT_CANDLE_OPEN`; the fill model enters at the next bar's open
  (`execution/factories.py:61`, `:101`; `backtests/fill_models.py:32-38`).
- Exits are conservative OHLC: SL is checked before TP; if both are hit in the
  same bar the exit is `AMBIGUITY`; gaps through SL use the bar open
  (`backtests/fill_models.py:40-84`). `AMBIGUITY` is scored -1R
  (`backtests/trade_simulator.py:276-281`).
- Planner builds `TradePlan` from setup + policy + sizer
  (`execution/planner.py:31-71`). Plan expiry defaults to 5 bars
  (`execution/policies.py:58-64`); open positions default to 60 bars
  (`backtests/backtest_runner.py:71-73`) and are force-closed at data end
  (`backtests/trade_simulator.py:92-121`).
- Fee/spread/slippage fields default to 0.0 and are not applied
  (`models/trade_plan.py:33-55`; `backtests/trade_simulator.py:37-43`).

## 5. Method and baseline

- Bars were loaded through the production service path
  (`server/research_service._load_bars` / `_range_bars`) so the same parser and
  ordering are used.
- Parameters were left at production defaults; no optimization or parameter
  search was performed. Bounded ranges were selected only to contain signals.
- Trade simulation was enabled exactly where the service enables it: S002 and
  S008. CORE remained signal-only.
- Baseline existing tests: 93 tests across strategy, backtest, UI-service, and
  API-route suites passed (`baseline_tests.txt`).
- Repeatability: every configuration was run twice through the service and
  twice through the direct runner (same instance + fresh instance); signals,
  trades, metrics, and input hashes were compared.

## 6. Test matrix

Statuses: `PASS`, `FAIL`, `BLOCKED`, `NOT APPLICABLE`, `NOT TESTED`. Evidence
paths are relative to `docs/qa/` (code paths in section 4 remain repository-relative).

| Test ID | Strategy | Scenario | Data/config | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| STRAT-001 | CORE_ZONE_BREAKOUT | Strategy documentation and rule mapping | `strategies/breakout.py`; `strategies/rules/breakout_rule.py` | Documented entry/break/exit/invalidation/SL/TP/sizing/features/zones/instruments/timeframes/limitations with citations | Documented from code; CORE has no SL/TP/sizing in the strategy layer and no trade simulation | PASS | section 4.1 |
| STRAT-002 | S002 | Strategy documentation and rule mapping | `strategies/breakout_retest.py` | Document causal breakout-to-retest rules and execution mapping with citations | Documented; retest signals map via `ZoneBreakoutRetestTradeSetupFactory` | PASS | section 4.2 |
| STRAT-003 | S008 | Strategy documentation and rule mapping | `strategies/liquidity_sweep.py`; `strategies/rules/liquidity_sweep_rule.py` | Document sweep rules, wick ratio, lookback, direction and execution mapping | Documented; sweep signals map via `SweepTradeSetupFactory` | PASS | section 4.3 |
| STRAT-004 | ALL | Registry discovery and UI spec parity | `strategies/registry.py`; `research_service.STRATEGY_SPECS` | Exactly the three known IDs are discovered and each has a spec | `['CORE_ZONE_BREAKOUT','S002','S008']`; spec IDs match; no additional strategies | PASS | `EVIDENCE/strategy/inventory.json` |
| STRAT-005 | S008 | Valid run on EURUSD with both directions | EURUSD/M1/2026 2026-05-04..2026-05-08; defaults; costs off; R=2.0 | Run completes and counts reconcile | bars=7,080; signals=303 (bullish 190, bearish 113); trades=272; signal reconciliation difference=0 | PASS | `EVIDENCE/strategy/runs/STRAT-005_S008_EURUSD.json` |
| STRAT-006 | S008 | Valid run on second pair GBPUSD | GBPUSD/M1/2026 2026-05-04..2026-05-08; defaults | Run completes and counts reconcile | bars=7,080; signals=206 (107 bearish, 99 bullish); trades=197; difference=0 | PASS | `EVIDENCE/strategy/runs/STRAT-006_S008_GBPUSD.json` |
| STRAT-007 | S002 | Valid run on EURUSD with actual 8-zone book | EURUSD/M1/2026 2026-03-23..2026-03-27; defaults tolerance=0.0005, max_wait=5 | Run completes and counts reconcile | bars=7,080; signals=516 (267 above, 249 below); trades=223; accepted=230, ignored=221, rejected_policy=65; difference=0 | PASS | `EVIDENCE/strategy/runs/STRAT-007_S002_EURUSD.json` |
| STRAT-008 | S002 | Valid run on GBPUSD with actual 1-zone book | GBPUSD/M1/2026 2026-04-01..2026-06-30; defaults | Run completes; zero signals is acceptable if the zone is not reached | bars=93,600; signals=0; trades=0; difference=0; only zone 1.2600-1.2625 versus price range 1.31419-1.36573 | PASS | `EVIDENCE/strategy/runs/STRAT-008_S002_GBPUSD.json` |
| STRAT-009 | CORE_ZONE_BREAKOUT | Signal study on EURUSD | EURUSD/M1/2026 2026-03-24..2026-03-25 | Signal study only; no fabricated trades | bars=2,880; signals=21,920 (close_outside 21,848; enter_zone 36; break_above 9; break_below 27); trades=0 | PASS | `EVIDENCE/strategy/runs/STRAT-009_CORE_ZONE_BREAKOUT_EURUSD.json` |
| STRAT-010 | CORE_ZONE_BREAKOUT | Signal study on GBPUSD | GBPUSD/M1/2026 2026-04-01..2026-04-02 | Signal study only; no fabricated trades | bars=2,880; signals=2,880 all close_outside; trades=0 (zone never interacted) | PASS | `EVIDENCE/strategy/runs/STRAT-010_CORE_ZONE_BREAKOUT_GBPUSD.json` |
| STRAT-011 | S008 | Supported derived timeframe | EURUSD/M1/2026 timeframe=M5 2026-05-04..2026-05-08 | M5 derived from M1; strategy runs on derived bars | derived=true; bars=1,416; signals=95; trades=85; derived-frame warning present | PASS | `EVIDENCE/strategy/runs/STRAT-011_S008_EURUSD_M5.json` |
| STRAT-012 | ALL | Unknown strategy ID | EURUSD/M1/2026; strategy_id=NOPE | Explicit unsupported-strategy error | `ValueError: Strategy 'NOPE' is not exposed in the UI` | PASS | `EVIDENCE/strategy/invalid/STRAT-012_unknown_strategy.json` |
| STRAT-013 | S008 | Parameter below minimum | lookback=1 | Explicit minimum error | `ValueError: lookback must be >= 2` | PASS | `EVIDENCE/strategy/invalid/STRAT-013_s008_lookback_below_min.json` |
| STRAT-014 | S002 | Parameter below minimum | max_wait=0 | Explicit minimum error | `ValueError: max_wait must be >= 1` | PASS | `EVIDENCE/strategy/invalid/STRAT-014_s002_max_wait_below_min.json` |
| STRAT-015 | S008 | Unknown parameter | parameters={not_a_parameter:1} | Explicit unknown-parameter error | `ValueError: Unknown parameters: not_a_parameter` | PASS | `EVIDENCE/strategy/invalid/STRAT-015_unknown_parameter.json` |
| STRAT-016 | S008 | Wrong parameter type | lookback="abc" | Explicit type error | `ValueError: lookback must be an integer` | PASS | `EVIDENCE/strategy/invalid/STRAT-016_wrong_type.json` |
| STRAT-017 | S002 | Missing zone book | AUDUSD/M1/2026; 2026-05-04..2026-05-05 | Explicit error naming AUDUSD and `config/zones.json`; no invented zones | `ValueError: No zone book is configured for AUDUSD in config/zones.json` | PASS | `EVIDENCE/strategy/invalid/STRAT-017_missing_zones_audusd_s002.json` |
| STRAT-018 | CORE_ZONE_BREAKOUT | Missing zone book | AUDUSD/M1/2026; 2026-05-04..2026-05-05 | Same explicit error | Same `ValueError` message | PASS | `EVIDENCE/strategy/invalid/STRAT-018_missing_zones_audusd_core.json` |
| STRAT-019 | S008 | Missing dataset | NZDUSD/M1/2026 (not stored) | Dataset-not-found error | `DatasetNotFoundError: Dataset not found: NZDUSD/M1/2026` | PASS | `EVIDENCE/strategy/invalid/STRAT-019_missing_dataset.json` |
| STRAT-020 | S008 | Malformed dataset id | EURUSD/M1 | Dataset id format error | `DatasetNotFoundError: Dataset id must be SYMBOL/TIMEFRAME/YEAR` | PASS | `EVIDENCE/strategy/invalid/STRAT-020_malformed_dataset_id.json` |
| STRAT-021 | S008 | Unsupported instrument at runner boundary | Direct runner with ZZZUSD | Explicit unsupported-symbol error | `BacktestDataError: Unsupported backtest symbol 'ZZZUSD'` with supported list | PASS | `EVIDENCE/strategy/invalid/STRAT-021_unsupported_instrument_runner.json` |
| STRAT-022 | S008 | Empty data at runner boundary | Direct runner with `[]` | No crash; empty result, no fabricated bars/trades | total_signals=0; symbols=(); started_at/ended_at=None | PASS | `EVIDENCE/strategy/invalid/STRAT-022_empty_runner.json` |
| STRAT-023 | S008 | Too-short selected range | Fixture EURUSD/M1/2026 one bar | Explicit at-least-2-bars error | `ValueError: The selected range contains 1 M1 bar(s); at least 2 are required.` | PASS | `EVIDENCE/strategy/invalid/STRAT-023_short_one_bar.json` |
| STRAT-024 | S008 | Range shorter than strategy requirement | Fixture GBPUSD/M1/2026 five bars; lookback=10 | Explicit lookback+2 requirement error | `ValueError: ... 5 bars, but S008 needs at least 12 with the current parameters.` | PASS | `EVIDENCE/strategy/invalid/STRAT-024_short_lookback.json` |
| STRAT-025 | S008 | Short but sufficient range | Fixture GBPUSD/M1/2026 five flat bars; lookback=2 | Valid run with zero signals | bars=5; signals=0; trades=0; no error | PASS | `EVIDENCE/strategy/invalid/STRAT-025_short_valid_lookback.json` |
| STRAT-026 | S002 | Valid no-signal range | EURUSD/M1/2026 2026-01-01..2026-01-02; actual zones | Valid run with zero signals, not an error | signals=0; trades=0; reconciliation difference=0 | PASS | `EVIDENCE/strategy/runs/STRAT-026_S002_EURUSD_nosignal.json` |
| STRAT-027 | S002 | Long and short on actual data | EURUSD 2026-03-23..2026-03-27; actual zones | Both directions occur; trades map to correct side | retest_above=267 first 2026-03-23T06:01; retest_below=249 first 2026-03-23T09:48; first LONG trade 2026-03-23T06:08; first SHORT trade 2026-03-23T09:49 | PASS | `EVIDENCE/strategy/runs/STRAT-027_S002_EURUSD_directions.json` |
| STRAT-028 | S008 | Long and short on actual data | EURUSD 2026-05-04..2026-05-08 | Both directions occur; trades map to correct side | bullish_sweep=190 first 2026-05-04T00:20; bearish_sweep=113 first 2026-05-04T00:37; first LONG trade 2026-05-04T00:48; first SHORT trade 2026-05-04T00:38 | PASS | `EVIDENCE/strategy/runs/STRAT-028_S008_EURUSD_directions.json` |
| STRAT-029 | CORE_ZONE_BREAKOUT | Long and short on actual data | EURUSD 2026-03-24..2026-03-25; actual zones | Both signal directions occur; no trades by design | break_above=9 first 2026-03-24T20:27; break_below=27 first 2026-03-24T00:17; no trades | PASS | `EVIDENCE/strategy/runs/STRAT-029_CORE_ZONE_BREAKOUT_EURUSD_directions.json` |
| STRAT-030 | S002 | Determinism and input/state isolation | EURUSD 2026-03-23..2026-03-27; repeated twice | Identical signals/trades/metrics; inputs not mutated; reset isolates runs | signals_equal=true; trades_equal=true; fresh-instance equal=true; bars and zone book unmutated=true; service repeat equal=true | PASS | `EVIDENCE/strategy/determinism/STRAT-030_S002.json` |
| STRAT-031 | S008 | Determinism and input/state isolation | EURUSD 2026-05-04..2026-05-08; repeated twice | Same | all comparisons true | PASS | `EVIDENCE/strategy/determinism/STRAT-031_S008.json` |
| STRAT-032 | CORE_ZONE_BREAKOUT | Determinism and input/state isolation | EURUSD 2026-03-24..2026-03-25; repeated twice | Same | all comparisons true | PASS | `EVIDENCE/strategy/determinism/STRAT-032_CORE_ZONE_BREAKOUT.json` |
| STRAT-033 | S002 | Signal vs trade accounting | EURUSD 2026-03-23..2026-03-27; simulate=true | Signal and execution reconciliations have difference 0 | signals=516, accepted=230, ignored=221, rejected_policy=65, trades=223; signal diff=0; execution diff=0 | PASS | `EVIDENCE/strategy/runs/STRAT-033_S002_EURUSD_accounting.json` |
| STRAT-034 | S008 | Signal vs trade accounting | EURUSD 2026-05-04..2026-05-08; simulate=true | Same | signals=303, accepted=289, ignored=14, rejected_policy=0, trades=272; signal diff=0; execution diff=0 | PASS | `EVIDENCE/strategy/runs/STRAT-034_S008_EURUSD_accounting.json` |
| STRAT-035 | CORE_ZONE_BREAKOUT | Signal/trade accounting for a signal study | EURUSD 2026-03-24..2026-03-25; simulation disabled | No trades fabricated; run labeled signal study | signals=21,920; trades=0; reconciliation difference=21,920 is expected because the execution path is not used | PASS | `EVIDENCE/strategy/runs/STRAT-035_CORE_EURUSD_accounting.json` |
| STRAT-036 | S008 | Gross/cost-free status | Simulated run metadata | Explicit costs-off and R-multiple statements; no profitability claim | costs_applied=false; result_units=R-multiples; cost and R warnings present | PASS | `EVIDENCE/strategy/runs/STRAT-036_cost_status.json` |
| STRAT-037 | S002 | AUDUSD missing-zone investigation via service | AUDUSD/M1/2026 exists; only EURUSD/GBPUSD zone books | Explicit, actionable error; no invented zones; dataset remains listed | `ValueError` with exact message; AUDUSD listed; zone books EURUSD=8, GBPUSD=1 | PASS | `EVIDENCE/strategy/audusd/STRAT-037_service_repro.json` |
| STRAT-038 | ALL | Defect reproduction and classification | See defects file | Each confirmed defect has severity, repro, expected, actual, evidence | 4 confirmed defects recorded | PASS | `EVIDENCE/strategy/audusd/defects.json` |
| STRAT-039 | S002 / CORE / S008 | AUDUSD missing-zone reproduction over HTTP | Temporary uvicorn 16904; GET/POST `/api/backtests` | Zone-requiring strategies return 400; zone-free S008 runs | S002 400; CORE 400; S008 200 (46 signals, 40 trades); unknown strategy 400; missing dataset 404 | PASS | `EVIDENCE/strategy/audusd/STRAT-039_http_repro.json`; `audusd/http_transcript.txt` |
| STRAT-040 | ALL | UI/API path classification | `ResearchPage`, `api.ts`, `server/main.py`, `research_service.py`; no zone catalog API | Classify the AUDUSD error | Correct service validation on incomplete config; UI surfaces the 400 detail; cannot pre-validate (UX gap) | PASS | `EVIDENCE/strategy/audusd/STRAT-040_ui_path.json` |
| STRAT-041 | S002 | Long/short on GBPUSD with actual zone book | GBPUSD/M1/2026 2026-04-01..2026-06-30; zone 1.2600-1.2625; price 1.31419-1.36573 | Both directions exercisable | BLOCKED: 0 signals because the only zone is never reached; direction coverage obtained on EURUSD | BLOCKED | `EVIDENCE/strategy/runs/STRAT-008_S002_GBPUSD.json`; `runs/S002_GBPUSD_state_probe.json` |
| STRAT-042 | CORE_ZONE_BREAKOUT | Trade simulation, SL, TP, sizing | `trade_simulation=false`; no breakout setup factory | Verify execution mapping only if wired | NOT APPLICABLE: CORE is signal study only | NOT APPLICABLE | `EVIDENCE/strategy/runs/STRAT-009_CORE_ZONE_BREAKOUT_EURUSD.json` |
| STRAT-043 | ALL | Cost-inclusive profitability/edge claim | Fees/spread/slippage not applied | Separate gross signal study from cost-aware profitability | NOT APPLICABLE: gross R only; no profitability claim | NOT APPLICABLE | `EVIDENCE/strategy/runs/STRAT-036_cost_status.json` |
| STRAT-044 | S002 | AUDUSD S002 signal/trade study with actual configuration | AUDUSD exists; no AUDUSD zone book | Run using real zones only | BLOCKED: cannot run without a zone book; no levels invented; guarded error is correct | BLOCKED | `EVIDENCE/strategy/audusd/STRAT-037_service_repro.json` |
| STRAT-045 | S008 | AUDUSD valid zone-free run over HTTP | POST AUDUSD/M1/2026 S008 2026-05-04..2026-05-05 | S008 runs because it requires no zones | HTTP 200; 46 signals, 40 trades | PASS | `EVIDENCE/strategy/audusd/STRAT-039_http_repro.json` |

## 7. Detailed results

### 7.1 Valid configurations

| Test | Bars | Signals | Trades | Signal reconciliation | Gross metrics (not a profitability claim) |
|---|---:|---:|---:|---|---|
| STRAT-005 S008 EURUSD | 7,080 | 303 | 272 | accepted 289, ignored 14, rejected 0, diff 0 | win rate 22.14%; PF 0.544; expectancy -0.365R; 19 ambiguous |
| STRAT-006 S008 GBPUSD | 7,080 | 206 | 197 | accepted 201, ignored 5, rejected 0, diff 0 | win rate 19.80%; PF 0.467; expectancy -0.437R; 4 ambiguous |
| STRAT-007 S002 EURUSD | 7,080 | 516 | 223 | accepted 230, ignored 221, rejected 65, diff 0 | win rate 33.18%; PF 0.980; expectancy -0.014R; 7 ambiguous |
| STRAT-008 S002 GBPUSD | 93,600 | 0 | 0 | diff 0 | no trades |
| STRAT-009 CORE EURUSD | 2,880 | 21,920 | 0 | signal study; execution path unused | no metrics claimed |
| STRAT-010 CORE GBPUSD | 2,880 | 2,880 | 0 | signal study; execution path unused | no metrics claimed |
| STRAT-011 S008 EURUSD M5 | 1,416 | 95 | 85 | accepted 87, ignored 8, diff 0 | derived frame |

All service summaries matched direct-run signal counts, trade counts, and
signal-type counts exactly (`consistency_check` true in every run JSON). The
metrics above are gross and sample-bounded; they are not evidence of an edge.

### 7.2 Invalid and edge configurations

- Unknown strategy, out-of-range/unknown/wrong-type parameters, missing zones,
  missing dataset, malformed dataset id, unsupported instrument, empty runner
  input, one-bar range, and lookback-short ranges all produced explicit errors
  (STRAT-012 to STRAT-024). No error was swallowed or turned into a fake empty
  success.
- A valid five-bar fixture with lookback=2 runs and returns zero signals
  (STRAT-025), confirming the short-data guard is a minimum-length rule, not a
  blanket rejection.
- A valid EURUSD range with no zone interaction returns zero signals and zero
  trades without error (STRAT-026).
- Audited path: parameter coercion `server/research_service.py:654-692`; range
  validation `:780-806`; dataset parsing `:216-263`; runner validation
  `backtests/backtest_runner.py:176-210`.

### 7.3 Long and short scenarios

| Strategy | Up signal | First up | Down signal | First down | First LONG trade | First SHORT trade |
|---|---|---|---|---|---|---|
| S002 EURUSD | retest_above 267 | 2026-03-23T06:01 | retest_below 249 | 2026-03-23T09:48 | 2026-03-23T06:08 | 2026-03-23T09:49 |
| S008 EURUSD | bullish_sweep 190 | 2026-05-04T00:20 | bearish_sweep 113 | 2026-05-04T00:37 | 2026-05-04T00:48 | 2026-05-04T00:38 |
| CORE EURUSD | break_above 9 | 2026-03-24T20:27 | break_below 27 | 2026-03-24T00:17 | n/a (signal study) | n/a (signal study) |

The S002 and S008 trade directions were verified against their factories:
`RETEST_ABOVE`/`BULLISH_SWEEP` -> LONG and
`RETEST_BELOW`/`BEARISH_SWEEP` -> SHORT (`execution/factories.py:41-46`,
`:80-86`). The S002 first LONG trade exited as `AMBIGUITY` (-1R), which is still
a correctly sided LONG; the direction mapping is independent of the exit reason.

### 7.4 Determinism, state, and input mutation

Repeating the same configuration produced exactly identical signal records and
trade records. Hashes from the evidence:

| Test | Signal digest (sha256 prefix) | Trade digest (sha256 prefix) | Bars before/after | Zone book before/after | Service repeat |
|---|---|---|---|---|---|
| S002 | `2aeed93f1de3e880` | `4a0fe99d8621352f` | `db48564121a2539f` / same | `35d8b807fcdc88ff` / same | equal |
| S008 | `bc8d164dca5756fb` | `82a3d479f230456d` | `1e61b131c45457c0` / same | `35d8b807fcdc88ff` / same | equal |
| CORE | `b61210dcb01966be` | `4f53cda18c2baa0c` (empty) | `a6ebf1205277773d` / same | `35d8b807fcdc88ff` / same | equal |

`BacktestRunner` calls `strategy.reset()` before replay
(`backtests/backtest_runner.py:60-61`), so state from a prior run cannot leak.
The direct checks confirm that neither the bar list nor the zone book is mutated
by any strategy.

### 7.5 Signal counts, trade counts, rejected signals, and rule consistency

- **S002 EURUSD:** 516 signals, 230 accepted, 221 ignored because a lifecycle
  was already active, 65 rejected at the policy boundary, 223 closed trades.
  Execution reconciliation: accepted 230 = closed 223 + expired 0 + rejected 7
  + cancelled 0 + active 0. The 7 execution rejects are gap-through-stop
  `REJECTED_INVALID_ENTRY` records. The 65 policy-boundary rejects are zero-risk
  setups (DEF-02), not counted as accepted.
- **S008 EURUSD:** 303 signals, 289 accepted, 14 ignored, 0 policy rejects,
  272 closed trades. Execution reconciliation:
  289 = 272 closed + 0 expired + 17 rejected + 0 cancelled + 0 active; the 17
  execution rejects are `REJECTED_INVALID_ENTRY`.
- **CORE EURUSD:** 21,920 signals, 0 trades by design. `reconcile_signals()`
  reports difference 21,920 because it is an execution-accounting helper and the
  execution path is intentionally not used when `simulate_trades=false`. This
  is a reporting caveat, not a lost trade.
- Rule/strategy consistency: the three strategies use the rules documented in
  section 4; the existing rule/strategy tests pass
  (`test_breakout`, `test_breakout_rule`, `test_breakout_retest`,
  `test_liquidity_sweep`, `test_strategy_interface`).

### 7.6 Gross/cost-free status

`research_service.run_backtest` always writes:
`assumptions.costs_applied=false`, `result_units="R-multiples"`, and warnings
that transaction costs (spread, commission, slippage) are not applied and that
performance has no currency equity or compounding
(`server/research_service.py:839-850`, `:940-948`). `TradePlan` fee fields are
0.0 and the simulator does not apply them
(`models/trade_plan.py:33-55`, `backtests/trade_simulator.py:37-43`). All results
here are therefore **gross**. The `CORE_ZONE_BREAKOUT` evidence is a **signal
study** with zero trades; the S002/S008 evidence is **gross trade simulation**.
No profitability statement is made.

## 8. Confirmed defects

### DEF-01 - MEDIUM - `CORE_ZONE_BREAKOUT` emits `CLOSE_OUTSIDE` for every zone on every bar outside that zone

- **Repro:** POST `/api/backtests` with `CORE_ZONE_BREAKOUT`, GBPUSD/M1/2026,
  start 2026-04-01, end 2026-04-02; or EURUSD 2026-03-24..2026-03-25.
- **Expected:** a signal should represent a zone interaction or state change; a
  close far outside an untouched zone should not produce one signal per zone per
  bar.
- **Actual:** `_detect_close_outside` is unconditionally
  `not zone.contains_price(close)` and `_evaluate_zone` emits it for every zone
  (`strategies/breakout.py:129-137`, `:183-189`). EURUSD 2 days: 21,848 of
  21,920 signals are `close_outside`. GBPUSD 2 days: 2,880 of 2,880 signals are
  `close_outside`; there are zero `enter_zone`, `break_above`, or `break_below`.
- **Evidence:** `EVIDENCE/strategy/runs/STRAT-009_CORE_ZONE_BREAKOUT_EURUSD.json`,
  `EVIDENCE/strategy/runs/STRAT-010_CORE_ZONE_BREAKOUT_GBPUSD.json`.
- **Status:** confirmed; behavior is visible in code and is materially noisy for
  signal studies.

### DEF-02 - LOW - S002 zero-risk retests are silently rejected at the policy boundary

- **Repro:** S002 EURUSD, 2026-03-23..2026-03-27, default parameters. Of 516
  signals, 65 are rejected by `FixedRiskRewardPolicy.build` because
  `entry_hint == stop_hint` (zero risk distance). Examples: 2026-03-23T06:01
  LONG entry=stop=1.15335; 2026-03-23T10:00 SHORT entry=stop=1.14954.
- **Cause:** the factory uses the signal-bar low/high as the stop
  (`execution/factories.py:80-86`); a retest bar that closes at that extreme
  makes the stop equal to the signal close, and the policy returns None when
  `risk_distance <= 1e-12` (`execution/policies.py:83-85`). The runner only
  increments `rejected_policy_boundary_count`
  (`backtests/backtest_runner.py:116-119`) and does not record a per-signal
  termination reason.
- **Expected:** either build a non-zero structural stop (for example the broken
  level) or record the rejection reason so the UI can explain the loss.
- **Actual:** 65/516 (12.6%) signals disappear from trade simulation with only
  an aggregate count; 7 other rejects are transparently recorded as
  `REJECTED_INVALID_ENTRY`.
- **Evidence:** `EVIDENCE/strategy/runs/S002_zero_risk_rejects.json`,
  `EVIDENCE/strategy/runs/STRAT-033_S002_EURUSD_accounting.json`.

### DEF-03 - LOW - UI cannot pre-validate zone availability (AUDUSD + S002/CORE)

- **Repro:** select AUDUSD + S002 in Strategy Lab and press Run.
- **Expected:** a known-incompatible dataset+strategy combination should be
  disabled or warned before submission.
- **Actual:** the request reaches `POST /api/backtests` and returns 400
  `No zone book is configured for AUDUSD in config/zones.json`. The UI does
  surface this detail (`frontend/src/api.ts:15-31`,
  `frontend/src/pages/ResearchPage.tsx:261-324`), but `/api/strategies` exposes
  only `requires_zones` (`server/research_service.py:193-208`) and there is no
  endpoint listing which symbols have zone books. The note shown in the form
  does not mention zone availability
  (`frontend/src/pages/ResearchPage.tsx:703-707`).
- **Evidence:** `EVIDENCE/strategy/audusd/STRAT-039_http_repro.json`,
  `EVIDENCE/strategy/audusd/STRAT-040_ui_path.json`.
- **Status:** confirmed UX/integration gap; the service-level validation itself
  is correct.

### DEF-04 - INFO - `BacktestRunner` defaults to the sweep factory for any strategy

- **Repro:** `BacktestRunner().run(S002_BreakoutRetest(zone_book), bars,
  simulate_trades=True)` without passing `setup_factory`.
- **Expected:** the runner should require or infer the strategy-specific factory,
  or fail explicitly.
- **Actual:** it defaults to `SweepTradeSetupFactory`
  (`backtests/backtest_runner.py:79`), which returns None for retest signals.
  Those signals are counted as `rejected_policy_boundary` and the run returns
  zero trades even though S002 supports simulation. `research_service` avoids
  this by passing `ZoneBreakoutRetestTradeSetupFactory` explicitly
  (`server/research_service.py:811-817`).
- **Evidence:** code paths cited above; the service runs in this report use the
  correct factory and are unaffected.

## 9. AUDUSD investigation

### Reproduction

- `AUDUSD/M1/2026` is present (93,600 bars) and is listed by `list_datasets()`
  and `GET /api/datasets`.
- `config/zones.json` has only EURUSD and GBPUSD books.
- `run_backtest` resolves the zone book by exact symbol
  (`server/research_service.py:807`) and raises
  `ValueError("No zone book is configured for AUDUSD in config/zones.json")`
  when a zone-requiring strategy is requested (`:808-809`). `server.main._fail`
  maps `ValueError` to HTTP 400 (`server/main.py:63-82`, `:197-212`).
- Service reproduction: `EVIDENCE/strategy/audusd/STRAT-037_service_repro.json`.
- HTTP reproduction (temporary uvicorn on 16904):
  `EVIDENCE/strategy/audusd/http_transcript.txt` and
  `EVIDENCE/strategy/audusd/STRAT-039_http_repro.json`. Results:
  - `GET /api/health` 200
  - `GET /api/strategies` 200; S002/CORE `requires_zones=true`,
    S008 `requires_zones=false`
  - `GET /api/datasets` 200; AUDUSD listed (cold parse exceeded an initial
    5-second client cap, retry returned immediately from cache)
  - `POST /api/backtests` AUDUSD+S002 -> 400 exact missing-zone detail
  - `POST /api/backtests` AUDUSD+CORE -> 400 same detail
  - `POST /api/backtests` AUDUSD+S008 -> 200; 46 signals, 40 trades
  - `POST /api/backtests` unknown strategy -> 400
  - `POST /api/backtests` missing dataset -> 404

### Classification

**Correct validation triggered by incomplete configuration; not a
strategy/engine/application calculation bug.**

Rationale:

1. The strategy contract genuinely requires zones for S002 and CORE
   (`server/research_service.py:116-152`, `:807-809`).
2. Refusing to run is safer than silently treating "no zones" as "no signals" or
   inventing zone levels; both S002 and CORE fail closed with the same explicit
   message.
3. The dataset, parser, resampler, API, and execution path are healthy: zone-free
   S008 runs on AUDUSD over HTTP and produces 46 signals/40 trades. This isolates
   the failure to the missing zone book, not AUDUSD data handling.
4. The only remaining issue is discoverability: the UI cannot pre-validate
   because no zone-catalog API exists (DEF-03, LOW). The error is surfaced, not
   hidden, and no state is corrupted.

## 10. Blocked and not-applicable tests

- **STRAT-041 BLOCKED:** S002 long/short on GBPUSD with the actual zone book.
  The only GBPUSD zone is 1.2600-1.2625, while the available GBPUSD data ranges
  1.31419-1.36573; no S002 signal can occur. Direction coverage for S002 was
  obtained on EURUSD. No zone levels were invented.
- **STRAT-044 BLOCKED:** AUDUSD S002 signal/trade study. AUDUSD has no zone book;
  running would require inventing zones, which is out of scope and prohibited.
- **STRAT-042 NOT APPLICABLE:** CORE trade simulation, SL, TP, and sizing. CORE
  is configured as a signal study only and has no setup factory.
- **STRAT-043 NOT APPLICABLE:** cost-inclusive profitability or edge claim.
  Costs are not modeled; only gross R-multiples were measured.
- No test was blocked by environment failure. The temporary HTTP server and
  temporary data fixtures were created and cleaned up without touching other
  processes or the project's real run directory.

## 11. Assumptions and non-claims

- All signal/trade results are **gross** and exclude spread, commission, and
  slippage; no profitability, edge, or production-readiness claim is made.
- Sample ranges are intentionally bounded and contain signals; they are not
  optimized. S002/S008 five-day samples of 197-272 closed trades are small and
  not statistically reliable.
- Zones are the existing manual annotations; their levels and provenance were
  not changed. Static zones have no confirmation timestamps.
- The `CORE_ZONE_BREAKOUT` evidence is a signal study, not a trade simulation.
- No parameter or configuration was tuned to manufacture results.
- The existing test suite was not modified; the 93-test baseline passed.

## 12. Evidence index

| Evidence | Contents |
|---|---|
| `EVIDENCE/strategy/results.json` | All 45 test records with status and evidence paths |
| `EVIDENCE/strategy/inventory.json` | Registry, specs, zones, datasets, instruments |
| `EVIDENCE/strategy/baseline_tests.txt` | Existing 93-test baseline output |
| `EVIDENCE/strategy/commands.md` | Commands and environment |
| `EVIDENCE/strategy/runs/` | Per-test run summaries, direction/accounting probes |
| `EVIDENCE/strategy/raw_runs/` | Raw service run JSON for the valid bounded runs |
| `EVIDENCE/strategy/determinism/` | Repeat-run and input/zone-book hash comparisons |
| `EVIDENCE/strategy/invalid/` | Explicit-error and short/empty-data evidence |
| `EVIDENCE/strategy/audusd/` | Service/HTTP reproduction, UI path, classification, defects |
| `EVIDENCE/strategy/runs/S002_zero_risk_rejects.json` | DEF-02 evidence |
| `EVIDENCE/strategy/runs/S002_GBPUSD_state_probe.json` | GBPUSD zone/price-range and state probe |
