import { useEffect, useMemo, useState } from "react";
import { GitCompareArrows, RefreshCw } from "lucide-react";
import { api, p1Api } from "../api";
import type { RunDetail, RunSummary, RunValidation } from "../types";
import { Button } from "../components/Button";
import { DataTable, type Column } from "../components/DataTable";
import { HelpLink } from "../components/HelpLink";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  Panel,
  StatusPill,
} from "../components/Primitives";
import {
  formatDateTime,
  formatDecimal,
  formatInteger,
  formatPercent,
  formatR,
} from "../lib/format";

function metricRow(
  label: string,
  a: RunSummary | undefined,
  b: RunSummary | undefined,
  render: (run: RunSummary) => string,
) {
  return (
    <div className="detail-row" key={label}>
      <span className="detail-key">{label}</span>
      <span className="detail-value">
        {a ? render(a) : "—"} <span className="faint">/</span> {b ? render(b) : "—"}
      </span>
    </div>
  );
}

export function RunsPage({
  refreshKey,
  onOpenHelp,
}: {
  refreshKey: number;
  onOpenHelp: (article: string) => void;
}) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [validation, setValidation] = useState<RunValidation | null>(null);
  const [detailError, setDetailError] = useState("");
  const [compareA, setCompareA] = useState("");
  const [compareB, setCompareB] = useState("");

  const load = () => {
    setLoading(true);
    api
      .runs(50)
      .then((data) => {
        setRuns(data);
        setError("");
        setCompareA((current) => current || data[0]?.id || "");
        setCompareB((current) => current || data[1]?.id || data[0]?.id || "");
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, [refreshKey]);

  const selectedA = useMemo(
    () => runs.find((item) => item.id === compareA),
    [runs, compareA],
  );
  const selectedB = useMemo(
    () => runs.find((item) => item.id === compareB),
    [runs, compareB],
  );

  async function openRun(run: RunSummary) {
    setDetailError("");
    setValidation(null);
    try {
      setDetail(await api.run(run.id));
      p1Api.validateRun(run.id).then(setValidation).catch(() => setValidation(null));
    } catch (reason) {
      setDetailError(reason instanceof Error ? reason.message : "Could not read run.");
    }
  }

  const columns: Column<RunSummary>[] = [
    {
      key: "id",
      header: "Run",
      render: (run) => (
        <span className="mono" style={{ fontSize: 9 }}>
          {run.id}
        </span>
      ),
    },
    {
      key: "strategy",
      header: "Strategy",
      render: (run) => (
        <div>
          <div className="primary-cell">{run.strategy?.name ?? "—"}</div>
          <div className="faint mono" style={{ fontSize: 9, marginTop: 3 }}>
            {run.strategy?.id ?? ""}
          </div>
        </div>
      ),
    },
    {
      key: "dataset",
      header: "Dataset",
      render: (run) => (
        <span className="mono" style={{ fontSize: 9 }}>
          {run.dataset_id ?? "—"}
          {run.timeframe ? ` · ${run.timeframe}` : ""}
        </span>
      ),
    },
    {
      key: "created",
      header: "Archived",
      render: (run) => (
        <span className="mono" style={{ fontSize: 9 }}>
          {formatDateTime(run.created_at)}
        </span>
      ),
    },
    {
      key: "trades",
      header: "Trades",
      align: "right",
      render: (run) => formatInteger(run.metrics?.total_trades),
    },
    {
      key: "expectancy",
      header: "Expectancy",
      align: "right",
      render: (run) => (
        <span className={run.metrics?.expectancy >= 0 ? "emerald" : "crimson"}>
          {formatR(run.metrics?.expectancy)}
        </span>
      ),
    },
    {
      key: "warning",
      header: "Warnings",
      align: "right",
      render: (run) => (
        <StatusPill tone={run.warning_count ? "warn" : "ok"}>
          {run.warning_count}
        </StatusPill>
      ),
    },
  ];

  if (loading && !runs.length) return <LoadingState label="Reading run archive" />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Run archive · reproducibility"
        title="Every result leaves a trace."
        subtitle="Each run is a JSON artifact: dataset, strategy parameters, metrics, warnings, reconciliation, and trade ledger. Compare only runs that share the same data and assumptions."
        actions={
          <Button variant="ghost" icon={<RefreshCw size={14} />} onClick={load}>
            Refresh archive
          </Button>
        }
      />

      {!runs.length ? (
        <EmptyState
          title="The archive is empty"
          copy="Execute a strategy in the lab. REX will persist the run, including its warnings and trade ledger."
        />
      ) : (
        <>
          <Panel kicker="Artifacts" title="Saved research runs" flush>
            <DataTable
              columns={columns}
              rows={runs}
              getKey={(run) => run.id}
              onRowClick={openRun}
              selectedKey={detail?.id}
            />
          </Panel>

          <div className="grid-main">
            <Panel
              kicker="Comparison"
              title="Side-by-side posture"
              subtitle="Select two archived runs. Differences in dataset, costs, or parameters can invalidate a naive comparison."
              action={
                <div className="btn-row">
                  <HelpLink onClick={() => onOpenHelp("in-sample-oos")}>
                    Validation
                  </HelpLink>
                  <GitCompareArrows size={16} className="gold" />
                </div>
              }
            >
              <div className="form-grid">
                <label className="field">
                  <span className="mono" style={{ fontSize: 8, color: "var(--silver)" }}>
                    RUN A
                  </span>
                  <select
                    className="select mono"
                    value={compareA}
                    onChange={(event) => setCompareA(event.target.value)}
                  >
                    {runs.map((run) => (
                      <option key={run.id} value={run.id}>
                        {run.strategy?.id} · {run.dataset_id}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="field">
                  <span className="mono" style={{ fontSize: 8, color: "var(--silver)" }}>
                    RUN B
                  </span>
                  <select
                    className="select mono"
                    value={compareB}
                    onChange={(event) => setCompareB(event.target.value)}
                  >
                    {runs.map((run) => (
                      <option key={run.id} value={run.id}>
                        {run.strategy?.id} · {run.dataset_id}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="divider" />
              <div className="detail-list">
                {metricRow("Trades", selectedA, selectedB, (run) =>
                  formatInteger(run.metrics?.total_trades),
                )}
                {metricRow("Win rate", selectedA, selectedB, (run) =>
                  formatPercent(run.metrics?.win_rate),
                )}
                {metricRow("Expectancy", selectedA, selectedB, (run) =>
                  formatR(run.metrics?.expectancy),
                )}
                {metricRow("Profit factor", selectedA, selectedB, (run) =>
                  run.metrics?.profit_factor === null || run.metrics?.profit_factor === undefined
                    ? "—"
                    : formatDecimal(run.metrics.profit_factor, 2),
                )}
                {metricRow("Max drawdown", selectedA, selectedB, (run) =>
                  `${formatDecimal(run.metrics?.max_drawdown_r, 2)}R`,
                )}
                {metricRow("Signals", selectedA, selectedB, (run) =>
                  formatInteger(run.metrics?.total_signals),
                )}
              </div>
              <p className="field-hint" style={{ marginTop: 12 }}>
                A comparison is evidence only when the dataset, period, costs, and
                strategy parameters match. The archive does not imply that any run is
                profitable or statistically reliable.
              </p>
            </Panel>

            <Panel
              kicker="Run detail"
              title={detail ? detail.strategy.name : "Select a run"}
              subtitle={
                detail
                  ? `${detail.dataset_id} · ${formatDateTime(detail.created_at)}`
                  : "Click an artifact to inspect its assumptions and warnings."
              }
            >
              {detailError ? (
                <div className="form-error">{detailError}</div>
              ) : detail ? (
                <>
                  <div className="quality-grid">
                    <div className="quality-cell">
                      <div className="quality-label">Trades</div>
                      <div className="quality-value">{formatInteger(detail.metrics.total_trades)}</div>
                    </div>
                    <div className="quality-cell">
                      <div className="quality-label">Expectancy</div>
                      <div
                        className={`quality-value ${
                          detail.metrics.expectancy >= 0 ? "" : "danger"
                        }`}
                      >
                        {formatR(detail.metrics.expectancy)}
                      </div>
                    </div>
                    <div className="quality-cell">
                      <div className="quality-label">Warnings</div>
                      <div className={`quality-value ${detail.warnings.length ? "warn" : ""}`}>
                        {detail.warnings.length}
                      </div>
                    </div>
                  </div>
                  <div className="divider" />
                  <div className="detail-list">
                    <div className="detail-row">
                      <span className="detail-key">Cost profile</span>
                      <span className="detail-value">{detail.cost_profile?.name ?? "Legacy / unavailable"}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-key">Gross expectancy</span>
                      <span className="detail-value">{formatR(detail.metrics.expectancy)}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-key">Net expectancy</span>
                      <span className="detail-value">{detail.net_metrics ? formatR(detail.net_metrics.expectancy) : "unavailable"}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-key">Independent validation</span>
                      <span className="detail-value">{validation ? (validation.valid ? "pass" : `${validation.error_count} error(s)`) : "not available"}</span>
                    </div>
                    {validation?.findings.slice(0, 4).map((finding) => (
                      <div className="detail-row" key={`${finding.code}-${finding.message}`}>
                        <span className="detail-key">{finding.severity}</span>
                        <span className="detail-value">{finding.message}</span>
                      </div>
                    ))}
                  </div>
                  <div className="divider" />
                  <div className="notice-list">
                    {detail.warnings.length ? (
                      detail.warnings.map((warning) => (
                        <div className="notice-row" key={warning}>
                          <span className="mono" style={{ color: "var(--gold)" }}>
                            !
                          </span>
                          <span>{warning}</span>
                        </div>
                      ))
                    ) : (
                      <div className="notice-row ok">
                        <span className="mono" style={{ color: "var(--emerald)" }}>
                          ✓
                        </span>
                        <span>No run-level warnings.</span>
                      </div>
                    )}
                  </div>
                  <div className="divider" />
                  <div className="detail-list">
                    {Object.entries(detail.assumptions).map(([key, value]) => (
                      <div className="detail-row" key={key}>
                        <span className="detail-key">{key.replace(/_/g, " ")}</span>
                        <span className="detail-value">{String(value)}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <EmptyState
                  title="Nothing selected"
                  copy="Choose an archived run to inspect the exact assumptions attached to its numbers."
                />
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
