import { useEffect, useMemo, useRef, useState } from "react";
import { CalendarRange, Info, Play, ShieldAlert } from "lucide-react";
import { api, p1Api, workspaceApi } from "../api";
import type {
  BarPoint,
  CostProfile,
  DatasetSummary,
  RangeSummary,
  RunDetail,
  ExperimentKind,
  PreflightResult,
  RunValidation,
  StrategySummary,
  TradeRow,
  WorkspaceRunPreset,
} from "../types";
import { Button } from "../components/Button";
import { EquityCharts, PriceChart } from "../components/Charts";
import { DataTable, type Column } from "../components/DataTable";
import { HelpLink } from "../components/HelpLink";
import { HelpTip } from "../components/HelpTip";
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
  formatDate,
  formatDateTime,
  formatDecimal,
  formatInteger,
  formatPercent,
  formatPrice,
  formatR,
  providerLabel,
  statusTone,
} from "../lib/format";

type ParamValue = number | boolean | string;
type Preset = "1M" | "3M" | "6M" | "12M" | "custom";

const TIMEFRAMES = ["M1", "M5", "M15", "H1", "H4"];
const PRESETS: { id: Preset; label: string; months?: number }[] = [
  { id: "1M", label: "1 month", months: 1 },
  { id: "3M", label: "3 months", months: 3 },
  { id: "6M", label: "6 months", months: 6 },
  { id: "12M", label: "12 months", months: 12 },
  { id: "custom", label: "Custom" },
];

function defaultsFor(strategy: StrategySummary | undefined): Record<string, ParamValue> {
  const result: Record<string, ParamValue> = {};
  for (const parameter of strategy?.parameters ?? []) {
    result[parameter.name] = parameter.default;
  }
  return result;
}

function dateOnly(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : "";
}

function subtractMonths(dateString: string, months: number): string {
  const date = new Date(`${dateString}T00:00:00Z`);
  date.setUTCMonth(date.getUTCMonth() - months);
  return date.toISOString().slice(0, 10);
}

export function ResearchPage({
  refreshKey,
  onRefresh,
  onOpenHelp,
  workspacePreset,
}: {
  refreshKey: number;
  onRefresh: () => void;
  onOpenHelp: (article: string) => void;
  workspacePreset?: WorkspaceRunPreset | null;
}) {
  const { notify } = useToast();
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [strategies, setStrategies] = useState<StrategySummary[]>([]);
  const [costProfiles, setCostProfiles] = useState<CostProfile[]>([]);
  const [costProfileId, setCostProfileId] = useState("zero_costs");
  const [preflight, setPreflight] = useState<PreflightResult | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [validation, setValidation] = useState<RunValidation | null>(null);
  const [instrument, setInstrument] = useState("");
  const [timeframe, setTimeframe] = useState("M1");
  const [datasetChoice, setDatasetChoice] = useState("");
  const [frame, setFrame] = useState<DatasetSummary | null>(null);
  const [frameLoading, setFrameLoading] = useState(false);
  const [range, setRange] = useState<RangeSummary | null>(null);
  const [rangeLoading, setRangeLoading] = useState(false);
  const [preset, setPreset] = useState<Preset>("1M");
  const [presetNote, setPresetNote] = useState("");
  const [strategyChoice, setStrategyChoice] = useState("");
  const [parameters, setParameters] = useState<Record<string, ParamValue>>({});
  const [rMultiple, setRMultiple] = useState("2");
  const [equity, setEquity] = useState("100000");
  const [riskFraction, setRiskFraction] = useState("0.01");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [chartBars, setChartBars] = useState<BarPoint[]>([]);
  const [tradePage, setTradePage] = useState(0);
  const [workspaceContext, setWorkspaceContext] = useState<WorkspaceRunPreset | null>(
    workspacePreset ?? null,
  );
  const [workspaceKind, setWorkspaceKind] = useState<ExperimentKind | "auto">(
    workspacePreset?.experiment_kind ?? "auto",
  );
  const userRangeRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([api.datasets(), api.strategies(), p1Api.costProfiles()])
      .then(([datasetList, strategyList, profiles]) => {
        if (cancelled) return;
        setDatasets(datasetList);
        setStrategies(strategyList);
        setCostProfiles(profiles);
        setCostProfileId((current) =>
          profiles.some((item) => item.id === current)
            ? current
            : profiles.find((item) => item.id === "zero_costs")?.id ?? profiles[0]?.id ?? "zero_costs",
        );
        const firstInstrument = datasetList[0]?.symbol ?? "";
        setInstrument((current) => current || firstInstrument);
        const simulated =
          strategyList.find((item) => item.trade_simulation && !item.requires_zones) ??
          strategyList.find((item) => item.trade_simulation);
        setStrategyChoice((current) => current || simulated?.id || strategyList[0]?.id || "");
        setError("");
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
    if (!workspacePreset) {
      setWorkspaceContext(null);
      return;
    }
    setWorkspaceContext(workspacePreset);
    setWorkspaceKind(workspacePreset.experiment_kind ?? "auto");
    setStrategyChoice(workspacePreset.strategy_id);
    if (workspacePreset.instrument) setInstrument(workspacePreset.instrument);
    if (workspacePreset.timeframe) setTimeframe(workspacePreset.timeframe);
    if (workspacePreset.dataset_id) setDatasetChoice(workspacePreset.dataset_id);
  }, [workspacePreset]);

  useEffect(() => {
    if (!workspaceContext?.dataset_id) return;
    if (datasets.some((dataset) => dataset.id === workspaceContext.dataset_id)) {
      setDatasetChoice(workspaceContext.dataset_id);
    }
  }, [datasets, workspaceContext]);

  const instruments = useMemo(
    () => Array.from(new Set(datasets.map((dataset) => dataset.symbol))).sort(),
    [datasets],
  );
  const instrumentDatasets = useMemo(
    () => datasets.filter((dataset) => dataset.symbol === instrument),
    [datasets, instrument],
  );
  const selectedStrategy = useMemo(
    () => strategies.find((item) => item.id === strategyChoice),
    [strategies, strategyChoice],
  );

  useEffect(() => {
    if (!instrumentDatasets.length) {
      setDatasetChoice("");
      return;
    }
    if (!instrumentDatasets.some((dataset) => dataset.id === datasetChoice)) {
      setDatasetChoice(instrumentDatasets[0].id);
    }
  }, [instrumentDatasets, datasetChoice]);

  useEffect(() => {
    if (!datasetChoice) {
      setFrame(null);
      return;
    }
    let cancelled = false;
    userRangeRef.current = false;
    setFrameLoading(true);
    api
      .frame(datasetChoice, timeframe)
      .then((result) => {
        if (cancelled) return;
        setFrame(result);
        setRange(null);
        const first = dateOnly(result.first_timestamp);
        const last = dateOnly(result.last_timestamp);
        if (!first || !last) {
          setStartDate("");
          setEndDate("");
          setPresetNote("This frame has no usable bars.");
          return;
        }
        if (userRangeRef.current) return;
        const start = subtractMonths(last, 1);
        const clipped = start < first;
        setStartDate(clipped ? first : start);
        setEndDate(last);
        setPreset("1M");
        setPresetNote(
          clipped
            ? "The 1-month preset was adjusted to the dataset's available range."
            : "",
        );
      })
      .catch((reason: Error) => {
        if (!cancelled) {
          setFrame(null);
          setFormError(reason.message);
        }
      })
      .finally(() => {
        if (!cancelled) setFrameLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [datasetChoice, timeframe]);

  useEffect(() => {
    const defaults = defaultsFor(selectedStrategy);
    if (workspaceContext && selectedStrategy?.id === workspaceContext.strategy_id) {
      setParameters({ ...defaults, ...workspaceContext.parameters });
    } else {
      setParameters(defaults);
    }
    setFormError("");
  }, [selectedStrategy, workspaceContext]);

  useEffect(() => {
    if (run) window.scrollTo({ top: 0, behavior: "smooth" });
  }, [run?.id]);

  useEffect(() => {
    if (!datasetChoice || !timeframe || !startDate || !endDate) {
      setRange(null);
      return;
    }
    let cancelled = false;
    setRangeLoading(true);
    const timer = window.setTimeout(() => {
      api
        .range(datasetChoice, timeframe, startDate, endDate)
        .then((result) => {
          if (!cancelled) setRange(result);
        })
        .catch((reason: Error) => {
          if (!cancelled) setFormError(reason.message);
        })
        .finally(() => {
          if (!cancelled) setRangeLoading(false);
        });
    }, 260);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [datasetChoice, timeframe, startDate, endDate]);

  useEffect(() => {
    if (!datasetChoice || !strategyChoice || !timeframe || !startDate || !endDate) {
      setPreflight(null);
      return;
    }
    let cancelled = false;
    setPreflightLoading(true);
    const timer = window.setTimeout(() => {
      p1Api
        .validateBacktest({
          dataset_id: datasetChoice,
          strategy_id: strategyChoice,
          timeframe,
          parameters,
          start_date: startDate,
          end_date: endDate,
          r_multiple: Number(rMultiple),
          equity: Number(equity),
          risk_fraction: Number(riskFraction),
          cost_profile_id: costProfileId,
          zone_ids: workspaceContext?.zone_ids ?? [],
        })
        .then((result) => {
          if (!cancelled) setPreflight(result);
        })
        .catch((reason: Error) => {
          if (!cancelled) {
            setPreflight({
              valid: false,
              errors: [{
                code: "PREFLIGHT_FAILED",
                severity: "error",
                component: "preflight",
                message: reason.message,
                suggestion: "Check the API and selected configuration.",
              }],
              warnings: [],
              info: [],
              details: {},
            });
          }
        })
        .finally(() => {
          if (!cancelled) setPreflightLoading(false);
        });
    }, 320);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    datasetChoice,
    strategyChoice,
    timeframe,
    startDate,
    endDate,
    rMultiple,
    equity,
    riskFraction,
    costProfileId,
    parameters,
  ]);

  function applyPreset(next: (typeof PRESETS)[number]) {
    if (!frame?.first_timestamp || !frame?.last_timestamp) return;
    userRangeRef.current = true;
    if (next.id === "custom") {
      setPreset("custom");
      setPresetNote("");
      return;
    }
    const first = dateOnly(frame.first_timestamp);
    const last = dateOnly(frame.last_timestamp);
    const candidate = subtractMonths(last, next.months ?? 1);
    const clipped = candidate < first;
    setStartDate(clipped ? first : candidate);
    setEndDate(last);
    setPreset(next.id);
    setPresetNote(
      clipped
        ? `The ${next.label} preset was adjusted to the dataset's available range.`
        : "",
    );
  }

  async function submit() {
    if (!datasetChoice || !strategyChoice) {
      setFormError("Select a dataset and a strategy first.");
      return;
    }
    if (!range) {
      setFormError("Wait for the range validation to finish, or choose valid dates.");
      return;
    }
    if (!range.valid) {
      setFormError(range.error || "The selected range is invalid.");
      return;
    }
    const r = Number(rMultiple);
    const cap = Number(equity);
    const risk = Number(riskFraction);
    if (!Number.isFinite(r) || r <= 0) {
      setFormError("R multiple must be a positive number.");
      return;
    }
    if (!Number.isFinite(cap) || cap <= 0) {
      setFormError("Equity must be a positive number.");
      return;
    }
    if (!Number.isFinite(risk) || risk <= 0 || risk > 0.1) {
      setFormError("Risk fraction must be between 0 and 0.1.");
      return;
    }
    setRunning(true);
    setFormError("");
    try {
      const result = await api.backtest({
        dataset_id: datasetChoice,
        strategy_id: strategyChoice,
        timeframe,
        parameters,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        r_multiple: r,
        equity: cap,
        risk_fraction: risk,
        cost_profile_id: costProfileId,
        zone_ids: workspaceContext?.zone_ids ?? [],
      });
      setRun(result);
      setTradePage(0);
      notify(
        `Run archived · ${result.strategy.name} · ${timeframe} · ${formatInteger(
          result.range.bar_count,
        )} bars`,
      );
      onRefresh();
      p1Api
        .validateRun(result.id)
        .then(setValidation)
        .catch(() => setValidation(null));
      if (
        workspaceContext &&
        result.strategy.id === workspaceContext.strategy_id
      ) {
        try {
          await workspaceApi.recordExperiment(workspaceContext.strategy_record_id, {
            variation_id: workspaceContext.variation_id,
            run_id: result.id,
            name: `${workspaceContext.variation_title} · ${datasetChoice} · ${timeframe}`,
            hypothesis: workspaceContext.hypothesis,
            experiment_kind:
              workspaceKind === "auto" ? undefined : workspaceKind,
          });
          notify(`Experiment linked to ${workspaceContext.variation_title}.`);
        } catch (reason) {
          setFormError(
            `Run archived, but the workspace experiment link failed: ${
              reason instanceof Error ? reason.message : "unknown error"
            }`,
          );
        }
      }
      try {
        const bars = await api.bars(
          datasetChoice,
          timeframe,
          1500,
          result.range.start,
          result.range.end,
        );
        setChartBars(bars);
      } catch {
        setChartBars([]);
      }
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "Backtest failed.");
    } finally {
      setRunning(false);
    }
  }

  const tradeColumns: Column<TradeRow>[] = [
    {
      key: "direction",
      header: "Side",
      render: (trade) => (
        <StatusPill tone={trade.direction === "LONG" ? "ok" : "danger"}>
          {trade.direction}
        </StatusPill>
      ),
    },
    {
      key: "entry",
      header: "Entry",
      render: (trade) => (
        <span className="mono" style={{ fontSize: 9 }}>
          {formatDateTime(trade.entry_time)}
        </span>
      ),
    },
    {
      key: "prices",
      header: "Entry / Exit",
      render: (trade) => (
        <span className="mono" style={{ fontSize: 9 }}>
          {formatPrice(trade.entry_price, trade.symbol)} →{" "}
          {formatPrice(trade.exit_price, trade.symbol)}
        </span>
      ),
    },
    {
      key: "risk",
      header: "Risk planned → realised",
      align: "right",
      render: (trade) => (
        <span className="mono" style={{ fontSize: 9 }}>
          {formatDecimal(trade.planned_risk_amount, 0)} →{" "}
          {formatDecimal(trade.realized_risk_amount, 0)}
        </span>
      ),
    },
    {
      key: "reason",
      header: "Exit",
      render: (trade) => (
        <span className="tag" title={trade.execution_assumption || trade.close_reason}>
          {trade.close_reason}
        </span>
      ),
    },
    {
      key: "pnl",
      header: "R",
      align: "right",
      render: (trade) => (
        <span className={`trade-pnl ${trade.pnl_r >= 0 ? "win" : "loss"}`}>
          {formatR(trade.pnl_r)}
        </span>
      ),
    },
    {
      key: "net",
      header: "Net R",
      align: "right",
      render: (trade) => (
        <span className={`trade-pnl ${(trade.net_pnl_r ?? trade.pnl_r) >= 0 ? "win" : "loss"}`}>
          {formatR(trade.net_pnl_r ?? trade.pnl_r)}
        </span>
      ),
    },
    {
      key: "hold",
      header: "Hold",
      align: "right",
      render: (trade) =>
        `${trade.holding_duration_candles} ${
          trade.holding_duration_candles === 1 ? "bar" : "bars"
        }`,
    },
  ];

  if (loading && !datasets.length) return <LoadingState label="Loading research catalog" />;
  if (error) return <ErrorState message={error} />;

  const rangeValid = Boolean(range?.valid);
  const canRun = rangeValid && !preflightLoading && Boolean(preflight?.valid);
  const minDate = dateOnly(frame?.first_timestamp);
  const maxDate = dateOnly(frame?.last_timestamp);

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Strategy lab · causal replay"
        title="Ask a falsifiable question."
        subtitle="Instrument, timeframe, dataset, and range are separate choices. REX validates every range against the actual bars and reports the limits beside the result."
        actions={
          <Button
            variant="primary"
            icon={<Play size={14} />}
            loading={running}
            onClick={submit}
            disabled={!datasets.length || !strategies.length || !canRun}
          >
            Run backtest
          </Button>
        }
      />

      {workspaceContext ? (
        <div className="workspace-lab-banner">
          <div>
            <span className="panel-kicker">Workspace experiment</span>
            <strong>{workspaceContext.variation_title}</strong>
            <span className="mono faint">{workspaceContext.strategy_id}</span>
          </div>
          <span className="field-hint">
            The run will be linked to this variation after the existing BacktestRunner archives it.
          </span>
          <label className="workspace-kind-select">
            <span className="workspace-context-label">Experiment kind</span>
            <select
              className="select"
              value={workspaceKind}
              onChange={(event) =>
                setWorkspaceKind(event.target.value as ExperimentKind | "auto")
              }
            >
              <option value="auto">Auto (baseline / repeat / experiment)</option>
              <option value="baseline">Baseline</option>
              <option value="experiment">Experimental variation</option>
              <option value="repeat">Repeated experiment</option>
              <option value="out_of_sample">Out-of-sample validation</option>
            </select>
          </label>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setWorkspaceContext(null);
              setWorkspaceKind("auto");
              setFormError("");
            }}
          >
            Clear context
          </Button>
        </div>
      ) : null}

      {!datasets.length ? (
        <EmptyState
          title="No dataset available"
          copy="The lab needs a stored M1 partition. Acquire one in Market Data first."
        />
      ) : (
        <div className="grid-research">
          <div className="stack">
            <Panel
              kicker="Configuration"
              title="Experiment"
              subtitle="The terminal composes the existing kernel; it does not change strategy logic."
              action={
                <HelpLink onClick={() => onOpenHelp("terminal-workflow")}>
                  Workflow
                </HelpLink>
              }
            >
              <div className="form-grid">
                <Field label="Instrument">
                  <select
                    className="select"
                    value={instrument}
                    onChange={(event) => setInstrument(event.target.value)}
                  >
                    {instruments.map((symbol) => (
                      <option key={symbol} value={symbol}>
                        {symbol}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Timeframe" hint="M5–H4 are derived from M1.">
                  <select
                    className="select"
                    value={timeframe}
                    onChange={(event) => setTimeframe(event.target.value)}
                  >
                    {TIMEFRAMES.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Dataset" span hint="Only stored M1 partitions are listed.">
                  <select
                    className="select"
                    value={datasetChoice}
                    onChange={(event) => setDatasetChoice(event.target.value)}
                  >
                    {instrumentDatasets.map((dataset) => (
                      <option key={dataset.id} value={dataset.id}>
                        {dataset.id} · {formatInteger(dataset.bar_count)} M1 bars
                      </option>
                    ))}
                  </select>
                </Field>
              </div>

              <div className="preset-block">
                <div className="preset-label">
                  <CalendarRange size={13} strokeWidth={1.5} />
                  <span>Date range</span>
                  <HelpLink onClick={() => onOpenHelp("choose-dataset")}>
                    Why ranges fail
                  </HelpLink>
                </div>
                <div className="preset-row">
                  {PRESETS.map((item) => (
                    <button
                      key={item.id}
                      className={`preset ${preset === item.id ? "active" : ""}`}
                      onClick={() => applyPreset(item)}
                      disabled={!frame}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <div className="form-grid" style={{ marginTop: 10 }}>
                  <Field label="Start date" hint={minDate ? `Earliest ${minDate}` : undefined}>
                    <input
                      className="input mono"
                      type="date"
                      value={startDate}
                      min={minDate || undefined}
                      max={maxDate || undefined}
                      onChange={(event) => {
                        userRangeRef.current = true;
                        setPreset("custom");
                        setPresetNote("");
                        setStartDate(event.target.value);
                      }}
                    />
                  </Field>
                  <Field label="End date" hint={maxDate ? `Latest ${maxDate}` : undefined}>
                    <input
                      className="input mono"
                      type="date"
                      value={endDate}
                      min={minDate || undefined}
                      max={maxDate || undefined}
                      onChange={(event) => {
                        userRangeRef.current = true;
                        setPreset("custom");
                        setPresetNote("");
                        setEndDate(event.target.value);
                      }}
                    />
                  </Field>
                </div>
                {presetNote ? <p className="field-hint">{presetNote}</p> : null}
                {rangeLoading ? (
                  <p className="field-hint">Validating range against stored bars…</p>
                ) : range ? (
                  <div className={`range-summary ${range.valid ? "" : "invalid"}`}>
                    <span className="mono">
                      {formatInteger(range.bar_count)} {timeframe} bars in range
                    </span>
                    <span className="mono">
                      {range.gap_count} gap{range.gap_count === 1 ? "" : "s"}
                    </span>
                    <span className="mono">
                      {formatDate(range.first_available)} → {formatDate(range.last_available)}
                    </span>
                  </div>
                ) : null}
              </div>

              {frame ? (
                <div className="dataset-facts">
                  <div className="dataset-facts-head">
                    <span>Dataset facts</span>
                    <StatusPill tone={statusTone(frame.status)}>
                      {frame.derived ? "Derived" : providerLabel(frame.provider)}
                    </StatusPill>
                  </div>
                  <div className="dataset-fact-grid">
                    <div>
                      <span>Instrument</span>
                      <strong>{frame.symbol}</strong>
                    </div>
                    <div>
                      <span>Frame</span>
                      <strong>{frame.timeframe}</strong>
                    </div>
                    <div>
                      <span>First bar</span>
                      <strong>{formatDateTime(frame.first_timestamp)}</strong>
                    </div>
                    <div>
                      <span>Last bar</span>
                      <strong>{formatDateTime(frame.last_timestamp)}</strong>
                    </div>
                    <div>
                      <span>Total bars</span>
                      <strong>{formatInteger(frame.bar_count)}</strong>
                    </div>
                    <div>
                      <span>Range bars</span>
                      <strong>{range ? formatInteger(range.bar_count) : "—"}</strong>
                    </div>
                  </div>
                  <div className="dataset-facts-foot">
                    <span>
                      Provider: {providerLabel(frame.provider)}
                      {frame.derived ? " · derived from M1" : ""}
                    </span>
                    <span>
                      Gaps in range:{" "}
                      {range ? formatInteger(range.gap_count) : "—"}
                    </span>
                  </div>
                  {frame.warnings.length ? (
                    <div className="dataset-warning">
                      <Info size={12} strokeWidth={1.5} />
                      <span>{frame.warnings[0]}</span>
                    </div>
                  ) : null}
                  <div className="btn-row">
                    <HelpLink onClick={() => onOpenHelp("storage-provenance")}>
                      Understand provenance
                    </HelpLink>
                    <HelpLink onClick={() => onOpenHelp("missing-timestamps")}>
                      Gaps explained
                    </HelpLink>
                  </div>
                </div>
              ) : frameLoading ? (
                <p className="field-hint">Reading dataset frame…</p>
              ) : null}

              <div className="divider" />
              <div className="form-grid">
                <Field label="Strategy" span>
                  <select
                    className="select"
                    value={strategyChoice}
                    onChange={(event) => {
                      const next = event.target.value;
                      setStrategyChoice(next);
                      if (workspaceContext && workspaceContext.strategy_id !== next) {
                        setWorkspaceContext(null);
                      }
                    }}
                  >
                    {strategies.map((strategy) => (
                      <option key={strategy.id} value={strategy.id}>
                        {strategy.id} · {strategy.name}
                      </option>
                    ))}
                  </select>
                </Field>
                {selectedStrategy?.parameters.map((parameter) => (
                  <Field
                    key={parameter.name}
                    label={parameter.label}
                    hint={parameter.help}
                    span={parameter.type === "boolean"}
                  >
                    {parameter.type === "boolean" ? (
                      <span className="checkbox-row">
                        <input
                          type="checkbox"
                          checked={Boolean(parameters[parameter.name])}
                          onChange={(event) =>
                            setParameters((current) => ({
                              ...current,
                              [parameter.name]: event.target.checked,
                            }))
                          }
                        />
                        Enabled
                      </span>
                    ) : (
                      <input
                        className="input mono"
                        type="number"
                        min={parameter.min}
                        max={parameter.max}
                        step={parameter.step}
                        value={String(parameters[parameter.name] ?? parameter.default)}
                        onChange={(event) =>
                          setParameters((current) => ({
                            ...current,
                            [parameter.name]:
                              parameter.type === "integer"
                                ? Number.parseInt(event.target.value, 10)
                                : Number.parseFloat(event.target.value),
                          }))
                        }
                      />
                    )}
                  </Field>
                ))}
                <Field label="R multiple" hint="Fixed target multiple of initial risk.">
                  <input
                    className="input mono"
                    type="number"
                    min="0.1"
                    step="0.1"
                    value={rMultiple}
                    onChange={(event) => setRMultiple(event.target.value)}
                  />
                </Field>
                <Field label="Account equity" hint="Used by the existing fixed-risk sizer.">
                  <input
                    className="input mono"
                    type="number"
                    min="1"
                    step="1000"
                    value={equity}
                    onChange={(event) => setEquity(event.target.value)}
                  />
                </Field>
                <Field label="Risk fraction" hint="Fraction of equity risked per trade.">
                  <input
                    className="input mono"
                    type="number"
                    min="0.001"
                    max="0.1"
                    step="0.001"
                    value={riskFraction}
                    onChange={(event) => setRiskFraction(event.target.value)}
                  />
                </Field>
                <Field label="Cost profile" hint={costProfiles.find((item) => item.id === costProfileId)?.description}>
                  <select
                    className="select"
                    value={costProfileId}
                    onChange={(event) => setCostProfileId(event.target.value)}
                  >
                    {costProfiles.map((profile) => (
                      <option key={profile.id} value={profile.id}>
                        {profile.name}{profile.estimated ? " · estimated proxy" : ""}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>

              <div className="form-help-row">
                <HelpLink onClick={() => onOpenHelp("r-multiple")}>
                  What is an R-multiple?
                </HelpLink>
                <HelpLink onClick={() => onOpenHelp("strategies")}>
                  Strategy behavior
                </HelpLink>
              </div>

              {selectedStrategy ? (
                <p className="field-hint" style={{ marginTop: 8 }}>
                  {selectedStrategy.note}
                </p>
              ) : null}

              {range && !range.valid ? (
                <div className="form-error" style={{ marginTop: 12 }}>
                  {range.error}
                </div>
              ) : null}
              {formError && !(range && !range.valid) ? (
                <div className="form-error" style={{ marginTop: 12 }}>
                  {formError}
                </div>
              ) : null}

              <div className="form-actions">
                <Button
                  variant="primary"
                  onClick={submit}
                  loading={running}
                  disabled={!canRun}
                >
                  Execute on existing kernel
                </Button>
              </div>
            </Panel>

            <Panel
              kicker="Preflight"
              title="Validation before execution"
              subtitle="Structured checks over the selected dataset, strategy, range, zones and cost profile."
            >
              {preflightLoading ? (
                <p className="field-hint">Validating configuration against stored data…</p>
              ) : preflight ? (
                <>
                  {preflight.errors.length ? (
                    <div className="notice-list">
                      {preflight.errors.map((issue) => (
                        <div className="notice-row" key={`${issue.code}-${issue.message}`}>
                          <ShieldAlert size={13} strokeWidth={1.5} />
                          <span>
                            <strong>{issue.code}</strong> · {issue.message}{" "}
                            <span className="field-hint">{issue.suggestion}</span>
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="notice-row ok">
                      <span className="mono" style={{ color: "var(--emerald)" }}>✓</span>
                      <span>No blocking validation errors.</span>
                    </div>
                  )}
                  {preflight.warnings.length ? (
                    <>
                      <div className="divider" />
                      <div className="notice-list">
                        {preflight.warnings.map((issue) => (
                          <div className="notice-row" key={`${issue.code}-${issue.message}`}>
                            <span className="mono" style={{ color: "var(--gold)" }}>!</span>
                            <span>{issue.message}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : null}
                </>
              ) : (
                <p className="field-hint">Choose a dataset and strategy to validate the run.</p>
              )}
            </Panel>

            <Panel kicker="Read before trusting" title="Execution assumptions">
              <div className="detail-list">
                <div className="detail-row">
                  <span className="detail-key">Costs</span>
                  <span className="detail-value">not applied</span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Entry model</span>
                  <span className="detail-value">next candle open</span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Result units</span>
                  <span className="detail-value">R-multiples</span>
                </div>
                <div className="detail-row">
                  <span className="detail-key">Zones</span>
                  <span className="detail-value">
                    {selectedStrategy?.requires_zones ? "manual / static" : "not used"}
                  </span>
                </div>
              </div>
            </Panel>
          </div>

          <div className="stack">
            {run ? (
              <>
                <Panel
                  kicker="Run result"
                  title={run.strategy.name}
                  subtitle={`${run.dataset_id} · ${run.request.timeframe} · ${formatDate(
                    run.range.start,
                  )} → ${formatDate(run.range.end)} · ${formatInteger(
                    run.range.bar_count,
                  )} bars`}
                  action={
                    <StatusPill tone={run.simulated ? "gold" : "warn"}>
                      {run.simulated ? "Trade simulation" : "Signal study"}
                    </StatusPill>
                  }
                >
                  <div className="metric-grid">
                    <div className="metric">
                      <div className="metric-label">Signals</div>
                      <div className="metric-value small">
                        {formatInteger(run.metrics.total_signals)}
                      </div>
                    </div>
                    <div className="metric">
                      <div className="metric-label">Closed trades</div>
                      <div className="metric-value small">
                        {formatInteger(run.metrics.total_trades)}
                      </div>
                    </div>
                    <div className="metric">
                      <div className="metric-label">
                        Win rate
                        <HelpTip
                          label="Win rate"
                          definition="Wins divided by decided outcomes. It ignores the size of winners and losers."
                          onOpen={() => onOpenHelp("win-rate")}
                        />
                      </div>
                      <div className="metric-value small">
                        {formatPercent(run.metrics.win_rate)}
                      </div>
                    </div>
                    <div className="metric">
                      <div className="metric-label">
                        Expectancy
                        <HelpTip
                          label="Expectancy"
                          definition="Average R per closed trade. It combines win rate and payoff but remains sample- and cost-dependent."
                          onOpen={() => onOpenHelp("expectancy")}
                        />
                      </div>
                      <div
                        className={`metric-value small ${
                          run.metrics.expectancy >= 0 ? "positive" : "negative"
                        }`}
                      >
                        {formatR(run.metrics.expectancy)}
                      </div>
                    </div>
                    <div className="metric">
                      <div className="metric-label">
                        Profit factor
                        <HelpTip
                          label="Profit factor"
                          definition="Gross positive R divided by absolute gross negative R. Undefined when there are no losses."
                          onOpen={() => onOpenHelp("profit-factor")}
                        />
                      </div>
                      <div className="metric-value small">
                        {run.metrics.profit_factor === null
                          ? "—"
                          : formatDecimal(run.metrics.profit_factor, 2)}
                      </div>
                    </div>
                    <div className="metric">
                      <div className="metric-label">
                        Max drawdown
                        <HelpTip
                          label="Maximum drawdown"
                          definition="Largest peak-to-trough decline in cumulative R. It is not currency equity."
                          onOpen={() => onOpenHelp("max-drawdown")}
                        />
                      </div>
                      <div className="metric-value small negative">
                        {formatDecimal(run.metrics.max_drawdown_r, 2)}R
                      </div>
                    </div>
                    <div className="metric">
                      <div className="metric-label">Ambiguous exits</div>
                      <div className="metric-value small">
                        {run.metrics.ambiguous_exits}
                      </div>
                    </div>
                    <div className="metric">
                      <div className="metric-label">Avg hold</div>
                      <div className="metric-value small">
                        {formatDecimal(run.metrics.avg_holding_duration, 1)} bars
                      </div>
                    </div>
                  </div>

                  {run.warnings.length ? (
                    <div className="notice-list" style={{ marginTop: 16 }}>
                      {run.warnings.map((warning) => (
                        <div className="notice-row" key={warning}>
                          <ShieldAlert size={13} strokeWidth={1.5} />
                          <span>{warning}</span>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  <div className="btn-row" style={{ marginTop: 12 }}>
                    <HelpLink onClick={() => onOpenHelp("read-results")}>
                      How to read this result
                    </HelpLink>
                    <HelpLink onClick={() => onOpenHelp("costs-slippage")}>
                      Why costs matter
                    </HelpLink>
                  </div>

                  <div className="divider" />
                  <div className="grid-2">
                    <div>
                      <div className="panel-kicker">Signal distribution</div>
                      <div className="detail-list">
                        {Object.entries(run.signals.by_type).map(([type, count]) => (
                          <div className="detail-row" key={type}>
                            <span className="detail-key">{type}</span>
                            <span className="detail-value">{formatInteger(count)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="panel-kicker">Lifecycle reconciliation</div>
                      <div className="detail-list">
                        {Object.entries(run.reconciliation).map(([key, count]) => (
                          <div className="detail-row" key={key}>
                            <span className="detail-key">{key.replace(/_/g, " ")}</span>
                            <span className="detail-value">{formatInteger(count)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {run.trade_distribution?.length ? (
                    <div className="trade-cadence">
                      <div className="panel-kicker">Trade cadence by day</div>
                      <div className="cadence-bars">
                        {run.trade_distribution.map((point) => {
                          const max = Math.max(
                            ...run.trade_distribution.map((item) => item.trades),
                            1,
                          );
                          return (
                            <span
                              key={point.date}
                              className="cadence-bar"
                              title={`${point.date}: ${point.trades} trade${
                                point.trades === 1 ? "" : "s"
                              }`}
                              style={{
                                height: `${Math.max(5, (point.trades / max) * 100)}%`,
                              }}
                            />
                          );
                        })}
                      </div>
                      <div className="coverage-labels">
                        <span>{run.trade_distribution[0]?.date}</span>
                        <span>
                          {run.trade_distribution[run.trade_distribution.length - 1]?.date}
                        </span>
                      </div>
                    </div>
                  ) : null}
                </Panel>

                <Panel
                  kicker="Costs and independent validation"
                  title="Gross is not net"
                  subtitle={
                    run.cost_profile
                      ? `${run.cost_profile.name} · ${run.cost_profile.estimated ? "ESTIMATED PROXY" : "explicit assumption"}`
                      : "Legacy cost-free run"
                  }
                >
                  <div className="detail-list">
                    <div className="detail-row">
                      <span className="detail-key">Gross expectancy</span>
                      <span className="detail-value">{formatR(run.metrics.expectancy)}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-key">Net expectancy</span>
                      <span className={`detail-value ${(run.net_metrics?.expectancy ?? 0) < 0 ? "danger" : ""}`}>
                        {run.net_metrics ? formatR(run.net_metrics.expectancy) : "unavailable"}
                      </span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-key">Total costs</span>
                      <span className="detail-value">
                        {formatR(
                          run.trades.reduce((sum, trade) => sum + (trade.total_cost_r ?? 0), 0),
                        )}
                      </span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-key">Spread / slippage / commission / swap</span>
                      <span className="detail-value mono" style={{ fontSize: 9 }}>
                        {formatR(run.trades.reduce((sum, trade) => sum + (trade.spread_cost_r ?? 0), 0))} /{" "}
                        {formatR(run.trades.reduce((sum, trade) => sum + (trade.slippage_cost_r ?? 0), 0))} /{" "}
                        {formatR(run.trades.reduce((sum, trade) => sum + (trade.commission_cost_r ?? 0), 0))} /{" "}
                        {formatR(run.trades.reduce((sum, trade) => sum + (trade.swap_cost_r ?? 0), 0))}
                      </span>
                    </div>
                  </div>
                  <div className="divider" />
                  {validation ? (
                    <>
                      <div className="detail-list">
                        <div className="detail-row">
                          <span className="detail-key">Independent trade validation</span>
                          <span className="detail-value">
                            {validation.valid ? "pass" : `${validation.error_count} error(s)`} · {validation.checked_trades} trades
                          </span>
                        </div>
                        {validation.findings.slice(0, 5).map((finding) => (
                          <div className="detail-row" key={`${finding.code}-${finding.message}`}>
                            <span className="detail-key">{finding.severity}</span>
                            <span className="detail-value">{finding.message}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="field-hint">Validation runs after the archived result is available.</p>
                  )}
                  {run.cost_profile?.estimated ? (
                    <p className="field-hint">Net figures are estimated, not observed historical execution costs.</p>
                  ) : null}
                </Panel>

                <Panel
                  kicker="Price and markers"
                  title="Where the trades sat"
                  subtitle="Stored bars or derived frame; markers are simulated entries and exits, sampled when dense."
                  flush
                >
                  <div className="chart-legend">
                    <span className="legend-item">
                      <span className="legend-swatch" /> Entry
                    </span>
                    <span className="legend-item">
                      <span className="legend-swatch emerald" /> Profit exit
                    </span>
                    <span className="legend-item">
                      <span className="legend-swatch crimson" /> Loss exit
                    </span>
                  </div>
                  <div style={{ padding: 12 }}>
                    <PriceChart
                      bars={chartBars}
                      symbol={run.dataset.symbol}
                      trades={run.trades}
                      tall
                    />
                  </div>
                </Panel>

                <Panel
                  kicker="Performance path"
                  title="Cumulative R and drawdown"
                  subtitle="Derived in the backend from closed trades. Not currency equity; costs are not included."
                >
                  <EquityCharts
                    equity={run.equity_curve.equity}
                    drawdown={run.equity_curve.drawdown}
                  />
                </Panel>

                <Panel
                  kicker="Trade ledger"
                  title={`Closed trades · ${formatInteger(run.trades.length)}`}
                  subtitle={`Showing ${formatInteger(
                    Math.min(tradePage * 25 + 1, run.trades.length),
                  )}–${formatInteger(
                    Math.min((tradePage + 1) * 25, run.trades.length),
                  )} of ${formatInteger(run.trades.length)}${
                    run.trades_truncated ? " (simulator artifact capped at 2,000)" : ""
                  }.`}
                  flush
                >
                  <DataTable
                    columns={tradeColumns}
                    rows={run.trades.slice(tradePage * 25, tradePage * 25 + 25)}
                    getKey={(trade) =>
                      `${trade.entry_time}-${trade.exit_time}-${trade.entry_price}-${trade.pnl_r}`
                    }
                    empty="No closed trades in this run."
                  />
                  {run.trades.length > 25 ? (
                    <div
                      className="form-actions"
                      style={{
                        justifyContent: "space-between",
                        padding: "12px 20px 16px",
                        borderTop: "1px solid var(--rule)",
                      }}
                    >
                      <span className="field-hint">
                        Page {tradePage + 1} of {Math.ceil(run.trades.length / 25)}
                      </span>
                      <div style={{ display: "flex", gap: 8 }}>
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={tradePage === 0}
                          onClick={() => setTradePage((current) => Math.max(0, current - 1))}
                        >
                          Previous
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={(tradePage + 1) * 25 >= run.trades.length}
                          onClick={() =>
                            setTradePage((current) =>
                              Math.min(
                                Math.ceil(run.trades.length / 25) - 1,
                                current + 1,
                              ),
                            )
                          }
                        >
                          Next
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </Panel>
              </>
            ) : (
              <Panel kicker="Awaiting experiment" title="No run loaded">
                <EmptyState
                  title="Configure an experiment"
                  copy="Choose an instrument, timeframe, dataset, and validated range. REX will execute the existing kernel and archive the result."
                  action={
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={submit}
                      disabled={running || !canRun}
                    >
                      Run with current settings
                    </Button>
                  }
                />
              </Panel>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
