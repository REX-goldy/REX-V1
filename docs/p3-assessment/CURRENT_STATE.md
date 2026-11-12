# Current State — Verified Repository Inventory

This document describes the implementation that exists in the repository at the time of P3.0
restoration. It does not describe P3.1+ proposals.

**P3.1 Stage 1/2A status:** historical indicator series, feature provenance and the
Stage 2A trend family (WMA/HMA/DEMA/TEMA) have since been added in [../p3-indicator-foundation/](../p3-indicator-foundation/). This file remains the
pre-Stage-1 baseline; the Stage 1 documentation is authoritative for the new series models.

## 1. Repository baseline

| Item | Verified state |
|---|---|
| Commit base | `95f8aaa` plus the uncommitted P0/P1/P2.1 working tree |
| Last verified full suite | **650 tests passing** at P2.1; P3-specific tests do not exist |
| Lint | PASS at P2.1 |
| Frontend build | PASS at P2.1 |
| Historical data | OHLC only; volume fields are empty (`Bar.volume=None`) |
| Strategy execution | Raw `Bar` sequences through `BacktestRunner` |
| Feature execution | `FeatureRepository` materialization, separate from strategies |
| Experiment persistence | P2.1 JSON workspace + immutable run references + reproduction records |
| Database | None; JSON/files only |

The P3 documentation step did not rerun the suite, modify code, or alter datasets/run artifacts.

## 2. Feature architecture

### Materializer

`core/features/repository.py::FeatureRepository`:

- accepts bars selected by timeframe;
- normalizes timestamps to UTC;
- sorts bars and rejects duplicate timestamps;
- resolves an as-of time;
- constructs completed higher timeframes through `prepare_causal_bars`;
- materializes selected packs from `FeaturePackRegistry`;
- returns an immutable `FeatureContext` with `MappingProxyType` bar/pack maps.

It is an **in-memory materializer**, not a persistent feature store. There is no feature cache.

### Feature packs

| Pack | Current payload |
|---|---|
| `price` | Simple/log returns per timeframe and recent closes |
| `volatility` | Range-expansion state/ratio and latest ATR |
| `indicators` | Latest EMA fast/slow, ATR, RSI, MACD/signal/histogram, relative volume |
| `structure` | Confirmed swing events by timeframe |
| `zones` | Active/nearest zone snapshot |
| `session` | Session/overlap/high-liquidity snapshot |

### Generators and views

| Component | Status |
|---|---|
| `ReturnsGenerator` | Implemented; simple and log returns |
| `SwingGenerator` | Implemented; strict left/right fractal extrema with confirmation times |
| `RangeExpansionGenerator` | Implemented; recent vs historical body-size ratio |
| `detect_swing_bos_series` | Implemented; method `swing_bos_v1` |
| `TrendView` | Implemented `market_structure_v1`; `drift_v1` reserved/unsupported |
| `MomentumView` | Implemented `ts_mom_v1` from simple returns |
| `VolatilityView` | Implemented `range_expansion_v1` |
| `PhaseView` | Implemented `heuristic_v1` |
| `LiquidityView` | Explicitly unsupported; no liquidity pack |
| `MarketStateBuilder` | Implemented for current views; no runtime integration |

### Causal / multi-timeframe behavior

`core/features/timeframes.py`:

- timestamps are treated as interval opens in UTC;
- HTF bars are built causally from the finest aggregatable source;
- only bars whose completion time is `<= asof` are emitted;
- incomplete buckets are not emitted;
- duplicate source timestamps fail closed;
- `FeatureRepository` rejects duplicates at entry.

The dataset resampler remains a separate path for dataset derivation, with FX-open
completeness; the causal feature path remains the feature materializer.

## 3. Indicator implementation

`core/indicators/IndicatorEngine` delegates to `PandasTAProvider`. Current public methods:

- SMA (`length=20`)
- EMA (`length=20`)
- RSI (`length=14`)
- ATR (`length=14`)
- MACD (`fast=12`, `slow=26`, `signal=9`)
- Bollinger Bands (`length=20`, `std=2`)
- ADX (`length=14`, includes +DI/−DI)
- relative volume (`length=20`)

The provider returns pandas Series/results aligned to the input bars. It rebuilds a pandas
OHLC frame on each call via `_ohlc`/`_close`. The indicator backend is
`pandas-ta-classic>=0.6.52`; the dependency is not pinned to an exact version.

`IndicatorPack` exposes only the **latest** values, not historical series.

### Relative volume / volume

`relative_volume` is implemented as an API, but current stored datasets have no volume.
It returns NaN/None when volume is absent and has no usable production value. It must be
classified as **unavailable for OHLC-only data**, not as a working feature.

## 4. Current performance and caching

- No feature cache, LRU, or persistent feature store exists.
- A read-only benchmark materialized default packs for EURUSD:
  - 20,000 M1 bars: ~0.55 s
  - 50,000 bars: ~1.47 s
  - 100,000 bars: ~2.96 s
  - **184,963 bars: ~5.7 s**
- Each indicator call reconstructs an OHLC DataFrame.
- Indicator results are not reused across packs.
- `FeatureContext` retains full bars by timeframe plus whatever pack payloads contain.

## 5. Known duplicate work

1. **ATR** is computed independently in `build_volatility_pack` and `build_indicator_pack`.
2. **TrendView** is computed by `MarketStateBuilder` for structure and again through
   `PhaseView.project`.
3. `PandasTAProvider` rebuilds OHLC frames for each indicator call.
4. `relative_volume` uses a Python loop over bars and a second volume-dependent path.

These are explicit P3 optimization targets; P3.0 does not change them.

## 6. Feature/experiment provenance

Current P2.1 experiment snapshots include:

- strategy/variation IDs and strategy/variation snapshots;
- dataset hash and metadata;
- zone version snapshots;
- cost profile and risk/execution configuration;
- backtest parameters, model versions and validation reference.

They do **not** include:

- feature pack/method/implementation versions;
- indicator parameter snapshots tied to feature materialization;
- a feature configuration hash;
- a feature/indicator snapshot.

P3.1 must add this before claiming feature-level experiment reproducibility.

## 7. Strategy relationship

All registered strategies (`CORE_ZONE_BREAKOUT`, `S002`, `S008`) consume raw
`Sequence[Bar]` through `generate_signals`. None consumes `FeatureContext`. P3 must not
silently migrate strategy logic to features; that requires a separate approved phase.

`BacktestRunner` remains the sole research execution path.

## 8. Data availability

- OHLCV-shaped `Bar` model exists, but stored partitions provide no volume.
- Stored data: EURUSD 184,963 M1 bars; GBPUSD/AUDUSD/USDJPY/USDCAD 93,600 each.
- EURUSD has documented provider-origin unexpected gaps.
- No bid/ask, tick data, portfolio/account-currency data or multi-symbol order book exists.

## 9. Assessment discrepancies found during verification

- The approved P3.0 files were absent from the repository before this documentation restoration.
- The P3.0 assessment's current-state claims otherwise match the code: limited indicator
  surface, scalar-only packs, no feature cache, duplicate ATR/TrendView work, no strategy
  feature consumption, and no volume data.
- P3.1 implementation/test files do not exist.

## Related documents

[README](README.md) · [Current state](CURRENT_STATE.md) · [Feature catalogue](FEATURE_CATALOGUE.md) · [Analytics](ANALYTICS_ASSESSMENT.md) · [Regime](REGIME_RESEARCH.md) · [Robustness](ROBUSTNESS_ASSESSMENT.md) · [Architecture](ARCHITECTURE_PROPOSAL.md) · [Roadmap](P3_ROADMAP.md) · [Risks](RISKS_AND_OPEN_QUESTIONS.md)
