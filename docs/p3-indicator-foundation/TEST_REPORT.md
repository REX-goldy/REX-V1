# P3.1 Test Report — Stage 1 + Stage 2A

- **Date:** 2026-11-06
- **Full backend suite:** **674 / 674 PASS**
- **P3 Stage 2A trend tests:** 18
- **P3 Stage 1 tests:** 6 (still passing)
- **Lint:** PASS
- **Frontend production build:** not affected (no frontend changes in Stage 2A)
- **P0/P1/P2 regression:** PASS (included in full suite)
- **No strategy, `BacktestRunner`, historical-data, experiment or run-artifact changes.**

## 1. Stage 2A test coverage

`tests/test_p3_trend_indicators.py` covers:

### Independent numerical references

- WMA against a direct weighted-window Python reference.
- HMA against a direct two-stage WMA Python reference.
- DEMA against a direct SMA-seeded EMA-chain Python reference.
- TEMA against a direct three-stage EMA-chain Python reference.
- The reference functions do not import or call pandas-ta-classic or
  `IndicatorEngine`.

### Parameters, warm-up and edge cases

- Default period 20 and custom WMA=7, HMA=9, DEMA=8, TEMA=6.
- Custom periods appear in series metadata and provenance.
- Deterministic warm-up counts: WMA 19, HMA 22, DEMA 38, TEMA 57 at period 20.
- Insufficient history yields all `None` values, not padded/partial values.
- Constant-price series equals the constant after warm-up.
- HMA period < 2 is rejected.
- Provider insufficient-history calls do not raise.

### Causality and alignment

- Series timestamps align one-for-one with canonical entry bars.
- `asof` contexts contain no bars after the cutoff.
- Changing appended future OHLC values does not change historical series at the
  same `asof`.
- Prefix invariance at both provider level and `FeatureRepository` level.
- Provider-level values for WMA/HMA/DEMA/TEMA match an independent reference on
  the prefix.

### Provenance, hashes and regression

- Indicator implementation versions and parameters are present in
  `FeatureContext.provenance`.
- Same config produces the same schema hash.
- Changing an indicator implementation version changes the schema hash.
- Existing SMA and EMA output remains numerically correct and unchanged.
- Existing scalar `ema_fast_last` still equals the last series value.
- Duplicate timestamps remain rejected by `FeatureRepository`.

Commands:

```bash
python -m unittest tests.test_p3_trend_indicators -v
python -m unittest tests.test_p3_indicator_series -v
python -m unittest discover -s tests
make lint
```

## 2. Results

```text
Ran 18 tests ... OK
Ran 6 tests ... OK
Ran 674 tests ... OK
lint exit 0
```

Evidence: `EVIDENCE/stage2a-tests.log`, `EVIDENCE/stage2a-tests-full.log`,
`EVIDENCE/stage2a-lint.log`, `EVIDENCE/stage2a-benchmark.txt`.

## 3. Mathematical validation

- The independent WMA/HMA/DEMA/TEMA references use only Python lists and
  arithmetic loops.
- WMA weights are `1..n` with the newest close weighted `n`.
- HMA uses `int(n/2)` and `int(sqrt(n))`, with a WMA composition.
- DEMA/TEMA use the SMA-seeded, non-adjusted EMA convention; references seed
  with the mean of the first `n` valid values and apply
  `alpha = 2/(n+1)`.
- Maximum observed absolute difference across the reference tests is on the
  order of `1e-15` (numerical round-off only).

## 4. Performance evidence

See [PERFORMANCE.md](PERFORMANCE.md) and
`EVIDENCE/stage2a-benchmark.txt`. No caching was added.

## 5. Known test gaps

- No test for the remaining indicator families (explicitly out of scope).
- No cache tests because caching is excluded.
- No P2 experiment snapshot feature-provenance integration test; Stage 2A only
  preserves the provenance object.
- Performance is an external benchmark, not a CI assertion.
- HMA/EMA behavior for pathological NaN inputs is not part of the OHLC-only
  production path; tests cover finite prices and insufficient history.
