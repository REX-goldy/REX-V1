# REX — Free Forex Data Provider Research

**Date:** 2026-10-29
**Scope:** EURUSD + GBPUSD historical M1 (derive M5/M15/H1/H4), multi-year, automated, genuinely free, commercial-path aware.
**Method:** official provider documentation and pricing pages, direct endpoint probes, and inspection of the existing REX ingestion code. Every pricing/limit claim below is dated 2026-10-29 and linked in §9.
**Labels:** VERIFIED (read/executed), PARTIALLY VERIFIED (some evidence, entitlement not testable here), ASSUMPTION, UNKNOWN.

---

## 0. Decision in one paragraph

**No provider satisfies “genuinely free + automated + commercially licensed” simultaneously.** Dukascopy is technically excellent and free, but its Terms of Use restrict use to personal, non-commercial purposes and prohibit automated access/database construction. **Recommendation: Twelve Data free tier as the primary integration for 2020→present M1** (official REST API + maintained Python SDK, UTC forex timestamps, 5,000 points/request, 800 requests/day), with **OANDA v20 demo/practice as the fallback and spread-validation source** (M1 back to 2005, bid/ask/mid candles, free demo account). **HistData is the free bulk-history cold-start** (2000→2026 M1, manual ZIPs). Commercializing REX requires either Twelve Data’s business plan (Venture, $499/month as of the pricing page) or a negotiated data license; that cost must be planned, not assumed away.

---

## 1. Existing REX data pipeline — what to reuse

**VERIFIED by source inspection.**

| Component | Current behavior | Reuse for a new provider |
|---|---|---|
| `historical/sources.py` | `HistoricalBarSource` protocol; `DukascopyAdapter` invokes `duka` via subprocess, parses, validates | Implement the same protocol for Twelve Data; no duplicate pipeline |
| `historical/downloader.py` | `HistoricalDownloader` loops yearly partitions, retries, assesses quality, writes storage. Constructs `DukascopyAdapter` by default but accepts `adapter=` | Pass a new adapter; keep retry/partition/quality orchestration |
| `historical/config.py` | Validates config, but **hard-requires `provider == "dukascopy"` and `timeframe == "M1"`** | Generalize provider; keep M1 as the supported source timeframe |
| `historical/storage.py` | Atomic yearly CSV + `.meta.json` (symbol, timeframe, year, dates, provider, bar_count) | Reuse unchanged |
| `historical/parser.py` / `bar_contract.py` | Strict CSV → `Bar`; OHLC validation; UTC wall-time policy; dataset quality report | Reuse unchanged |
| `historical/provider.py` | Local read API over stored partitions | Reuse unchanged |
| `research/free_ohlc/*` | CSV format adapters + deterministic M1→M5/M15/M30/H1/H4/D1 resampler (`fx_open_minutes_v1`) | Reuse resampler for HTF; do not re-download HTF |
| `research/truefx/tick_csv.py` | TrueFX tick parser (research only) | Useful for tick/spread validation, not production |
| `research/yahoo/adapter.py` | Yahoo H1 research adapter (no M1 history) | Not suitable for M1 research |
| `research/free_ohlc/acquire.py` | Downloads a **Kaggle sample** dataset | **Licensing risk**; do not promote to production |

### Conflicts with the stated direction

1. **“Integrate through House of Apps.”** The House of Apps reference available in this environment is a CRM API/SDK, not a market-data provider. It can run/schedule the job, but it cannot supply forex candles. The adapter must live in REX; House of Apps is the orchestration/automation layer. **VERIFIED (reference description); ASSUMPTION about intended role.**
2. **“Genuinely free” vs “commercialize later.”** Free tiers are personal/internal-use licenses, not redistribution licenses. Twelve Data’s Basic plan is explicitly internal, non-display; business use starts at $499/month. Dukascopy is non-commercial by its terms. This is the central trade-off.
3. **Existing Dukascopy automation is legally questionable.** Dukascopy’s Terms prohibit scrapers/robots and database construction without written consent, and limit downloads to personal, non-commercial use. The current `duka` subprocess path is automated access to Dukascopy data. **VERIFIED (terms text); legal interpretation is ASSUMPTION and should be confirmed by counsel before commercial use.**

---

## 2. Ranked shortlist and comparison

| Rank | Provider | Free access | M1 history | API/SDK | Auth | Automation | Licensing | Integration effort |
|---|---|---|---|---|---|---|---|---|
| **1** | **Twelve Data** | Basic $0: 8 req/min, 800/day | Docs say 2020-02-10; **this key's earliest = 2020-04-07** (live); forex intraday multiple years | REST + official Python SDK (`twelvedata-python`) | API key | Yes | Personal/internal on Basic; **commercial requires business plan**; no redistribution | **Low** (S/M) |
| **2** | **OANDA v20** | Free **demo/practice** account; no subscription | Back to **2005** | REST v20; personal access token; no first-party Python SDK (community clients) | Account + token | Yes | API license; redistribution/commercial display needs review | **Low–Medium** |
| **3** | **HistData** | Free manual ZIPs | **2000 → 2026** (EURUSD page verified) | No API; CSV ZIP; FTP/SFTP paid; automatic updates $7/mo | None for manual | **No (manual)**; paid automation | No explicit commercial license found; no warranty; bid-only OHLC | **Medium** (parser + EST→UTC) |
| **4** | **Dukascopy** | Free | Tick → monthly; deep history | No official API; community `duka` | None | Yes (unofficial) | **Personal, non-commercial; no scraping/database** | **Low technically, high legal risk** |
| **5** | **TrueFX** | Free after registration | Tick archives | No API/SDK; manual downloads | Registration | No | Indicative data; licensing unclear | Medium (tick parser; manual) |
| — | MetaTrader 5 | Free with broker demo | Broker-dependent | Python package `MetaTrader5` | Broker account | Windows terminal; poor on Linux servers | Broker-dependent | High |
| — | FXCM public data | Advertised free historically | UNKNOWN | None official; public CDN historically | None | UNKNOWN | UNKNOWN | **Not verifiable here** |

**Notes on the table**

- Twelve Data’s Basic plan is “internal non-display usage”; Grow/Pro/Ultra are personal plans; **Venture ($499/mo) and Enterprise ($1,099/mo)** are the commercial tiers. Prices verified on the pricing pages; annual billing discounts may apply.
- OANDA’s introduction states API accounts require a v20 trading account, with a **free demo** option and historical pricing **dating back to 2005**; M1/M5/M15/M30/H1/H4 are supported granularities. Candles can be requested by **bid, ask, or mid**, which is uniquely useful for spread modeling.
- HistData’s FAQ states the timezone is **EST without daylight-saving adjustments**, bars are **bid-price only**, and volume is removed. This requires an explicit fixed UTC−5 conversion, not `America/New_York`.
- Dukascopy’s terms: use “solely for your own non-commercial use,” no resale/redistribution, no database construction, and no “scraper, robot, bot, spider, data mining … to access, acquire, copy, or monitor any portion of the Website.” This conflicts with an automated research platform.
- FXCM: the official historical-data page returned HTTP 403 (Cloudflare challenge) and the public `candledata.fxcorporate.com` paths tested (EURUSD M1 2019/2020/2024, yearly/weekly variants) returned 404. **UNKNOWN whether the service is retired or merely blocked in this environment.** Do not select it without a direct verification.

---

## 3. Why not Dukascopy (the default should change)

Dukascopy is the best *raw data* value: free, deep, tick-level, no key. It is not the best *platform* choice:

1. **License:** personal/non-commercial only; no redistribution; no database construction. Commercial REX is out of scope without a written agreement.
2. **Automation:** terms prohibit automated acquisition without consent. The existing `duka` subprocess is exactly that.
3. **Maintenance:** `duka==0.2.0` is an old community package that shells out to `python -m duka.main`; the endpoint failed in this sandbox (network or provider change — UNKNOWN). No SLA, no official support.
4. **Causality is fine** (UTC timestamps), but the operational/legal risk is not.

Keep Dukascopy as an optional **personal research** adapter; do not make it the production source.

---

## 4. Recommendation

### Primary: Twelve Data (free Basic for now)

Why:
- Official, documented REST API and a maintained Python SDK.
- API key only; no broker account; simplest “Zerodha-like” onboarding.
- 1-min interval with `start_date`/`end_date`, `timezone=UTC`, `outputsize` up to 5,000.
- 1-min OHLC from 2020-02-10; enough for the 2020–2025 research window; forex intraday spans multiple years.
- Free tier throughput is sufficient: 5 years × 2 pairs ≈ 60–120 requests (5,000 bars ≈ 3.5 days of M1), well inside 800/day; the 8 req/min limit means a full bootstrap takes minutes, not hours.
- Clear commercial upgrade path ($499/mo Venture) instead of an unbounded legal risk.

Limits to plan for:
- No bid/ask; spread must be modeled separately (use OANDA/TrueFX for calibration).
- Free tier is personal/internal, non-display; cannot expose raw data in a commercial UI without a business license.
- Live verification on 2026-10-29: the free key returns 1-min data back to **2020-04-07**; a 2020-02-10 request returns HTTP 400 “No data”. The generic docs’ 2020-02-10 date does not apply to this key. **VERIFIED for this key.**
- Rate limit requires a token bucket and retry/backoff.

### Fallback: OANDA v20 demo/practice

Why:
- Free demo account; M1 back to 2005; documented granularities; bid/ask/mid candles; `complete` flag supports causal handling.
- Better for **spread and execution-assumption calibration** than Twelve Data.
- REST + token is straightforward; rate guidance is generous (100 req/s on a persistent connection).

Risks: account signup; API license/redistribution restrictions; demo account lifecycle; broker-specific prices. Use it as the second source and for cross-validation, not as the only source.

### Free bulk baseline: HistData

Use once to seed 2000–2026 M1 history and to cross-check Twelve Data/OANDA. Manual ZIPs, EST-no-DST, bid-only, no volume. Automating it is a paid feature ($7/mo updates, paid FTP/SFTP), so it does not meet “free unattended” by itself.

### Do not select

- **Dukascopy** for production (licensing/automation).
- **FXCM** until its current access path is verified.
- **MetaTrader 5** as the primary source (Windows terminal, broker-dependent history, poor unattended Linux operation).
- **TrueFX** as primary (manual archives, unclear licensing), but keep it for tick/spread validation.

---

## 5. Integration estimate into REX

**Effort: S/M — roughly 1–2 focused engineering days for the adapter + tests; no strategy or backtest changes.** The existing pipeline was designed for this: a source adapter returns canonical `Bar`s; storage, validation, quality, provider, and resampling are reusable.

### Files/components

| File | Change |
|---|---|
| `historical/sources.py` (or new `historical/providers/twelve_data.py`) | Add `TwelveDataAdapter` implementing `HistoricalBarSource.fetch_bars()` |
| `historical/config.py` | Generalize `provider` beyond `dukascopy`; add `api_key_env`, `base_url`, `max_points_per_request`, `requests_per_minute`; keep M1 supported-timeframe rule |
| `historical/downloader.py` | Build the source from config (`build_source(config)`); keep yearly partitioning, retries, quality report; handle 429/5xx with backoff |
| `config/historical_data.json` | Add Twelve Data provider block; keep Dukascopy block as an alternative profile |
| `.env.example` (new) | `TWELVE_DATA_API_KEY=` placeholder; never commit the real key |
| `tests/test_twelve_data_adapter.py` (new) | Fixture-driven tests: pagination boundaries, UTC parsing, duplicate/missing handling, 429 retry, OHLC validation, symbol mapping |
| `tests/test_historical_downloader.py` | Add a source-selection regression test |
| `README.md` / `PROJECT_CONTEXT.md` | Document provider selection, free-tier limits, and licensing |
| `research/free_ohlc/resampler.py` | Reuse for M1→M5/M15/H1/H4; no changes expected |

No changes to `strategies/`, `backtests/`, `execution/`, or `models/`.

### Implementation notes

- Endpoint: `GET https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=1min&start_date=...&end_date=...&timezone=UTC&outputsize=5000&apikey=...`
- Map `EURUSD` → `EUR/USD`, `GBPUSD` → `GBP/USD`; reject unsupported symbols explicitly.
- Parse `values[].datetime` as UTC; `Bar.timestamp` is naive UTC by REX convention. Do not use local time.
- Page by 5,000 points; ensure the next window starts at `last_timestamp + 1 minute` to avoid boundary duplicates.
- Enforce 8 requests/minute with a monotonic token bucket; retry 429/5xx with exponential backoff; cap retries; fail the partition loudly.
- Store via `HistoricalStorage.write_year`; metadata must include provider, request parameters, fetched_at, row count, and content hash.
- Run `assess_dataset_quality(..., expected_step_minutes=1)` and fail on invalid OHLC/duplicates; report gaps (weekends are expected).
- Determinism: same date range and provider version must produce the same bars; record the adapter version.

### Risks

- Free-plan 1-min history depth/entitlement (verify with a real key before committing).
- 8 req/min throughput for large backfills; acceptable for 2 pairs, plan for more pairs.
- Commercial license cost ($499/mo Venture) once REX charges users.
- Provider API changes; keep the adapter thin and contract-tested.

---

## 6. Verification plan (small EURUSD + GBPUSD download)

**Test window:** 2026-01-05 → 2026-01-16 (two full trading weeks) plus one known high-volatility week; repeat for 2020-02-10 → 2020-02-21 to test the earliest 1-min boundary.

1. **Coverage**
   - Expect ~7,200 M1 bars per full 5-day week per pair (weekends excluded; maintenance gaps allowed).
   - Confirm first/last timestamps and that the requested range is fully covered.
   - Confirm `2020-02-10` returns data and `2020-02-09` does not (documented M1 start).
2. **Timestamp correctness**
   - Request `timezone=UTC`; assert `datetime` strings are UTC and monotonic after parsing.
   - Assert no DST shift: compare a March and a November week; spacing must stay 60 seconds.
3. **Duplicates**
   - Count duplicate `(symbol, timestamp)` across pagination boundaries; must be 0.
4. **Missing candles**
   - Compute expected FX-open minutes with the repo’s `fx_open_minutes_v1` rule; report every gap > 1 minute.
   - Confirm weekend closure is not counted as missing.
5. **OHLC validation**
   - Every bar: `high >= max(open, close)`, `low <= min(open, close)`, `high >= low`, all prices > 0; use `validate_ohlc`.
6. **Cross-provider sanity**
   - Overlap window with OANDA (or HistData) for EURUSD; compare closes; investigate differences > a documented tolerance (e.g. 2 pips) and record them, do not average them away.
7. **HTF derivation**
   - Resample M1 → H1 using `research/free_ohlc/resampler.py`; compare against provider H1 (if available) and check bucket alignment/completeness.
8. **Operational**
   - Force a 429 and verify backoff; kill mid-run and verify idempotent resume; rerun and verify identical output hash.
9. **Acceptance**
   - Zero duplicate timestamps, zero invalid OHLC, no missing open minutes except documented closures, deterministic rerun, manifest written, and a short data-quality report attached to the dataset.

---

## 7. Cost and licensing summary

| Scenario | Twelve Data | OANDA | HistData | Dukascopy |
|---|---|---|---|---|
| Personal/internal research | Free (800/day) | Free demo | Free manual | Free |
| Commercial product | $499/mo Venture (business) | Negotiate API/data license | Unclear; assume permission needed | Written agreement required |
| Redistribution/display | Not on Basic; business add-on/agreement | Not by default | Not stated | Prohibited without consent |
| Automation | Yes | Yes | Paid ($7/mo updates / FTP) | Terms prohibit |

**Do not describe any provider as “completely free” for a commercial REX.** Free access is real for internal research; commercial rights are separate.

---

## 8. What this means for the REX roadmap

1. Integrate Twelve Data now for internal research; keep the key out of git.
2. Use OANDA for a second-source + spread benchmark before claiming cost realism.
3. Build the dataset manifest/provenance at the same time (provider, request params, fetched_at, hash).
4. Keep Dukascopy only as an optional personal adapter; remove it as the default.
5. Revisit commercial data licensing before any paid launch; budget the $499/month business tier or a negotiated license.

---

## 8b. Live verification (2026-10-29, this key)

| Run | Bars | Pages/requests | Duplicates | Invalid OHLC | Gaps > 1 min |
|---|---|---|---|---|---|
| EURUSD M1, 2026-10-15 → 2026-10-29 | 21,389 | 5 | 0 | 0 | 0 |
| GBPUSD M1, 2026-10-15 → 2026-10-29 | 21,390 | 5 | 0 | 0 | 0 |
| EURUSD M1, 2020-04-08 → 2020-04-21 | 14,392 | 3 | 0 | 0 | 64 |
| GBPUSD M1, 2020-04-08 → 2020-04-21 | 14,303 | 3 | 0 | 0 | 77 |

- Pagination is **backward** because the API returns the latest 5,000 points even when
  `order=asc` is requested. Each next page uses `end_date = earliest_bar - 1 minute`.
- The 2020 gaps are weekend closures plus provider minute gaps around the 21:00–23:00 UTC
  rollover; they are recorded, not hidden.
- A full downloader run wrote EURUSD 2026-10-15 → 2026-10-29 to a temp directory:
  **21,391 bars**, `.meta.json` with provider/requested/actual coverage/retrieved_at/
  duplicates/invalid/gaps, and a second run was byte-identical (idempotent).
- M1→HTF via the existing resampler: M5 3,126, M15 1,042, H1 260, H4 67; one incomplete
  final bucket skipped; zero invalid OHLC.
- 2020-02-10 → 2020-02-12 returns HTTP 400 “No data is available on the specified dates”
  after one request (not retried); earliest endpoint reports **2020-04-07 16:54** for EURUSD.

---

## 9. Sources (accessed 2026-10-29)

- Twelve Data pricing (personal): https://twelvedata.com/pricing
- Twelve Data pricing (business): https://twelvedata.com/pricing-business
- Twelve Data docs — time series: https://twelvedata.com/docs#time-series
- Twelve Data support — historical depth (1-min from 2020-02-10): https://support.twelvedata.com/en/articles/5656039-how-to-get-historical-prices
- Twelve Data terms (internal use/no redistribution): https://twelvedata.com/terms
- OANDA v20 introduction (free demo, history to 2005): https://developer.oanda.com/rest-live-v20/introduction/
- OANDA instrument definitions (M1/M5/M15/H1/H4; bid/ask/mid): https://developer.oanda.com/rest-live-v20/instrument-df/
- OANDA best practices (rate guidance): https://developer.oanda.com/rest-live-v20/best-practices/
- HistData download page (2000–2026, M1): https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/eurusd
- HistData FAQ (EST without DST, bid-only, no volume): https://www.histdata.com/f-a-q/
- Dukascopy historical export (free, tick→monthly): https://www.dukascopy.com/swiss/english/marketwatch/historical/
- Dukascopy terms (personal/non-commercial, no scraping/database): https://www.dukascopy.com/swiss/english/legal-pages/terms-of-use/
- TrueFX historical downloads (free registration, tick data): https://www.truefx.com/truefx-historical-downloads-2/
- TrueFX FAQ: https://www.truefx.com/truefx-market-data-faq/
- MetaTrader 5 Python integration: https://www.mql5.com/en/docs/python_metatrader5
- Alpha Vantage premium (FX intraday is premium): https://www.alphavantage.co/premium/ and https://www.alphavantage.co/documentation/#fx-intraday
- TraderMade pricing (7-day trial; business £599/mo): https://tradermade.com/pricing

**Unverified / blocked:** FXCM official historical page (HTTP 403 Cloudflare); `candledata.fxcorporate.com` paths (HTTP 404). Dukascopy end-to-end download failed in this sandbox (network or endpoint; UNKNOWN). TrueFX archive access requires registration and was not exercised.
