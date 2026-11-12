# REX Historical Market Data Validation Report

- **Date (UTC):** 2026-11-03T13:47:54Z
- **Agent:** Agent 4 — Historical Market Data QA
- **Workspace:** `/home/user/workspaces/7de05e41da33`
- **Scope:** `data/historical/{EURUSD,GBPUSD,AUDUSD,USDJPY,USDCAD}/M1/2026.csv` and `.meta.json`
- **Mode:** Read-only audit. No historical dataset, metadata, config, strategy, or application code was modified.
- **Verdict:** 5 datasets inventoried; 75 checks executed, 74 PASS / 1 FAIL / 0 BLOCKED / 0 NOT TESTED.
- **Immutability:** SHA-256 before == after for all 10 dataset/metadata files.
- **Synthetic data:** none used; every check ran against the committed real datasets.


## 1. Method and exact definitions

The audit read the CSV files directly with Python's `csv` module and independently with pandas 3.1.0. It then loaded them through the project parser (`HistoricalDataParser`), resampled with `research.free_ohlc.resampler.resample_bars`, and compared the causal path `core.features.timeframes.aggregate_completed_bars` against the dataset resampler.

Session rule used everywhere: `historical.calendar.is_fx_market_open_minute_utc` — naive UTC minutes, closed all Saturday, Friday from 22:00, and Sunday before 22:00 (weekly closure Friday 22:00 inclusive → Sunday 22:00 exclusive).

Definitions used in the calculations:

- **Gap:** consecutive timestamps whose delta is **greater than 1 minute**. `missing_minutes = duration_minutes - 1`.
- **Expected-open missing:** missing minutes for which `is_fx_market_open_minute_utc` is true.
- **Unexpected gap:** a gap with at least one expected-open missing minute.
- **Closure-only gap:** a gap whose missing minutes are all inside the FX closure window.
- **Crosses closure:** a gap with at least one missing minute inside the closure window (the gap may simultaneously contain open and closed missing minutes).
- **Completeness accounting:** `open_minutes_in_range - open_minutes_before_actual_start - unexpected_missing_open_minutes == actual_bar_count`.
- **Independent OHLC check:** pandas vectorised comparison of `high >= max(open, close)`, `low <= min(open, close)`, `high >= low`, positive prices, and finite values.
- **Independent resampling check:** a separate bucket-floor function and separate FX-open completeness/aggregation implementation, not the resampler helpers.
- **Causal comparison:** `aggregate_completed_bars` at `asof = last M1 timestamp + 1 minute` compared with `resample_bars`; resampler naive-UTC timestamps were made UTC-aware only for comparison.


## 2. Dataset inventory


| Instrument | Provider | Source file | TF | Metadata coverage | Actual first | Actual last | Bar count | Size | Trading dates | Quality | closure_filtered | Raw gaps | Unexpected gaps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EURUSD | twelve_data | data/historical/EURUSD/M1/2026.csv | M1 | 2026-01-01 → 2026-06-30 | 2026-01-01T13:00:00 | 2026-06-30T23:59:00 | 184,963 (ref 184,963) | 9,902,091 B | 155 | PASS | 70564 | 35 | 10 |
| GBPUSD | twelve_data | data/historical/GBPUSD/M1/2026.csv | M1 | 2026-04-01 → 2026-06-30 | 2026-04-01T00:00:00 | 2026-06-30T23:59:00 | 93,600 (ref 93,600) | 5,012,055 B | 78 | PASS | 37432 | 13 | 0 |
| AUDUSD | twelve_data | data/historical/AUDUSD/M1/2026.csv | M1 | 2026-04-01 → 2026-06-30 | 2026-04-01T00:00:00 | 2026-06-30T23:59:00 | 93,600 (ref 93,600) | 5,008,654 B | 78 | PASS | 37432 | 13 | 0 |
| USDJPY | twelve_data | data/historical/USDJPY/M1/2026.csv | M1 | 2026-04-01 → 2026-06-30 | 2026-04-01T00:00:00 | 2026-06-30T23:59:00 | 93,600 (ref 93,600) | 5,761,240 B | 78 | PASS | 37432 | 13 | 0 |
| USDCAD | twelve_data | data/historical/USDCAD/M1/2026.csv | M1 | 2026-04-01 → 2026-06-30 | 2026-04-01T00:00:00 | 2026-06-30T23:59:00 | 93,600 (ref 93,600) | 5,013,265 B | 78 | PASS | 37432 | 13 | 0 |

All five bar counts match the reference counts exactly (EURUSD 184,963; other four 93,600 each). Metadata has no explicit quality-status field; the `Quality` column is derived from zero duplicate/order/malformed/invalid findings, not from a stored status. EURUSD's source-data completeness is separately marked FAIL in Section 5 and Section 11 because it contains 10 unexpected gaps.


## 3. Timestamp and ordering integrity


| Dataset | Rows | Duplicates | Order violations | Malformed | Non-minute deltas | Nonzero seconds | 1-minute deltas | Other deltas (minutes: count) | Status |
|---|---|---|---|---|---|---|---|---|---|
| EURUSD | 184963 | 0 | 0 | 0 | 0 | 0 | 184927 | 2×5, 3×2, 4×2, 2881×25, 2883×1 | PASS |
| GBPUSD | 93600 | 0 | 0 | 0 | 0 | 0 | 93586 | 2881×13 | PASS |
| AUDUSD | 93600 | 0 | 0 | 0 | 0 | 0 | 93586 | 2881×13 | PASS |
| USDJPY | 93600 | 0 | 0 | 0 | 0 | 0 | 93586 | 2881×13 | PASS |
| USDCAD | 93600 | 0 | 0 | 0 | 0 | 0 | 93586 | 2881×13 | PASS |

Strict monotonic ordering holds for every dataset; there are no duplicate timestamps, no out-of-order rows, no malformed timestamps, no sub-minute timestamps, and no seconds/microseconds. Every non-gap delta is exactly 1 minute. The non-1-minute deltas are the audited gaps; for the four Apr–Jun datasets all are the 2,881-minute weekend closure gap. EURUSD additionally has the short intraday gaps listed in Section 5.


## 4. OHLC and volume validity


| Dataset | Invalid bars | high<max(o,c) | low>min(o,c) | high<low | ≤0 prices | Non-finite | Pandas invalid | Pandas non-finite | Pandas ≤0 | Volume blank rows | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EURUSD | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 184,963/184,963 | PASS |
| GBPUSD | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 93,600/93,600 | PASS |
| AUDUSD | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 93,600/93,600 | PASS |
| USDJPY | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 93,600/93,600 | PASS |
| USDCAD | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 93,600/93,600 | PASS |

Primary CSV checks and the independent pandas check agree: **0 invalid bars** in all five datasets (0 high below max(open, close), 0 low above min(open, close), 0 high below low, 0 non-positive or non-finite prices). `meta.json` reports `invalid_bar_count: 0`, which matches.

**Volume:** every `volume` field in all five CSVs is empty. The parser therefore returns `Bar.volume = None` for every row and the resampler returns `volume = None` for every derived bar (summation is not attempted when any contributor is missing). No volume was fabricated. This is a data limitation, not a corruption; see OBS-002.


## 5. Boundary and session handling


No bar in any dataset falls inside the FX closure window. The first and last bars of every dataset are FX-open. Weekend closure gaps are present and expected; only EURUSD has additional unexpected intraday gaps.


| Dataset | Bars in closure | First FX-open | Last FX-open | Raw gaps | Closure-only gaps | Unexpected gaps | Missing open minutes | Missing closed minutes | Status |
|---|---|---|---|---|---|---|---|---|---|
| EURUSD | 0 | True | True | 35 | 25 | 10 | 17 | 74880 | PASS |
| GBPUSD | 0 | True | True | 13 | 13 | 0 | 0 | 37440 | PASS |
| AUDUSD | 0 | True | True | 13 | 13 | 0 | 0 | 37440 | PASS |
| USDJPY | 0 | True | True | 13 | 13 | 0 | 0 | 37440 | PASS |
| USDCAD | 0 | True | True | 13 | 13 | 0 | 0 | 37440 | PASS |

The typical weekend gap is `Fri 21:59 → Sun 22:00`, duration 2,881 minutes: the 2,880 minutes Friday 22:00 through Sunday 21:59 are closed and are not required. EURUSD has 25 such closure-only gaps; the other four datasets have 13 each. EURUSD also has 10 unexpected gaps, exactly matching the README claim.


### 5.1 Every unexpected gap (real data)


| Dataset | Before | After | Duration (min) | Missing minutes | Open-minute count | Closed-minute count | Crosses closure |
|---|---|---|---|---|---|---|---|
| EURUSD | 2026-01-21 01:19:00 | 2026-01-21 01:23:00 | 4 | 3 | 3 | 0 | False |
| EURUSD | 2026-02-06 21:59:00 | 2026-02-08 22:02:00 | 2883 | 2882 | 2 | 2880 | True |
| EURUSD | 2026-02-08 22:28:00 | 2026-02-08 22:30:00 | 2 | 1 | 1 | 0 | False |
| EURUSD | 2026-02-08 22:35:00 | 2026-02-08 22:39:00 | 4 | 3 | 3 | 0 | False |
| EURUSD | 2026-02-08 22:41:00 | 2026-02-08 22:44:00 | 3 | 2 | 2 | 0 | False |
| EURUSD | 2026-02-08 22:46:00 | 2026-02-08 22:48:00 | 2 | 1 | 1 | 0 | False |
| EURUSD | 2026-02-08 22:49:00 | 2026-02-08 22:51:00 | 2 | 1 | 1 | 0 | False |
| EURUSD | 2026-02-08 22:52:00 | 2026-02-08 22:54:00 | 2 | 1 | 1 | 0 | False |
| EURUSD | 2026-02-09 04:49:00 | 2026-02-09 04:51:00 | 2 | 1 | 1 | 0 | False |
| EURUSD | 2026-03-03 18:01:00 | 2026-03-03 18:04:00 | 3 | 2 | 2 | 0 | False |

All 10 unexpected gaps are in EURUSD. Nine are short intraday holes (2–4 minutes) on 2026-01-21, 2026-02-08, 2026-02-09, and 2026-03-03. The tenth (`2026-02-06 21:59 → 2026-02-08 22:02`, 2,883 minutes) crosses the weekend closure: 2,880 closed minutes plus 2 missing FX-open minutes (Sunday 22:00 and 22:01). Total unfilled FX-open time is 17 minutes. The README's `10 unexpected gaps` statement is independently confirmed.

Every unexpected gap was traced through the derived timeframes: all derived missing buckets contain at least one of these 17 source minutes, and no untraceable derived gap exists.


## 6. Metadata and provenance consistency


| Dataset | Provider | symbol/TF/year/provider | Actual start (meta / actual) | Actual end (meta / actual) | Bars (meta / actual) | Duplicates (meta / actual) | Invalid (meta / actual) | Gaps (meta / actual) | All checks | Accounting |
|---|---|---|---|---|---|---|---|---|---|---|
| EURUSD | twelve_data | PASS/PASS/PASS/PASS | 2026-01-01T13:00:00 / 2026-01-01T13:00:00 | 2026-06-30T23:59:00 / 2026-06-30T23:59:00 | 184963 / 184963 | 0 / 0 | 0 / 0 | 35 / 35 | YES | YES |
| GBPUSD | twelve_data | PASS/PASS/PASS/PASS | 2026-04-01T00:00:00 / 2026-04-01T00:00:00 | 2026-06-30T23:59:00 / 2026-06-30T23:59:00 | 93600 / 93600 | 0 / 0 | 0 / 0 | 13 / 13 | YES | YES |
| AUDUSD | twelve_data | PASS/PASS/PASS/PASS | 2026-04-01T00:00:00 / 2026-04-01T00:00:00 | 2026-06-30T23:59:00 / 2026-06-30T23:59:00 | 93600 / 93600 | 0 / 0 | 0 / 0 | 13 / 13 | YES | YES |
| USDJPY | twelve_data | PASS/PASS/PASS/PASS | 2026-04-01T00:00:00 / 2026-04-01T00:00:00 | 2026-06-30T23:59:00 / 2026-06-30T23:59:00 | 93600 / 93600 | 0 / 0 | 0 / 0 | 13 / 13 | YES | YES |
| USDCAD | twelve_data | PASS/PASS/PASS/PASS | 2026-04-01T00:00:00 / 2026-04-01T00:00:00 | 2026-06-30T23:59:00 / 2026-06-30T23:59:00 | 93600 / 93600 | 0 / 0 | 0 / 0 | 13 / 13 | YES | YES |

All recorded metadata fields match the actual files. `start_date`/`end_date` are the requested coverage range; `actual_start_date`/`actual_end_date` are the actual first/last timestamps. EURUSD correctly records an actual start of `2026-01-01T13:00:00` even though coverage starts on `2026-01-01`.

### 6.1 Completeness and `closure_filtered_count` reconciliation


| Dataset | Actual bars | Meta closure_filtered | Theoretical closed minutes | Closed minutes not returned | Open before first bar | Unexpected open missing | Total missing calendar minutes | Implied raw absent | Identity A | Identity B |
|---|---|---|---|---|---|---|---|---|---|---|
| EURUSD | 184963 | 70564 | 74880 | 4316 | 780 | 17 | 75677 | 5113 | YES | YES |
| GBPUSD | 93600 | 37432 | 37440 | 8 | 0 | 0 | 37440 | 8 | YES | YES |
| AUDUSD | 93600 | 37432 | 37440 | 8 | 0 | 0 | 37440 | 8 | YES | YES |
| USDJPY | 93600 | 37432 | 37440 | 8 | 0 | 0 | 37440 | 8 | YES | YES |
| USDCAD | 93600 | 37432 | 37440 | 8 | 0 | 0 | 37440 | 8 | YES | YES |

Both reconciliation identities hold for all five datasets:

- **A (final calendar):** `theoretical_closed + open_before_first + unexpected_open_missing == total_missing_calendar_minutes`.
- **B (provider response):** `closed_not_returned + open_before_first + unexpected_open_missing == implied_raw_absent`, where `implied_raw_absent = calendar_minutes - actual_bars - closure_filtered_count`.

`closure_filtered_count` is the number of closed-window rows actually returned by the provider and then removed; it is not the theoretical number of closed calendar minutes. The difference is exactly accounted for by closed minutes the provider never returned (EURUSD 4,316; other four 8 each). This is an expected provider-coverage nuance, not a metadata mismatch; see OBS-001.


## 7. Storage, parser, and loading consistency


| Dataset | CSV rows | Parsed rows | Value mismatches | Repeat load identical | Quality bars | Quality dup | Quality invalid | Quality gaps | SHA-256 (prefix) | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| EURUSD | 184963 | 184963 | 0 | YES | 184963 | 0 | 0 | 35 | 65cab86789eb8239 | PASS |
| GBPUSD | 93600 | 93600 | 0 | YES | 93600 | 0 | 0 | 13 | 7d1b1d3df6cfbd40 | PASS |
| AUDUSD | 93600 | 93600 | 0 | YES | 93600 | 0 | 0 | 13 | d315a52fd48b2792 | PASS |
| USDJPY | 93600 | 93600 | 0 | YES | 93600 | 0 | 0 | 13 | b252bbc12ac36092 | PASS |
| USDCAD | 93600 | 93600 | 0 | YES | 93600 | 0 | 0 | 13 | b7cc92578d76b341 | PASS |

Each file parsed twice into identical `Bar` lists. Row counts and timestamp/OHLC/volume values match the raw CSV exactly (0 mismatches). `assess_dataset_quality` reproduces the recorded bar counts and raw gap counts for all five datasets. No source modification occurred (Section 10).


## 8. Derived M5/M15/H1/H4 verification


For every instrument and timeframe, the dataset resampler was compared with an independent FX-open bucket aggregator. The independent path reimplemented UTC bucket flooring, required every FX-open M1 minute in the bucket, aggregated `open=first`, `high=max`, `low=min`, `close=last`, and summed volume only when all contributors were non-null.


| Dataset | TF | Emitted | Skipped incomplete | Skipped closed | Misaligned | Invalid OHLC | Containment violations | Independent mismatches | Unexpected derived gaps | Traceable / untraceable | Volume None | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EURUSD | M5 | 36,987 | 9 | 0 | 0 | 0 | 0 | 0 | 6 | 9/0 | 36,987 | PASS |
| EURUSD | M15 | 12,325 | 7 | 0 | 0 | 0 | 0 | 0 | 4 | 7/0 | 12,325 | PASS |
| EURUSD | H1 | 3,079 | 4 | 0 | 0 | 0 | 0 | 0 | 4 | 4/0 | 3,079 | PASS |
| EURUSD | H4 | 792 | 5 | 0 | 0 | 0 | 0 | 0 | 4 | 4/0 | 792 | PASS |
| GBPUSD | M5 | 18,720 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 18,720 | PASS |
| GBPUSD | M15 | 6,240 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 6,240 | PASS |
| GBPUSD | H1 | 1,560 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 1,560 | PASS |
| GBPUSD | H4 | 403 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 403 | PASS |
| AUDUSD | M5 | 18,720 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 18,720 | PASS |
| AUDUSD | M15 | 6,240 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 6,240 | PASS |
| AUDUSD | H1 | 1,560 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 1,560 | PASS |
| AUDUSD | H4 | 403 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 403 | PASS |
| USDJPY | M5 | 18,720 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 18,720 | PASS |
| USDJPY | M15 | 6,240 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 6,240 | PASS |
| USDJPY | H1 | 1,560 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 1,560 | PASS |
| USDJPY | H4 | 403 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 403 | PASS |
| USDCAD | M5 | 18,720 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 18,720 | PASS |
| USDCAD | M15 | 6,240 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 6,240 | PASS |
| USDCAD | H1 | 1,560 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 1,560 | PASS |
| USDCAD | H4 | 403 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/0 | 403 | PASS |

**Structural result:** 20/20 dataset-timeframe combinations pass. Every emitted bucket timestamp is aligned to its UTC boundary, every derived bar has valid OHLC, no bucket contains a timestamp outside `[bucket_start, bucket_start + timeframe)`, no bucket is emitted with a future constituent, and the resampler's emitted counts/skip counters exactly match the independent implementation. Incomplete buckets are skipped; `skipped_closed_buckets` is 0 because no source bars exist in fully closed buckets.

**Gap propagation:** the four Apr–Jun datasets have no derived gaps beyond the normal weekend closure gaps. EURUSD's derived series has 4–6 unexpected gaps per timeframe, and **every** derived missing bucket is traceable to the 17 missing source M1 minutes listed in Section 5.1 (untraceable = 0 everywhere). The resampler is behaving correctly; the EURUSD gaps are upstream source-data holes.

**H4 boundary behavior:** H4 buckets crossing the Friday/Sunday closure (e.g. Friday 20:00 and Sunday 20:00) are emitted by the dataset resampler when all FX-open minutes are present, even though the bucket contains closed minutes. This is the documented `fx_open_minutes_v1` rule, not a future leak.


## 9. Causal feature timeframe comparison


`core.features.timeframes.aggregate_completed_bars` requires every calendar M1 minute of an interval, uses timezone-aware UTC, and emits a bar only when `completion_time <= asof`. It was run at `asof = last M1 timestamp + 1 minute` and compared with `resample_bars`.


| Dataset | TF | Causal bars | Resampler bars | Common | Causal-only | Resampler-only | Resampler-only partial-closure | OHLCV mismatches | Future leaks | As-of stability failures | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EURUSD | M5 | 36987 | 36987 | 36987 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| EURUSD | M15 | 12325 | 12325 | 12325 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| EURUSD | H1 | 3079 | 3079 | 3079 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| EURUSD | H4 | 741 | 792 | 741 | 0 | 51 | 51 | 0 | 0 | 0 | PASS |
| GBPUSD | M5 | 18720 | 18720 | 18720 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| GBPUSD | M15 | 6240 | 6240 | 6240 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| GBPUSD | H1 | 1560 | 1560 | 1560 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| GBPUSD | H4 | 377 | 403 | 377 | 0 | 26 | 26 | 0 | 0 | 0 | PASS |
| AUDUSD | M5 | 18720 | 18720 | 18720 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| AUDUSD | M15 | 6240 | 6240 | 6240 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| AUDUSD | H1 | 1560 | 1560 | 1560 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| AUDUSD | H4 | 377 | 403 | 377 | 0 | 26 | 26 | 0 | 0 | 0 | PASS |
| USDJPY | M5 | 18720 | 18720 | 18720 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| USDJPY | M15 | 6240 | 6240 | 6240 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| USDJPY | H1 | 1560 | 1560 | 1560 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| USDJPY | H4 | 377 | 403 | 377 | 0 | 26 | 26 | 0 | 0 | 0 | PASS |
| USDCAD | M5 | 18720 | 18720 | 18720 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| USDCAD | M15 | 6240 | 6240 | 6240 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| USDCAD | H1 | 1560 | 1560 | 1560 | 0 | 0 | 0 | 0 | 0 | 0 | PASS |
| USDCAD | H4 | 377 | 403 | 377 | 0 | 26 | 26 | 0 | 0 | 0 | PASS |

**Result:** 20/20 combinations pass. On every common bucket the OHLCV values are identical (0 mismatches). There are no causal-only buckets; every resampler-only bucket is a documented partial-closure H4 bucket.

**Intentional differences:** M5/M15/H1 produce identical bar sets because the closure boundaries align with those bucket edges. H4 differs exactly where a bucket contains closed minutes: EURUSD has 51 resampler-only H4 buckets and each of the other four datasets has 26. All are partial-closure buckets (Friday 20:00 and Sunday 20:00 UTC). The resampler emits them from complete FX-open minutes; the causal aggregator requires all 240 calendar minutes and therefore omits them. This is the documented dataset-derivation vs causal-feature difference, not lookahead.

**No future data:** 0 bars violate `completion_time <= asof`; 0 causal bars lack source containment; and recomputation at four earlier as-of cutoffs (first+3 days, mid-series, last timestamp, last+1 minute) reproduced exactly the full causal series filtered by completion time. No future leakage was found.


## 10. Original dataset preservation (SHA-256)


| File | SHA-256 before | SHA-256 after | Unchanged |
|---|---|---|---|
| data/historical/AUDUSD/M1/2026.csv | d315a52fd48b2792a1e2b4b51e02205f9e9517dec62b2eb3181417650119d557 | d315a52fd48b2792a1e2b4b51e02205f9e9517dec62b2eb3181417650119d557 | YES |
| data/historical/AUDUSD/M1/2026.meta.json | 93faedca3bdca3a4ad3e22421fd3efa9ee0b2642f33a508485343c5376230deb | 93faedca3bdca3a4ad3e22421fd3efa9ee0b2642f33a508485343c5376230deb | YES |
| data/historical/EURUSD/M1/2026.csv | 65cab86789eb82393f4d54e130d7cbeb1358db869c40814d52058dc130ec4208 | 65cab86789eb82393f4d54e130d7cbeb1358db869c40814d52058dc130ec4208 | YES |
| data/historical/EURUSD/M1/2026.meta.json | d9cd718493bd4634d0ba597a67074c26fc4d91fad22861d0729e65f25707e2be | d9cd718493bd4634d0ba597a67074c26fc4d91fad22861d0729e65f25707e2be | YES |
| data/historical/GBPUSD/M1/2026.csv | 7d1b1d3df6cfbd40a43eea99034811e9fe9758a1b47d2b596e5b8cad3bb6a62b | 7d1b1d3df6cfbd40a43eea99034811e9fe9758a1b47d2b596e5b8cad3bb6a62b | YES |
| data/historical/GBPUSD/M1/2026.meta.json | b01c8e79a0f97cd72a6111b4c6d9b4c00f21306907619dbb92ccc85d9bd84324 | b01c8e79a0f97cd72a6111b4c6d9b4c00f21306907619dbb92ccc85d9bd84324 | YES |
| data/historical/USDCAD/M1/2026.csv | b7cc92578d76b34151ae3628121758767fc68a2eb47261a50ec3880374a5f55d | b7cc92578d76b34151ae3628121758767fc68a2eb47261a50ec3880374a5f55d | YES |
| data/historical/USDCAD/M1/2026.meta.json | 69f62564e0d6c8dbed5d23df22c61fb94d99f02be3136835ceb9ba9dfab258a3 | 69f62564e0d6c8dbed5d23df22c61fb94d99f02be3136835ceb9ba9dfab258a3 | YES |
| data/historical/USDJPY/M1/2026.csv | b252bbc12ac36092e6f1c8f5c8668074c9e4e948d3a94408f1533e75968d004c | b252bbc12ac36092e6f1c8f5c8668074c9e4e948d3a94408f1533e75968d004c | YES |
| data/historical/USDJPY/M1/2026.meta.json | c3f522e78ed536dcd875ebafde3dc3638a810342ea07aa0f3a8c55ae5e8d4bcc | c3f522e78ed536dcd875ebafde3dc3638a810342ea07aa0f3a8c55ae5e8d4bcc | YES |

`hash_comparison.json` records the same values. All 10 CSV/metadata files are byte-identical before and after the audit. Nothing was written under `data/historical/`; the only new repository content is this report and `docs/qa/EVIDENCE/data/`. `git status --short` showed only `?? docs/qa/`.


## 11. Confirmed findings, defects, and blocked tests


### DEFECT-001 — EURUSD M1 unexpected gaps (confirmed data-quality finding; documented in README)

- **Severity:** Medium for research completeness (small, localized, but causes incomplete HTF buckets to be skipped); Low for parser/resampler correctness, which is unaffected.
- **Repro:** run the gap audit in `commands.log` or inspect `gaps.csv`; filter EURUSD rows with `unexpected=True`.
- **Evidence:** `docs/qa/EVIDENCE/data/gaps.csv`, `gaps.json`, `session_gaps.json`, `resampled_summary.json`.
- **Actual:** 10 unexpected gaps, 17 missing FX-open minutes; 9 intraday holes (2–4 min) and 1 weekend-crossing gap with 2 open minutes missing. Exactly matches README's `10 unexpected gaps`.
- **Impact:** EURUSD M5/M15/H1/H4 skip 9/7/4/5 incomplete buckets respectively; every resulting derived gap is traceable to these source holes.
- **No correction was applied.** Re-acquiring the affected minutes from the provider would be required if complete EURUSD coverage is desired; this report does not modify the dataset.

### OBS-001 — `closure_filtered_count` is provider-returned, not theoretical

- **Severity:** Informational (no inconsistency).
- **Detail:** theoretical closure windows total 74,880 minutes for EURUSD and 37,440 for each Apr–Jun dataset. Metadata records 70,564 / 37,432. The differences (4,316 / 8) are closed minutes the provider never returned; the completeness identity in Section 6.1 still holds exactly.

### OBS-002 — volume is absent in all source CSVs

- **Severity:** Informational data limitation.
- **Detail:** every `volume` field is blank; parsed and derived volumes are `None`. No volume was invented. Any future volume-based research on these files is not supported.

### Confirmed clean areas

- No timestamp, ordering, duplicate, malformed-timestamp, or OHLC validity defect was found.
- No parser count/value mismatch, no non-deterministic load, and no source mutation.
- No resampler alignment, OHLC aggregation, completeness, containment, or lookahead defect was found.
- No causal future-leak or as-of-instability defect was found.

### Blocked / not tested / synthetic

- **Blocked:** none.
- **Not tested:** provider fetch/re-download behavior (network acquisition was out of scope); D1 derivation (not requested); tick data.
- **Synthetic cases:** none; all cases used the committed real CSV files.


## 12. Full test results table


| Test ID | Dataset | Scenario | Test data | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| DATA-001 | EURUSD | Dataset inventory | data/historical/EURUSD/M1/2026.csv; meta=data/historical/EURUSD/M1/2026.meta.json | bar_count=184963, metadata start/end consistent | bar_count=184963, first=2026-01-01T13:00:00, last=2026-06-30T23:59:00, size=9902091B, closure_filtered=70564, raw_gaps=35, unexpected_gaps=10 | PASS | inventory.json |
| DATA-002 | EURUSD | Timestamp/order integrity | 184963 rows | strictly increasing, 0 duplicates/order violations/malformed/non-minute deltas | duplicates=0, order_violations=0, malformed=0, non_minute_deltas=0, seconds_microseconds_nonzero=0, delta_minutes_distribution={1: 184927, 2: 5, 3: 2, 4: 2, 2881: 25, 2883: 1} | PASS | timestamp_integrity.json |
| DATA-003 | EURUSD | OHLC/volume validity | 184963 rows; independent pandas cross-check | 0 invalid bars (high>=max(o,c), low<=min(o,c), high>=low, positive, finite); volume reported | invalid=0 (high<max(o,c)=0, low>min(o,c)=0, high<low=0, nonpositive=0, nonfinite=0); pandas_invalid=0; volume_blank_rows=184963/184963 | PASS | ohlc_validation.json |
| DATA-004 | EURUSD | Session/closure boundaries and gaps | fx_open_minutes_v1 (Fri 22:00-Sun 22:00 UTC closed) | 0 bars inside closure; unexpected gaps <=10 (README); all other gaps closure-only | closed_bars=0, first_open=True, last_open=True, raw_gaps=35, closure_only=25, unexpected=10, open_missing_total=17 | PASS | session_gaps.json; gaps.csv |
| DATA-005 | EURUSD | Source data completeness (unexpected gaps) | fx_open_minutes_v1 gap audit | 0 unexpected gaps that remove FX-open minutes | unexpected_gaps=10, unfilled_open_minutes=17 | FAIL | gaps.csv; session_gaps.json |
| DATA-006 | EURUSD | Metadata/provenance consistency | data/historical/EURUSD/M1/2026.meta.json vs actual CSV | symbol/timeframe/year/provider/coverage/counts match; open-minute completeness reconciles | all_metadata_checks_pass=True, checks={'symbol': True, 'timeframe': True, 'year': True, 'provider_present': True, 'actual_start_date': True, 'actual_end_date': True, 'bar_count': True, 'duplicate_count': True, 'invalid_bar_count': True, 'timestamp_gap_count': True}, expected_present_open_bars=184963, actual_bars=184963, closure_filtered=70564 vs theoretical_closed=74880 | PASS | metadata_comparison.json |
| DATA-007 | EURUSD | Storage/loading consistency | HistoricalDataParser.parse_file two independent loads, 184963 rows | row counts/values match CSV; repeated loads identical; source hash unchanged | parsed_rows=184963, value_mismatches=0, deterministic=True, quality_bar_count=184963, quality_gap_count=35 | PASS | parser_consistency.json |
| DATA-008 | EURUSD | Derived M5 resampling | resample_bars(M1 -> M5) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=36987, independent=36987, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=9, unexpected_derived_gaps=6 (traceable_to_source=9, untraceable=0), volume_none=36987 | PASS | resampled_summary.json |
| DATA-009 | EURUSD | Causal M5 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=36987, resampler=36987, common=36987, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-010 | EURUSD | Derived M15 resampling | resample_bars(M1 -> M15) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=12325, independent=12325, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=7, unexpected_derived_gaps=4 (traceable_to_source=7, untraceable=0), volume_none=12325 | PASS | resampled_summary.json |
| DATA-011 | EURUSD | Causal M15 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=12325, resampler=12325, common=12325, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-012 | EURUSD | Derived H1 resampling | resample_bars(M1 -> H1) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=3079, independent=3079, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=4, unexpected_derived_gaps=4 (traceable_to_source=4, untraceable=0), volume_none=3079 | PASS | resampled_summary.json |
| DATA-013 | EURUSD | Causal H1 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=3079, resampler=3079, common=3079, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-014 | EURUSD | Derived H4 resampling | resample_bars(M1 -> H4) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=792, independent=792, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=5, unexpected_derived_gaps=4 (traceable_to_source=4, untraceable=0), volume_none=792 | PASS | resampled_summary.json |
| DATA-015 | EURUSD | Causal H4 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=741, resampler=792, common=741, causal_only=0 (unexpected=0), resampler_only=51 (partial-closure=51), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-016 | GBPUSD | Dataset inventory | data/historical/GBPUSD/M1/2026.csv; meta=data/historical/GBPUSD/M1/2026.meta.json | bar_count=93600, metadata start/end consistent | bar_count=93600, first=2026-04-01T00:00:00, last=2026-06-30T23:59:00, size=5012055B, closure_filtered=37432, raw_gaps=13, unexpected_gaps=0 | PASS | inventory.json |
| DATA-017 | GBPUSD | Timestamp/order integrity | 93600 rows | strictly increasing, 0 duplicates/order violations/malformed/non-minute deltas | duplicates=0, order_violations=0, malformed=0, non_minute_deltas=0, seconds_microseconds_nonzero=0, delta_minutes_distribution={1: 93586, 2881: 13} | PASS | timestamp_integrity.json |
| DATA-018 | GBPUSD | OHLC/volume validity | 93600 rows; independent pandas cross-check | 0 invalid bars (high>=max(o,c), low<=min(o,c), high>=low, positive, finite); volume reported | invalid=0 (high<max(o,c)=0, low>min(o,c)=0, high<low=0, nonpositive=0, nonfinite=0); pandas_invalid=0; volume_blank_rows=93600/93600 | PASS | ohlc_validation.json |
| DATA-019 | GBPUSD | Session/closure boundaries and gaps | fx_open_minutes_v1 (Fri 22:00-Sun 22:00 UTC closed) | 0 bars inside closure; unexpected gaps =0; all other gaps closure-only | closed_bars=0, first_open=True, last_open=True, raw_gaps=13, closure_only=13, unexpected=0, open_missing_total=0 | PASS | session_gaps.json; gaps.csv |
| DATA-020 | GBPUSD | Source data completeness (unexpected gaps) | fx_open_minutes_v1 gap audit | 0 unexpected gaps that remove FX-open minutes | unexpected_gaps=0, unfilled_open_minutes=0 | PASS | gaps.csv; session_gaps.json |
| DATA-021 | GBPUSD | Metadata/provenance consistency | data/historical/GBPUSD/M1/2026.meta.json vs actual CSV | symbol/timeframe/year/provider/coverage/counts match; open-minute completeness reconciles | all_metadata_checks_pass=True, checks={'symbol': True, 'timeframe': True, 'year': True, 'provider_present': True, 'actual_start_date': True, 'actual_end_date': True, 'bar_count': True, 'duplicate_count': True, 'invalid_bar_count': True, 'timestamp_gap_count': True}, expected_present_open_bars=93600, actual_bars=93600, closure_filtered=37432 vs theoretical_closed=37440 | PASS | metadata_comparison.json |
| DATA-022 | GBPUSD | Storage/loading consistency | HistoricalDataParser.parse_file two independent loads, 93600 rows | row counts/values match CSV; repeated loads identical; source hash unchanged | parsed_rows=93600, value_mismatches=0, deterministic=True, quality_bar_count=93600, quality_gap_count=13 | PASS | parser_consistency.json |
| DATA-023 | GBPUSD | Derived M5 resampling | resample_bars(M1 -> M5) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=18720, independent=18720, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=18720 | PASS | resampled_summary.json |
| DATA-024 | GBPUSD | Causal M5 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=18720, resampler=18720, common=18720, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-025 | GBPUSD | Derived M15 resampling | resample_bars(M1 -> M15) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=6240, independent=6240, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=6240 | PASS | resampled_summary.json |
| DATA-026 | GBPUSD | Causal M15 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=6240, resampler=6240, common=6240, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-027 | GBPUSD | Derived H1 resampling | resample_bars(M1 -> H1) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=1560, independent=1560, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=1560 | PASS | resampled_summary.json |
| DATA-028 | GBPUSD | Causal H1 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=1560, resampler=1560, common=1560, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-029 | GBPUSD | Derived H4 resampling | resample_bars(M1 -> H4) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=403, independent=403, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=403 | PASS | resampled_summary.json |
| DATA-030 | GBPUSD | Causal H4 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=377, resampler=403, common=377, causal_only=0 (unexpected=0), resampler_only=26 (partial-closure=26), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-031 | AUDUSD | Dataset inventory | data/historical/AUDUSD/M1/2026.csv; meta=data/historical/AUDUSD/M1/2026.meta.json | bar_count=93600, metadata start/end consistent | bar_count=93600, first=2026-04-01T00:00:00, last=2026-06-30T23:59:00, size=5008654B, closure_filtered=37432, raw_gaps=13, unexpected_gaps=0 | PASS | inventory.json |
| DATA-032 | AUDUSD | Timestamp/order integrity | 93600 rows | strictly increasing, 0 duplicates/order violations/malformed/non-minute deltas | duplicates=0, order_violations=0, malformed=0, non_minute_deltas=0, seconds_microseconds_nonzero=0, delta_minutes_distribution={1: 93586, 2881: 13} | PASS | timestamp_integrity.json |
| DATA-033 | AUDUSD | OHLC/volume validity | 93600 rows; independent pandas cross-check | 0 invalid bars (high>=max(o,c), low<=min(o,c), high>=low, positive, finite); volume reported | invalid=0 (high<max(o,c)=0, low>min(o,c)=0, high<low=0, nonpositive=0, nonfinite=0); pandas_invalid=0; volume_blank_rows=93600/93600 | PASS | ohlc_validation.json |
| DATA-034 | AUDUSD | Session/closure boundaries and gaps | fx_open_minutes_v1 (Fri 22:00-Sun 22:00 UTC closed) | 0 bars inside closure; unexpected gaps =0; all other gaps closure-only | closed_bars=0, first_open=True, last_open=True, raw_gaps=13, closure_only=13, unexpected=0, open_missing_total=0 | PASS | session_gaps.json; gaps.csv |
| DATA-035 | AUDUSD | Source data completeness (unexpected gaps) | fx_open_minutes_v1 gap audit | 0 unexpected gaps that remove FX-open minutes | unexpected_gaps=0, unfilled_open_minutes=0 | PASS | gaps.csv; session_gaps.json |
| DATA-036 | AUDUSD | Metadata/provenance consistency | data/historical/AUDUSD/M1/2026.meta.json vs actual CSV | symbol/timeframe/year/provider/coverage/counts match; open-minute completeness reconciles | all_metadata_checks_pass=True, checks={'symbol': True, 'timeframe': True, 'year': True, 'provider_present': True, 'actual_start_date': True, 'actual_end_date': True, 'bar_count': True, 'duplicate_count': True, 'invalid_bar_count': True, 'timestamp_gap_count': True}, expected_present_open_bars=93600, actual_bars=93600, closure_filtered=37432 vs theoretical_closed=37440 | PASS | metadata_comparison.json |
| DATA-037 | AUDUSD | Storage/loading consistency | HistoricalDataParser.parse_file two independent loads, 93600 rows | row counts/values match CSV; repeated loads identical; source hash unchanged | parsed_rows=93600, value_mismatches=0, deterministic=True, quality_bar_count=93600, quality_gap_count=13 | PASS | parser_consistency.json |
| DATA-038 | AUDUSD | Derived M5 resampling | resample_bars(M1 -> M5) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=18720, independent=18720, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=18720 | PASS | resampled_summary.json |
| DATA-039 | AUDUSD | Causal M5 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=18720, resampler=18720, common=18720, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-040 | AUDUSD | Derived M15 resampling | resample_bars(M1 -> M15) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=6240, independent=6240, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=6240 | PASS | resampled_summary.json |
| DATA-041 | AUDUSD | Causal M15 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=6240, resampler=6240, common=6240, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-042 | AUDUSD | Derived H1 resampling | resample_bars(M1 -> H1) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=1560, independent=1560, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=1560 | PASS | resampled_summary.json |
| DATA-043 | AUDUSD | Causal H1 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=1560, resampler=1560, common=1560, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-044 | AUDUSD | Derived H4 resampling | resample_bars(M1 -> H4) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=403, independent=403, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=403 | PASS | resampled_summary.json |
| DATA-045 | AUDUSD | Causal H4 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=377, resampler=403, common=377, causal_only=0 (unexpected=0), resampler_only=26 (partial-closure=26), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-046 | USDJPY | Dataset inventory | data/historical/USDJPY/M1/2026.csv; meta=data/historical/USDJPY/M1/2026.meta.json | bar_count=93600, metadata start/end consistent | bar_count=93600, first=2026-04-01T00:00:00, last=2026-06-30T23:59:00, size=5761240B, closure_filtered=37432, raw_gaps=13, unexpected_gaps=0 | PASS | inventory.json |
| DATA-047 | USDJPY | Timestamp/order integrity | 93600 rows | strictly increasing, 0 duplicates/order violations/malformed/non-minute deltas | duplicates=0, order_violations=0, malformed=0, non_minute_deltas=0, seconds_microseconds_nonzero=0, delta_minutes_distribution={1: 93586, 2881: 13} | PASS | timestamp_integrity.json |
| DATA-048 | USDJPY | OHLC/volume validity | 93600 rows; independent pandas cross-check | 0 invalid bars (high>=max(o,c), low<=min(o,c), high>=low, positive, finite); volume reported | invalid=0 (high<max(o,c)=0, low>min(o,c)=0, high<low=0, nonpositive=0, nonfinite=0); pandas_invalid=0; volume_blank_rows=93600/93600 | PASS | ohlc_validation.json |
| DATA-049 | USDJPY | Session/closure boundaries and gaps | fx_open_minutes_v1 (Fri 22:00-Sun 22:00 UTC closed) | 0 bars inside closure; unexpected gaps =0; all other gaps closure-only | closed_bars=0, first_open=True, last_open=True, raw_gaps=13, closure_only=13, unexpected=0, open_missing_total=0 | PASS | session_gaps.json; gaps.csv |
| DATA-050 | USDJPY | Source data completeness (unexpected gaps) | fx_open_minutes_v1 gap audit | 0 unexpected gaps that remove FX-open minutes | unexpected_gaps=0, unfilled_open_minutes=0 | PASS | gaps.csv; session_gaps.json |
| DATA-051 | USDJPY | Metadata/provenance consistency | data/historical/USDJPY/M1/2026.meta.json vs actual CSV | symbol/timeframe/year/provider/coverage/counts match; open-minute completeness reconciles | all_metadata_checks_pass=True, checks={'symbol': True, 'timeframe': True, 'year': True, 'provider_present': True, 'actual_start_date': True, 'actual_end_date': True, 'bar_count': True, 'duplicate_count': True, 'invalid_bar_count': True, 'timestamp_gap_count': True}, expected_present_open_bars=93600, actual_bars=93600, closure_filtered=37432 vs theoretical_closed=37440 | PASS | metadata_comparison.json |
| DATA-052 | USDJPY | Storage/loading consistency | HistoricalDataParser.parse_file two independent loads, 93600 rows | row counts/values match CSV; repeated loads identical; source hash unchanged | parsed_rows=93600, value_mismatches=0, deterministic=True, quality_bar_count=93600, quality_gap_count=13 | PASS | parser_consistency.json |
| DATA-053 | USDJPY | Derived M5 resampling | resample_bars(M1 -> M5) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=18720, independent=18720, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=18720 | PASS | resampled_summary.json |
| DATA-054 | USDJPY | Causal M5 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=18720, resampler=18720, common=18720, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-055 | USDJPY | Derived M15 resampling | resample_bars(M1 -> M15) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=6240, independent=6240, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=6240 | PASS | resampled_summary.json |
| DATA-056 | USDJPY | Causal M15 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=6240, resampler=6240, common=6240, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-057 | USDJPY | Derived H1 resampling | resample_bars(M1 -> H1) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=1560, independent=1560, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=1560 | PASS | resampled_summary.json |
| DATA-058 | USDJPY | Causal H1 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=1560, resampler=1560, common=1560, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-059 | USDJPY | Derived H4 resampling | resample_bars(M1 -> H4) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=403, independent=403, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=403 | PASS | resampled_summary.json |
| DATA-060 | USDJPY | Causal H4 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=377, resampler=403, common=377, causal_only=0 (unexpected=0), resampler_only=26 (partial-closure=26), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-061 | USDCAD | Dataset inventory | data/historical/USDCAD/M1/2026.csv; meta=data/historical/USDCAD/M1/2026.meta.json | bar_count=93600, metadata start/end consistent | bar_count=93600, first=2026-04-01T00:00:00, last=2026-06-30T23:59:00, size=5013265B, closure_filtered=37432, raw_gaps=13, unexpected_gaps=0 | PASS | inventory.json |
| DATA-062 | USDCAD | Timestamp/order integrity | 93600 rows | strictly increasing, 0 duplicates/order violations/malformed/non-minute deltas | duplicates=0, order_violations=0, malformed=0, non_minute_deltas=0, seconds_microseconds_nonzero=0, delta_minutes_distribution={1: 93586, 2881: 13} | PASS | timestamp_integrity.json |
| DATA-063 | USDCAD | OHLC/volume validity | 93600 rows; independent pandas cross-check | 0 invalid bars (high>=max(o,c), low<=min(o,c), high>=low, positive, finite); volume reported | invalid=0 (high<max(o,c)=0, low>min(o,c)=0, high<low=0, nonpositive=0, nonfinite=0); pandas_invalid=0; volume_blank_rows=93600/93600 | PASS | ohlc_validation.json |
| DATA-064 | USDCAD | Session/closure boundaries and gaps | fx_open_minutes_v1 (Fri 22:00-Sun 22:00 UTC closed) | 0 bars inside closure; unexpected gaps =0; all other gaps closure-only | closed_bars=0, first_open=True, last_open=True, raw_gaps=13, closure_only=13, unexpected=0, open_missing_total=0 | PASS | session_gaps.json; gaps.csv |
| DATA-065 | USDCAD | Source data completeness (unexpected gaps) | fx_open_minutes_v1 gap audit | 0 unexpected gaps that remove FX-open minutes | unexpected_gaps=0, unfilled_open_minutes=0 | PASS | gaps.csv; session_gaps.json |
| DATA-066 | USDCAD | Metadata/provenance consistency | data/historical/USDCAD/M1/2026.meta.json vs actual CSV | symbol/timeframe/year/provider/coverage/counts match; open-minute completeness reconciles | all_metadata_checks_pass=True, checks={'symbol': True, 'timeframe': True, 'year': True, 'provider_present': True, 'actual_start_date': True, 'actual_end_date': True, 'bar_count': True, 'duplicate_count': True, 'invalid_bar_count': True, 'timestamp_gap_count': True}, expected_present_open_bars=93600, actual_bars=93600, closure_filtered=37432 vs theoretical_closed=37440 | PASS | metadata_comparison.json |
| DATA-067 | USDCAD | Storage/loading consistency | HistoricalDataParser.parse_file two independent loads, 93600 rows | row counts/values match CSV; repeated loads identical; source hash unchanged | parsed_rows=93600, value_mismatches=0, deterministic=True, quality_bar_count=93600, quality_gap_count=13 | PASS | parser_consistency.json |
| DATA-068 | USDCAD | Derived M5 resampling | resample_bars(M1 -> M5) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=18720, independent=18720, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=18720 | PASS | resampled_summary.json |
| DATA-069 | USDCAD | Causal M5 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=18720, resampler=18720, common=18720, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-070 | USDCAD | Derived M15 resampling | resample_bars(M1 -> M15) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=6240, independent=6240, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=6240 | PASS | resampled_summary.json |
| DATA-071 | USDCAD | Causal M15 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=6240, resampler=6240, common=6240, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-072 | USDCAD | Derived H1 resampling | resample_bars(M1 -> H1) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=1560, independent=1560, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=1560 | PASS | resampled_summary.json |
| DATA-073 | USDCAD | Causal H1 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=1560, resampler=1560, common=1560, causal_only=0 (unexpected=0), resampler_only=0 (partial-closure=0), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |
| DATA-074 | USDCAD | Derived H4 resampling | resample_bars(M1 -> H4) vs independent FX-open aggregation | aligned UTC buckets, valid OHLC, complete buckets only, no containment/future leak, independent match | emitted=403, independent=403, misaligned=0, invalid_ohlc=0, containment=0, independent_mismatches=0, stats_match=True, skipped_incomplete=0, unexpected_derived_gaps=0 (traceable_to_source=0, untraceable=0), volume_none=403 | PASS | resampled_summary.json |
| DATA-075 | USDCAD | Causal H4 vs resampler | aggregate_completed_bars asof=2026-07-01T00:00:00+00:00 vs resample_bars | common buckets identical; no future data; stable under earlier as-of; differences only documented closure/as-of | causal=377, resampler=403, common=377, causal_only=0 (unexpected=0), resampler_only=26 (partial-closure=26), mismatches=0, future_leaks=0, stability_failures=0 | PASS | causal_htf.json |

## 13. Summary


- **Datasets validated:** 5 — EURUSD, GBPUSD, AUDUSD, USDJPY, USDCAD.
- **Checks:** 75 total; 74 PASS, 1 FAIL, 0 BLOCKED, 0 NOT TESTED.
- **Derived resampling:** 20/20 PASS (M5/M15/H1/H4 × 5 instruments).
- **Causal timeframe comparison:** 20/20 PASS.
- **Defects:** 1 confirmed data-quality finding — EURUSD 10 unexpected gaps / 17 missing FX-open minutes (DEFECT-001, already documented in README). No parser, metadata, resampler, causal, or immutability defect.
- **Immutability:** 10/10 files unchanged (SHA-256 before == after).
- **Report:** `docs/qa/DATA_VALIDATION_REPORT.md`
- **Evidence:** `docs/qa/EVIDENCE/data/`
