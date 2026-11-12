# Robustness Assessment

## 1. Existing capability

REX can execute a single configuration through the validated `BacktestRunner`. P1 provides
cost profiles and independent validation; P2/P2.1 provides experiment snapshots and
version-pinned reproduction. Existing research scripts contain ad hoc experiment probes, but
there is no supported robustness orchestration service.

Current run artifacts store a single strategy/configuration/date range and an immutable
result. There is no sweep ledger, split protocol or multiple-testing record.

## 2. Required new infrastructure

### Parameter sensitivity

- Input: strategy, variation, parameter ranges, fixed dataset/instrument/timeframe/range,
  cost profile and risk/execution configuration.
- Generate each trial, execute through `BacktestRunner`, and store trial index, parameters,
  result, validation status and failure reason.
- Preserve all trials, including failed/invalid/no-signal runs.
- Do not select parameters using the same data later reported as validation.

### Walk-forward / out-of-sample

- Define explicit in-sample, validation and final holdout splits by time.
- Never leak future bars into a split.
- Record split boundaries and the selected configuration before evaluating holdout.
- Report each split separately, not a pooled metric that hides instability.
- Treat out-of-sample as a separate experiment kind in the P2.1 model.

### Rolling performance

- Compute rolling trade-based R and drawdown by trade count and/or calendar window.
- Report zero/insufficient windows explicitly.
- Do not imply annualized returns without a frequency and currency basis.

### Regime-conditioned performance

- Join each trade only to a causal regime available before entry.
- Require regime/feature version compatibility.
- Report sample counts per regime; suppress conclusions for sparse cells.

### Overfitting and multiple testing

- Store the total number of trials attempted, including failed/invalid trials.
- Record parameter grids and split definitions.
- Use explicit multiple-testing language; do not present the best trial as an unbiased result.
- Prefer held-out evaluation and pre-registered hypotheses.
- Consider correction methods only after defining the family of tests.

## 3. Architecture

- Reuse `BacktestRunner`; no second execution engine.
- Add a read-only orchestration layer that invokes existing runs and records an immutable
  robustness artifact.
- Reuse P2.1 experiment snapshots for configuration, dataset, zone, cost and validation
  provenance.
- Add feature/regime version references once P3.1/P3.3 exist.
- Store failed trials explicitly; a missing trial must not silently disappear.

## 4. Acceptance criteria

1. A parameter grid can be executed and every trial recorded.
2. Each trial has a stable id, configuration snapshot, result reference and status.
3. Walk-forward splits are recorded and future data is excluded from training/selection.
4. Holdout results are separate and cannot be selected retroactively.
5. Rolling metrics are reproducible from trade records.
6. Regime-conditioned metrics only use causal regime labels.
7. Total trial count and failures are visible.
8. P0/P1/P2 behavior and existing runs remain untouched.
9. Full regression, lint, frontend build and evidence pass.

## Related documents

[README](README.md) · [Current state](CURRENT_STATE.md) · [Feature catalogue](FEATURE_CATALOGUE.md) · [Analytics](ANALYTICS_ASSESSMENT.md) · [Regime](REGIME_RESEARCH.md) · [Robustness](ROBUSTNESS_ASSESSMENT.md) · [Architecture](ARCHITECTURE_PROPOSAL.md) · [Roadmap](P3_ROADMAP.md) · [Risks](RISKS_AND_OPEN_QUESTIONS.md)
