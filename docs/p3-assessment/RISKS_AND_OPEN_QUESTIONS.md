# Risks and Open Questions

## 1. Data risks

### No volume
Current partitions are OHLC-only. OBV, VWAP, MFI, CMF, Volume Profile and relative volume
cannot be implemented honestly. Relative volume exists as a provider API but has no usable
data and must be marked unavailable. Do not synthesize or zero-fill volume.

### Data gaps
EURUSD has 10 unexpected provider gaps; any indicator/regime analytics must preserve
dataset-quality flags and not interpolate.

### No bid/ask/tick data
Intrabar order and spread cannot be reconstructed. Execution remains OHLC-based; no claims
about observed historical spread.

## 2. Mathematical and implementation risks

- Formula drift between the library implementation, independent tests and documented
  convention (HMA/DEMA/TEMA, Wilder RSI/ATR/ADX, Bollinger std convention, Stochastic
  smoothing).
- `pandas-ta-classic` dependency is currently bounded (`>=0.6.52`) but not pinned exactly.
  P3.1 must pin it and record the version in feature provenance.
- EMA/HMA/DEMA/TEMA seeds and warm-up differ across libraries. Tests must assert the chosen
  convention.
- Constant prices, zero ranges and zero denominators need explicit NaN/None behavior.
- Volume may be accidentally zero-filled in a frame; never use that to advertise a volume
  feature.

## 3. Causality and look-ahead

- Regime thresholds, rolling quantiles, rolling correlations and rolling z-scores must use
  only completed bars at or before the as-of time.
- HTF inputs must be completed buckets; incomplete buckets must not be emitted.
- Feature caches must include the as-of boundary, bar/data identity, config hash and
  implementation versions; otherwise stale or future-leaking data could be returned.
- Prefix invariance and future-append tests are mandatory.

## 4. Performance and memory

- Current full-history feature materialization measured ~5.7 s for 184,963 M1 bars with no
  cache.
- Per-indicator DataFrame reconstruction and full close-series retention increase memory.
- Adding all series to every pack could make contexts large; use bounded lookback/windows
  and latest-only values where full history is unnecessary.
- Cache size and eviction must be bounded; no unbounded global feature cache.

## 5. Reproducibility

- Existing feature schema hash covers only pack IDs; it must include config, method IDs,
  parameters, implementation versions and relevant library versions.
- P2.1 experiment snapshots currently lack feature provenance; new P3.1 experiments must
  record it, while legacy experiments remain unchanged and return structured incompatibility.
- Reproduction must not silently use newer indicator definitions or current configuration.
- Dataset hash verification is required; metadata should be snapshotted.

## 6. Analytics risks

- Monthly/session grouping depends on unambiguous trade attribution (entry vs exit).
- SessionManager uses fixed UTC windows/IST reporting without DST/holiday modeling.
- R-multiple metrics are not account-currency returns; portfolio equity, exposure,
  compounding, margin and currency conversion are unsupported.
- Truncated trade ledgers may make distributions partial; expose `trades_truncated`.
- Small samples and multiple trials can manufacture apparent edge.

## 7. Strategy integration risk

All current strategies consume raw bars. Moving them to `FeatureContext` in P3 would alter
strategy behavior and belongs to a separately approved phase. P3 analytics/regimes must
remain additive and must not silently change strategy outputs.

## 8. Robustness/multiple-testing risks

- Parameter sweeps without trial accounting create selection bias.
- Walk-forward split boundaries must be explicit and causal.
- Failed/invalid trials must be recorded; dropping them biases results.
- Multiple-testing corrections and holdout discipline must be defined before evaluating
  holdout results.

## 9. Architecture risks

- Creating new feature packs/views that duplicate FeatureRepository or IndicatorEngine.
- Adding a database/ClickHouse before storage needs are evidenced.
- Cache invalidation errors or cross-experiment feature reuse.
- API/UI displaying hardcoded or stale metrics rather than run/feature outputs.

## Open questions

1. Should feature series be stored in packs as bounded windows, or computed on demand from
   cached indicator series?
2. What exact default windows should be used for new indicators and regime axes?
3. Should regime thresholds be fixed config values or causal rolling quantiles?
4. Which feature/method implementation version should be considered the first stable
   `v1` set?
5. How should feature snapshots be embedded in P2.1 experiments without modifying legacy
   records?
6. Should trade analytics attribute a trade to entry date, exit date, or both?
7. Which sample-size and multiple-testing conventions are required before P3.4?
8. How should session analytics represent DST and exchange holidays?

## Related documents

[README](README.md) · [Current state](CURRENT_STATE.md) · [Feature catalogue](FEATURE_CATALOGUE.md) · [Analytics](ANALYTICS_ASSESSMENT.md) · [Regime](REGIME_RESEARCH.md) · [Robustness](ROBUSTNESS_ASSESSMENT.md) · [Architecture](ARCHITECTURE_PROPOSAL.md) · [Roadmap](P3_ROADMAP.md) · [Risks](RISKS_AND_OPEN_QUESTIONS.md)
