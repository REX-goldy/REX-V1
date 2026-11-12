# Indicator Series Reference — Stage 2A

Stage 2A adds the **trend family** (WMA, HMA, DEMA, TEMA) to the Stage 1
timestamp-aligned series contract. It does not add momentum, volatility,
structure, statistical, volume or regime indicators.

## 1. Available series

`IndicatorPack.series` is a mapping keyed by indicator ID. Stage 2A adds the
four IDs below; all Stage 1 series remain available.

| Indicator ID | Method ID | Implementation | Default period | Scalar alias |
|---|---|---|---|---|
| `sma` | `sma_v1` | SMA of close | 20 | none (series-only) |
| `ema_fast` | `ema_v1` | EMA of close | 20 | `ema_fast_last` |
| `ema_slow` | `ema_v1` | EMA of close | 50 | `ema_slow_last` |
| `wma` | `wma_v1` | Linearly weighted MA | 20 | none (series-only) |
| `hma` | `hma_v1` | Hull MA | 20 | none (series-only) |
| `dema` | `dema_v1` | Double EMA | 20 | none (series-only) |
| `tema` | `tema_v1` | Triple EMA | 20 | none (series-only) |
| `atr` | `atr_v1` | Wilder ATR | 14 | `atr_last` |
| `rsi` | `rsi_v1` | Wilder RSI | 14 | `rsi_last` |
| `macd` | `macd_v1` | MACD line | 12/26 | `macd_last` |
| `macd_signal` | `macd_v1` | MACD signal | 9 | `macd_signal_last` |
| `macd_histogram` | `macd_v1` | MACD histogram | 9 | `macd_histogram_last` |
| `bb_upper` | `bollinger_v1` | Upper Bollinger band | 20 | none (series-only) |
| `bb_middle` | `bollinger_v1` | Middle Bollinger band | 20 | none (series-only) |
| `bb_lower` | `bollinger_v1` | Lower Bollinger band | 20 | none (series-only) |
| `adx` | `adx_v1` | Wilder ADX | 14 | none in pack |
| `plus_di` | `adx_v1` | +DI | 14 | none in pack |
| `minus_di` | `adx_v1` | −DI | 14 | none in pack |
| `relative_volume` | `relative_volume_v1` | current/previous mean volume | 20 | `relative_volume_last` |

The Stage 2A indicators are **series-only additions**. No scalar field was
added to `IndicatorPack`, so existing consumers are unaffected.

## 2. Trend-family formulas

All trend indicators use **close** and are aligned to the canonical entry
timeframe bars. `None`/NaN denotes an unavailable value; values are never
forward-filled or fabricated.

### WMA — Weighted Moving Average

For period `n` at bar `t`:

```text
WMA_t = Σ(k × close_{t-n+k}) / (n(n+1)/2),  k = 1..n
```

The newest close receives weight `n`; the oldest receives weight `1`. This is
the `asc=True` convention in pandas-ta-classic. Default: `wma_period=20`.
Warm-up: `n-1` bars (the first valid value is at zero-based index `n-1`).
Supported custom parameter: `length` (`wma_period`), positive integer.

### HMA — Hull Moving Average

```text
half = int(n / 2)                 # floor
root = int(sqrt(n))               # floor
raw_t = 2 × WMA(close, half)_t − WMA(close, n)_t
HMA_t = WMA(raw, root)_t
```

`int()` is truncation toward zero for the supported positive periods. Default:
`hma_period=20`. Warm-up: `n + root − 2` bars (22 for the default 20). Supported
custom parameter: `length` (`hma_period`), with `length >= 2`; `length < 2` is
rejected rather than substituted with another formula.

### DEMA — Double Exponential Moving Average

`EMA` here is the **SMA-seeded, non-adjusted** EMA used by the existing RSI
provider: the first EMA value is the arithmetic mean of the first `n` closes,
then `EMA_t = α·close_t + (1−α)·EMA_{t−1}` with `α = 2/(n+1)`.

```text
ema1 = EMA(close, n)
ema2 = EMA(ema1, n)
DEMA_t = 2 × ema1_t − ema2_t
```

Default: `dema_period=20`. Warm-up: `2(n−1)` bars (38 for the default 20).
Supported custom parameter: `length` (`dema_period`), positive integer.

### TEMA — Triple Exponential Moving Average

Same EMA convention as DEMA:

```text
ema1 = EMA(close, n)
ema2 = EMA(ema1, n)
ema3 = EMA(ema2, n)
TEMA_t = 3 × (ema1_t − ema2_t) + ema3_t
```

Default: `tema_period=20`. Warm-up: `3(n−1)` bars (57 for the default 20).
Supported custom parameter: `length` (`tema_period`), positive integer.

## 3. Alignment, warm-up and unavailable values

- `timestamps[i]` corresponds one-for-one with `values[i]` and the canonical
  source bar at that timestamp.
- Warm-up positions are `None` in `IndicatorSeries`; the provider exposes them
  as NaN internally.
- `warmup_bars` is the number of leading unavailable observations in the
  retained window. If no finite value exists, it equals the retained length.
- Insufficient history returns an all-unavailable series rather than a partial
  or padded result.
- Constant-price inputs produce the constant value once the warm-up is
  complete; no zero is invented for a zero/denominator edge case.
- `relative_volume` remains unavailable when volume is missing; volume is not
  synthesized.

## 4. Series window and scalar compatibility

- Default `series_window=2048` bars.
- `start_index` points into the full causal source bars; `source_bar_count` is
  the total materialized bar count.
- The latest-value scalar fields (`ema_fast_last`, etc.) are unchanged and are
  still the last value of the corresponding Stage 1 series.
- Stage 2A trend series are not added to the scalar pack surface.

## 5. Configuration

`FeatureConfig.indicators` (JSON object `indicators`) supports:

```json
{
  "wma_period": 20,
  "hma_period": 20,
  "dema_period": 20,
  "tema_period": 20
}
```

The defaults apply when the keys are omitted. Invalid periods fail
configuration validation; `hma_period < 2` is rejected. Parameter changes are
captured in `FeatureContext.provenance.indicator_parameters` and in the
configuration/schema hashes.

## 6. Unsupported / deferred

Not implemented in Stage 2A: Stochastic, CCI, ROC, Williams %R, Keltner,
Donchian, momentum/volatility/structure/statistical families, explicit
HH/HL/LH/LL, candle patterns, rolling standard deviation/Z-score/correlation,
ADR/daily range, caching, regime classification and strategy integration.

Unsupported: OBV, VWAP, MFI, CMF, Volume Profile and other volume-dependent
families.
