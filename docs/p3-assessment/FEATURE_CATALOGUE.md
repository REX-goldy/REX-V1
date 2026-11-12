# OHLC Feature Catalogue

- **Scope:** P3 indicator/feature assessment
- **Data:** canonical OHLC bars only; volume is unavailable
- **Status meaning:**
  - **Implemented** — exists in current feature/indicator code and is exercised by tests.
  - **Partial** — some computation exists but is not exposed as a usable causal series or is unusable with current data.
  - **Proposed** — required by P3, not implemented in the current tree.
  - **Unsupported** — cannot be computed from current OHLC-only data.

This catalogue documents expected conventions. It does not claim proposed features exist.

## 1. Conventions

- All indicator inputs are canonical `Bar` values aligned to bar open timestamps.
- Causal series at `T` may use bars with timestamp/completion `<= T` only.
- Indicator outputs are aligned 1:1 to the source bar sequence; warm-up values are `NaN`
  in pandas series or `None` in feature-pack scalars.
- Missing/invalid inputs return `NaN`/`None` or an explicit unavailable/unsupported result;
  they are never filled with fabricated values.
- HMA/DEMA/TEMA/Stochastic/Donchian/Keltner conventions must be documented and validated
  independently; the provider library is an implementation detail, not the definition.
- Timeframes: M1 is stored; M5/M15/H1/H4 are derived through the existing causal path.
- Volume-dependent features are not computed or approximated.

## 2. Current implemented features

| ID / feature | Group | Formula / convention | Defaults | Warm-up | Missing behavior | Causal | Status / source |
|---|---|---|---|---|---|---|---|
| `sma` | Trend | Arithmetic mean of close over `n` | `n=20` | `n-1` NaNs (provider convention) | NaN until warm-up | Yes, prefix | **Implemented** — `PandasTAProvider.sma`; scalar via `IndicatorPack` |
| `ema` | Trend | Recursive `EMA_t = α·C_t + (1-α)·EMA_{t-1}`, `α=2/(n+1)` | `n=20` | first finite at `n` (library convention) | NaN until warm-up | Yes | **Implemented** — scalar pack |
| `rsi` | Momentum | Wilder gain/loss ratio, 0–100 | `n=14` | first finite at `n` | NaN until warm-up | Yes | **Implemented** — scalar pack |
| `atr` | Volatility | Wilder average of true range | `n=14` | first finite at `n` | NaN until warm-up | Yes | **Implemented** — but duplicate in volatility/indicator packs |
| `macd` | Momentum | `EMA_fast − EMA_slow`, signal EMA, histogram | `12/26/9` | `slow + signal` | NaN until warm-up | Yes | **Implemented** — scalar components in `IndicatorPack` |
| `bollinger` | Volatility | SMA ± `k·std(close,n)` | `n=20`, `k=2` | `n` | NaN until warm-up | Yes | **Implemented** — scalar bands not exposed in pack |
| `adx` | Trend strength | Wilder ADX; +DI/−DI | `n=14` | ~`2n` | NaN until warm-up | Yes | **Partial** — engine exists, pack does not expose series |
| `swings` | Structure | Strict local fractal high/low: candidate strictly greater/less than `left+right` neighbors | `left=2`, `right=2` | `left+right+1` | No events when insufficient | Yes; confirmation time recorded | **Implemented** — `SwingGenerator` |
| `bos` | Structure | Latest confirmed swing high/low broken by a later close; swing consumed once | method `swing_bos_v1` | at least one confirmed swing | No event, reason | Yes; `confirmation_index < break_index` | **Implemented** — `detect_swing_bos_series` |
| `range_expansion` | Range | Recent mean body / historical mean body | recent 5, historical 20 | 20 | `UNAVAILABLE`, no ratio | Yes; uses supplied completed bars | **Implemented** — `RangeExpansionGenerator` |
| `returns` | Statistics | Close-to-close simple/log returns | no lookback | 2 bars | 0.0 on non-positive/zero denominator by current code | Yes | **Implemented** — but zero-denominator convention should be reconsidered |
| `relative_volume` | Volume | Current volume / mean previous `n` volumes | 20 | `n+1` | NaN when volume missing/zero baseline | Yes | **Partial/unavailable** — no stored volume |

## 3. Proposed trend indicators

| Feature | Formula | Defaults | Warm-up | NaN / missing | Status |
|---|---|---|---|---|---|
| WMA | `Σ(i·C_{t-n+i}) / Σi`, weight 1..n | 20 | `n-1` | NaN until window complete | Proposed |
| HMA | `WMA(⌊√n⌋)` of `2·WMA(n/2) − WMA(n)` | 20 | ~`2n` | NaN until all nested windows valid | Proposed |
| DEMA | `2·EMA(C,n) − EMA(EMA(C,n),n)` | 20 | ~`2n` | NaN until warm-up | Proposed |
| TEMA | `3·EMA1 − 3·EMA2 + EMA3` | 20 | ~`3n` | NaN until warm-up | Proposed |

ADX is implemented at the engine level but must be exposed as reusable ADX/+DI/−DI series
and a pack before treating it as an available feature family.

## 4. Proposed momentum indicators

| Feature | Formula | Defaults | Warm-up | Missing behavior | Status |
|---|---|---|---|---|---|
| Stochastic %K | `100·(C−LL_n)/(HH_n−LL_n)`; `%D=SMA(%K,k)` | 14, smooth 3 | `n + k` | NaN if zero range or insufficient | Proposed |
| CCI | `(TP−SMA(TP,n))/(0.015·mean deviation)` | 20 | `n` | NaN if mean deviation zero | Proposed |
| ROC | `100·(C_t/C_{t-n}−1)` | 12 | `n` | NaN if denominator non-positive/zero | Proposed |
| Williams %R | `−100·(HH_n−C)/(HH_n−LL_n)` | 14 | `n` | NaN if zero range | Proposed |
| MACD histogram | `MACD − signal` | 12/26/9 | `slow+signal` | NaN until warm-up | Implemented scalar; series proposed |
| RSI | Wilder | 14 | `n` | NaN until warm-up | Implemented scalar; series proposed |

## 5. Proposed volatility and channel features

| Feature | Formula | Defaults | Warm-up | Missing behavior | Status |
|---|---|---|---|---|---|
| True Range | `max(H−L, |H−C_prev|, |L−C_prev|)` | — | one previous bar | NaN for first bar | Proposed explicit series |
| ATR | Wilder mean TR | 14 | `n` | NaN until warm-up | Implemented scalar; series proposed |
| Bollinger | SMA ± `k·population/sample std` (exact convention to pin) | 20,2 | `n` | NaN until warm-up | Implemented scalar; series proposed |
| Keltner | EMA ± `k·ATR` | 20,2,14 | `max(n_ema,n_atr)` | NaN until warm-up | Proposed |
| Donchian | rolling highest high / lowest low | 20 | `n` | NaN until window complete | Proposed |
| ADX/+DI/−DI | Wilder directional movement | 14 | ~`2n` | NaN until warm-up | Engine implemented; pack series proposed |

## 6. Price structure and candle features

| Feature | Convention | Defaults | Causal / missing | Status |
|---|---|---|---|---|
| Swing highs/lows | strict fractal extrema with confirmation time | left/right 2 | confirmed events only | Implemented |
| HH/HL/LH/LL | compare confirmed swing sequence: higher highs/lows, lower highs/lows | derived | requires ≥2 confirmed swings; `UNKNOWN` otherwise | Proposed as explicit labels |
| Body size | `abs(close-open)` | one bar | NaN/None if invalid bar | Proposed |
| Upper wick | `high - max(open,close)` | one bar | non-negative | Proposed |
| Lower wick | `min(open,close) - low` | one bar | non-negative | Proposed |
| Wick ratios | wick / `(high-low)` | one bar | `None` if zero range | Proposed |
| Bullish engulfing | current body fully engulfs prior body and closes bullish | two bars | no signal if insufficient | Proposed |
| Bearish engulfing | current body fully engulfs prior body and closes bearish | two bars | no signal if insufficient | Proposed |
| Pin bar | long wick relative to body/range with configured thresholds | proposed config | no signal if zero range | Proposed |
| Inside bar | current high≤prior high and low≥prior low | two bars | no signal if insufficient | Proposed |
| Outside bar | current high>prior high and low<prior low | two bars | no signal if insufficient | Proposed |
| Range expansion | body-size ratio | 5/20 | unavailable if baseline zero | Implemented |

## 7. Statistical and range features

| Feature | Formula | Defaults | Warm-up | Missing / causal | Status |
|---|---|---|---|---|---|
| Simple returns | `C_t/C_{t-1}−1` | — | 2 bars | current code appends 0.0 for non-positive denominator; proposal should use NaN | Implemented |
| Log returns | `ln(C_t/C_{t-1})` | — | 2 bars | NaN when non-positive/zero | Implemented with current 0.0 fallback |
| Rolling standard deviation | std of selected series over `n` | 20 | `n` | NaN until warm-up | Proposed |
| Rolling Z-score | `(x−rolling_mean)/rolling_std` | 20 | `n+1` | NaN if std zero/insufficient | Proposed |
| Rolling correlation | `corr(x,y)` over aligned causal window | 20 | `n` | requires two aligned series; `None` otherwise | Proposed |
| Daily range | daily high−low from completed daily bars | — | one completed day | no future day; None if no completed day | Proposed |
| ADR | mean daily range over `n` days | 14 | `n` completed days | None/NaN until warm-up | Proposed |

## 8. Unsupported volume-dependent features

The following remain **unsupported** for current datasets and must not be approximated:

- OBV
- VWAP
- MFI
- CMF
- Volume Profile
- Relative volume (listed as partial API; unusable without volume)

`PandasTAProvider._ohlc` currently substitutes `0.0` for missing volume when building frames.
That fallback must never be used to advertise volume indicators as available. P3 must
represent missing volume explicitly through the existing unavailable/unsupported mechanism.

## 9. Reference validation requirements

For every implemented/proposed feature:

1. Independent calculation in test code (NumPy/pandas or explicit loops), not the same
   provider function.
2. Default and custom parameter cases.
3. Warm-up/insufficient-history NaN behavior.
4. Constant-price and zero-range/denominator cases.
5. Missing/invalid bars.
6. Prefix invariance: adding future candles must not change values at earlier timestamps.
7. Causal as-of boundary tests.
8. Timeframe alignment through `prepare_causal_bars`.
9. Feature pack dependency tests.
10. Configuration/version hash changes when parameters/method implementations change.

## 10. Current test coverage vs gaps

- `tests/test_indicators.py` covers current provider methods and some warm-up/NaN behavior.
- `tests/test_feature_repository.py`, `test_feature_views.py`, `test_swing_events.py`,
  `test_swing_bos.py`, `test_market_state.py` cover existing packs/views.
- No tests exist for the proposed indicator catalogue, feature-series packs, feature cache,
  feature config hash, candle features, rolling statistics, or regime features.

## Related documents

[README](README.md) · [Current state](CURRENT_STATE.md) · [Feature catalogue](FEATURE_CATALOGUE.md) · [Analytics](ANALYTICS_ASSESSMENT.md) · [Regime](REGIME_RESEARCH.md) · [Robustness](ROBUSTNESS_ASSESSMENT.md) · [Architecture](ARCHITECTURE_PROPOSAL.md) · [Roadmap](P3_ROADMAP.md) · [Risks](RISKS_AND_OPEN_QUESTIONS.md)
