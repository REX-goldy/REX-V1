# Priority Gaps and Recommended Actions

Priority meanings:

- **P0** — blocks a responsible decision or a trustworthy research claim.
- **P1** — important integrity, realism or operational gap; should be addressed before
  expanding the product.
- **P2** — important capability enhancement; can follow the P1 work.

No dependency below is invented. There is no external engineering blocker preventing P3.1
Stage 2B or P3.2 from starting. Docker runtime verification and remote data access are
environmental constraints, not product-level blockers.

## Top 10 outstanding items

| # | Gap | What is missing / problematic | Why it matters | Business / research impact | Technical dependency | Priority | Recommended next action |
|---|---|---|---|---|---|---|---|
| 1 | No demonstrated trading edge | Three strategies, small 2026 samples, and **no archived run with positive gross expectancy** (24/24 archived runs negative). The best run is still a loss-making research sample. | A quant platform is only as valuable as the evidence it can produce. Current results do not support a claim of profitability. | Prevents positioning REX as an alpha engine or trading product; supports an “evidence before conviction” research story only. | More data, out-of-sample testing, robustness controls and strategy variation; no code change alone can create edge. | **P0** | Keep all current results labeled exploratory. Require an out-of-sample, cost-aware, multi-regime study before any “validated” status. Do not market current strategies as profitable. |
| 2 | Feature provenance is not persisted | `FeatureContext.provenance` exists with hashes/versions, but P2.1 experiment snapshots contain no feature config hash, pack/method versions or indicator parameters. Stage 2A has no independent acceptance. | A replay can reproduce current execution inputs but not prove which feature definitions existed when a feature-dependent strategy is later introduced. | Undermines the reproducibility promise as soon as strategies consume features. | P3.1 Stage 1/2A provenance; P2.1 snapshot schema; reproduction comparison. | **P1** | Add feature snapshot fields to **new** experiments only; compare them during reproduction; return structured incompatibility; obtain independent review of Stage 2A. |
| 3 | Execution and cost realism | Fills are OHLC assumptions: next-candle open, conservative stop-first inside a bar, no observed bid/ask, no latency/queue or partial fills. Costs are explicit **proxy** estimates; supplied profiles use zero commission/swap. | Small edge can disappear under real spread, slippage and execution constraints. R-multiple results are not account returns. | Net results are sensitivity evidence, not a deployable execution forecast. | Historical bid/ask/tick data or calibrated broker assumptions; execution-model work. | **P1** | Acquire/record bid-ask or calibrated spread data; add execution-assumption scenarios; publish gross/net with explicit proxy labels. Do not claim live-equivalent fills. |
| 4 | Data breadth and quality | Five 2026 datasets; only EURUSD has Jan–Jun coverage. Four pairs cover Apr–Jun only. EURUSD has **10 unexpected gaps / 17 missing FX-open minutes**. No volume, bid, ask or tick data. | Robustness and regime conclusions require multiple years and market states; current data cannot support them. | Limits every strategy conclusion and any claim about durability. | Provider credentials/connectivity, storage and data-quality operations. | **P1** | Backfill multiple years/symbols using the existing adapters; keep gaps explicit; add a research-readiness gate; do not interpolate missing candles or synthesize volume. |
| 5 | Robustness and overfitting controls | No parameter grid, walk-forward, in-sample/out-of-sample enforcement, trial ledger, multiple-testing metadata or failed-trial preservation. | With three strategies and small samples, it is easy to select noise and call it edge. | A positive sample could be a selection artifact; without trial accounting, the research record is incomplete. | P3.1 features, P3.2 analytics, P3.4 design, `BacktestRunner`. | **P1** | Implement P3.4 trial ledger and walk-forward discipline before making strategy claims; record every trial, including failures and invalid runs. |
| 6 | Security and operational readiness | No user authentication/authorization; wildcard CORS; provider keys are server-side and masked but the API is open to any caller who can reach it. JSON stores and file locks assume a single service process. Docker/Compose is untested here. | Shared-preview or multi-user deployment could expose data/provider usage; no role/audit model. | Blocks a hosted or team-facing product; acceptable only as a local/single-user research tool. | Auth/session layer, deployment hardening, process model, DB/migrations if multi-instance. | **P1** | Add authentication and role boundaries before multi-user deployment; restrict CORS in non-dev environments; protect write/credential endpoints; add backup and deployment verification. |
| 7 | Portfolio and account-currency risk | Fixed-risk, single-instrument, R-multiple only. No portfolio heat, correlated exposure, margin, leverage, compounding, currency conversion, equity curve in account currency or risk-of-ruin. | Users cannot answer “what would this do to an account?” or “what happens across simultaneous positions?” | Limits the product to strategy research, not portfolio management or paper trading. | Account/contract metadata, multi-position ledger, FX conversion, portfolio analytics. | **P2** | Keep R-multiple as the research unit; add portfolio simulation as a separately scoped phase with explicit currency/leverage assumptions. |
| 8 | Feature caching and performance | No cache or incremental computation. Stage 2A full default-pack workload: **18.806 s / 112.9 MiB** at 184,963 bars (Stage 1 baseline 15.354 s/107.3 MiB). ATR is computed twice; TrendView is recomputed in two places. | Research iteration is slower and heavier than necessary; the performance trend will worsen as families are added. | Reduces experiment throughput and raises compute cost; not a correctness blocker. | P3.1 feature architecture, cache-key design (data/config/as-of/version), duplicate elimination. | **P2** | Add a bounded cache only with strict keys and invalidation tests; eliminate duplicate ATR/TrendView work; benchmark before/after. |
| 9 | Market-regime and strategy analytics | P3.2 analytics and P3.3 regime are not implemented. No regime-conditioned results, session/monthly attribution, rolling metrics or cost attribution. | Users cannot tell whether a strategy works only in one regime or one session, or whether results are consistent. | Weakens the research narrative and increases overfitting risk. | P3.1 features, P3.2/P3.3 design, read-only run artifacts. | **P2** | After P3.1 review, implement read-only P3.2 analytics first; then causal regime classification with `UNKNOWN` states and no future leakage. |
| 10 | Feature/indicator integration, UI exposure and acceptance | Strategies still consume raw bars. 19 feature series, `MarketState` and automatic-zone research are not exposed in the UI. Stage 2A is self-tested but not independently reviewed. Root README still documents ports 8000/5173. | Capabilities exist but are hard to use or easy to misinterpret; stale docs undermine trust. | Slows researcher adoption and creates avoidable support/onboarding cost. | Product/UI work, strategy integration decision, documentation updates, independent review. | **P2** | Review/accept Stage 2A, fix README/port and P3.0 status drift, expose feature metadata read-only when a research workflow needs it, and treat strategy `FeatureContext` integration as a separately approved behavior change. |

## Critical engineering gaps vs future enhancements

### Critical engineering / research-integrity gaps

1. Feature provenance persistence and Stage 2A acceptance (item 2).
2. Execution/cost realism and data breadth/quality (items 3–4).
3. Robustness/trial accounting (item 5).
4. Security and operational readiness (item 6).
5. The absence of demonstrated edge is a program-level P0 decision risk, not a missing line
   of code (item 1).

### Future enhancements

- Feature cache/incremental computation and duplicate-work removal (item 8).
- Portfolio/account-currency risk (item 7).
- P3.2 analytics and P3.3 regime classification (item 9).
- Feature/indicator UI exposure, strategy integration, documentation polish (item 10).

## What should not be prioritized yet

- A database or ClickHouse migration before feature/portfolio storage needs are evidenced.
- Live broker execution or paper trading before execution realism, security and portfolio
  accounting exist.
- More indicator families before the current feature provenance and strategy-evidence
  questions are settled.
- A large UI expansion for features that no strategy consumes.
