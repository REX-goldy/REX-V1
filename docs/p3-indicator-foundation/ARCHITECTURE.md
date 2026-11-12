# P3.1 Indicator Foundation Architecture — Stage 1 + Stage 2A

## 1. Reused architecture

P3.1 extends, and does not replace:

- `core.indicators.IndicatorProvider` / `IndicatorEngine` for indicator math;
- `core.features.FeatureRepository` for materialization;
- `core.features.packs` for immutable pack payloads;
- `FeatureContext` for the point-in-time snapshot;
- `BacktestRunner` unchanged for strategy research.

No second indicator engine, feature store or backtest pipeline was introduced.

## 2. Series models

`core/indicators/series.py::IndicatorSeries`:

```python
IndicatorSeries(
    indicator_id: str,
    method_id: str,
    timeframe: str,
    timestamps: tuple[datetime, ...],
    values: tuple[float | None, ...],
    parameters: Mapping[str, object],
    implementation_version: str,
    warmup_bars: int,
    start_index: int,
    source_bar_count: int,
)
```

- `timestamps[i]` aligns to `values[i]`;
- unavailable/warm-up observations are `None`, never fabricated zeros;
- `start_index` identifies the source bar position of the first retained value;
- `source_bar_count` identifies the full materialized bar count;
- `warmup_bars` is the leading unavailable count in the retained window;
- parameters and implementation version are immutable provenance fields.

The existing scalar fields on `IndicatorPack` remain for backward compatibility.

## 3. Materialization flow

```
FeatureRepository.materialize(...)
  → normalized causal bars at asof
  → selected packs
  → IndicatorPack:
      engine.prepare(bars)       # one OHLC DataFrame
      engine.sma/ema/atr/rsi/...
      engine.wma/hma/dema/tema  # Stage 2A trend family
      IndicatorSeries per indicator
  → FeatureContext(
      bars_by_timeframe,
      packs,
      schema_hash,
      provenance=FeatureProvenance(...)
  )
```

`PandasTAProvider.prepare` reuses one OHLC frame for subsequent calls in the same
materialization. There is no cross-call feature cache in Stage 1.

## 4. Series bounds

`IndicatorPackConfig.series_window` defaults to **2048 bars**. The retained series is the last
window; `source_bar_count` and `start_index` preserve full-source context. This bounds memory
without changing the scalar latest values.

## 5. Provenance

`FeatureContext.provenance` records:

- feature schema version and config version;
- config hash;
- schema hash;
- selected pack IDs;
- view method IDs;
- indicator implementation versions;
- indicator parameters;
- entry timeframe.

P3.2/P2.1 integration can serialize this provenance into **new** experiment snapshots later;
Stage 1 does not modify existing experiment records.

## 6. Configuration

`FeatureConfig.indicators` now includes:

- existing EMA/ATR/RSI/MACD/relative-volume parameters;
- `sma_period`, `bollinger_period`, `bollinger_std`, `adx_period`;
- `wma_period`, `hma_period`, `dema_period`, `tema_period` (default 20 each);
- `series_window`.

Defaults preserve previous behavior for the prior scalar fields. Stage 2A adds
the four trend periods as explicit, configurable fields; they are recorded in
provenance and hashes and are not used by strategies.

## 7. Duplicate work status

- OHLC DataFrame construction is reused inside an indicator materialization.
- ATR is still independently requested by the volatility and indicator packs.
- TrendView is still computed independently by `MarketStateBuilder` structure and through
  `PhaseView`.
- These remaining duplicates are documented for a later optimization stage; Stage 1 does not
  change their output.

## 8. Causality

- `FeatureRepository` filters to bars available at `asof`.
- `prepare_causal_bars` emits only completed higher-timeframe bars.
- Series are built from the same causal bar mapping.
- Tests compare a historical prefix against a longer dataset at the same as-of and verify
  identical series values.
- Future bars never appear in a context materialized at an earlier `asof`.
- Stage 2A tests verify provider-level prefix invariance and repository-level
  as-of invariance for WMA/HMA/DEMA/TEMA, including appended future bars whose
  OHLC values are changed.

## 9. Stage 2A trend family

WMA, HMA, DEMA and TEMA are exposed by the existing `IndicatorProvider`,
`IndicatorEngine` and `IndicatorPack.series` contracts. Each uses the shared
prepared close series in the same materialization. No caching, new execution
path or strategy integration is added. Exact formulas and warm-up counts are
in [INDICATOR_REFERENCE.md](INDICATOR_REFERENCE.md).
