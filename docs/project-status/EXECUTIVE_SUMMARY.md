# REX Executive Summary

## 1. What REX is

REX is an evidence-focused research terminal for foreign-exchange strategies. It is designed
to make a trading idea testable in a way that can be inspected later: which data was used,
which zones and parameters were active, how a trade was filled, what it cost, how the result
was validated, and whether the experiment can be reproduced.

It is a **research and backtesting platform**. It is not a broker, a live trading system or a
promise of future returns.

## 2. What has been accomplished

- A working FastAPI + React application with eight research pages and 46 backend routes.
- Five stored FX datasets, 559,363 M1 bars, with quality reports and timeframe derivation.
- Three registered strategies; two support simulated trade execution.
- A single causal `BacktestRunner` with fixed-risk sizing, conservative OHLC fills, gap and
  ambiguity handling, R-multiple metrics, trade ledgers and equity curves.
- Cost profiles and gross/net separation, with explicit proxy-cost warnings.
- An independent trade/run validator; all 24 archived run artifacts validate with zero
  arithmetic errors.
- A Strategy Workspace with strategies, variations, experiments, comparisons, immutable
  snapshots and reproduction for newly created experiments.
- A versioned Zone Manager with audited historical imports and temporal integrity rules.
- A server-side provider credential vault with masked hints and environment fallback.
- A P3.1 indicator foundation: 19 causal historical series, including WMA/HMA/DEMA/TEMA,
  with deterministic hashes and tests.
- **674 automated tests passing**, lint passing and a successful frontend production build.

## 3. Current development stage

The last implemented phase is **P3.1 Stage 2A** (trend indicators). It is complete in the
working tree, self-tested and documented, but **not yet independently reviewed or formally
accepted**. The three prior phases are complete for their scoped work, and P2.1 repaired the
main audit findings in research management. P3.1 Stage 2B, feature caching, feature
provenance persistence, P3.2 analytics, P3.3 regime, P3.4 robustness and P3.5 integration
have **not started**. There is no active development task at audit time.

## 4. Strongest existing capabilities

1. **Traceability:** experiments capture dataset hash, zones, strategy configuration, cost
   profile, risk settings and model versions.
2. **Independent validation:** trade arithmetic is re-checked by a separate implementation.
3. **Reproducibility for new experiments:** snapshotted experiments can be re-run with
   version checks; four recorded reproductions match.
4. **Research workflow:** data → strategy configuration → preflight → backtest → validation
   → experiment → comparison → archive.
5. **Honest data behavior:** gaps are surfaced, incomplete buckets are skipped, and volume
   is never fabricated.

## 5. Biggest outstanding challenges

- **No proven edge.** All 24 archived run artifacts currently show negative gross
  expectancy. The strategy set and samples are too small to support a profitability claim.
- **Feature provenance is not yet in experiments.** Feature definitions exist but are not
  pinned in P2.1 snapshots, so feature-dependent reproduction is not complete.
- **Execution realism is limited.** Fills are OHLC-based; costs are proxy estimates; there
  is no observed bid/ask, volume, latency or partial-fill model.
- **Data breadth is thin.** Five 2026 datasets; EURUSD has 10 unexpected gaps / 17 missing
  open minutes; no volume or tick data.
- **Robustness is absent.** No walk-forward, trial ledger or multiple-testing discipline.
- **Operational hardening is incomplete.** No application authentication, wildcard CORS,
  JSON single-process persistence and no verified Docker deployment in this environment.
- **Portfolio/account-currency capability is absent.** Results remain R-multiples.

## 6. Recommended immediate priorities

1. Keep every current strategy labeled **exploratory**, not validated or profitable.
2. Add feature provenance to new experiment snapshots and verify it on reproduction.
3. Obtain independent review of P3.1 Stage 2A before extending the indicator family.
4. Improve execution/data realism and state proxy assumptions explicitly.
5. Build robustness/trial accounting before making any edge claim.
6. Harden authentication/CORS and verify deployment before shared or multi-user use.

## 7. Overall maturity assessment

**Classification: functional quantitative research platform (single-user, research-only).**

Why not a research prototype: the core workflow is implemented end-to-end, tested,
validated, persisted and usable through the UI.

Why not paper-trading-ready: there is no broker/paper execution, no portfolio ledger, no
account-currency P&L and no live risk controls; execution assumptions remain approximate.

Why not production automated trading: there is no live order path, authentication/role
model, operational monitoring, deployment verification or demonstrated edge.

REX has built the research cockpit and the audit trail. It has not yet built the evidence
that a strategy works, or the operational machinery required to trade it.
