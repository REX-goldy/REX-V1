# REX Backend API QA Report

| | |
|---|---|
| Agent | Agent 3 — Backend API QA |
| Date (UTC) | 2026-11-03 (run window 13:35–13:39 UTC) |
| Repository | `/home/user/workspaces/7de05e41da33` |
| Commit under test | `95f8aaa998f1ce1539c65777b5dd10ac063cbd34` |
| Live API | `http://127.0.0.1:16901` (FastAPI 0.162.0, Python 3.11.6, uvicorn 0.54.0) |
| Isolated API (dummy env key) | `http://127.0.0.1:16902` |
| Isolated API (no provider key) | `http://127.0.0.1:16903` |
| Dataset under test | `data/historical/*/M1/2026.csv` (read-only) |
| Evidence | `docs/qa/EVIDENCE/api/` (53 files, ~2.5 MB) |
| Harness | `/tmp/opencode/qa-api/run_tests.py` (temporary, not committed) |

## Executive summary

- **51 / 51 required API tests executed and PASSED** (0 FAIL, 0 BLOCKED in the required matrix).
- **1 confirmed defect**, severity **LOW**: the unsupported-symbol error on `POST /api/downloads` lists only two symbols although the API accepts seven (`D-01`).
- No 5xx responses were produced by any invalid-input scenario; all errors were JSON with an understandable `detail`.
- Dataset counts and first/last timestamps returned by `/api/overview`, `/api/datasets`, `/api/dataset` match the CSV files exactly (EURUSD 184,963; GBPUSD/AUDUSD/USDJPY/USDCAD 93,600 each).
- Valid S008 backtests for EURUSD and GBPUSD returned complete `ui_run_v1` artifacts, and the artifacts were retrievable through `GET /api/runs/{run_id}`.
- Credential handling was exercised only with dummy keys against an isolated temp store; no full key was ever returned, and the real `data/provider_keys.json` remained empty. No paid/provider download was triggered.

## Method and constraints

- Read-only requests were sent to the live API on `16901`.
- All mutating operations (backtests, credential writes) were directed to isolated uvicorn instances using temporary `REX_RUNS_DIR` and `REX_KEYS_FILE`; the real dataset directory was mounted read-only from the instance's perspective (no writes were made to it).
- Instance `16902` used the **dummy** environment key `dummy-env-key-0001` to test env fallback/precedence. Instance `16903` had no provider key to test the missing-credential path.
- No real credentials were read, printed, stored, or used. No `POST /api/downloads` request with valid provider/symbol/date data was sent to a credentialed server, so no paid provider request was made.
- Constraint compliance: application code, tests, config, datasets, and strategy logic were **not modified**; the only workspace additions are `docs/qa/API_TEST_REPORT.md` and `docs/qa/EVIDENCE/api/`.
- The host had a concurrent agent creating its own run artifacts in `research/outputs/ui_runs/` during the window (range 2026-06-01..2026-06-30). Those are **not** products of this QA run; this QA's backtests wrote only to `/tmp/opencode/qa-api/runs_a/`.

## Coverage map

| Requirement | Tests |
|---|---|
| 1. Health, OpenAPI, CORS | API-001 … API-004 |
| 2. Overview, datasets, dataset, frame, range, bars, strategies, runs, run | API-005 … API-014 |
| 3. Valid S008 EURUSD/GBPUSD backtests + artifact retrieval | API-026, API-027, API-028 |
| 4. Invalid requests (dataset/id/traversal/timeframe/limits/dates/strategy/params/zones/empty/no-signal) | API-015 … API-025 |
| 5. Provider settings (masking, PUT/DELETE, unknown, empty/oversized/control, precedence) | API-030 … API-037 |
| 6. Download validation without paid provider | API-038 … API-043 |
| 7. Response consistency (NaN/Infinity, order, counts, errors, leakage) | API-044 … API-047 |
| 8. Safe rate/robustness (concurrency, repetition, large bounded bars) | API-048 … API-050 |

## Detailed test matrix

All statuses were derived from captured HTTP evidence in `docs/qa/EVIDENCE/api/`. `API-002`'s "15 paths" includes the root `/` in addition to the 14 expected API paths.

| Test ID | Endpoint | Scenario | Test data | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| API-001 | `/api/health` | Health endpoint returns ok | GET /api/health | 200 with status=ok and service=rex-research-terminal | status=200 body={"status":"ok","service":"rex-research-terminal"} | **PASS** | `docs/qa/EVIDENCE/api/API-001_health.json` |
| API-002 | `/openapi.json` | OpenAPI document availability and paths | GET /openapi.json | 200, OpenAPI 3.x, all 14 route paths and key methods present | paths=15; openapi=3.1.0; methods include backtests POST and settings PUT+DELETE | **PASS** | `docs/qa/EVIDENCE/api/API-002_openapi.json` |
| API-003 | `OPTIONS /api/overview` | CORS preflight | Origin: https://preview.example.test; ACRM: GET; ACRH: content-type | 200 with allow-origin and GET/content-type allowed | status=200 acao=* methods=DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT, QUERY headers=content-type | **PASS** | `docs/qa/EVIDENCE/api/API-003_cors_preflight.json` |
| API-004 | `GET /api/health` | CORS headers on actual response | Origin header | access-control-allow-origin present, no credentials+wildcard | status=200 acao=* | **PASS** | `docs/qa/EVIDENCE/api/API-004_cors_headers.json` |
| API-005 | `/api/overview` | Overview schema and dataset cross-check | GET /api/overview | 200; 5 datasets with expected counts; EURUSD bounds; 3 strategies; capabilities | 5 datasets: EURUSD 184963, GBPUSD/AUDUSD/USDJPY/USDCAD 93600; strategies CORE_ZONE_BREAKOUT, S002, S008 | **PASS** | `docs/qa/EVIDENCE/api/API-005_overview.json` |
| API-006 | `/api/datasets` | Dataset list vs CSV files | GET /api/datasets | 200; 5 entries; bar_count and first/last timestamps equal CSV contents | EURUSD 184963; others 93600; first/last timestamps match CSV for all 5 | **PASS** | `docs/qa/EVIDENCE/api/API-006_datasets_crosscheck.json` |
| API-007 | `/api/dataset` | Dataset detail EURUSD | dataset_id=EURUSD/M1/2026 | 200; 184963 bars; provider twelve_data; M1..H4 available; metadata | id=EURUSD/M1/2026 bars=184963 provider=twelve_data tf=['M1','M5','M15','H1','H4'] | **PASS** | `docs/qa/EVIDENCE/api/API-007_dataset_detail.json` |
| API-008 | `/api/frame` | Derived timeframes from M1 | timeframe=M5,M15,H1,H4 | 200; derived_from M1; plausible bar counts; derivation warning | M5:36987; M15:12325; H1:3079; H4:792 | **PASS** | `docs/qa/EVIDENCE/api/API-008_frame_derived.json` |
| API-009 | `/api/range` | Valid range summary | EURUSD 2026-03-02..2026-03-06 | 200; valid true; positive bar_count; total_frame_bars 184963 | valid=True bars=7078 gaps=1 unexpected=1 | **PASS** | `docs/qa/EVIDENCE/api/API-009_range_valid.json` |
| API-010 | `/api/bars` | Valid bars window | EURUSD 2026-03-02, limit=100 | 200; <=100 ascending bars; OHLC finite and valid; date matches | n=100 ascending; OHLC valid; all on 2026-03-02 | **PASS** | `docs/qa/EVIDENCE/api/API-010_bars_valid.json` |
| API-011 | `/api/strategies` | Strategy registry | GET /api/strategies | 200; CORE_ZONE_BREAKOUT/S002/S008 with correct flags and S008 params | ids=['CORE_ZONE_BREAKOUT','S002','S008']; flags and params correct | **PASS** | `docs/qa/EVIDENCE/api/API-011_strategies.json` |
| API-012 | `/api/runs` | Runs list schema and ordering | limit=25 and limit=1 | 200; list schema; created_at desc; limit honored | n=5, sorted desc, limit=1 returns one | **PASS** | `docs/qa/EVIDENCE/api/API-012_runs_list.json` |
| API-013 | `/api/runs/{run_id}` | Existing run schema | first run id from /api/runs | 200; ui_run_v1; full schema; reconciliation difference 0 | ui_run_v1; full schema; reconciliation difference 0 | **PASS** | `docs/qa/EVIDENCE/api/API-013_run_detail.json` |
| API-014 | `/api/runs/{run_id}` | Unknown/invalid run id | does-not-exist_123; bad!id | 404 with Run not found / Invalid run id | unknown=404 {"detail":"Run not found"}; invalid=404 {"detail":"Invalid run id"} | **PASS** | `docs/qa/EVIDENCE/api/API-014_run_invalid.json` |
| API-015 | `/api/dataset\|frame\|range\|bars` | Unknown dataset | dataset_id=NOPE/M1/2026 on 4 read endpoints | 404 Dataset not found, not 5xx | 404 dataset-not-found detail on all four | **PASS** | `docs/qa/EVIDENCE/api/API-015_unknown_dataset.json` |
| API-016 | `/api/dataset` | Malformed id / path traversal | 2 parts, extra parts, ../, non-numeric year, absent year, encoded ../ | 4xx each; no file contents leaked | all 404 with specific messages; no file contents leaked | **PASS** | `docs/qa/EVIDENCE/api/API-016_malformed_dataset.json` |
| API-017 | `/api/dataset\|bars\|backtests` | Unsupported timeframe | timeframe=M2 | 400 with allowed-timeframe message on all three | dataset=400 bars=400 backtest=400, each listing M1/M5/M15/H1/H4 | **PASS** | `docs/qa/EVIDENCE/api/API-017_unsupported_timeframe.json` |
| API-018 | `/api/bars\|runs` | Limit boundaries | bars 0/5001/-1 and 1; runs 0/101 | 422 for out-of-range, 200 for limit=1 | bars:0=422; bars:5001=422; bars:-1=422; bars:1=200/n=1; runs:0=422; runs:101=422 | **PASS** | `docs/qa/EVIDENCE/api/API-018_limit_boundaries.json` |
| API-019 | `/api/bars\|backtests` | Invalid dates | start>end; malformed date | 400 for start>end, 422 for malformed date | bars>end=400; bars malformed=422; backtest>end=400; backtest malformed=422 | **PASS** | `docs/qa/EVIDENCE/api/API-019_invalid_dates.json` |
| API-020 | `/api/range` | Invalid range dates | start>end; out-of-coverage dates | No 5xx; 200 with valid=false and understandable error (documented contract) | 200 valid=False with "Start date is after the end date…"; coverage error also reported in-body | **PASS** | `docs/qa/EVIDENCE/api/API-020_range_invalid_dates.json` |
| API-021 | `/api/backtests` | Unknown strategy | strategy_id=NOPE | 400 with not-exposed detail | status=400 "Strategy 'NOPE' is not exposed in the UI" | **PASS** | `docs/qa/EVIDENCE/api/API-021_unknown_strategy.json` |
| API-022 | `/api/backtests` | Invalid strategy parameters | lookback 1/abc/true, foo, min_wick_ratio 1.5, tolerance -0.1 | 400 with parameter-specific detail | all six cases 400 with precise messages | **PASS** | `docs/qa/EVIDENCE/api/API-022_invalid_parameters.json` |
| API-023 | `/api/backtests` | Zone-based strategy without zone config | AUDUSD + S002 | 400 No zone book is configured for AUDUSD | status=400 "No zone book is configured for AUDUSD in config/zones.json" | **PASS** | `docs/qa/EVIDENCE/api/API-023_missing_zone_book.json` |
| API-024 | `/api/backtests` | Range outside coverage | EURUSD 2026-07-01..2026-07-02 | 400 with after-the-last-available-bar detail | status=400 "End date 2026-07-02 is after the last available M1 bar (2026-06-30)." | **PASS** | `docs/qa/EVIDENCE/api/API-024_empty_range.json` |
| API-025 | `/api/backtests` | Valid range with zero signals | EURUSD weekend 2026-01-03..2026-01-04, S008 defaults | 200; zero signals/trades; profit_factor null; finite JSON | status=200; total_signals=0, total_trades=0, profit_factor=null, empty trades/equity | **PASS** | `docs/qa/EVIDENCE/api/API-025_no_signal_range.json` |
| API-026 | `/api/backtests` | Valid S008 EURUSD backtest | EURUSD 2026-03-02..2026-03-06; lookback 10; R=2 | 200 full run schema; finite metrics; reconciliation 0; warnings; artifact saved | 200; bars=7078; 51 signals/51 trades; win_rate 35.29%; PF 1.0909; reconciliation 0; warning count matches | **PASS** | `docs/qa/EVIDENCE/api/API-026_bt_eurusd.json` |
| API-027 | `/api/backtests` | Valid S008 GBPUSD backtest | GBPUSD 2026-05-01..2026-05-08 | 200 full run schema; finite metrics; reconciliation 0; artifact saved | 200; bars=8520; 229 signals/218 trades; win_rate 21.10%; PF 0.5099; reconciliation 0 | **PASS** | `docs/qa/EVIDENCE/api/API-027_bt_gbpusd.json` |
| API-028 | `/api/runs/{run_id}` | Backtest artifact retrieval | GET the EURUSD run id; also list + disk file | 200; identical metrics/trades; listed; temp-run file exists | 200 identical payload; listed in /api/runs; file exists in temp runs dir | **PASS** | `docs/qa/EVIDENCE/api/API-028_run_artifact.json` |
| API-029 | `/api/backtests` | Backtest numeric boundaries | r_multiple 0/101; risk_fraction 0/0.2; equity 0/-5 | 422 for each Pydantic violation | all six 422 | **PASS** | `docs/qa/EVIDENCE/api/API-029_bt_boundaries.json` |
| API-030 | `/api/settings/providers` | Masked provider status, env fallback | GET on isolated store with dummy env key | 200; two providers; twelve_data source=environment hint=0001; no api_key | 200; twelve_data configured/source=environment/hint=0001; dukascopy source=none; no api_key | **PASS** | `docs/qa/EVIDENCE/api/API-030_provider_get_masked.json` |
| API-031 | `/api/settings/providers/{id}` | Store dummy key and mask it | PUT twelve_data dummy-stored-key-9999 | 200 source=stored hint=9999; full key absent; store mode 0600 | 200 source=stored hint=9999; full key absent; store mode 0o600 | **PASS** | `docs/qa/EVIDENCE/api/API-031_provider_put.json` |
| API-032 | `/api/settings/providers/{id}` | Delete stored key, env fallback restored | GET then DELETE twelve_data; DELETE again | 200; source falls back to environment; store entry removed; idempotent | delete=200 source=environment hint=0001; store entry removed; second delete=200 | **PASS** | `docs/qa/EVIDENCE/api/API-032_provider_delete.json` |
| API-033 | `/api/settings/providers/{id}` | Unknown provider | PUT and DELETE /api/settings/providers/nope | 404 Unknown provider on both | PUT=404, DELETE=404, "Unknown provider: 'nope'" | **PASS** | `docs/qa/EVIDENCE/api/API-033_provider_unknown.json` |
| API-034 | `/api/settings/providers/{id}` | Empty/whitespace key | PUT api_key='' and '   ' | 400 cannot be empty | both 400 "API key cannot be empty" | **PASS** | `docs/qa/EVIDENCE/api/API-034_provider_empty.json` |
| API-035 | `/api/settings/providers/{id}` | Oversized/boundary key | PUT 513 x's then 512 b's | 400 >512; 512 accepted and masked; cleanup delete | 513=400 "…longer than 512…"; 512=200 hint=bbbb; cleanup=200 | **PASS** | `docs/qa/EVIDENCE/api/API-035_provider_oversized.json` |
| API-036 | `/api/settings/providers/{id}` | Control characters in key | newline, NUL, tab, DEL | 400 control-character detail | all four 400 "…cannot contain control characters or newlines" | **PASS** | `docs/qa/EVIDENCE/api/API-036_provider_control.json` |
| API-037 | `/api/settings/providers/{id}` | Stored vs environment precedence | env -> PUT stored -> GET -> DELETE -> GET | stored overrides env; delete reverts to env; no full key echoed | env->stored(2222)->env(0001); no full key echoed | **PASS** | `docs/qa/EVIDENCE/api/API-037_provider_precedence.json` |
| API-038 | `/api/downloads` | Unsupported provider | provider=bogus | 422 validation pattern error | 422 string_pattern_mismatch on body.provider | **PASS** | `docs/qa/EVIDENCE/api/API-038_download_invalid_provider.json` |
| API-039 | `/api/downloads` | Unsupported symbol | symbol=XXXYYY, dukascopy | 400 before any provider call | 400 "UI downloads currently support EURUSD and GBPUSD" (see D-01) | **PASS** | `docs/qa/EVIDENCE/api/API-039_download_invalid_symbol.json` |
| API-040 | `/api/downloads` | Unsupported download timeframe | timeframe=M5 | 400 M1 only | 400 "UI downloads currently support M1 only" | **PASS** | `docs/qa/EVIDENCE/api/API-040_download_invalid_timeframe.json` |
| API-041 | `/api/downloads` | Invalid download dates/range | start>end; >31 days; future end | 400 with specific detail each | start>end=400; >31d=400; future=400 with specific messages | **PASS** | `docs/qa/EVIDENCE/api/API-041_download_invalid_dates.json` |
| API-042 | `/api/downloads` | Provider provenance conflict | dukascopy over twelve_data EURUSD 2026 partition | 400 written by twelve_data, not dukascopy | 400 "Existing partition 2026.csv was written by twelve_data, not dukascopy…" | **PASS** | `docs/qa/EVIDENCE/api/API-042_download_provenance.json` |
| API-043 | `/api/downloads` | Missing provider credential | twelve_data on isolated no-key instance | 503 not configured; fast rejection, no network | 503 "Twelve Data API key is not configured…"; 3.5 ms, no network | **PASS** | `docs/qa/EVIDENCE/api/API-043_download_missing_key.json` |
| API-044 | `multiple` | No NaN/Infinity values | overview, datasets, detail, range, bars, strategies, runs, run, backtests, no-signal | All floats finite; no NaN/Infinity tokens | 11 payloads scanned; all finite; no NaN/Infinity tokens | **PASS** | `docs/qa/EVIDENCE/api/API-044_non_finite.json` |
| API-045 | `/api/backtests + /api/bars` | Timestamp/order/count consistency | EURUSD/GBPUSD runs; 100 bars | ascending orders; signal/trade/reconciliation counts consistent; finite | bars ascending; trade/equity/distribution order + counts consistent | **PASS** | `docs/qa/EVIDENCE/api/API-045_consistency.json` |
| API-046 | `multiple` | Error content type and detail | all captured 4xx/5xx samples (57 samples) | application/json with detail string/list | all 57 samples JSON with `detail`; 422s use structured list | **PASS** | `docs/qa/EVIDENCE/api/API-046_error_shape.json` |
| API-047 | `multiple` | Sensitive data leakage | provider views + overview + backtests | no api_key fields; hints <=4 chars; dummy secrets never echoed | 13 provider views clean; hints ≤4; dummy values never echoed | **PASS** | `docs/qa/EVIDENCE/api/API-047_sensitive.json` |
| API-048 | `GET health/strategies/bars/overview` | Concurrent reads | 44 requests, 12 workers | all 200; stable per-endpoint bodies | 44/44 200 in 270 ms; bodies stable (overview compared excluding `generated_at`) | **PASS** | `docs/qa/EVIDENCE/api/API-048_concurrency.json` |
| API-049 | `GET health/runs` | Repeated requests | 50x health; 20x runs | all 200; consistent bodies | 50/50 and 20/20 200; 1 distinct runs body | **PASS** | `docs/qa/EVIDENCE/api/API-049_repeated.json` |
| API-050 | `/api/bars` | Large bounded bars request | limit=5000 | 200; exactly 5000 ascending finite bars; <2MB | n=5000; 467,660 bytes; 35 ms; ascending | **PASS** | `docs/qa/EVIDENCE/api/API-050_large_bars.json` |
| API-051 | `/api/backtests` | Zone-based S002 backtest | EURUSD 2026-03-02..2026-03-06 | 200 full schema; finite metrics; reconciliation 0 | 200; 322 signals/143 trades; PF 0.9093; reconciliation 0 | **PASS** | `docs/qa/EVIDENCE/api/API-051_bt_s002.json` |

## Confirmed defects

### D-01 — Unsupported download symbol message lists only 2 of 7 accepted symbols (LOW)

- **Severity:** LOW (misleading error message; no functional or data impact).
- **Reproduction:**
  ```bash
  curl -s -X POST http://127.0.0.1:16901/api/downloads \
    -H 'Content-Type: application/json' \
    -d '{"provider":"dukascopy","symbol":"XXXYYY","timeframe":"M1","start_date":"2025-01-01","end_date":"2025-01-02"}'
  # -> 400 {"detail":"UI downloads currently support EURUSD and GBPUSD"}
  ```
- **Expected:** The message should reflect the actual accepted set
  (`EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, NZDUSD, USDCHF`) or avoid enumerating symbols.
- **Actual:** `UI downloads currently support EURUSD and GBPUSD` while
  `server/research_service.py:53-61` defines seven `DOWNLOAD_SYMBOLS` and the
  validation at `server/research_service.py:1022-1023` accepts all seven.
- **Evidence:** `docs/qa/EVIDENCE/api/API-039_download_invalid_symbol.json`
  (HTTP 400, exact body captured); code references `server/research_service.py:53-61`, `server/research_service.py:1022-1023`.
- **Confirmation:** Reproduced in the executed run; status code and body captured.

No other defects were confirmed. All required invalid-input tests returned the intended 4xx class (or the documented 200-with-`valid=false` range contract) and no 5xx.

## Observations and non-defects

- **O-01 (range validation contract):** `GET /api/range` returns **200** with
  `valid=false` and an `error` string for `start > end` or out-of-coverage dates,
  unlike `/api/bars` and `/api/backtests`, which return 400. This is consistent
  with the endpoint being a range-validation summary and produced no 5xx; recorded
  as documented behavior rather than a defect. Evidence: `API-020`.
- **O-02 (live env fallback active):** The live instance reports
  `capabilities.twelve_data=true` while `data/provider_keys.json` is empty, i.e. an
  environment fallback key is present. Per instructions, this QA never sent a valid
  credentialed download; the 503 path was tested on the isolated no-key instance.
- **O-03 (credential endpoints are unauthenticated):** `/api/settings/providers` is
  writable without authentication and CORS allows any origin. This matches the
  local research-terminal design and was not treated as a defect, but it should be
  protected before exposing the API beyond a trusted local/preview environment.
- **O-04 (concurrent artifacts):** During this run another agent created four
  `research/outputs/ui_runs/*.json` artifacts (EURUSD 2026-06-01..2026-06-30).
  They are not products of this QA run; this QA's runs are under
  `/tmp/opencode/qa-api/runs_a/`. Existing artifacts were preserved.
- **O-05 (non-finite values):** `profit_factor` is `null` when there are no losses
  (and for zero-trade runs), which is valid JSON and was not counted as NaN.

## Blocked / not tested

| Item | Status | Reason |
|---|---|---|
| Successful real provider download (`twelve_data` / `dukascopy`) | BLOCKED | Would require real credentials and incur paid provider requests; explicitly prohibited. |
| `POST /api/downloads` 409 "download already running" | NOT TESTED | Would require an in-flight real download; not safely reproducible without provider calls. |
| Corrupt credential-store handling (500 path) | NOT TESTED | Outside the required matrix; would require deliberately corrupting the isolated store. |
| Malformed/corrupt dataset CSV parse handling | NOT TESTED | Would require modifying datasets, which is prohibited. |
| `trades_truncated` for >2000 trades | NOT TESTED | Not required; would require a much larger in-memory backtest. |
| Higher-timeframe derivation from non-M1 storage | NOT APPLICABLE | All supplied datasets are stored as M1. |

## Reproduction

The exact harness is `/tmp/opencode/qa-api/run_tests.py`; it writes the evidence
files listed above. The isolated instances were started as follows (dummy key only
for instance 16902; no key for 16903):

```bash
cd /home/user/workspaces/7de05e41da33

REX_DATA_DIR=$PWD/data/historical \
REX_RUNS_DIR=/tmp/opencode/qa-api/runs_a \
REX_KEYS_FILE=/tmp/opencode/qa-api/keys_a.json \
TWELVE_DATA_API_KEY=dummy-env-key-0001 \
setsid nohup python3 -m uvicorn server.main:app --host 0.0.0.0 --port 16902 \
  >/tmp/opencode/qa-api/server_a.log 2>&1 &

env -u TWELVE_DATA_API_KEY \
REX_DATA_DIR=$PWD/data/historical \
REX_RUNS_DIR=/tmp/opencode/qa-api/runs_b \
REX_KEYS_FILE=/tmp/opencode/qa-api/keys_b.json \
setsid nohup python3 -m uvicorn server.main:app --host 0.0.0.0 --port 16903 \
  >/tmp/opencode/qa-api/server_b.log 2>&1 &

python3 /tmp/opencode/qa-api/run_tests.py
```

The isolated instances were stopped after evidence capture. The real
`data/provider_keys.json` was verified unchanged (empty `providers` object).

## Evidence manifest

- `docs/qa/EVIDENCE/api/_environment.json` — date, commit, instances, dataset expectations.
- `docs/qa/EVIDENCE/api/_summary.json` — machine-readable 51-result summary.
- `docs/qa/EVIDENCE/api/API-001_*.json` … `API-051_*.json` — per-test raw request/response,
  assertions, HTTP codes, durations, and redacted request bodies (credential write
  bodies show `"api_key": "<redacted>"`).
- Error samples referenced by API-046 are captured across `API-014` … `API-043`
  (57 samples, all JSON with `detail`).

## Conclusion

The REX backend API meets the required behavior for the tested matrix: health,
OpenAPI, CORS, dataset/strategy/run reads, valid and invalid backtests, credential
masking/precedence, download validation, response consistency, and safe robustness
checks. No 5xx, NaN/Infinity, secret leakage, path traversal, or artifact-retrieval
failures were observed. The only confirmed issue is the low-severity unsupported-symbol
message (`D-01`).
