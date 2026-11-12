# P3 Assessment — Research Analytics and Feature Intelligence

- **Status:** documentation restored after approval
- **Scope:** P3 assessment only; no P3 implementation
- **Repository snapshot:** current working tree on top of `95f8aaa`
- **Source of truth for this directory:** the approved P3 assessment, re-verified against the current repository
- **Implementation status:** P0, P1, P2 and P2.1 are present; P3.1+ is not implemented.

## Purpose

This directory defines the architecture, feature catalogue, analytics scope, regime design,
robustness plan and implementation roadmap for P3. It is a design baseline, not a claim that
the proposed indicators or analytics exist today.

## Documents

| Document | Responsibility |
|---|---|
| [CURRENT_STATE.md](CURRENT_STATE.md) | Verified current implementation inventory, duplicates, caching and data constraints |
| [FEATURE_CATALOGUE.md](FEATURE_CATALOGUE.md) | Indicator/feature formulas, parameters, warm-up, NaN behavior, causality and implementation status |
| [ANALYTICS_ASSESSMENT.md](ANALYTICS_ASSESSMENT.md) | What can be calculated from current runs; R-multiple vs currency/portfolio limits |
| [REGIME_RESEARCH.md](REGIME_RESEARCH.md) | Causal, transparent OHLC regime classification proposal |
| [ROBUSTNESS_ASSESSMENT.md](ROBUSTNESS_ASSESSMENT.md) | Parameter sensitivity, walk-forward/OOS, rolling and multiple-testing requirements |
| [ARCHITECTURE_PROPOSAL.md](ARCHITECTURE_PROPOSAL.md) | Reuse of FeatureRepository/BacktestRunner; versioning, caching, API/UI and testing |
| [P3_ROADMAP.md](P3_ROADMAP.md) | Independently testable P3 phases and acceptance criteria |
| [RISKS_AND_OPEN_QUESTIONS.md](RISKS_AND_OPEN_QUESTIONS.md) | Explicit risks, blockers and open decisions |

## Non-negotiable decisions

- `FeatureRepository` remains the **single feature-materialization architecture**.
- `BacktestRunner` remains the **only backtest execution path**.
- Stored historical data is **OHLC-only**. Volume-dependent features remain unsupported.
- Existing strategies continue to consume raw `Bar` sequences until a separately approved
  strategy-integration phase.
- Indicator/feature configuration, method IDs and implementation versions are prerequisites
  for experiment-level reproducibility.
- No database, ClickHouse, or second analytics pipeline is introduced by P3.
- P4–P6 are out of scope.

## Relationship to prior phases

- P0 execution integrity and P1 costs/validation/preflight are existing capabilities.
- P2/P2.1 strategy workspace, zones, experiment snapshots and reproduction are existing
  capabilities; P3 must integrate with them rather than replace them.
- The original P2 audit remains at
  [../p2-research-management/AUDIT.md](../p2-research-management/AUDIT.md), with remediation at
  [../p2-research-management/AUDIT_REMEDIATION.md](../p2-research-management/AUDIT_REMEDIATION.md).
- P3 implementation proposals are in [P3_ROADMAP.md](P3_ROADMAP.md).

## Executive summary

REX has a strong causal feature kernel and a validated research execution pipeline, but its
analytics layer is thin. The current indicator surface is limited, packs mostly expose latest
scalars, there is no feature cache, and feature provenance is not yet part of experiment
snapshots. The fastest responsible path is to extend the existing provider/repository
architecture, add versioned historical indicator series, and build read-only analytics,
regime and robustness services on top of existing run artifacts.

The most important constraints are: no volume data, no account-currency P&L, no portfolio
accounting, and no confirmation that strategies use `FeatureContext` (they do not).
