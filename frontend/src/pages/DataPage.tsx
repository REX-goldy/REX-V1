import { useEffect, useMemo, useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import { api, p1Api, type DownloadPayload } from "../api";
import type { BarPoint, DatasetQualityReport, DatasetSummary, Overview } from "../types";
import { Button } from "../components/Button";
import { DataTable, type Column } from "../components/DataTable";
import { HelpLink } from "../components/HelpLink";
import { Modal } from "../components/Modal";
import { PriceChart } from "../components/Charts";
import {
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  PageHeader,
  Panel,
  StatusPill,
} from "../components/Primitives";
import { useToast } from "../components/Toast";
import {
  formatBytes,
  formatDate,
  formatDateTime,
  formatInteger,
  providerLabel,
  statusTone,
} from "../lib/format";

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function DataPage({
  refreshKey,
  onRefresh,
  onOpenHelp,
}: {
  refreshKey: number;
  onRefresh: () => void;
  onOpenHelp: (article: string) => void;
}) {
  const { notify } = useToast();
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [selectedId, setSelectedId] = useState<string>("");
  const [selected, setSelected] = useState<DatasetSummary | null>(null);
  const [bars, setBars] = useState<BarPoint[]>([]);
  const [quality, setQuality] = useState<DatasetQualityReport | null>(null);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [modalOpen, setModalOpen] = useState(false);

  const [provider, setProvider] = useState<DownloadPayload["provider"]>("twelve_data");
  const [symbol, setSymbol] = useState("EURUSD");
  const [startDate, setStartDate] = useState(() => {
    const date = new Date();
    date.setUTCDate(date.getUTCDate() - 13);
    return isoDate(date);
  });
  const [endDate, setEndDate] = useState(() => isoDate(new Date()));
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([api.datasets(), api.overview()])
      .then(([datasetList, overviewData]) => {
        if (cancelled) return;
        setDatasets(datasetList);
        setOverview(overviewData);
        setError("");
        setSelectedId((current) => current || datasetList[0]?.id || "");
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

  useEffect(() => {
    if (!selectedId) {
      setSelected(null);
      setBars([]);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    Promise.all([api.dataset(selectedId), api.bars(selectedId, "M1", 700)])
      .then(([detail, series]) => {
        if (cancelled) return;
        setSelected(detail);
        setBars(series);
        setDownloadError("");
      })
      .catch((reason: Error) => {
        if (!cancelled) setDownloadError(reason.message);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, refreshKey]);

  useEffect(() => {
    if (!selectedId) {
      setQuality(null);
      return;
    }
    let cancelled = false;
    setQualityLoading(true);
    p1Api
      .datasetQuality(selectedId)
      .then((report) => {
        if (!cancelled) setQuality(report);
      })
      .catch(() => {
        if (!cancelled) setQuality(null);
      })
      .finally(() => {
        if (!cancelled) setQualityLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId, refreshKey]);

  const columns: Column<DatasetSummary>[] = [
    {
      key: "symbol",
      header: "Dataset",
      render: (row) => (
        <div>
          <div className="primary-cell">{row.symbol}</div>
          <div className="faint mono" style={{ fontSize: 9, marginTop: 3 }}>
            {row.timeframe} · {row.year} · {formatBytes(row.size_bytes)}
          </div>
        </div>
      ),
    },
    {
      key: "provider",
      header: "Source",
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
        <span className="mono" style={{ fontSize: 9, lineHeight: 1.6 }}>
          {formatDate(row.coverage.start ?? row.first_timestamp)}
          <br />
          {formatDate(row.coverage.end ?? row.last_timestamp)}
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

  const canDownload = provider === "dukascopy" || Boolean(overview?.capabilities.twelve_data);
  const maxDays = overview?.capabilities.download_max_days ?? 31;

  const dateError = useMemo(() => {
    if (!startDate || !endDate) return "Choose both a start and end date.";
    const start = new Date(`${startDate}T00:00:00Z`);
    const end = new Date(`${endDate}T00:00:00Z`);
    if (start > end) return "Start date must be before end date.";
    if (end > new Date()) return "End date cannot be in the future.";
    const days = Math.ceil((end.getTime() - start.getTime()) / 86_400_000);
    if (days > maxDays) return `UI downloads are limited to ${maxDays} days per request.`;
    return "";
  }, [startDate, endDate, maxDays]);

  async function submitDownload() {
    if (dateError) {
      setDownloadError(dateError);
      return;
    }
    setDownloading(true);
    setDownloadError("");
    try {
      const result = await api.download({
        provider,
        symbol,
        timeframe: "M1",
        start_date: startDate,
        end_date: endDate,
      });
      const first = result[0];
      notify(
        first
          ? `Downloaded ${first.symbol} ${first.timeframe} ${first.year}: ${formatInteger(first.bar_count)} bars.`
          : "Download completed.",
      );
      setModalOpen(false);
      onRefresh();
      if (first) setSelectedId(first.id);
    } catch (reason) {
      setDownloadError(reason instanceof Error ? reason.message : "Download failed.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Market data · historical workspace"
        title="The record, before the model."
        subtitle="Every dataset is a canonical M1 partition with provenance and quality read from storage. Downloads are bounded and synchronous; this terminal never holds provider keys."
        actions={
          <>
            <Button
              variant="primary"
              icon={<Download size={14} />}
              onClick={() => {
                setDownloadError("");
                setModalOpen(true);
              }}
            >
              Download data
            </Button>
            <Button
              variant="ghost"
              icon={<RefreshCw size={14} />}
              onClick={onRefresh}
            >
              Refresh
            </Button>
          </>
        }
      />

      {loading && !datasets.length ? (
        <LoadingState label="Scanning historical storage" />
      ) : error ? (
        <ErrorState message={error} />
      ) : (
        <div className="grid-data">
          <div className="stack">
          <Panel
            kicker="Estate"
            title="Stored partitions"
            subtitle={`${datasets.length} dataset${datasets.length === 1 ? "" : "s"} · data root ${overview?.data_root ?? "—"}`}
            flush
          >
            {datasets.length ? (
              <DataTable
                columns={columns}
                rows={datasets}
                getKey={(row) => row.id}
                selectedKey={selectedId}
                onRowClick={(row) => setSelectedId(row.id)}
              />
            ) : (
              <div style={{ padding: 20 }}>
                <EmptyState
                  title="No partitions yet"
                  copy="Start with a bounded Twelve Data download, or place canonical M1 files under the data root."
                  action={
                    <Button
                      size="sm"
                      onClick={() => {
                        setDownloadError("");
                        setModalOpen(true);
                      }}
                    >
                      Download data
                    </Button>
                  }
                />
              </div>
            )}
          </Panel>

          <Panel
            kicker="Pipeline"
            title="Acquisition policy"
            subtitle="The terminal exposes only bounded, auditable operations."
            action={
              <HelpLink onClick={() => onOpenHelp("data-providers")}>
                Providers
              </HelpLink>
            }
          >
            <div className="detail-list">
              <div className="detail-row">
                <span className="detail-key">Source timeframe</span>
                <span className="detail-value">M1 only</span>
              </div>
              <div className="detail-row">
                <span className="detail-key">UI window</span>
                <span className="detail-value">{maxDays} days / request</span>
              </div>
              <div className="detail-row">
                <span className="detail-key">Transport</span>
                <span className="detail-value">synchronous API call</span>
              </div>
              <div className="detail-row">
                <span className="detail-key">Credentials</span>
                <span className="detail-value">backend environment</span>
              </div>
            </div>
            <div className="divider" />
            <p className="field-hint">
              Full multi-year backfills belong in the resumable CLI. The UI is for
              inspection, validation, and bounded refreshes, not bulk ingestion.
            </p>
          </Panel>
          </div>

          <div className="stack">
            {selected ? (
              <>
                <Panel
                  kicker="Selected dataset"
                  title={`${selected.symbol} ${selected.timeframe}`}
                  subtitle={`${selected.year} · ${providerLabel(selected.provider)} · ${formatBytes(selected.size_bytes)}`}
                  action={
                    <StatusPill tone={statusTone(selected.status)}>
                      {selected.status === "ok" ? "Verified" : selected.status}
                    </StatusPill>
                  }
                >
                  <div className="quality-grid">
                    <div className="quality-cell">
                      <div className="quality-label">Bars</div>
                      <div className="quality-value">{formatInteger(selected.bar_count)}</div>
                    </div>
                    <div className="quality-cell">
                      <div className="quality-label">Duplicates</div>
                      <div
                        className={`quality-value ${
                          selected.quality.duplicate_count ? "danger" : ""
                        }`}
                      >
                        {selected.quality.duplicate_count ?? 0}
                      </div>
                    </div>
                    <div className="quality-cell">
                      <div className="quality-label">Invalid OHLC</div>
                      <div
                        className={`quality-value ${
                          selected.quality.invalid_bar_count ? "danger" : ""
                        }`}
                      >
                        {selected.quality.invalid_bar_count ?? 0}
                      </div>
                    </div>
                    <div className="quality-cell">
                      <div className="quality-label">Raw gaps</div>
                      <div
                        className={`quality-value ${
                          selected.quality.timestamp_gap_count ? "warn" : ""
                        }`}
                      >
                        {selected.quality.timestamp_gap_count ?? "—"}
                      </div>
                    </div>
                    <div className="quality-cell">
                      <div className="quality-label">First bar</div>
                      <div className="quality-value" style={{ fontSize: 14 }}>
                        {formatDateTime(selected.first_timestamp)}
                      </div>
                    </div>
                    <div className="quality-cell">
                      <div className="quality-label">Last bar</div>
                      <div className="quality-value" style={{ fontSize: 14 }}>
                        {formatDateTime(selected.last_timestamp)}
                      </div>
                    </div>
                  </div>

                  {selected.warnings.length ? (
                    <>
                      <div className="divider" />
                      <div className="notice-list">
                        {selected.warnings.map((warning) => (
                          <div className="notice-row" key={warning}>
                            <span className="mono" style={{ color: "var(--gold)" }}>
                              !
                            </span>
                            <span>{warning}</span>
                          </div>
                        ))}
                      </div>
                      <div style={{ marginTop: 8 }}>
                        <HelpLink onClick={() => onOpenHelp("missing-timestamps")}>
                          Why gaps matter
                        </HelpLink>
                      </div>
                    </>
                  ) : null}

                  <div className="divider" />
                  <div className="grid-2">
                    <div className="detail-list">
                      <div className="detail-row">
                        <span className="detail-key">Requested</span>
                        <span className="detail-value">
                          {selected.coverage.requested_start ?? "—"} →{" "}
                          {selected.coverage.requested_end ?? "—"}
                        </span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-key">Actual coverage</span>
                        <span className="detail-value">
                          {selected.coverage.actual_start?.slice(0, 10) ?? "—"} →{" "}
                          {selected.coverage.actual_end?.slice(0, 10) ?? "—"}
                        </span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-key">Retrieved</span>
                        <span className="detail-value">
                          {formatDateTime(selected.coverage.retrieved_at)}
                        </span>
                      </div>
                    </div>
                    <div className="detail-list">
                      <div className="detail-row">
                        <span className="detail-key">Provider</span>
                        <span className="detail-value">{providerLabel(selected.provider)}</span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-key">Path</span>
                        <span className="detail-value">{selected.path ?? "—"}</span>
                      </div>
                      <div className="detail-row">
                        <span className="detail-key">Metadata</span>
                        <span className="detail-value">
                          {selected.provider === "unknown" ? "missing" : "present"}
                        </span>
                      </div>
                      {Number(selected.metadata?.closure_filtered_count ?? 0) > 0 ? (
                        <div className="detail-row">
                          <span className="detail-key">Closure bars excluded</span>
                          <span className="detail-value">
                            {formatInteger(
                              Number(selected.metadata?.closure_filtered_count ?? 0),
                            )}
                          </span>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </Panel>

                <Panel
                  kicker="Dataset quality"
                  title="Source and derived integrity"
                  subtitle="Read-only audit. No candles are filled or changed by this report."
                  action={
                    quality ? (
                      <StatusPill tone={quality.quality.status === "ok" ? "ok" : quality.quality.status === "error" ? "danger" : "warn"}>
                        {quality.quality.status}
                      </StatusPill>
                    ) : null
                  }
                >
                  {qualityLoading ? (
                    <p className="field-hint">Composing quality report…</p>
                  ) : quality ? (
                    <>
                      <div className="quality-grid">
                        <div className="quality-cell"><div className="quality-label">Unexpected gaps</div><div className={`quality-value ${quality.counts.unexpected_gap_count ? "danger" : ""}`}>{quality.counts.unexpected_gap_count}</div></div>
                        <div className="quality-cell"><div className="quality-label">Missing open min</div><div className={`quality-value ${quality.counts.missing_open_minutes ? "warn" : ""}`}>{quality.counts.missing_open_minutes}</div></div>
                        <div className="quality-cell"><div className="quality-label">Closure min</div><div className="quality-value">{formatInteger(quality.counts.missing_closure_minutes)}</div></div>
                        <div className="quality-cell"><div className="quality-label">Raw gaps</div><div className="quality-value">{quality.counts.raw_gap_count ?? "—"}</div></div>
                      </div>
                      <div className="divider" />
                      <div className="detail-list">
                        <div className="detail-row"><span className="detail-key">Coverage</span><span className="detail-value mono">{quality.coverage.actual_start?.slice(0, 16) ?? "—"} → {quality.coverage.actual_end?.slice(0, 16) ?? "—"}</span></div>
                        <div className="detail-row"><span className="detail-key">Provider</span><span className="detail-value">{providerLabel(quality.provider)}</span></div>
                        <div className="detail-row"><span className="detail-key">Bars in closure</span><span className="detail-value">{quality.counts.bars_in_closure}</span></div>
                        {Object.entries(quality.derived).map(([tf, item]) => (
                          <div className="detail-row" key={tf}>
                            <span className="detail-key">{tf}</span>
                            <span className="detail-value">{item.status === "ok" ? `${formatInteger(item.emitted_bar_count)} bars · ${item.skipped_incomplete_buckets ?? 0} incomplete skipped` : item.error ?? "unavailable"}</span>
                          </div>
                        ))}
                      </div>
                      {quality.quality.errors.length || quality.quality.warnings.length ? (
                        <>
                          <div className="divider" />
                          <div className="notice-list">
                            {[...quality.quality.errors, ...quality.quality.warnings].map((message) => (
                              <div className="notice-row" key={message}><span className="mono" style={{ color: "var(--gold)" }}>!</span><span>{message}</span></div>
                            ))}
                          </div>
                        </>
                      ) : null}
                    </>
                  ) : (
                    <p className="field-hint">Quality report unavailable for this dataset.</p>
                  )}
                </Panel>

                <Panel
                  kicker="Price record"
                  title="Candlestick preview"
                  subtitle="Last stored M1 bars. The chart is a record, not a recommendation."
                  flush
                >
                  <div className="chart-legend">
                    <span className="legend-item">
                      <span className="legend-swatch emerald" /> Up
                    </span>
                    <span className="legend-item">
                      <span className="legend-swatch crimson" /> Down
                    </span>
                    <span>UTC · {selected.symbol}</span>
                  </div>
                  <div style={{ padding: 12 }}>
                    <PriceChart bars={bars} symbol={selected.symbol} tall />
                  </div>
                </Panel>
              </>
            ) : detailLoading ? (
              <LoadingState label="Reading dataset detail" />
            ) : (
              <Panel kicker="Selected dataset" title="Nothing selected">
                <EmptyState
                  title="Select a partition"
                  copy="Choose a dataset from the estate to inspect its coverage, quality counters, and price record."
                />
              </Panel>
            )}
          </div>
        </div>
      )}

      <Modal
        open={modalOpen}
        title="Acquire historical data"
        copy="Bounded synchronous download through the existing REX downloader. Twelve Data credentials stay in the backend environment."
        onClose={() => {
          if (!downloading) setModalOpen(false);
        }}
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => setModalOpen(false)}
              disabled={downloading}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={submitDownload}
              loading={downloading}
              disabled={Boolean(dateError) || !canDownload}
            >
              Download
            </Button>
          </>
        }
      >
        <div className="form-grid">
          <Field label="Provider" hint="Twelve Data is the preferred M1 source.">
            <select
              className="select"
              value={provider}
              onChange={(event) =>
                setProvider(event.target.value as DownloadPayload["provider"])
              }
              disabled={downloading}
            >
              <option value="twelve_data">Twelve Data</option>
              <option value="dukascopy">Dukascopy</option>
            </select>
          </Field>
          <Field label="Instrument">
            <select
              className="select"
              value={symbol}
              onChange={(event) => setSymbol(event.target.value)}
              disabled={downloading}
            >
              <option value="EURUSD">EURUSD</option>
              <option value="GBPUSD">GBPUSD</option>
              <option value="USDJPY">USDJPY</option>
              <option value="AUDUSD">AUDUSD</option>
              <option value="USDCAD">USDCAD</option>
              <option value="NZDUSD">NZDUSD</option>
              <option value="USDCHF">USDCHF</option>
            </select>
          </Field>
          <Field label="Timeframe" hint="M1 is the only stored source timeframe.">
            <input className="input mono" value="M1" readOnly />
          </Field>
          <Field label="Maximum window" hint={`${maxDays} days per synchronous request.`}>
            <input className="input mono" value={`${maxDays} days`} readOnly />
          </Field>
          <Field label="Start date" hint="UTC calendar date.">
            <input
              className="input mono"
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
              disabled={downloading}
            />
          </Field>
          <Field label="End date" hint="UTC calendar date.">
            <input
              className="input mono"
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
              disabled={downloading}
            />
          </Field>
          <div className="span-2">
            {!canDownload ? (
              <div className="form-error">
                TWELVE_DATA_API_KEY is not configured on the backend. Add it to the
                environment or use Dukascopy.
              </div>
            ) : dateError ? (
              <div className="form-error">{dateError}</div>
            ) : downloadError ? (
              <div className="form-error">{downloadError}</div>
            ) : (
              <p className="field-hint">
                The request uses the provider’s free-tier limits. Existing partitions
                without provenance are refused to prevent provider mixing; set a
                separate <span className="mono">REX_DATA_DIR</span> when switching
                sources. Full multi-year backfills belong in the resumable CLI.
              </p>
            )}
          </div>
        </div>
      </Modal>
    </div>
  );
}
