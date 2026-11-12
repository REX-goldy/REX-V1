# REX — Feature Engineering & Market Structure QA Report

- **Agent:** Agent 5 — Feature Engineering & Market Structure QA
- **Workspace:** `/home/user/workspaces/7de05e41da33`
- **Date:** 2026-11-03
- **Scope:** `core/features/` (repository, context, packs, generators, views, timeframes), `core/indicators/`, `core/zones/`, `core/market_state/`, `core/session_manager.py`, `models/bar.py`
- **Verdict:** **54 PASS / 2 FAIL / 2 BLOCKED / 1 NOT TESTED** across 59 checks. Two confirmed defects are reported below. CHoCH and liquidity are not implemented and are reported as BLOCKED rather than fabricated. Live/runtime MarketState integration was not tested and is not claimed.

## Constraints and change footprint

No application code, strategy logic, config, dataset, or existing test was modified. Nothing was committed, pushed, or deployed. The only repository changes are:

- `docs/qa/FEATURE_VALIDATION_REPORT.md` (this report)
- `docs/qa/EVIDENCE/features/*` (raw JSON evidence and logs)

The read-only harness lives outside the repository at `/tmp/opencode/qa-features/qa_lib.py` and `/tmp/opencode/qa-features/run_qa.py`.

## 1. Inputs and environment

### Real market data

Loaded with `historical.parser.HistoricalDataParser` from the repository’s canonical CSV partitions:

| Input | Rows | Range | Notes |
|---|---:|---|---|
| `data/historical/EURUSD/M1/2026.csv` | 184,963 M1 bars | 2026-01-01 13:00 → 2026-06-30 23:59 | `twelve_data`; volume is empty/None; 35 raw gaps, all weekly FX closures |
| EURUSD contiguous week used for most checks | 7,200 M1 bars | 2026-01-04 22:00 → 2026-01-09 21:59 | Longest gap-free run (start index 1980) |
| `data/historical/GBPUSD/M1/2026.csv` | 93,600 M1 bars | 2026-04-01 00:00 → 2026-06-30 23:59 | Cross-instrument materialization |
| GBPUSD contiguous week | 7,200 M1 bars | 2026-04-05 22:00 → 2026-04-10 21:59 | Longest gap-free run (start index 4200) |
| `config/zones.json` | 8 EURUSD zones, 1 GBPUSD zone | — | Manual levels only; H1/weekly/daily mix |

### Synthetic inputs

Synthetic fixtures were used only for isolated mathematical/boundary cases. Every synthetic fixture and evidence JSON is labelled:

`SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA`

Synthetic fixtures cover: fractal ties/flat series, insufficient swing windows, BOS equality/confirmation cases, range-expansion thresholds and zero-body baseline, a zone tie-break, fixed session clock times, a missing-minute H1 bucket, and a volume-baseline check. Real EURUSD/GBPUSD bars remain the basis for materialization, causality, views, indicators, zones, MarketState, and multi-timeframe checks.

### Environment

- Python 3 with `pandas 3.1.0`
- `pandas_ta_classic` available (the only module importing it is `core/indicators/pandas_provider.py`)
- Related existing regression tests: **161 passed** (`docs/qa/EVIDENCE/features/existing_tests.log`)

## 2. Method and independent calculations

The harness materializes real `FeatureContext` snapshots, projects views, builds `MarketState`, queries `ZoneEngine`, and exercises generators directly. Determinism is checked by repeated runs and canonical SHA-256 snapshots of bars/packs.

Independent calculations used for spot checks:

- **SMA:** rolling mean of close over `length`; provider NaN warmup is `length-1`.
- **EMA:** TA-Lib/pandas-ta convention — seed with the SMA of the first `length` closes at index `length-1`, then recurse with `alpha = 2/(length+1)`. The earlier plain `ewm(adjust=False)` comparison was discarded because it uses a different seed; the corrected TA-Lib-compatible implementation matched exactly.
- **MACD:** EMA(fast=12) − EMA(slow=26), signal = EMA(9) of MACD, histogram = MACD − signal, using the same SMA-seed convention.
- **RSI:** Wilder RMA over gains/losses with `length=14`; first valid index 14.
- **ATR:** True Range `max(high-low, |high-prev_close|, |low-prev_close|)` with Wilder RMA `length=14`; first valid index 14.
- **Momentum (`ts_mom_v1`):** sum of the last up-to-20 simple close-to-close returns; direction is the sign; strength is `abs(sum)`.
- **Range expansion:** recent average body / historical average body, where body = `abs(close-open)`; LOW if `< 0.7`, HIGH if `> 1.3`, else NORMAL; UNAVAILABLE if fewer than 20 bars or historical average body is zero.
- **Trend:** strict 2-left/2-right fractal swings; bullish = last 2 highs rising and last 2 lows rising; bearish = last 2 highs falling and last 2 lows falling; otherwise ranging/unknown.
- **Zones:** exact configured levels, inclusive `low <= price <= high`, `htf_only` = weekly/daily supply or demand, nearest = closest edge, pips via instrument pip size.
- **MTF:** interval start is floored from the bar open; completion = start + duration; source bars with open `<= asof`; HTF bars emitted only when `completion <= asof`; full source coverage required.

## 3. Test results

The table is grouped by audit area rather than numeric ID order (FEAT-057/058 were added during zone/range-expansion boundary work). Full raw detail is in `docs/qa/EVIDENCE/features/results.json` and the individual JSON files.

| Test ID | Component | Scenario | Data | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| FEAT-001 | Inventory | Enumerate actual feature/API surface and method_ids | Static inspection of core/features/, core/indicators/, core/zones/, core/market_state/, config | All six packs, primitive generators, BOS method and five views inventoried; no invented features | packs=['price', 'volatility', 'indicators', 'zones', 'session', 'structure']; registry=['price', 'structure', 'volatility', 'indicators', 'zones', 'session']; views=['TrendView', 'MomentumView', 'VolatilityView', 'PhaseView', 'LiquidityView']; choch_modules=[] | PASS | FEAT-001_inventory.json |
| FEAT-002 | FeatureRepository | Materialize all default packs on real EURUSD M1 bars | REAL EURUSD M1 week: 2026-01-04 22:00:00 .. 2026-01-09 21:59:00 (7200 bars) | Six packs materialized; M1 entry plus causal M15/M30/H1/H4 built; non-empty | packs=['price', 'volatility', 'indicators', 'zones', 'session', 'structure']; bars={'M1': 7200, 'M15': 479, 'M30': 239, 'H1': 119, 'H4': 29}; asof=2026-01-09T21:59:00+00:00; schema_hash=510ee1f393647a11 | PASS | FEAT-002_materialize_real_eurusd.json |
| FEAT-002b | FeatureRepository | Cross-instrument materialization on real GBPUSD M1 bars | REAL GBPUSD M1 week: 2026-04-05 22:00:00 .. 2026-04-10 21:59:00 (7200 bars) | Same six-pack surface materialized | packs=['price', 'volatility', 'indicators', 'zones', 'session', 'structure']; M1=7200; H4=29 | PASS | FEAT-002_materialize_real_gbpusd.json |
| FEAT-003 | FeatureRepository | Determinism across repeated materializations | REAL EURUSD M1 week (7200 bars), identical inputs/config/repo instances | Bars, packs, asof and schema_hash identical | context_equal=True; packs_digest=514dff74aefd7a84…; bars_digest=d15828c23aab1b64… | PASS | FEAT-003_determinism.json |
| FEAT-004 | Views | method_id is required and unknown/reserved methods are rejected | Real EURUSD FeatureContext; Trend/Momentum/Volatility/Phase/Liquidity views | Every missing/unknown/reserved/unsupported method raises UnsupportedMethodError; no silent default | {"trend_none": "UnsupportedMethodError: method_id is required; silent defaults are not allowed", "trend_blank": "UnsupportedMethodError: method_id is required; silent defaults are not allowed", "trend_unknown": "UnsupportedMethodError: Unknown trend method_id… | PASS | FEAT-004_method_ids.json |
| FEAT-005 | FeatureRepository | StructurePack/BOS integration surface | Static inspection + real context | StructurePack contains swings only; BOS is standalone and not materialized in packs | StructurePack fields=['pack_id', 'swings']; BOS method=swing_bos_v1; no BOS field in FeatureContext packs | PASS | FEAT-001_inventory.json |
| FEAT-006 | FeatureRepository | Full history vs truncated history at cutoff | REAL EURUSD M1 week, cutoff=2026-01-07T00:00:00+00:00 (index 3000) | All bars/packs available at cutoff are identical; future bars have no effect | equal=True; equal_without_explicit_asof=True | PASS | FEAT-006_causal_full_vs_truncated.json |
| FEAT-007 | FeatureRepository | Future bar mutation invariant | REAL EURUSD M1 week, 4199 future bars replaced with extreme values | Context at cutoff unchanged after future mutation | context_equal=True | PASS | FEAT-007_future_mutation.json |
| FEAT-008 | core.features.timeframes | HTF completion boundary at as-of | REAL EURUSD M1 week; as-of 2026-01-05 10:37 and 10:45 UTC | Incomplete HTF intervals excluded; M15 10:30 appears only at 10:45 | all_htf_completed=True; M15@10:37=2026-01-05 10:15:00+00:00; M15@10:45=2026-01-05 10:30:00+00:00 | PASS | FEAT-008_htf_completion_boundary.json |
| FEAT-009 | FeatureRepository | Entry-timeframe as-of inclusivity | REAL EURUSD M1, as-of=2026-01-07T00:00:00+00:00 | Documented contract: entry bars with open timestamp <= asof are included; later bars excluded | includes_bar_at_asof=True; includes_next_bar=False | PASS | FEAT-009_entry_asof_semantics.json |
| FEAT-010 | core.features.timeframes | Timezone-equivalent as-of values | REAL EURUSD M1 week; UTC vs America/New_York vs Asia/Kolkata | Identical causal context regardless of as-of timezone | context_equal=True | PASS | FEAT-010_timezone_equivalence.json |
| FEAT-011 | SwingGenerator | Fractal swing detection golden vector | SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA (11 bars) | Strict 2-left/2-right fractal highs (15,14) and lows (7,6) | highs=(15.0, 14.0); lows=(7.0, 6.0); events=4 | PASS | FEAT-011_swings_golden.json |
| FEAT-012 | SwingGenerator | Strict equality/ties and flat prices | SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA | Equal highs/lows and flat series produce no confirmed swings (strict inequality) | tie_highs=(), tie_lows=(), flat_swings=0 | PASS | FEAT-012_swing_ties_flat.json |
| FEAT-013 | SwingGenerator | Insufficient bars for fractal window | SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA (4 bars, left=2 right=2) | Explicit empty swing output, no exception/fabrication | bars=4; swings=0 | PASS | FEAT-013_swing_insufficient.json |
| FEAT-014 | SwingGenerator | Causal confirmation time filtering | SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA | Swing confirmed at index+right is unavailable before confirmation_time | @min3 highs=() lows=(); @min4 highs=(15.0,) | PASS | FEAT-014_swing_causal.json |
| FEAT-015 | SwingGenerator | Structural relationship of swing events on real bars | REAL EURUSD M1 week, first 500 confirmed swings | price/kind/timestamp/index/confirmation_time/id are internally consistent | sampled=500; violations=0; total=1421 | PASS | FEAT-015_swing_structural_relationships.json |
| FEAT-016 | detect_swing_bos | Bullish/bearish BOS, equality and wick-only exclusions | SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA | Close strictly beyond confirmed swing; equality/wick-only not BOS; method swing_bos_v1 | {"data_label": "SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA", "bullish": {"detected": true, "direction": "bullish", "broken_swing_id": "M15:high:2", "break_index": 6, "break_close": 12.5, "method_id": "swing_bos_v1"}, "bearish": {"detected": true, "dir… | PASS | FEAT-016_bos_semantics.json |
| FEAT-017 | detect_swing_bos_series | BOS confirmation causality and swing consumption | SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA | confirmation_index must be < break_index; each swing emits at most one BOS; deterministic | same_index=False; future=False; consumption_events=1; deterministic=True | PASS | FEAT-016_bos_semantics.json |
| FEAT-018 | detect_swing_bos_series | BOS structural relationships on real confirmed swings | REAL EURUSD M1 week | Every BOS references a previously confirmed swing and a strict close break at the break bar | events=1322; sampled=500; violations=0 | PASS | FEAT-018_bos_real_relationships.json |
| FEAT-019 | CHoCH | CHoCH-like structure | Static search of repository; StructurePack fields; real context | A CHoCH implementation with explicit method_id and causal rules | choch_modules=[]; StructurePack fields=['pack_id', 'swings'] | BLOCKED | FEAT-001_inventory.json |
| FEAT-020 | TrendView | market_structure_v1 trend and structure score vs independent recomputation | REAL EURUSD M1 week (7200 bars); all timeframes | Same trend labels/scores and MTF agreement as independent rule | entry=ranging; score=35; mtf=35; violations=[] | PASS | FEAT-020_trend_view.json |
| FEAT-021 | MomentumView | ts_mom_v1 cumulative return vs independent calculation | REAL EURUSD M1 week; lookback=20 | Direction and strength equal sum of last 20 simple returns | view=bullish/0.0002837032490993289; independent=bullish/0.00028370324909920974 | PASS | FEAT-021_momentum_view.json |
| FEAT-022 | VolatilityView | range_expansion_v1 body ratio vs independent calculation | REAL EURUSD M1 week; recent=5, historical=20 | Ratio and LOW/NORMAL/HIGH state match independent body-size mean ratio | view=high/1.9789473684213674; independent=high/1.9789473684213674 | PASS | FEAT-022_volatility_view.json |
| FEAT-023 | PhaseView | heuristic_v1 phase vs independent recomputation | REAL EURUSD M1 week | Phase equals independent implementation of the documented heuristic | view=range; independent=range | PASS | FEAT-023_phase_view.json |
| FEAT-024 | Views | Repeated projection stability | Same real EURUSD FeatureContext projected twice | All view result dataclasses identical across repeated projections | stable=True | PASS | FEAT-024_view_stability.json |
| FEAT-025 | Views | Missing/insufficient data | REAL EURUSD first 3 bars and first 1 bar | Trend unknown; range expansion unavailable; phase range; single-bar momentum unknown; no fabricated values | {"bars": 3, "trend": "unknown", "momentum_direction": "bullish", "momentum_strength": 5.971400570259975e-05, "volatility_state": "unavailable", "phase": "range", "single_bar_momentum_direction": "unknown", "single_bar_momentum_strength": 0.0} | PASS | FEAT-025_views_insufficient.json |
| FEAT-057 | RangeExpansionGenerator | Ratio thresholds and zero-body baseline | SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA (body-size boundary cases) | Strict < low_ratio / > high_ratio boundaries; zero historical body -> UNAVAILABLE with ratio None | {"data_label": "SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA", "boundary_cases": {"below_low": {"state": "low", "ratio": 0.6792452830188679}, "exact_low_0.70": {"state": "normal", "ratio": 0.7}, "middle_1.00": {"state": "normal", "ratio": 1.0}, "exact_h… | PASS | FEAT-057_range_expansion_boundaries.json |
| FEAT-026 | LiquidityView | Liquidity feature availability | Real EURUSD FeatureContext | Documented liquidity method_id exists only if a liquidity pack is materialized | project() -> UnsupportedMethodError: Liquidity method 'unsupported' has no materialized liquidity pack in Phase 1 | BLOCKED | FEAT-004_method_ids.json |
| FEAT-027 | SessionManager/SessionPack | Known UTC session windows and real-asof session pack | REAL EURUSD week; SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA (fixed session clock time… | Dominant session/overlap/high-liquidity flags follow documented UTC windows; pack matches SessionManager | windows_ok=True; pack_matches=True | PASS | FEAT-027_session.json |
| FEAT-028 | PandasTAProvider/IndicatorEngine | SMA versus independent rolling mean | REAL EURUSD M1 last 500 bars | SMA equals rolling mean; NaN warmup of length-1 | first_valid=19; max_abs_diff=0.0; last=1.163153 | PASS | FEAT-028_indicators.json |
| FEAT-029 | PandasTAProvider/IndicatorEngine | EMA versus independent calculation | REAL EURUSD M1 last 500 bars; length=20 | EMA matches independent implementation; explicit NaN warmup | first_valid=19; max_abs_diff=0.0; last=1.1632244519 | PASS | FEAT-028_indicators.json |
| FEAT-030 | PandasTAProvider/IndicatorEngine | RSI versus independent calculation | REAL EURUSD M1 last 500 bars; length=14 | RSI matches independent implementation; explicit NaN warmup | first_valid=14; max_abs_diff=2.842170943040401e-14; last=70.1620699297 | PASS | FEAT-028_indicators.json |
| FEAT-031 | PandasTAProvider/IndicatorEngine | ATR versus independent calculation | REAL EURUSD M1 last 500 bars; length=14 | ATR matches independent implementation; explicit NaN warmup | first_valid=14; max_abs_diff=1.0842021724855044e-19; last=9.12456e-05 | PASS | FEAT-028_indicators.json |
| FEAT-032 | PandasTAProvider/IndicatorEngine | MACD line/signal/histogram versus independent EMA calculation | REAL EURUSD M1 last 500 bars; 12/26/9 | MACD and signal match independent EMAs; histogram = macd - signal | max_abs_diff_macd=0.0; max_abs_diff_signal=0.0; hist_abs_diff=0.0 | PASS | FEAT-028_indicators.json |
| FEAT-033 | PandasTAProvider.relative_volume | Relative volume baseline excludes current bar; missing real volume | REAL EURUSD M1 (volume=None); SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA (volume basel… | Real missing volume -> NaN; synthetic 20-bar baseline -> current/mean(previous 20) | real_is_nan=True; synthetic=2.0 expected=2.0 | PASS | FEAT-028_indicators.json |
| FEAT-034 | PandasTAProvider | NaN/warmup behavior | REAL EURUSD M1 last 500 bars | Warmup is explicit NaN, never fabricated zeros; provider-defined first-valid offsets | {"sma": {"nan_count": 19, "first_valid_index": 19, "length": 20}, "ema": {"nan_count": 19, "first_valid_index": 19, "length": 20}, "rsi": {"nan_count": 14, "first_valid_index": 14, "length": 14}, "atr": {"nan_count": 14, "first_valid_index": 14, "length": 14}} | PASS | FEAT-028_indicators.json |
| FEAT-035 | IndicatorPack/FeatureRepository | Timeframe alignment of indicator pack on causal M15 | REAL EURUSD M1 week aggregated to M15 as-of 2026-01-09T22:00:00+00:00 | Indicator pack is computed on M15 bars, not M1, and matches direct engine call | m15_bars=480; diffs={'ema_fast_last': 0.0, 'ema_slow_last': 0.0, 'atr_last': 0.0, 'rsi_last': 0.0} | PASS | FEAT-028_indicators.json |
| FEAT-036 | IndicatorEngine/IndicatorPack | Empty/short input handling | Real EURUSD bars truncated to 3 and 1 bars | Empty bars raises ValueError; short series returns NaN; 1-bar pack fields None | empty=ValueError: bars must be a non-empty sequence; short_all_nan=True; one_bar_pack_all_none=True | PASS | FEAT-036_indicator_errors.json |
| FEAT-037 | ManualZoneProvider/ZoneEngine | Load config/zones.json without inventing levels | config/zones.json (manual EURUSD/GBPUSD zones) | Every loaded zone level matches config exactly; all source=manual | symbols=['EURUSD', 'GBPUSD']; levels_match=True; provenance={'EURUSD': {'manual'}, 'GBPUSD': {'manual'}} | PASS | FEAT-037_zones_load.json |
| FEAT-038 | ZoneEngine | Zone queries: htf filtering, kind, active, nearest, unknown symbol | config/zones.json (EURUSD levels) + unknown symbol XAUUSD | Deterministic filtering/semantics; unknown symbol returns empty/None/False | {"all_eurusd_ids": [1, 2, 3, 4, 5, 6, 7, 8], "htf_eurusd_ids": [5, 6, 7, 8], "supply_ids": [5, 7], "demand_ids": [6, 8], "price_1_1425_active_htf": [6], "price_1_1867_active_include_h1": [1], "nearest_from_1_1830": {"zone_id": 7, "side": "above", "distance_pi… | PASS | FEAT-038_zone_queries.json |
| FEAT-039 | ZonePack | Zone pack on real FeatureContext | REAL EURUSD M1 week close=1.16353 | Pack reflects HTF (daily/weekly supply/demand) zones only; H1 unclassified config zones excluded by documente… | {"price": 1.16353, "active_ids": [], "nearest": {"zone_id": 8, "side": "below"}, "inside_zone": false, "note": "ZonePack calls active_zones/distance/is_inside with default htf_only=True"} | PASS | FEAT-039_zone_pack.json |
| FEAT-058 | ZoneEngine/Zone | Inclusive zone price boundaries | config/zones.json EURUSD weekly demand 1.1400-1.1450 | contains_price is inclusive at low/high and exclusive just outside | {"at_low_1_1400": [6], "at_high_1_1450": [6], "below_low_1_1399": [], "above_high_1_1451": []} | PASS | FEAT-058_zone_boundaries.json |
| FEAT-040 | ZoneEngine | Deterministic repeated queries and inside-zone tie-break | config/zones.json + SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA (tie-break zones) | Repeated queries identical; preference is strength then tightest range then highest id | active=[6]==[6]; preferred_id=11 | PASS | FEAT-040_zone_determinism.json |
| FEAT-041 | MarketStateBuilder | Build from real FeatureContext with all packs | REAL EURUSD M1 week context; manual zones; pandas-ta indicators | Valid schema version/hash, context hash, available sections, explicit unsupported liquidity | schema=1.0.0; schema_hash=2ff2b89ca6b959f5; trend=ranging; liquidity=unsupported | PASS | FEAT-041_market_state.json |
| FEAT-042 | MarketStateBuilder | Serialization determinism and JSON round-trip | Same real FeatureContext built twice | to_dict/to_json identical; parse(JSON) equals dict; stable hash | deterministic=True; roundtrip=True; sha256=73e270fefa062aaf… | PASS | FEAT-042_market_state_determinism.json |
| FEAT-043 | MarketStateBuilder | Missing packs are explicit | Real EURUSD context materialized with PACK_PRICE only | Dependent sections report unavailable; liquidity remains unsupported | {"price": "available", "structure": "unavailable", "momentum": "available", "phase": "unavailable", "indicators": "unavailable", "volatility": "unavailable", "zones": "unavailable", "session": "unavailable", "liquidity": "unsupported"} | PASS | FEAT-043_market_state_missing_packs.json |
| FEAT-044 | MarketStateBuilder/ZonePack | Missing ZoneEngine dependency | REAL EURUSD context materialized with zone_engine=None | Zone section should be explicitly unavailable/unsupported when no ZoneEngine is configured | status=available; active=[]; nearest=None; inside=False | FAIL | FEAT-044_market_state_missing_zone_engine.json |
| FEAT-045 | MarketStateBuilder | Runtime integration claim | Static search of server/, strategies/, execution/ | No runtime integration is claimed or tested; only builder/serialization behavior is validated | runtime files referencing MarketState=[] | NOT TESTED | FEAT-045_market_state_runtime_search.json |
| FEAT-046 | core.features.timeframes vs research.free_ohlc.resampler | M1→M15/M30/H1 OHLCV comparison on real data | REAL EURUSD M1 week (7200 bars); as-of 2026-01-09T22:00:00+00:00 | Completed intraday bars match exactly between causal aggregator and dataset resampler | {"M15": {"causal": 480, "resampled": 480, "mismatches": 0}, "M30": {"causal": 240, "resampled": 240, "mismatches": 0}, "H1": {"causal": 120, "resampled": 120, "mismatches": 0}} | PASS | FEAT-046_timeframes_vs_resampler.json |
| FEAT-047 | core.features.timeframes vs research.free_ohlc.resampler | Documented intentional H4/D1 FX-boundary differences | REAL EURUSD M1 week; as-of 2026-01-09T22:00:00+00:00 | Causal aggregator requires full calendar interval; resampler requires full FX-open minutes; boundary buckets … | {"H4": {"causal": 29, "resampled": 31, "only_causal": [], "only_resampled": ["2026-01-04T20:00:00", "2026-01-09T20:00:00"], "common_mismatches": 0}, "D1": {"causal": 4, "resampled": 6, "only_causal": [], "only_resampled": ["2026-01-04T00:00:00", "2026-01-09T0… | PASS | FEAT-046_timeframes_vs_resampler.json |
| FEAT-048 | core.features.timeframes | No future leak in causal aggregation | REAL EURUSD M1 week; mid-week as-of 2026-01-07T12:37:00+00:00 | Aggregation at T equals full aggregation filtered to completion_time <= T; future mutation has no effect | equal=True; mutation_equal=True; bars=62 | PASS | FEAT-048_timeframes_no_future_leak.json |
| FEAT-049 | FeatureRepository.prepare_causal_bars | Configured HTFs equal direct causal aggregation | REAL EURUSD M1 week; as-of 2026-01-09T22:00:00+00:00 | prepare_causal_bars injects exactly the completed aggregated HTF series | {"M15": {"direct": 480, "context": 480, "equal": true}, "M30": {"direct": 240, "context": 240, "equal": true}, "H1": {"direct": 120, "context": 120, "equal": true}, "H4": {"direct": 29, "context": 29, "equal": true}} | PASS | FEAT-049_prepare_causal_consistency.json |
| FEAT-050 | research.free_ohlc.resampler | Resampler input contract: duplicates and timezone | Real EURUSD bars with injected duplicate + aware timestamps | Explicit rejection of duplicate source timestamps and aware timestamps | duplicate=ResampleError: duplicate source timestamp: 2026-01-04 22:00:00; aware=ResampleError: source timestamps must be naive UTC | PASS | FEAT-050_resampler_input_contract.json |
| FEAT-051 | FeatureRepository/timeframes | Empty series | Empty M1 input | Explicit ValueError from repository; empty tuple from aggregation | materialize=ValueError: Missing entry timeframe candles: M1 (provide entry bars or an explicit asof with aggregatable LTF source); aggregate_bars=0 | PASS | FEAT-051_boundary_empty.json |
| FEAT-052 | FeatureRepository/MarketStateBuilder | Single-bar and short-series handling | REAL EURUSD first 1 and first 3 M1 bars | No crash; explicit unknown/unavailable/empty outputs | single_price=1.17234; structure=unknown; momentum=unknown; phase=range; swings=0 | PASS | FEAT-052_boundary_single_short.json |
| FEAT-053 | core.features.timeframes | Missing source bar does not invent an HTF bar | SYNTHETIC TEST FIXTURE — NOT REAL MARKET DATA (60-minute fixture, minute 30 removed) | Complete hour emits one H1; gapped hour emits none | full=1; gapped=0 | PASS | FEAT-053_boundary_missing_bar.json |
| FEAT-054 | FeatureRepository/timeframes | Duplicate timestamps handling | REAL EURUSD bars with one injected duplicate timestamp | Explicit rejection (or controlled de-duplication) at every entry point | entry_materialize={'materialize_succeeded': True, 'entry_bars': 3, 'duplicate_retained': True, 'm1_swings': 0}; m15=ValueError: Missing entry timeframe candles: M15 (provide entry bars or an explicit asof with aggregatable LTF source); aggregate_bars=0; resam… | FAIL | FEAT-054_boundary_duplicates.json |
| FEAT-055 | FeatureRepository/timeframes | Symbol and timeframe label validation | GBPUSD bar passed as EURUSD; empty timeframe; unknown timeframe X9 | Explicit ValueError/UnknownTimeframeError for invalid labels | wrong_symbol=ValueError: All bars for M1 must match EURUSD; empty_tf=ValueError: Timeframe cannot be empty; unknown_tf=UnknownTimeframeError: Unsupported timeframe for causal aggregation: 'X9' | PASS | FEAT-055_boundary_labels.json |
| FEAT-056 | FeatureRepository | Unsorted input normalization | REAL EURUSD first 200 bars supplied in reverse order | Repository sorts by timestamp; identical context to sorted input | context_equal=True | PASS | FEAT-056_boundary_unsorted.json |

## 4. Confirmed defects

### DEF-001 — Duplicate entry-timestamp bars are silently retained; HTF path fails with an unrelated error

- **Severity:** Medium
- **Test:** FEAT-054
- **Component:** `FeatureRepository._normalize_bars`, `core.features.timeframes.aggregate_completed_bars`
- **Repro (evidence `FEAT-054_boundary_duplicates.json`):** pass real EURUSD M1 bars with one injected duplicate timestamp:
  - Entry `M1`: materialization succeeds with 3 bars, including both bars sharing the same timestamp. No error, no de-duplication.
  - Entry `M15` built from the same M1 input: `ValueError: Missing entry timeframe candles: M15 (...)` — the duplicate causes the minutes sequence to mismatch, the HTF bucket is silently dropped, and the resulting error is about a missing entry timeframe rather than a duplicate.
  - Direct `aggregate_completed_bars(... M1→M15 ...)`: emits 0 bars (silent drop).
  - `research.free_ohlc.resampler.resample_bars`: correctly raises `ResampleError: duplicate source timestamp: 2026-01-04 22:00:00`.
- **Expected:** Consistent input validation — reject duplicate timestamps explicitly (as the canonical bar contract and resampler do), or deterministically de-duplicate with a documented rule.
- **Actual:** Duplicates are retained for entry-timeframe M1 features (swings/returns/indicators can treat the duplicate as a second observation), while HTF aggregation silently drops the bucket. This violates “explicit errors/empty outputs, not silent fabrication” and makes duplicate-data failures hard to diagnose.
- **Suggested remediation:** Reject duplicate timestamps in `FeatureRepository._normalize_bars` with a clear `ValueError`, and/or make `aggregate_completed_bars` raise a duplicate-specific error before bucketing.

### DEF-002 — Missing `ZoneEngine` is reported as “available with no zones”

- **Severity:** Low
- **Test:** FEAT-044
- **Component:** `core.features.packs.build_zone_pack` + `core.market_state.builder._build_zones`
- **Repro (evidence `FEAT-044_market_state_missing_zone_engine.json`):** construct `FeatureRepository(zone_engine=None, indicator_engine=...)`, materialize a real EURUSD context with all default packs, then build MarketState. The zones section is:
  ```json
  {"status": "available", "active_zones": [], "nearest": null, "inside_zone": false, "reason": null}
  ```
- **Expected:** A missing zone dependency should be explicitly unavailable/unsupported (like missing indicator/session packs in FEAT-043), or the pack should carry an availability flag distinct from a genuinely empty zone book.
- **Actual:** `zone_engine=None` produces an empty `ZonePack`; MarketState labels it `available`, indistinguishable from “the provider has no zones for this symbol.” An AI/consumer can misread dependency absence as a valid no-zone market state.
- **Suggested remediation:** Have `ZonePack` carry an explicit availability/source status, or mark `MarketStateZones.status = UNAVAILABLE` when `FeatureRepository` was created without a `ZoneEngine`.

## 5. Blocked, unsupported, and not tested

| Item | Status | Evidence | Finding |
|---|---|---|---|
| CHoCH / Change of Character | **BLOCKED** | FEAT-019, `FEAT-001_inventory.json` | No `choch*.py` in the working tree; no CHoCH method_id; `StructurePack` contains only `swings`. BOS (`swing_bos_v1`) is the only structural break primitive. Not fabricated. |
| Liquidity view/pack | **BLOCKED** | FEAT-026, `FEAT-004_method_ids.json` | `LiquidityView.project()` always raises `UnsupportedMethodError` because no liquidity pack exists in Phase 1. Explicit failure, no invented liquidity state. |
| Live/runtime MarketState integration | **NOT TESTED** | FEAT-045, `FEAT-045_market_state_runtime_search.json` | Static search of `server/`, `strategies/`, `execution/` found no `MarketState`/`MarketStateBuilder` references. This report validates only the builder/serialization layer; no runtime integration is claimed. |

## 6. Multi-timeframe comparison detail

`core.features.timeframes` and `research.free_ohlc.resampler` agree exactly on completed intraday bars:

| Timeframe | Causal aggregator | Resampler | Common buckets | OHLCV mismatches |
|---|---:|---:|---:|---:|
| M15 | 480 | 480 | 480 | 0 |
| M30 | 240 | 240 | 240 | 0 |
| H1 | 120 | 120 | 120 | 0 |
| H4 | 29 | 31 | 29 | 0 |
| D1 | 4 | 6 | 4 | 0 |

Intentional differences at FX weekly boundaries (documented in both modules, no look-ahead in either):

- **H4:** the causal aggregator requires all 240 calendar minutes; the resampler requires all FX-open minutes. The resampler emits extra Sunday 2026-01-04 20:00 and Friday 2026-01-09 20:00 buckets that the causal path omits.
- **D1:** the causal aggregator requires all 1,440 calendar minutes; the resampler requires FX-open minutes. The resampler emits extra Sunday 2026-01-04 and Friday 2026-01-09 D1 buckets that the causal path omits.
- All common H4/D1 buckets have identical OHLCV.
- Causal aggregation is as-of aware (`source timestamp <= asof`, `completion_time <= asof`); the resampler has no as-of parameter and requires naive UTC input, rejecting aware timestamps and duplicate timestamps explicitly.

## 7. Design observations (not confirmed defects)

1. **Entry-timeframe as-of inclusivity.** `FEAT-009` confirms the documented contract: entry bars with open timestamp `<= asof` are included, while HTF bars require `completion_time <= asof`. Therefore an M1 bar opening exactly at `asof` is included even though its interval completes one minute later. This is asserted by existing tests and is not a defect against the current contract, but consumers that interpret `asof` as a decision/close time should account for the one-bar difference.
2. **EMA/MACD warmup convention.** `pandas_ta_classic` seeds EMA with the SMA of the first `length` closes, not with the first close. The independent check was adjusted to this TA-Lib-compatible convention and then matched exactly; warmup is explicit NaN (SMA/EMA first valid at `length-1`, RSI/ATR at `length`, MACD later).
3. **ZonePack HTF default.** `ZonePack` uses `ZoneEngine` defaults (`htf_only=True`), so H1 zones without a supply/demand `kind` are excluded from the feature pack even though `zones(..., htf_only=False)` returns them. This is documented ZoneEngine behavior, not invented data.
4. **BOS is standalone.** BOS (`swing_bos_v1`) exists as a generator API but is not materialized in `StructurePack`/`FeatureContext`, and no view projects it. Any consumer expecting BOS in the feature snapshot will not find it.
5. **Schema hash scope.** `FeatureContext.schema_hash` hashes only the selected pack IDs; `MarketState` schema hash hashes the schema version plus method IDs. Neither hashes config values. This is acceptable for a schema identifier but should not be treated as a config/provenance hash.
6. **Builder config coupling.** `MarketStateBuilder` accepts a `FeatureConfig`; when a `FeatureRepository` is built with a custom config, callers should pass the same config to the builder. The QA used the default config for both, so mismatched-config interpretation was not exercised.

## 8. Evidence manifest

All paths are relative to the repository root. `results.json` is the machine-readable aggregate; each test also has a focused JSON file.

| Area | Files |
|---|---|
| Aggregate / inputs | `docs/qa/EVIDENCE/features/results.json`, `real_data_manifest.json`, `existing_tests.log` |
| Inventory / repository | `FEAT-001_inventory.json`, `FEAT-002_materialize_real_eurusd.json`, `FEAT-002_materialize_real_gbpusd.json`, `FEAT-003_determinism.json`, `FEAT-004_method_ids.json` |
| Causality | `FEAT-006_causal_full_vs_truncated.json`, `FEAT-007_future_mutation.json`, `FEAT-008_htf_completion_boundary.json`, `FEAT-009_entry_asof_semantics.json`, `FEAT-010_timezone_equivalence.json` |
| Swings / BOS | `FEAT-011_swings_golden.json`, `FEAT-012_swing_ties_flat.json`, `FEAT-013_swing_insufficient.json`, `FEAT-014_swing_causal.json`, `FEAT-015_swing_structural_relationships.json`, `FEAT-016_bos_semantics.json`, `FEAT-018_bos_real_relationships.json` |
| Views / session | `FEAT-020_trend_view.json`, `FEAT-021_momentum_view.json`, `FEAT-022_volatility_view.json`, `FEAT-023_phase_view.json`, `FEAT-024_view_stability.json`, `FEAT-025_views_insufficient.json`, `FEAT-057_range_expansion_boundaries.json`, `FEAT-027_session.json` |
| Indicators | `FEAT-028_indicators.json`, `FEAT-036_indicator_errors.json` |
| Zones | `FEAT-037_zones_load.json`, `FEAT-038_zone_queries.json`, `FEAT-039_zone_pack.json`, `FEAT-040_zone_determinism.json`, `FEAT-058_zone_boundaries.json` |
| MarketState | `FEAT-041_market_state.json`, `FEAT-042_market_state_determinism.json`, `FEAT-043_market_state_missing_packs.json`, `FEAT-044_market_state_missing_zone_engine.json`, `FEAT-045_market_state_runtime_search.json` |
| Multi-timeframe | `FEAT-046_timeframes_vs_resampler.json`, `FEAT-048_timeframes_no_future_leak.json`, `FEAT-049_prepare_causal_consistency.json`, `FEAT-050_resampler_input_contract.json` |
| Boundary / robustness | `FEAT-051_boundary_empty.json`, `FEAT-052_boundary_single_short.json`, `FEAT-053_boundary_missing_bar.json`, `FEAT-054_boundary_duplicates.json`, `FEAT-055_boundary_labels.json`, `FEAT-056_boundary_unsorted.json` |

## 9. Reproduction

From the repository root:

```bash
PYTHONPATH=. python3 /tmp/opencode/qa-features/run_qa.py
```

The harness is read-only with respect to application code and writes only `docs/qa/EVIDENCE/features/*`. The focused existing regression suite was run with:

```bash
python3 -m unittest \
  tests.test_feature_repository tests.test_feature_views tests.test_swing_bos \
  tests.test_swing_events tests.test_market_state tests.test_indicators \
  tests.test_zone_engine tests.test_zone_semantics tests.test_causal_htf \
  tests.test_free_ohlc_resampler tests.test_range_expansion_unavailable \
  tests.test_structure_score_naming tests.test_session_manager -v
```

Result: **161 tests passed** (`docs/qa/EVIDENCE/features/existing_tests.log`).
