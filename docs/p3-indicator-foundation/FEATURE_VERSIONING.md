# Feature and Indicator Versioning

## 1. Versions

`core/features/versioning.py` defines:

```python
FEATURE_SCHEMA_VERSION = "p3_feature_v1"
FEATURE_CONFIG_VERSION = 1
```

Indicator implementation versions are explicit string IDs. Stage 2A adds:

| Indicator ID | Method ID | Implementation version |
|---|---|---|
| `wma` | `wma_v1` | `wma_v1` |
| `hma` | `hma_v1` | `hma_v1` |
| `dema` | `dema_v1` | `dema_v1` |
| `tema` | `tema_v1` | `tema_v1` |

Existing IDs (`sma_v1`, `ema_v1`, `atr_v1`, `bollinger_v1`, `adx_v1`, etc.)
remain unchanged. Method IDs identify view semantics
(`market_structure_v1`, `ts_mom_v1`, `range_expansion_v1`, `heuristic_v1`, etc.).

Changing a formula, smoothing convention, parameter interpretation or implementation must
change the implementation version. Stage 2A did not silently redefine SMA or EMA.

## 2. Configuration hash

`feature_config_hash(config)` hashes canonical JSON containing:

- feature schema/config versions;
- all `FeatureConfig` fields, including the Stage 2A `wma_period`,
  `hma_period`, `dema_period` and `tema_period`;
- indicator parameters including SMA/Bollinger/ADX/series-window;
- indicator implementation versions;
- indicator/method ID maps.

The same config and versions produce the same hash. A custom period, method mapping, or
implementation version changes it. Because Stage 2A adds configuration fields, the hash of a
given config is intentionally different from a pre-Stage-2A config hash; no historical
experiment record was modified.

## 3. Schema hash

`feature_schema_hash(...)` hashes:

- schema/config versions;
- sorted selected pack IDs;
- view method IDs;
- indicator method IDs;
- indicator implementation versions;
- feature config hash;
- entry timeframe.

This replaces the old pack-ID-only hash. `FeatureContext.schema_hash` uses this value.

## 4. FeatureContext provenance

`FeatureContext.provenance` is a `FeatureProvenance` containing:

- schema/config versions and hashes;
- pack IDs;
- method IDs;
- indicator versions;
- indicator parameters;
- entry timeframe.

Stage 2A preserves this structure and records the four new trend indicators in
`indicator_versions` and `indicator_parameters`. It does **not** modify existing
P2.1 experiment records or run artifacts.

## 5. Reproduction compatibility

Future P3.1/P2.1 integration must:

- snapshot `feature_schema_version`, `feature_config_hash`, method/indicator versions and
  parameters;
- compare them before reproducing a run;
- return a structured `FEATURE_SNAPSHOT_MISSING` or `FEATURE_VERSION_INCOMPATIBLE` failure
  rather than silently using current definitions;
- leave old experiments unchanged.

Stage 1 and Stage 2A exclude that persistence change.
