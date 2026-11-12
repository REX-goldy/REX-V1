# REX — Security & Configuration QA Report

- **Agent:** Agent 8 (Security & Configuration QA)
- **Date:** 2026-11-03
- **Repository:** `/home/user/workspaces/7de05e41da33`
- **Scope:** credential store, provider-key API, masking/exposure, env fallback,
  provider-error redaction, file permissions, frontend key handling, delivery
  env references, and documented operating-envelope gaps.
- **Result:** **27 PASS · 1 FAIL (low severity) · 1 BLOCKED · 1 NOT TESTED · 1 NOT APPLICABLE**

## Method and safety constraints

- Inspected **tracked files only** for secrets. Real `.env*`, `houseofapps_creds.env`,
  and `data/provider_keys.json` contents were never printed or read into evidence.
- All vault tests used isolated stores via `REX_KEYS_FILE=/tmp/...` and dummy keys
  (`SEC-DUMMY-*`). The final isolated vault was left empty; temp vault directories
  were removed after evidence capture.
- No application code, tests, config, datasets, or existing credentials were modified.
  No provider network request was made and no real API key was used.
- The real `data/provider_keys.json` was verified unchanged by SHA-256 before/after
  (`7f496d2b…bae6b`), without reading its contents.
- HTTP behavior was exercised against a **short-lived ephemeral uvicorn** on spare port
  `16904` with an isolated dummy vault, then stopped. The long-running 16900/16901
  services were not restarted or modified. A production frontend build was produced
  (gitignored output only) for bundle inspection.

## Test matrix

| Test ID | Component | Scenario | Test data | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|---|---|
| SEC-001 | Repository | Tracked secret/credential files | `git ls-files`; `.env.example` | No real credential files tracked; placeholders empty | No `.env*`/store/credential secret file tracked; `.env.example` has one empty var; high-confidence token scan clean | PASS | `sec-001-repo-secret-hygiene.txt` |
| SEC-002 | `server/provider_keys.py` | Empty isolated vault | `REX_KEYS_FILE=<temp>` | Two providers, unconfigured, no file | ids `[twelve_data, dukascopy]`, configured false, source `none`, no file | PASS | `sec-002-empty-vault.txt` |
| SEC-003 | `server/provider_keys.py` | Atomic write, mode, JSON shape, temp cleanup | Dummy key, nested temp path | `0600`, parent created, versioned JSON, no `*.tmp` | file `0600`, parent `0755`, `{version:1,providers}`, zero leftovers | PASS | `sec-003-store-shape.txt` |
| SEC-004 | `server/provider_keys.py` | Failed atomic replace | `os.replace -> OSError` | Error raised, old store intact, temp cleaned | `ProviderKeyStoreError`; JSON unchanged; no `*.tmp` | PASS | `sec-004-atomic-failure.txt` |
| SEC-005 | `server/provider_keys.py` | Corrupt store handling | `{not valid json` | Fail closed, do not wipe | `ProviderKeyStoreError`; file preserved byte-for-byte | PASS | `sec-005-corruption.txt` |
| SEC-006 | `server/provider_keys.py` | Unsupported store version | `version: 99` | Reject | `ProviderKeyStoreError` | PASS | `sec-006-version.txt` |
| SEC-007 | `server/provider_keys.py` | Concurrent access | 40 writes / 8 threads | Serialized, valid JSON, no leftovers | all writes/reads succeeded; valid JSON; zero leftovers | PASS | `sec-007-concurrency.txt` |
| SEC-008 | `server/provider_keys.py` | Key validation | empty, spaces, 513 chars, newline, tab, DEL, non-string | All rejected | All `InvalidProviderKeyError` | PASS | `sec-008-validation.txt` |
| SEC-009 | `server/provider_keys.py` | Hint masking | `abcd`, `abcde`, long key | `<=4` fully masked; otherwise last 4 only | `••••`, `bcde`, `1234`; full value absent | PASS | `sec-009-hints.txt` |
| SEC-010 | `server/main.py` | GET/PUT/DELETE masking | PUT dummy, GET list, DELETE | No full key, no `api_key`, hint last 4 | full key absent; `api_key` absent; hint `1234` | PASS | `sec-010-api-responses.txt`, `sec-010-012-http-responses.txt` |
| SEC-011 | `server/main.py` | API error mapping / no echo | unknown provider; blank/newline/513-char keys | 404 / 400, submitted value not echoed | `404 Unknown provider: 'ghost'`; `400` validation messages contain no key | PASS | `sec-011-api-errors.txt` |
| SEC-012 | `server/main.py` | Store failure response | Corrupt vault | 500 generic, no stack/path/secret | `500 {"detail":"Provider key store error"}` | PASS | `sec-012-store-500.txt`, `sec-010-012-http-responses.txt` |
| SEC-013 | `server/main.py` | CORS behavior | Middleware + live preflight | Wildcard origins, credentials disabled | `Access-Control-Allow-Origin: *`; no allow-credentials header | PASS | `sec-013-cors-config.txt`, `sec-013-cors-http-headers.txt` |
| SEC-014 | `server/provider_keys.py` | Env fallback / stored precedence / delete fallback | Dummy env + dummy stored | environment → stored → environment | exact expected transitions observed | PASS | `sec-014-precedence.txt` |
| SEC-015 | `server/provider_keys.py` | Unknown provider | id `ghost` | `UnknownProviderError` on get/set/delete | all three rejected | PASS | `sec-015-unknown.txt` |
| SEC-016 | `server/research_service.py` | Download key resolution | Stored key + different env value | Use stored key; do not mutate env | `build_source(api_key=<stored>)`; env unchanged | PASS | `sec-016-download-key.txt` |
| SEC-017 | Filesystem / git | Permissions and cleanup | Real store metadata only; temp vaults | Store `0600`, not tracked, no leftovers | real store `0600`; not tracked; zero temp leftovers; real store SHA unchanged | PASS | `sec-017-file-permissions.txt` |
| SEC-018 | `historical/twelve_data.py` | Provider HTTP error redaction | 401 message containing dummy key | No key in exception; `***` substitution | `Twelve Data request failed (HTTP 401): invalid key ***` | PASS | `sec-018-redaction.txt` |
| SEC-019 | `historical/twelve_data.py` | Provider payload error redaction | JSON `code 401` message with dummy key | No key in exception | `... (code 401): bad key ***` | PASS | `sec-019-payload-redaction.txt` |
| SEC-020 | `historical/downloader.py` | Retry logs / final exception | Failing adapter, 2 attempts | Key absent from logs and exceptions | 3 log records; key absent from both | PASS | `sec-020-downloader-logs.txt` |
| SEC-021 | `historical/storage.py` | Dataset metadata | Offline fake Twelve Data fetch | `.meta.json` has provenance, no key | metadata exists; key absent | PASS | `sec-021-metadata.txt` |
| SEC-022 | `server/research_service.py` | UI run artifacts | Offline S008 backtest with stored dummy key | Run JSON contains no key | 1 run written; key absent | PASS | `sec-022-run-artifact.txt` |
| SEC-023 | `server/provider_keys.py` | Isolated vault final state | Delete all providers | `providers == {}` | `{}` | PASS | `sec-023-final-vault.txt` |
| SEC-024 | Frontend | Password input, state clearing, bundle | Source + production bundle | `type=password`, autocomplete off, secret cleared; no app storage/console/dangerous HTML; no secret in bundle | all source checks pass; bundle has 0 dummy keys and 0 token patterns; vendor-only React/TradingView `innerHTML`/`console` internals | PASS | `sec-024-frontend-security.txt` |
| SEC-025 | Delivery config | Env references / public surface | `.appforge/*.json`, compose, Docker | `$VAR` references only; only web public | `TWELVE_DATA_API_KEY` is `$…`/`${…}` reference; web public, api non-public/expose-only | PASS | `sec-025-deploy-env-references.txt` |
| SEC-026 | Documentation | Security gaps recorded | Source docs/config | Gaps documented | 7 accepted gaps documented below | PASS | `sec-026-security-gaps.txt` |
| SEC-027 | Existing tests | Credential/API regression tests | `tests.test_provider_keys`, `tests.test_api_routes` | All pass | 18 tests, `OK` | PASS | `sec-027-targeted-tests.log` |
| SEC-028 | Browser runtime | Live DOM/network inspection in a real browser | Preview UI | Observe no key in DOM/network/storage | Not exercised in a browser; static source + production bundle inspected instead | NOT TESTED | `sec-024-frontend-security.txt` |
| SEC-029 | Provider | Real provider request with a real key | Live Twelve Data | Confirm redaction on live traffic | Forbidden by assignment: no real keys / no provider requests. Offline injection covered instead | BLOCKED | `sec-018-redaction.txt`, `sec-019-payload-redaction.txt` |
| SEC-030 | Auth | Authentication / multi-user isolation | N/A | Enforced | Not implemented by design (local single-user); documented gap | NOT APPLICABLE | `sec-026-security-gaps.txt` |
| SEC-031 | Repository | Credential env file covered by tracked `.gitignore` | `houseofapps_creds.env` | Tracked ignore rule exists | Only `.git/info/exclude:15` covers it; tracked `.gitignore` has no matching rule | **FAIL** | `finding-01-gitignore-houseofapps.txt` |

## Confirmed defect

### FINDING-01 — `houseofapps_creds.env` is ignored only by local `.git/info/exclude` (Low)

- **Repro:** `git check-ignore -v houseofapps_creds.env` → `.git/info/exclude:15:houseofapps_creds.env`
- **Expected:** the tracked `.gitignore` explicitly ignores `houseofapps_creds.env` (or `*.env`) so every checkout is protected.
- **Actual:** only the untracked local exclude covers it. The tracked `.gitignore` rules `.env`, `.env.*`, `data/provider_keys.json` do not match this filename.
- **Impact:** no secret is currently tracked, and `.dockerignore` keeps the file out of build contexts, but a fresh clone or lost local exclude leaves it unignored and easy to `git add` accidentally.
- **Evidence:** `docs/qa/EVIDENCE/security/finding-01-gitignore-houseofapps.txt`
- **Suggested fix (not applied):** add `houseofapps_creds.env` (or `*.env`) to tracked `.gitignore`, and consider `git rm --cached` only if it ever becomes tracked.

No medium- or high-severity security defects were confirmed.

## Security gaps (documented / accepted)

1. **No authentication, authorization, sessions, or per-user isolation** on the API; the UI explicitly says “run this locally.”
2. **Plaintext local store:** provider keys are JSON `api_key` values at `data/provider_keys.json`, protected only by POSIX `0600`.
3. **No encryption at rest** and no KMS/secret-manager integration.
4. **Environment visibility:** `TWELVE_DATA_API_KEY` / `DUKASCOPY_API_KEY` are read from the process environment and are visible to the process/OS and child processes.
5. **Wildcard dev CORS** (`*`) with credentials disabled; acceptable for a local single-user research terminal.
6. **Limited key lifecycle:** no rotation/expiry policy or deletion audit trail beyond `updated_at`.
7. **Local API reachability:** any local process can reach port 16901; deployment keeps the API non-public (`deploy.json`), but local isolation is not enforced.

## Blocked / not tested

- **SEC-029 (BLOCKED):** live provider request with a real key — prohibited by the assignment.
- **SEC-028 (NOT TESTED):** real-browser DOM/network runtime inspection — no browser automation used; source and built bundle were inspected instead.
- **SEC-030 (NOT APPLICABLE):** authentication/multi-user isolation — feature does not exist by design.

## Evidence index

All evidence is under `docs/qa/EVIDENCE/security/`:

- `sec-001-repo-secret-hygiene.txt` — tracked-file secret scan, ignore decisions, placeholder check
- `finding-01-gitignore-houseofapps.txt` — reproducible `.gitignore` gap
- `sec-002…sec-023-*.txt` — isolated vault, masking, precedence, API errors, redaction, artifacts
- `sec-010-012-http-responses.txt` — live HTTP status/body checks (isolated store)
- `sec-013-cors-config.txt`, `sec-013-cors-http-headers.txt`, `sec-013-http-summary.txt`, `sec-013-http-server.log`
- `sec-017-file-permissions.txt` — modes, tracking, real-store SHA unchanged, evidence redaction check
- `sec-024-frontend-security.txt` — input attributes, state clearing, source/bundle scans
- `sec-025-deploy-env-references.txt` — `$VAR` references and public-service surface
- `sec-026-security-gaps.txt` — documented operating-envelope gaps
- `sec-027-targeted-tests.log` — 18 existing credential/API tests, all passing
- `sec-harness-run.log` — consolidated vault harness output
