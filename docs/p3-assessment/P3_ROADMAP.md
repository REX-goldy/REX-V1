# P3 Roadmap

P3 is split into independently testable phases. Each phase must preserve P0/P1/P2 and stop
before the next phase until its gate passes.

## P3.0 — Assessment documentation

**Status:** restored by this directory; no implementation.

Deliverables: nine assessment documents.

Acceptance:

- current implementation claims verified against the repository;
- proposed vs implemented vs unsupported clearly separated;
- P3.1 scope and risks approved.

## P3.1 — Indicator series and feature foundation

**Status:** Stage 1 (series/provenance) and Stage 2A (trend family) implemented; remaining indicator families and caching remain pending.

**Goal:** reusable causal OHLC indicator series through the existing feature architecture.

Scope:

- extend `IndicatorProvider`/`IndicatorEngine` for the requested OHLC indicators;
- add bounded historical series/pack payloads;
- add explicit indicator IDs, method IDs, parameters and implementation versions;
- add feature configuration hash including pack IDs, methods, parameters, versions and
  relevant config;
- build one OHLC frame per timeframe per materialization;
- remove duplicate ATR and TrendView work;
- add bounded LRU feature cache with strict data/config/as-of/version keys;
- implement candle/statistical/range feature primitives;
- expose swing HH/HL/LH/LL; retain swing confirmation semantics;
- keep volume-dependent features unsupported.

Deliverables:

- `docs/p3-indicator-foundation/` (`README.md`, `ARCHITECTURE.md`,
  `INDICATOR_REFERENCE.md`, `FEATURE_VERSIONING.md`, `PERFORMANCE.md`, `TEST_REPORT.md`,
  `EVIDENCE/`);
- tests listed in the P3.1 brief;
- benchmarks against the 5.7 s full-history baseline.

Acceptance:

- every implemented indicator has independent reference tests;
- prefix/as-of/multi-timeframe tests pass;
- cache hit/miss/staleness tests pass;
- feature hash changes when config/method/version changes;
- duplicate ATR/TrendView work removed without behavior change;
- P0/P1/P2 regression remains green;
- full suite, lint, frontend build pass;
- memory and cache performance evidence recorded.

## P3.2 — Strategy performance analytics

**Goal:** read-only analytics over immutable run/experiment artifacts.

Scope:

- gross/net metrics and cost attribution;
- R distribution, duration, long/short;
- monthly/weekly/daily and session breakdowns;
- rolling metrics and drawdown;
- sample-size and truncation warnings;
- no account-currency or portfolio claims.

Acceptance:

- independent aggregation tests;
- no run mutation;
- API/UI reads real artifacts;
- P2.1 snapshot/experiment compatibility.

## P3.3 — Market regime analysis

**Goal:** transparent causal regime classification.

Scope:

- `RegimePack`/`RegimeView`, method `ohlc_regime_v1`;
- trend/range, volatility, expansion, momentum and persistence axes;
- fixed thresholds or causal rolling thresholds;
- explicit `UNKNOWN`/unavailable states;
- regime-conditioned analytics joins with causal availability.

Acceptance:

- synthetic/real regime fixtures;
- prefix invariance and as-of tests;
- no future data leakage;
- versioned feature/regime provenance in snapshots;
- no ML required for initial version.

## P3.4 — Robustness research

**Goal:** traceable parameter sensitivity and validation experiments.

Scope:

- parameter grids and trial ledger;
- walk-forward/in-sample/out-of-sample splits;
- rolling and regime-conditioned performance;
- multiple-testing metadata and total trial count;
- failed/invalid trial preservation;
- all runs through `BacktestRunner`.

Acceptance:

- failed trials recorded;
- split boundaries and holdout discipline enforced;
- no optimization on holdout;
- comparable experiment grouping;
- immutable robustness artifacts.

## P3.5 — Integration and verification

**Goal:** make P3 analytics usable through existing interfaces with P2.1 provenance.

Scope:

- API/frontend for analytics and regime snapshots;
- feature/regime snapshot fields in new experiment records;
- reproduction compatibility checks;
- E2E workflows for experiment → analytics → regime → robustness;
- documentation and evidence.

Acceptance:

- browser workflows verified;
- old experiments preserved and structured as legacy/non-reproducible where applicable;
- no fabricated metrics;
- full P0/P1/P2/P3 regression, lint and build;
- evidence record complete.

## Dependency order

```
P3.0 → P3.1 → P3.2/P3.3 → P3.4 → P3.5
```

P3.2 and P3.3 may share the P3.1 feature/caching foundation but must not create a second
pipeline. P3.4 depends on P3.1/P3.2 (and optionally P3.3 for regime conditioning).

## Related documents

[README](README.md) · [Current state](CURRENT_STATE.md) · [Feature catalogue](FEATURE_CATALOGUE.md) · [Analytics](ANALYTICS_ASSESSMENT.md) · [Regime](REGIME_RESEARCH.md) · [Robustness](ROBUSTNESS_ASSESSMENT.md) · [Architecture](ARCHITECTURE_PROPOSAL.md) · [Roadmap](P3_ROADMAP.md) · [Risks](RISKS_AND_OPEN_QUESTIONS.md)
