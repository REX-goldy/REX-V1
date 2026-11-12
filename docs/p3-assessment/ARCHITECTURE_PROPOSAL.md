# Architecture Proposal

## 1. Reuse boundaries

| Concern | Existing owner | P3 rule |
|---|---|---|
| Feature materialization | `core/features/FeatureRepository` | Extend only; single architecture |
| Indicator math | `core/indicators/IndicatorProvider` / `IndicatorEngine` | Extend provider surface; no second engine |
| Backtest execution | `backtests/BacktestRunner` | Reuse only; no second pipeline |
| Cost/risk/validation | P1 modules | Reuse; record assumptions |
| Experiment/run persistence | P2.1 JSON workspace + run archive | Add feature provenance; do not rewrite old records |
| Historical data | `historical/` | Read-only; no volume fabrication |

P3 must not let analytics or regimes create independent feature engines.

## 2. Feature/indicator extension design

### Indicator provider

Extend `IndicatorProvider` and `PandasTAProvider` with the proposed methods. Every method:

- takes canonical bars or a shared OHLC frame;
- returns a pandas Series/result aligned to canonical timestamps;
- has a documented convention, parameters, warm-up and NaN behavior;
- has an implementation version ID.

To avoid repeated frame construction, add a batch calculation path that builds one frame
per timeframe and reuses it across indicator methods. Existing public methods remain
compatible; no output changes without documented correction.

### Feature packs and views

Extend existing packs rather than creating a parallel hierarchy:

- `IndicatorPack`: latest values plus optional bounded historical series;
- new candle/statistics/range packs;
- `RegimePack` and `RegimeView` (P3.3);
- `StructurePack` gains explicit HH/HL/LH/LL projections where required.

Historical series should be bounded by a configured lookback/window; do not store every
series for every full-history bar in every snapshot.

### FeatureContext / versioning

Add:

- `feature_config_hash`;
- pack IDs;
- method/indicator IDs;
- parameter values;
- implementation versions;
- library/provider version;
- as-of/timeframe context.

The feature hash must change when any of those change. It is distinct from the existing
pack-ID-only `schema_hash`.

## 3. Caching

Use an in-memory bounded cache inside the existing repository or service layer:

```
key = (
  dataset identity/hash,
  symbol,
  entry timeframe,
  pack IDs,
  indicator/method versions,
  parameters/config hash,
  asof,
  bounded window,
)
```

Rules:

- Never return a context computed from a different bar prefix or config.
- Cache immutable contexts; no mutation after return.
- Use an LRU/max-entry and max-series-window policy.
- Invalidate naturally via key changes; no stale global cache.
- Do not persist cache to a database.
- Reproduction must verify feature/version snapshots before using any cache.

## 4. Duplicate calculation elimination

1. Compute ATR once and pass it to both volatility and indicator packs.
2. Compute TrendProjection once per `FeatureContext`; pass it to PhaseView and
   MarketStateBuilder rather than recalculating.
3. Build one pandas OHLC frame per timeframe/materialization and reuse it.
4. Reuse returns/close windows across momentum/statistics features.

These are internal performance refactors; outputs must remain equivalent unless a
documented formula correction is approved and tested.

## 5. API and frontend

Proposed read-only API additions:

- feature catalogue/metadata (IDs, versions, parameters, availability);
- feature snapshot for a dataset/as-of (bounded series);
- run analytics endpoint;
- regime series/snapshot;
- robustness artifact and trial summary.

Frontend integration, when implemented in later P3 phases:

- Strategy Lab/Analytics: gross/net, long/short, distribution, regime context;
- Run Archive: analytics and feature/validation provenance;
- Strategy Workspace: experiment reproducibility status;
- no fabricated or hardcoded metrics.

No API change is part of P3.0.

## 6. Experiment provenance

For new experiments after P3.1:

```json
{
  "feature_config_hash": "...",
  "feature_snapshot_version": 1,
  "feature_methods": {
    "sma": {"method_id": "sma_v1", "parameters": {"length": 20}, "implementation_version": "1"}
  },
  "feature_timeframes": ["M1", "M15", "H1"],
  "feature_data_hash": "..."
}
```

P2.1 reproduction must:

- compare feature configuration/method/implementation versions;
- refuse to substitute newer definitions;
- return `FEATURE_SNAPSHOT_MISSING` or `FEATURE_VERSION_INCOMPATIBLE` if unavailable;
- leave old completed experiments unchanged.

## 7. Testing strategy

- Independent numerical reference tests for every indicator/statistic.
- Warm-up/NaN/zero-denominator/constant series tests.
- Causal prefix, as-of and multi-timeframe alignment tests.
- Cache hit/miss/invalidation/staleness tests.
- Feature hash/version change tests.
- Duplicate ATR/TrendView equivalence tests.
- P2.1 snapshot/reproduction compatibility tests.
- Existing P0/P1/P2 regression tests.
- Performance/memory evidence for 184,963 EURUSD M1 bars.

## 8. Explicit non-goals

- No ClickHouse/database migration.
- No new feature-generation architecture.
- No strategy migration to `FeatureContext` in P3.1.
- No volume synthesis.
- No ML regime model in the initial version.
- No P4–P6 features.

## Related documents

[README](README.md) · [Current state](CURRENT_STATE.md) · [Feature catalogue](FEATURE_CATALOGUE.md) · [Analytics](ANALYTICS_ASSESSMENT.md) · [Regime](REGIME_RESEARCH.md) · [Robustness](ROBUSTNESS_ASSESSMENT.md) · [Architecture](ARCHITECTURE_PROPOSAL.md) · [Roadmap](P3_ROADMAP.md) · [Risks](RISKS_AND_OPEN_QUESTIONS.md)
