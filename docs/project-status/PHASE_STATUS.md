# Phase Status

All phases below use the local working tree as the source of truth. Test counts are
historical phase records except the current full-suite count, which was re-run for this audit.

| Phase | Implementation status | Review / acceptance status | Evidence | What is missing |
|---|---|---|---|---|
| QA baseline and infrastructure | COMPLETED (scoped) | QA assessment completed; **release recommendation: ready with known limitations for research**, not paper/live | `docs/qa/` — 305 checks, 284 pass, 9 fail, 5 blocked, 2 not tested; preview/deploy config; seed bootstrap; provider vault | 15 QA defects were logged. P0 fixed the four execution-critical ones. Other low/medium findings and documentation drift remain. Deployment was not runtime-tested. |
| P0 — Execution Integrity | COMPLETED | Completion gate passed; self-verified | **604 tests**; realised-risk mismatches 0/606 EURUSD and 0/468 GBPUSD; gap ambiguity records actual fill; CORE close-outside transition-only; duplicate timestamps rejected. `docs/p0-execution-integrity/` | Does not cover subsequent indicator/provenance work. No account-currency risk. |
| P1 — Realistic Backtesting | COMPLETED (scoped) | Completion gate passed; self-verified | **628 tests**; 24 P1 tests; cost profiles, independent validation, dataset quality, preflight, gross/net UI. `docs/p1-realistic-backtesting/` | Costs are estimated proxies, not observed bid/ask. No currency P&L, partial exits or portfolio. |
| P2 — Research Management | COMPLETED (implementation) | **Original independent audit verdict: FAIL** | **637 tests**; workspace, variations, experiments, comparisons, Zone Manager, dashboard. `docs/p2-research-management/` | Temporal zone integrity and reproduction defects found by audit; remediated in P2.1. |
| P2.1 — Audit Remediation | COMPLETED | **PASS WITH LEGACY LIMITATION** | **650 tests**; 22 P2-specific tests; zone provenance/import, immutable snapshots, version-pinned reproduction, completion invariant, amendments, file locks, backup/recovery. `docs/p2-research-management/AUDIT_REMEDIATION.md` | Experiments created before P2.1 remain non-reproducible (`SNAPSHOT_MISSING`). Feature provenance is still absent from snapshots. |
| P3.0 — Research Assessment | COMPLETED (documentation only) | Assessment delivered; no implementation | Nine documents under `docs/p3-assessment/`: current state, feature catalogue, analytics, regime, robustness, architecture, roadmap, risks. | Contains pre-P3.1 statements; several “not implemented” lines are now stale. It is a baseline, not current status. |
| P3.1 Stage 1 — Indicator series foundation | COMPLETED | **Provisionally accepted** by the requester; **no independent audit** | **656 tests** at Stage 1 close; `IndicatorSeries`, provenance/versioning, 15 series, bounded 2048-bar window, prefix/as-of tests. `docs/p3-indicator-foundation/` | No cache, no strategy integration, no snapshot persistence. Some duplicate ATR/TrendView work remains. |
| P3.1 Stage 2A — WMA/HMA/DEMA/TEMA | COMPLETED (self-verified) | **Not yet reviewed or formally accepted; no independent audit** | **674 tests** current; 18 Stage 2A tests with independent numerical references; full suite/lint/build PASS. `docs/p3-indicator-foundation/INDICATOR_REFERENCE.md`, `TEST_REPORT.md`, `PERFORMANCE.md` | Remaining families and Stage 2B+ are absent. No cache. No feature snapshot persistence. Stage 2A performance is documented but not a CI gate. |
| P3.1 Stage 2B and later indicator families | NOT STARTED | — | Only the roadmap/catalogue exists | Stochastic, CCI, ROC, Williams %R, Keltner, Donchian, candle/statistical/range primitives, explicit HH/HL/LH/LL and additional families. |
| P3.1 feature caching / incremental computation | NOT STARTED | — | Explicitly excluded from Stage 1 and Stage 2A | No cache, no incremental materialization, no cache invalidation tests. |
| P3.1 feature provenance persistence into experiment snapshots | NOT STARTED | — | `FeatureContext.provenance` exists; `MODEL_VERSIONS` in the workspace has no feature entry | New experiments still snapshot execution/cost/model versions but not feature config hash, pack/method versions or indicator parameters. |
| P3.2 — Strategy performance analytics | PLANNED | — | Roadmap and analytics assessment only | Gross/net attribution, R distributions, monthly/session/long-short breakdowns, rolling metrics, sample-size warnings, UI. |
| P3.3 — Market regime analysis | PLANNED | — | Regime research proposal only | `RegimePack`/`RegimeView`, causal regime axes, availability states, regime-conditioned analytics. |
| P3.4 — Robustness research | PLANNED | — | Robustness assessment only | Parameter grids, trial ledger, walk-forward/out-of-sample splits, multiple-testing metadata, failed-trial preservation. |
| P3.5 — Integration and verification | PLANNED | — | Roadmap only | Feature/regime snapshot fields, analytics/regime UI, E2E workflows, migration and final regression. |

## P3.1 position at audit time

P3.1 is **PARTIALLY COMPLETED** overall:

- **Stage 1** implemented the causal, versioned `IndicatorSeries` foundation and was
  provisionally accepted. It is not independently audited.
- **Stage 2A** added WMA, HMA, DEMA and TEMA with independent reference tests and
  documentation. It is the latest implemented increment and has not yet been reviewed.
- **Stage 2B** and all later indicator families are **NOT STARTED**.
- **Caching/incremental computation** is **NOT STARTED** and was explicitly excluded from
  the implemented stages.
- **Feature provenance persistence into P2.1 snapshots** is **NOT STARTED**. The provenance
  object exists, but it is not written into experiments.
- **P3.2, P3.3, P3.4 and P3.5** are **PLANNED**, not active development.

## Phase evidence notes

### QA baseline

The QA assessment reported a coherent platform but listed execution-layer assumptions as
not trustworthy for paper/live use. Four critical findings were subsequently fixed in P0:
realised-risk sizing, gap/ambiguity fill accounting, repeated CORE `CLOSE_OUTSIDE` signals,
and duplicate entry timestamps. The older QA documents remain useful historical evidence;
they are not a current defect list.

### P0/P1/P2/P2.1

The phase sequence is genuine implementation work, not documentation-only:

- P0 changed sizing and fill semantics and added regression tests.
- P1 added cost profiles, an independent validator, dataset quality and preflight.
- P2 added the workspace/experiment/zone product surface.
- P2.1 remediated the P2 audit's temporal and reproducibility findings. Its verdict is
  **PASS WITH LEGACY LIMITATION**, not a clean pass for all historical experiments.

### P3.0

P3.0 is assessment-only. It did not add code. Its current-state document explicitly describes
the pre-P3.1 repository and is therefore stale about P3.1/Stage 2A.

### P3.1

Stage 1 and Stage 2A both reuse `IndicatorEngine`/`IndicatorProvider` and
`FeatureRepository`; no second engine or backtest path exists. Stage 2A adds four
series-only indicators. Strategies still consume raw bars, so none of this changes live
research outputs yet. There is no independent audit and no acceptance record for Stage 2A.

## Active development

**None.** At audit time P3.1 Stage 2A is complete in the working tree and awaiting review.
The working tree is uncommitted; there is no separate active feature branch in the local
repository state visible here.

## Not blockers

- The absence of a feature cache is not a blocker for correctness; it is a performance gap.
- The absence of regime/robustness modules is not a hidden implementation; those phases are
  explicitly planned.
- No external dependency is preventing the next phase. Docker being unavailable in this
  environment blocks only runtime deployment verification, not source development.
