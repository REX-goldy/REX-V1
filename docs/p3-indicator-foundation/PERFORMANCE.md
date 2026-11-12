# Performance and Memory — Stage 1 + Stage 2A

## 1. Environment and workloads

Environment: current workspace, Python 3.11, EURUSD/M1/2026, default feature packs,
`series_window=2048`, no feature cache.

Two workloads are reported separately:

1. **Trend-only provider workload** — prepare the close/OHLC frame once, then
   compute the four new Stage 2A series (`wma`, `hma`, `dema`, `tema`, length
   20). This isolates the new indicator math.
2. **Full default-pack workload** — `FeatureRepository.materialize(...)` with
   default packs. This is the workload used by the Stage 1 baseline and now
   contains **19 series** (15 Stage 1 + 4 Stage 2A).

The Stage 1 baseline is **15.354 s for 184,963 bars** with 15 series. It is not
the same workload as the trend-only measurement.

## 2. Measured results (uninstrumented)

| Workload | Bars | Elapsed | Series |
|---|---:|---:|---:|
| Trend-only | 20,000 | **0.116 s** | 4 |
| Full default pack | 20,000 | **2.013 s** | 19 |
| Trend-only | 184,963 | **0.990 s** | 4 |
| Full default pack | 184,963 | **18.806 s** | 19 |
| Stage 1 baseline (reference only) | 184,963 | 15.354 s | 15 |

The full default-pack increase is **+20.2% at 20,000 bars** and **+22.5% at
184,963 bars** versus the Stage 1 baseline. This includes the four additional
trend calculations and the existing Stage 1 work; it is not a claim that the
new indicators alone cost 3.5 s.

## 3. Peak memory (tracemalloc-instrumented)

| Workload | Bars | Elapsed (instrumented) | Peak |
|---|---:|---:|---:|
| Trend-only | 20,000 | 0.467 s | **3.0 MiB** |
| Full default pack | 20,000 | 9.430 s | **12.3 MiB** |
| Trend-only | 184,963 | 4.377 s | **26.8 MiB** |
| Full default pack | 184,963 | 88.267 s | **112.9 MiB** |

For comparison, the Stage 1 full-default instrumented run was 72.665 s and
107.3 MiB peak; Stage 2A adds approximately **5.6 MiB** peak and 4 new series
to that workload. Tracemalloc materially slows execution; use the uninstrumented
table for timing.

## 4. What was optimized / not optimized

- The Stage 1 `prepare()` OHLC frame is reused across all indicator calls in one
  materialization, including the new trend calculations.
- No caching or incremental computation is introduced; Stage 2A excludes both.
- The new HMA is a composition of WMA passes and shares the same close series.
- ATR is still independently requested by volatility and indicator packs.
- TrendView is still independently computed by `MarketStateBuilder` and
  `PhaseView`.
- Full-history series are computed even though only the last 2048 values are
  retained.
- Memory remains dominated by full `FeatureContext` bars and pandas
  intermediate frames.

## 5. Remaining work

- Add paging/windowed materialization for analytics that do not need full-history
  scalars.
- Eliminate the remaining ATR/TrendView duplicate work before claiming a broad
  performance improvement.
- Add a bounded feature cache only when a later stage explicitly authorizes it.
- Re-benchmark all families together after Stage 2 completion.
