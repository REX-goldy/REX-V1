# P3.1 Indicator Foundation — Stage 1 + Stage 2A

- **Status:** Stage 1 and Stage 2A (trend family) implemented; later families not started
- **Scope:** versioned, causal indicator series through the existing feature architecture
- **Data:** OHLC-only; no volume synthesis
- **Backtest impact:** none; strategies still consume raw bars
- **Platform:** Python 3.11, pandas-ta-classic (existing dependency)
- **No commit, push or deployment performed.**

## What Stage 1 adds

- timestamp-aligned `IndicatorSeries` outputs;
- series for the existing indicator families (SMA/EMA/RSI/ATR/MACD/Bollinger/ADX/+DI/−DI/relative volume);
- Stage 2A trend series: WMA, HMA, DEMA, TEMA with explicit formulas and warm-up semantics;
- bounded series windows (2048 observations by default) with `source_bar_count` and `start_index`;
- `FeatureProvenance` on `FeatureContext` with pack IDs, method IDs, indicator parameters,
  indicator implementation versions, config hash, schema hash and timeframe;
- deterministic `feature_config_hash` and `schema_hash`;
- one reusable OHLC DataFrame per indicator materialization;
- tests for alignment, warm-up, as-of/prefix invariance, custom parameters, hash determinism,
  version changes, scalar compatibility and independent numerical references.

## Not added

- remaining indicator families (Stochastic, CCI, ROC, Williams %R, Keltner,
  Donchian, momentum/volatility/structure/statistical families, candle patterns,
  rolling statistics, ADR/daily range);
- feature caching (explicit Stage 1 exclusion);
- regime classification;
- strategy `FeatureContext` integration;
- P2.1 experiment snapshot writes;
- parameter sweeps or walk-forward infrastructure;
- volume data.

## Documents

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [INDICATOR_REFERENCE.md](INDICATOR_REFERENCE.md)
- [FEATURE_VERSIONING.md](FEATURE_VERSIONING.md)
- [PERFORMANCE.md](PERFORMANCE.md)
- [TEST_REPORT.md](TEST_REPORT.md)
- [EVIDENCE/](EVIDENCE/)
- [P3 assessment](../p3-assessment/README.md)
- [P3.1 roadmap](../p3-assessment/P3_ROADMAP.md)
- [P3 risks](../p3-assessment/RISKS_AND_OPEN_QUESTIONS.md)
