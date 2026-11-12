import { useEffect, useState } from "react";
import { ArrowRight, Database, FlaskConical } from "lucide-react";
import { api } from "../api";
import type { Overview } from "../types";
import {
  EmptyState,
  ErrorState,
  LoadingState,
  Metric,
  PageHeader,
  Panel,
  StatusPill,
} from "../components/Primitives";
import { Button } from "../components/Button";
import { DataTable, type Column } from "../components/DataTable";
import type { DatasetSummary } from "../types";
import {
  formatDate,
  formatInteger,
  formatR,
  providerLabel,
  statusTone,
} from "../lib/format";

export function OverviewPage({
  onNavigate,
  refreshKey,
}: {
  onNavigate: (page: "data" | "research" | "runs" | "system") => void;
  refreshKey: number;
}) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .overview()
      .then((data) => {
        if (!cancelled) {
          setOverview(data);
          setError("");
        }
      })
      .catch((reason: Error) => {
        if (!cancelled) setError(reason.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  if (loading && !overview) return <LoadingState label="Assembling research state" />;
  if (error && !overview) return <ErrorState message={error} />;
  if (!overview) return null;

  const columns: Column<DatasetSummary>[] = [
    {
      key: "symbol",
      header: "Instrument",
      render: (row) => (
        <div className="row-symbol">
          <span className="instrument-mark">{row.symbol.slice(0, 3)}</span>
          <div>
            <div className="primary-cell">{row.symbol}</div>
            <div className="faint mono" style={{ fontSize: 9, marginTop: 3 }}>
              {row.timeframe} · {row.year}
            </div>
          </div>
        </div>
      ),
    },
    {
      key: "provider",
      header: "Provider",
      render: (row) => <span className="tag">{providerLabel(row.provider)}</span>,
    },
    {
      key: "bars",
      header: "Bars",
      align: "right",
      render: (row) => formatInteger(row.bar_count),
    },
    {
      key: "coverage",
      header: "Coverage",
      render: (row) => (
        <span className="mono" style={{ fontSize: 9 }}>
          {formatDate(row.coverage.start ?? row.first_timestamp)} →{" "}
          {formatDate(row.coverage.end ?? row.last_timestamp)}
        </span>
      ),
    },
    {
      key: "gaps",
      header: "Gaps",
      align: "right",
      render: (row) => (
        <span className={row.quality.timestamp_gap_count ? "gold" : "muted"}>
          {row.quality.timestamp_gap_count ?? "—"}
        </span>
      ),
    },
    {
      key: "status",
      header: "State",
      align: "right",
      render: (row) => (
        <StatusPill tone={statusTone(row.status)}>
          {row.status === "ok" ? "Verified" : row.status}
        </StatusPill>
      ),
    },
  ];

  const warnings = overview.warnings;

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Research terminal · overview"
        title={
          <>
            Evidence before
            <br />
            <em>conviction.</em>
          </>
        }
        subtitle="A causal, reproducible research desk for Forex strategies. Inspect datasets, run the existing kernel, and read every assumption before interpreting a number."
        actions={
          <>
            <Button
              variant="primary"
              icon={<FlaskConical size={14} />}
              onClick={() => onNavigate("research")}
            >
              Open strategy lab
            </Button>
            <Button
              variant="ghost"
              icon={<Database size={14} />}
              onClick={() => onNavigate("data")}
            >
              Inspect data
            </Button>
          </>
        }
      />

      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Institutional research discipline</p>
          <h2 className="hero-title">
            A quiet terminal for <em>serious</em> market evidence.
          </h2>
          <p className="hero-subtitle">
            REX does not sell signals. It replays completed candles causally, executes
            the existing trade simulation, and surfaces the limitations that matter:
            costs, sample size, static zones, and data provenance.
          </p>
          <div className="hero-actions">
            <Button variant="primary" onClick={() => onNavigate("research")}>
              Run a backtest <ArrowRight size={14} />
            </Button>
            <Button variant="ghost" onClick={() => onNavigate("system")}>
              Read the system limits
            </Button>
          </div>
        </div>
        <div className="hero-aside">
          <span className="hero-aside-label">Current dataset estate</span>
          <span className="hero-aside-value">{overview.datasets.length}</span>
          <span className="hero-aside-note">
            Stored M1 partitions under the research data root. Provider and quality
            metadata are read from the dataset itself, not invented.
          </span>
          <div className="gold-rule" style={{ marginTop: 8 }} />
          <span className="hero-aside-label" style={{ marginTop: 10 }}>
            Trade simulation
          </span>
          <span className="mono" style={{ color: "var(--ivory-dim)", fontSize: 11 }}>
            {overview.capabilities.trade_simulation.length
              ? overview.capabilities.trade_simulation.join(" · ")
              : "No factories wired"}
          </span>
        </div>
      </section>

      <div className="metric-grid">
        <Metric
          label="Instruments"
          value={overview.instruments.length}
          meta="Registered in the instrument catalog"
        />
        <Metric
          label="Datasets"
          value={overview.datasets.length}
          meta="Stored M1 partitions"
          tone="gold"
        />
        <Metric
          label="Strategies"
          value={overview.strategies.length}
          meta={`${overview.capabilities.trade_simulation.length} trade-simulated`}
        />
        <Metric
          label="Recent runs"
          value={overview.runs.length}
          meta="Persisted JSON artifacts"
        />
      </div>

      <div className="grid-main">
        <Panel
          kicker="Data estate"
          title="Available datasets"
          subtitle="Coverage and quality are read directly from storage metadata and the canonical bar parser."
          action={
            <Button size="sm" variant="ghost" onClick={() => onNavigate("data")}>
              Open workspace
            </Button>
          }
          flush
        >
          {overview.datasets.length ? (
            <DataTable
              columns={columns}
              rows={overview.datasets}
              getKey={(row) => row.id}
              onRowClick={() => onNavigate("data")}
            />
          ) : (
            <div style={{ padding: 20 }}>
              <EmptyState
                title="No historical datasets"
                copy="Download M1 data or place canonical partitions under the configured data root before running research."
                action={
                  <Button size="sm" onClick={() => onNavigate("data")}>
                    Configure data
                  </Button>
                }
              />
            </div>
          )}
        </Panel>

        <div className="stack">
          <Panel
            kicker="Integrity"
            title="Research warnings"
            subtitle="Warnings are not decoration. They are the current limits of the evidence."
          >
            {warnings.length ? (
              <div className="notice-list">
                {warnings.slice(0, 6).map((warning) => (
                  <div className="notice-row" key={warning}>
                    <span className="mono" style={{ color: "var(--gold)" }}>
                      !
                    </span>
                    <span>{warning}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="notice-row ok">
                <span className="mono" style={{ color: "var(--emerald)" }}>
                  ✓
                </span>
                <span>No dataset warnings. Assumptions still apply to every run.</span>
              </div>
            )}
            <div className="divider" />
            <div className="detail-list">
              <div className="detail-row">
                <span className="detail-key">Twelve Data key</span>
                <span className="detail-value">
                  {overview.capabilities.twelve_data ? "configured" : "not set"}
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-key">Data root</span>
                <span className="detail-value">{overview.data_root}</span>
              </div>
              <div className="detail-row">
                <span className="detail-key">Download limit</span>
                <span className="detail-value">
                  {overview.capabilities.download_max_days} days / request
                </span>
              </div>
            </div>
          </Panel>

          <Panel
            kicker="Catalog"
            title="Strategy posture"
            action={
              <Button size="sm" variant="ghost" onClick={() => onNavigate("research")}>
                Lab
              </Button>
            }
          >
            {overview.strategies.map((strategy) => (
              <div className="strategy-row" key={strategy.id}>
                <div>
                  <div className="strategy-id">{strategy.id}</div>
                  <p className="strategy-name">{strategy.name}</p>
                  <p className="strategy-desc">{strategy.description}</p>
                </div>
                <div className="strategy-meta">
                  <StatusPill tone={strategy.trade_simulation ? "ok" : "warn"}>
                    {strategy.trade_simulation ? "Simulated" : "Signal only"}
                  </StatusPill>
                  {strategy.requires_zones ? (
                    <StatusPill tone="neutral">Zones</StatusPill>
                  ) : null}
                </div>
              </div>
            ))}
          </Panel>
        </div>
      </div>

      <Panel
        kicker="Run archive"
        title="Recent research runs"
        subtitle="Every persisted run is a JSON artifact with its dataset, parameters, metrics, warnings, and trade ledger."
        action={
          <Button size="sm" variant="ghost" onClick={() => onNavigate("runs")}>
            Read archive
          </Button>
        }
        flush
      >
        {overview.runs.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Strategy</th>
                  <th>Dataset</th>
                  <th className="num">Trades</th>
                  <th className="num">Expectancy</th>
                  <th className="num">Warnings</th>
                </tr>
              </thead>
              <tbody>
                {overview.runs.map((run) => (
                  <tr key={run.id}>
                    <td className="mono" style={{ fontSize: 9 }}>
                      {run.id}
                    </td>
                    <td className="primary-cell">{run.strategy?.name ?? "—"}</td>
                    <td className="mono" style={{ fontSize: 9 }}>
                      {run.dataset_id ?? "—"}
                      {run.timeframe ? ` · ${run.timeframe}` : ""}
                    </td>
                    <td className="num">{formatInteger(run.metrics?.total_trades)}</td>
                    <td className="num">{formatR(run.metrics?.expectancy)}</td>
                    <td className="num">{run.warning_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ padding: 20 }}>
            <EmptyState
              title="No saved runs"
              copy="Run a strategy in the lab. Completed runs are archived automatically with their warnings and trade ledger."
              action={
                <Button size="sm" onClick={() => onNavigate("research")}>
                  Open strategy lab
                </Button>
              }
            />
          </div>
        )}
      </Panel>
    </div>
  );
}
