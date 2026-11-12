import { useEffect, useMemo, useRef, useState } from "react";
import {
  ColorType,
  CrosshairMode,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { Archive, Layers, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { api, zoneApi, workspaceApi } from "../api";
import type { BarPoint, DatasetSummary, ManualZone, StrategyWorkspaceSummary, ZonePayload } from "../types";
import { Button } from "../components/Button";
import { Modal } from "../components/Modal";
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
import { formatDateTime } from "../lib/format";

type DrawDraft = { low: number; high: number; start_time: string };

function toLocalInput(iso: string | null | undefined): string {
  return iso ? iso.slice(0, 16) : "";
}

function toIso(local: string): string | undefined {
  if (!local) return undefined;
  const date = new Date(local);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

function priceDigits(symbol: string): number {
  if (symbol.includes("JPY")) return 3;
  return symbol === "XAUUSD" ? 2 : 5;
}

function coordinateTimeToIso(time: unknown): string | null {
  if (typeof time === "number") return new Date(time * 1000).toISOString();
  if (time && typeof time === "object" && "year" in time) {
    const value = time as { year: number; month: number; day: number };
    return new Date(Date.UTC(value.year, value.month - 1, value.day)).toISOString();
  }
  return null;
}

function ZoneChart({
  bars,
  symbol,
  zones,
  drawMode,
  onDraw,
}: {
  bars: BarPoint[];
  symbol: string;
  zones: ManualZone[];
  drawMode: boolean;
  onDraw: (draft: DrawDraft) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [revision, setRevision] = useState(0);
  const [draft, setDraft] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(null);
  const draftRef = useRef<{ x1: number; y1: number; x2: number; y2: number } | null>(null);
  const startRef = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !bars.length) return;
    const chart = createChart(container, {
      width: container.clientWidth,
      height: 440,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8f9bac",
        fontFamily: "Inter, Segoe UI, sans-serif",
        fontSize: 10,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "rgba(165, 179, 199, 0.055)" },
        horzLines: { color: "rgba(165, 179, 199, 0.055)" },
      },
      rightPriceScale: { borderColor: "rgba(165, 179, 199, 0.14)" },
      timeScale: { borderColor: "rgba(165, 179, 199, 0.14)", timeVisible: true },
      crosshair: { mode: CrosshairMode.Normal },
    });
    const series = chart.addCandlestickSeries({
      upColor: "#43cf9a",
      downColor: "#df6a6a",
      borderVisible: false,
      wickUpColor: "#43cf9a",
      wickDownColor: "#df6a6a",
      priceFormat: { type: "price", precision: priceDigits(symbol), minMove: symbol.includes("JPY") ? 0.001 : 0.00001 },
    });
    series.setData(
      bars.map((bar) => ({
        time: bar.time as UTCTimestamp,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      })),
    );
    chart.timeScale().fitContent();
    const onRange = () => setRevision((value) => value + 1);
    chart.timeScale().subscribeVisibleLogicalRangeChange(onRange);
    const observer = new ResizeObserver(() => chart.applyOptions({ width: container.clientWidth }));
    observer.observe(container);
    chartRef.current = chart;
    seriesRef.current = series;
    setRevision((value) => value + 1);
    return () => {
      observer.disconnect();
      chart.timeScale().unsubscribeVisibleLogicalRangeChange(onRange);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [bars, symbol]);

  const rectangles = useMemo(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series || !bars.length || !revision) return [];
    const first = bars[0].time as UTCTimestamp;
    const last = bars[bars.length - 1].time as UTCTimestamp;
    return zones
      .filter((zone) => zone.status !== "archived")
      .map((zone) => {
        const startTime = zone.effective_timestamp
          ? Math.floor(new Date(zone.effective_timestamp).getTime() / 1000)
          : Number(first);
        const endTime = zone.invalidation_timestamp
          ? Math.floor(new Date(zone.invalidation_timestamp).getTime() / 1000)
          : Number(last);
        const x1 = chart.timeScale().timeToCoordinate(Math.max(startTime, Number(first)) as UTCTimestamp);
        const x2 = chart.timeScale().timeToCoordinate(Math.min(endTime, Number(last)) as UTCTimestamp);
        const y1 = series.priceToCoordinate(zone.high);
        const y2 = series.priceToCoordinate(zone.low);
        if (x1 === null || x2 === null || y1 === null || y2 === null) return null;
        return {
          zone,
          left: Math.min(x1, x2),
          width: Math.max(2, Math.abs(x2 - x1)),
          top: Math.min(y1, y2),
          height: Math.max(2, Math.abs(y2 - y1)),
        };
      })
      .filter(Boolean) as {
      zone: ManualZone;
      left: number;
      width: number;
      top: number;
      height: number;
    }[];
  }, [bars, zones, revision]);

  function pointer(event: React.PointerEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }

  function finishDraw() {
    const chart = chartRef.current;
    const series = seriesRef.current;
    const start = startRef.current;
    const activeDraft = draftRef.current;
    if (!chart || !series || !start || !activeDraft) {
      setDraft(null);
      draftRef.current = null;
      startRef.current = null;
      return;
    }
    if (Math.abs(activeDraft.x2 - activeDraft.x1) < 8 || Math.abs(activeDraft.y2 - activeDraft.y1) < 8) {
      setDraft(null);
      draftRef.current = null;
      startRef.current = null;
      return;
    }
    const left = Math.min(activeDraft.x1, activeDraft.x2);
    const right = Math.max(activeDraft.x1, activeDraft.x2);
    const top = Math.min(activeDraft.y1, activeDraft.y2);
    const bottom = Math.max(activeDraft.y1, activeDraft.y2);
    const startTime = chart.timeScale().coordinateToTime(left);
    const startIso = coordinateTimeToIso(startTime);
    const high = series.coordinateToPrice(top);
    const low = series.coordinateToPrice(bottom);
    setDraft(null);
    draftRef.current = null;
    startRef.current = null;
    if (startIso && high !== null && low !== null && high > low) {
      onDraw({ low, high, start_time: startIso });
    }
  }

  if (!bars.length) {
    return <EmptyState title="No price series" copy="Choose a dataset with stored bars." />;
  }

  return (
    <div className="zone-chart-frame">
      <div className="zone-chart-canvas" ref={containerRef} />
      <div
        className={`zone-overlay ${drawMode ? "drawing" : ""}`}
        onPointerDown={(event) => {
          if (!drawMode) return;
          event.currentTarget.setPointerCapture(event.pointerId);
          const point = pointer(event);
          startRef.current = point;
          const next = { x1: point.x, y1: point.y, x2: point.x, y2: point.y };
          draftRef.current = next;
          setDraft(next);
        }}
        onPointerMove={(event) => {
          if (!drawMode || !startRef.current) return;
          const point = pointer(event);
          const next = { x1: startRef.current.x, y1: startRef.current.y, x2: point.x, y2: point.y };
          draftRef.current = next;
          setDraft(next);
        }}
        onPointerUp={finishDraw}
        onPointerCancel={finishDraw}
        onClick={(event) => {
          if (!drawMode) return;
          const chart = chartRef.current;
          const series = seriesRef.current;
          if (!chart || !series) return;
          const point = pointer(event as unknown as React.PointerEvent<HTMLDivElement>);
          const startTime = chart.timeScale().coordinateToTime(point.x);
          const startIso = coordinateTimeToIso(startTime);
          const price = series.coordinateToPrice(point.y);
          if (startIso && price !== null) {
            const width = symbol.includes("JPY") ? 0.1 : 0.0005;
            onDraw({ low: price - width, high: price + width, start_time: startIso });
          }
        }}
      >
        {rectangles.map(({ zone, left, top, width, height }) => (
          <span
            key={zone.id}
            className={`zone-rect ${zone.zone_type}`}
            style={{ left, top, width, height }}
            title={`${zone.zone_type} ${zone.low}–${zone.high} · v${zone.version}`}
          />
        ))}
        {draft ? (
          <span
            className="zone-rect drawing"
            style={{
              left: Math.min(draft.x1, draft.x2),
              top: Math.min(draft.y1, draft.y2),
              width: Math.abs(draft.x2 - draft.x1),
              height: Math.abs(draft.y2 - draft.y1),
            }}
          />
        ) : null}
      </div>
    </div>
  );
}

export function ZoneManagerPage() {
  const { notify } = useToast();
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [strategies, setStrategies] = useState<StrategyWorkspaceSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [bars, setBars] = useState<BarPoint[]>([]);
  const [zones, setZones] = useState<ManualZone[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [drawMode, setDrawMode] = useState(false);
  const [draft, setDraft] = useState<DrawDraft | null>(null);
  const [editing, setEditing] = useState<ManualZone | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState("");

  const selected = datasets.find((item) => item.id === selectedId) ?? null;

  const loadZones = () => {
    if (!selected) return;
    zoneApi
      .list({ symbol: selected.symbol, status: statusFilter || undefined })
      .then(setZones)
      .catch((reason: Error) => setError(reason.message));
  };

  useEffect(() => {
    Promise.all([api.datasets(), workspaceApi.list()])
      .then(([datasetList, strategyList]) => {
        setDatasets(datasetList);
        setStrategies(strategyList);
        setSelectedId((current) => current || datasetList[0]?.id || "");
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selected) return;
    const timer = window.setTimeout(() => {
      api
        .bars(selected.id, "M1", 1500)
        .then(setBars)
        .catch((reason: Error) => setError(reason.message));
      loadZones();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [selectedId, statusFilter]);

  const formInitial = useMemo(
    () => editing ?? {
      id: "",
      dataset_id: selectedId,
      instrument: selected?.symbol ?? "",
      source_timeframe: "M1",
      zone_type: "demand",
      low: draft?.low ?? 0,
      high: draft?.high ?? 0,
      start_timestamp: draft?.start_time ?? null,
      effective_timestamp: draft?.start_time ?? null,
      invalidation_timestamp: null,
      status: "active",
      strength: 5,
      notes: "",
      strategy_id: null,
      variation_id: null,
      provenance: "manual",
      source: "manual",
      version: 1,
      created_at: null,
      updated_at: null,
      legacy: false,
      versions: [],
      historical_import: true,
      import_source: "zone-manager",
      import_operator: "local-user",
      imported_at: null,
    } satisfies ManualZone,
    [editing, selected, selectedId, draft],
  );

  async function saveZone(payload: ZonePayload) {
    setSaving(true);
    setActionError("");
    try {
      if (editing && !editing.legacy) {
        await zoneApi.update(editing.id, payload);
        notify("Zone updated as a new version.");
      } else {
        await zoneApi.create(payload);
        notify("Zone created.");
      }
      setModalOpen(false);
      setEditing(null);
      setDraft(null);
      loadZones();
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "Could not save zone.");
    } finally {
      setSaving(false);
    }
  }

  if (loading && !datasets.length) return <LoadingState label="Loading zone manager" />;
  if (error && !datasets.length) return <ErrorState message={error} />;

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Market data · zone manager"
        title="Draw the area, keep the version."
        subtitle="Manual supply and demand annotations are stored separately from candles. Backtests use only zones effective before the simulated range; versions are preserved."
        actions={
          <>
            <Button variant="primary" icon={<Plus size={14} />} onClick={() => { setEditing(null); setDraft(null); setModalOpen(true); }}>
              New zone
            </Button>
            <Button variant={drawMode ? "primary" : "ghost"} icon={<Layers size={14} />} onClick={() => setDrawMode((value) => !value)}>
              {drawMode ? "Drawing active" : "Draw on chart"}
            </Button>
          </>
        }
      />

      <div className="zone-toolbar">
        <Field label="Dataset">
          <select className="select" value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
            {datasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>{dataset.id}</option>
            ))}
          </select>
        </Field>
        <Field label="Zone status">
          <select className="select" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">All</option>
            <option value="active">Active</option>
            <option value="invalidated">Invalidated</option>
            <option value="archived">Archived</option>
          </select>
        </Field>
        <div className="zone-toolbar-spacer" />
        <span className="field-hint">
          {drawMode ? "Drag on the chart to define a rectangle." : "Select “Draw on chart”, then drag a rectangle."}
        </span>
      </div>

      {selected ? (
        <Panel
          kicker="Chart"
          title={`${selected.symbol} · M1`}
          subtitle="Last 1,500 stored bars. Existing zones are overlays; the candle data is never modified."
          action={<StatusPill tone={drawMode ? "gold" : "neutral"}>{drawMode ? "draw mode" : "inspect"}</StatusPill>}
        >
          <ZoneChart
            bars={bars}
            symbol={selected.symbol}
            zones={zones}
            drawMode={drawMode}
            onDraw={(value) => {
              setDrawMode(false);
              setEditing(null);
              setDraft(value);
              setModalOpen(true);
            }}
          />
        </Panel>
      ) : null}

      <Panel kicker="Zones" title={`Annotations · ${zones.length}`} flush>
        {zones.length ? (
          <div className="zone-list">
            {zones.map((zone) => (
              <div className="zone-row" key={zone.id}>
                <div>
                  <div className="zone-row-head">
                    <span className={`tag ${zone.zone_type}`}>{zone.zone_type}</span>
                    <strong>{zone.low} – {zone.high}</strong>
                    <StatusPill tone={zone.status === "active" ? "ok" : zone.status === "invalidated" ? "warn" : "neutral"}>{zone.status}</StatusPill>
                    {zone.legacy ? <span className="tag">legacy config</span> : null}
                  </div>
                  <div className="zone-row-meta mono">
                    {zone.id} · v{zone.version} · {zone.source_timeframe} · strength {zone.strength}
                    {zone.effective_timestamp ? ` · effective ${formatDateTime(zone.effective_timestamp)}` : ""}
                    {zone.invalidation_timestamp ? ` · invalid ${formatDateTime(zone.invalidation_timestamp)}` : ""}
                  </div>
                  {zone.notes ? <p className="workspace-prose">{zone.notes}</p> : null}
                </div>
                <div className="workspace-inline-actions">
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={<Pencil size={12} />}
                    disabled={zone.legacy}
                    onClick={() => { setEditing(zone); setDraft(null); setModalOpen(true); }}
                  >
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={<Archive size={12} />}
                    disabled={zone.legacy || zone.status === "archived"}
                    onClick={async () => {
                      if (!window.confirm(`Archive zone ${zone.id}? Its versions remain in history.`)) return;
                      try {
                        await zoneApi.archive(zone.id);
                        notify("Zone archived.");
                        loadZones();
                      } catch (reason) {
                        setActionError(reason instanceof Error ? reason.message : "Could not archive zone.");
                      }
                    }}
                  >
                    Archive
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ padding: 20 }}>
            <EmptyState title="No zones for this dataset" copy="Draw a rectangle or create a zone with exact boundaries." />
          </div>
        )}
      </Panel>

      {actionError ? <div className="form-error">{actionError}</div> : null}

      <Modal
        open={modalOpen}
        title={editing ? "Edit zone (new version)" : "Create zone"}
        copy="Every edit appends a version; historical experiment references are never overwritten."
        onClose={() => { if (!saving) setModalOpen(false); }}
        footer={
          <>
            <Button variant="ghost" onClick={() => setModalOpen(false)} disabled={saving}>Cancel</Button>
            <Button
              variant="primary"
              disabled={saving}
              onClick={() => {
                const form = document.getElementById("zone-form") as HTMLFormElement | null;
                if (!form) return;
                const data = new FormData(form);
                const low = Number(data.get("low"));
                const high = Number(data.get("high"));
                const effective = toIso(String(data.get("effective_timestamp") || ""));
                const invalidation = toIso(String(data.get("invalidation_timestamp") || ""));
                const strategyId = String(data.get("strategy_id") || "");
                const variationId = String(data.get("variation_id") || "");
                saveZone({
                  dataset_id: selectedId,
                  source_timeframe: String(data.get("source_timeframe") || "M1"),
                  zone_type: String(data.get("zone_type") || "neutral"),
                  low,
                  high,
                  start_timestamp: effective,
                  effective_timestamp: effective,
                  invalidation_timestamp: invalidation,
                  status: String(data.get("status") || "active"),
                  strength: Number(data.get("strength")),
                  notes: String(data.get("notes") || ""),
                  strategy_id: strategyId || undefined,
                  variation_id: variationId || undefined,
                  historical_import: Boolean(data.get("historical_import")),
                  import_source: String(data.get("import_source") || "") || undefined,
                  import_operator: String(data.get("import_operator") || "") || undefined,
                });
              }}
            >
              {saving ? "Saving…" : "Save zone"}
            </Button>
          </>
        }
      >
        <form id="zone-form" className="form-grid" onSubmit={(event) => event.preventDefault()}>
          <Field label="Dataset"><input className="input mono" value={selectedId} readOnly /></Field>
          <Field label="Source timeframe">
            <select className="select" name="source_timeframe" defaultValue={formInitial.source_timeframe}>
              {["M1", "M5", "M15", "H1", "H4", "D1", "WEEKLY", "DAILY"].map((tf) => <option key={tf}>{tf}</option>)}
            </select>
          </Field>
          <Field label="Zone type">
            <select className="select" name="zone_type" defaultValue={formInitial.zone_type}>
              <option value="supply">Supply</option>
              <option value="demand">Demand</option>
              <option value="neutral">Neutral</option>
            </select>
          </Field>
          <Field label="Strength (0–10)"><input className="input mono" name="strength" type="number" min="0" max="10" defaultValue={formInitial.strength} /></Field>
          <Field label="Lower price"><input className="input mono" name="low" type="number" step="0.00001" defaultValue={formInitial.low || ""} /></Field>
          <Field label="Upper price"><input className="input mono" name="high" type="number" step="0.00001" defaultValue={formInitial.high || ""} /></Field>
          <Field label="Effective from" hint="Zone is unavailable before this UTC timestamp."><input className="input mono" name="effective_timestamp" type="datetime-local" defaultValue={toLocalInput(formInitial.effective_timestamp)} /></Field>
          <Field label="Invalidation (optional)"><input className="input mono" name="invalidation_timestamp" type="datetime-local" defaultValue={toLocalInput(formInitial.invalidation_timestamp)} /></Field>
          <Field label="Status">
            <select className="select" name="status" defaultValue={formInitial.status}>
              <option value="active">Active</option>
              <option value="invalidated">Invalidated</option>
              <option value="archived">Archived</option>
            </select>
          </Field>
          <Field label="Associate strategy (optional)">
            <select className="select" name="strategy_id" defaultValue={formInitial.strategy_id ?? ""}>
              <option value="">None</option>
              {strategies.map((strategy) => <option key={strategy.id} value={strategy.id}>{strategy.title}</option>)}
            </select>
          </Field>
          <Field label="Associate variation ID (optional)" span hint="Paste a workspace variation ID; the API validates nothing beyond the string.">
            <input className="input mono" name="variation_id" defaultValue={formInitial.variation_id ?? ""} />
          </Field>
          <Field label="Notes" span><textarea className="input" name="notes" rows={3} defaultValue={formInitial.notes} /></Field>
          <Field label="Historical import?" span hint="Manual zones cannot become effective before creation. Check this for documented historical annotations; source and operator are required.">
            <span className="checkbox-row">
              <input type="checkbox" name="historical_import" defaultChecked={formInitial.historical_import ?? false} />
              Audited historical import
            </span>
          </Field>
          <Field label="Import source"><input className="input" name="import_source" defaultValue={formInitial.import_source ?? "zone-manager"} /></Field>
          <Field label="Import operator"><input className="input" name="import_operator" defaultValue={formInitial.import_operator ?? "local-user"} /></Field>
        </form>
      </Modal>
    </div>
  );
}
