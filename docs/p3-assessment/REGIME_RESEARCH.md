# Market Regime Research

## 1. Current regime-adjacent implementation

REX currently has descriptive structure/phase features, not a general regime classifier:

- `MarketTrend`: `bullish`, `bearish`, `ranging`, `unknown`.
- `MarketPhase`: `trend`, `pullback`, `range`, `compression`, `reversal`.
- `RangeExpansionState`: `low`, `normal`, `high`, `unavailable`.
- `TrendView` uses confirmed swing sequence (`market_structure_v1`).
- `MomentumView` uses cumulative simple return (`ts_mom_v1`).
- `VolatilityView` projects range expansion.
- `PhaseView` combines trend, range expansion, recent closes and configured scores.
- `MarketStateBuilder` packages these into an availability-aware snapshot.

`PhaseView` is a heuristic descriptive phase, not a probability or validated regime model.
`MarketTrend`/`MarketPhase` labels are deterministic, but regime research needs a clearer,
versioned, causal feature set.

## 2. Proposed regime axes

Keep the first classifier transparent and threshold-based:

| Axis | Inputs | Labels |
|---|---|---|
| Trend vs range | confirmed swings, ADX/+DI/−DI, close drift | trend-up, trend-down, range, transition, unknown |
| Volatility | ATR relative to causal rolling baseline, Bollinger width | low, normal, high, unknown |
| Momentum strength | RSI, MACD histogram, ROC | weak, neutral, strong, unknown |
| Expansion | range expansion / Donchian width | contraction, normal, expansion, unknown |
| Directional persistence | sign/return persistence, swing sequence | persistent-up, persistent-down, mixed, unknown |

A combined label should be a small, documented tuple or enum:
`trend_regime × volatility_regime × expansion_regime`, with an explicit `unknown` on any
insufficient input. Do not turn a score into a probability.

## 3. Causal architecture

- Implement `RegimePack` and `RegimeView` within the existing feature architecture.
- Use `FeatureRepository.materialize(..., asof=T)`; only bars/completed HTF bars available
  at `T` may contribute.
- Indicator calculation uses prefixes of the source series.
- Thresholds:
  - fixed configured thresholds in the first version;
  - rolling quantiles only if computed from prior complete bars and validated for prefix
    invariance.
- Regime labels at `T` must be identical when future bars after `T` are appended.
- Warm-up produces `unknown`/unavailable, not a default label.
- Store method ID, config version and implementation version in the snapshot.
- No machine learning in the first implementation; no use of future regime labels to
  classify earlier bars.

## 4. Proposed method ID

`ohlc_regime_v1`

Inputs/dependencies:

- `StructurePack` / `market_structure_v1`
- `IndicatorPack` (ADX, RSI, MACD, ATR, Bollinger, ROC)
- `VolatilityPack` / `range_expansion_v1`
- `PricePack` returns
- new candle/range/statistics packs where implemented

Outputs:

- trend regime;
- volatility regime;
- expansion regime;
- momentum strength;
- directional persistence;
- `unknown`/reason strings;
- feature/version provenance.

## 5. Validation plan

- Synthetic monotonic, ranging, high-volatility and compression fixtures.
- Real EURUSD/GBPUSD/AUDUSD/USDJPY/USDCAD windows.
- Prefix-invariance tests at multiple as-of points.
- Constant/zero-range series and insufficient history.
- Boundary tests around every threshold.
- Regime labels must be stable for repeated materialization.
- Regime-conditioned performance must join trades only to regimes available at entry time.

## 6. Open questions

- Should regime be computed on the entry timeframe only, or across a configured multi-timeframe
  confluence set?
- Should thresholds be fixed config values or causal rolling quantiles?
- Should regime labels be exposed to strategies only after separate approval?
- How should `transition` be defined without ML or hindsight?
- How should regimes be compared across instruments with very different volatility scales?

## Related documents

[README](README.md) · [Current state](CURRENT_STATE.md) · [Feature catalogue](FEATURE_CATALOGUE.md) · [Analytics](ANALYTICS_ASSESSMENT.md) · [Regime](REGIME_RESEARCH.md) · [Robustness](ROBUSTNESS_ASSESSMENT.md) · [Architecture](ARCHITECTURE_PROPOSAL.md) · [Roadmap](P3_ROADMAP.md) · [Risks](RISKS_AND_OPEN_QUESTIONS.md)
