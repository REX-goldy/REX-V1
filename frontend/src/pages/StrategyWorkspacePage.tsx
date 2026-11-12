import { useCallback, useEffect, useState } from "react";
import {
  Archive,
  ArrowLeft,
  ChevronRight,
  Copy,
  FlaskConical,
  Pencil,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";
import { api, workspaceApi, workspaceDashboardApi, workspaceIntegrityApi } from "../api";
import type {
  ComparisonGroup,
  ComparisonRow,
  StrategyExperiment,
  StrategyNote,
  ResearchDashboard,
  StrategyStatus,
  StrategySummary,
  StrategyVariation,
  StrategyWorkspaceDetail,
  StrategyWorkspaceSummary,
  WorkspaceRules,
  WorkspaceRunPreset,
} from "../types";
import { Button } from "../components/Button";
import { DataTable, type Column } from "../components/DataTable";
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
import {
  formatDate,
  formatDateTime,
  formatDecimal,
  formatInteger,
  formatPercent,
  formatR,
} from "../lib/format";

const STATUSES: StrategyStatus[] = [
  "Draft",
  "Research",
  "Experimental",
  "Validated",
  "Archived",
];
const TIMEFRAMES = ["M1", "M5", "M15", "H1", "H4"];

function workspaceTone(status: string): "ok" | "warn" | "danger" | "neutral" | "gold" {
  if (status === "Validated") return "ok";
  if (status === "Experimental") return "gold";
  if (status === "Archived") return "neutral";
  if (status === "Draft") return "warn";
  return "neutral";
}

function splitList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinList(value: string[] | undefined): string {
  return (value ?? []).join(", ");
}

function parseJsonConfig(value: string): Record<string, number | boolean | string> {
  const parsed: unknown = JSON.parse(value || "{}");
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Parameter configuration must be a JSON object.");
  }
  for (const [key, item] of Object.entries(parsed as Record<string, unknown>)) {
    if (item !== null && !["string", "number", "boolean"].includes(typeof item)) {
      throw new Error(`Parameter ${key} must be a string, number, boolean or null.`);
    }
  }
  return parsed as Record<string, number | boolean | string>;
}

function metricText(value: number | null | undefined, digits = 2): string {
  return value === null || value === undefined ? "—" : formatDecimal(value, digits);
}

function rulesLines(value: string[] | undefined): string {
  return (value ?? []).join("\n");
}

interface StrategyFormProps {
  title: string;
  submitLabel: string;
  initial?: Partial<StrategyWorkspaceDetail> | null;
  registryOptions: StrategySummary[];
  saving: boolean;
  error: string;
  onSubmit: (payload: Record<string, unknown>) => void;
  onClose: () => void;
}

function StrategyForm({
  title,
  submitLabel,
  initial,
  registryOptions,
  saving,
  error,
  onSubmit,
  onClose,
}: StrategyFormProps) {
  const [form, setForm] = useState({
    title: initial?.title ?? "",
    short_description: initial?.short_description ?? "",
    description: initial?.description ?? "",
    hypothesis: initial?.hypothesis ?? "",
    research_objective: initial?.research_objective ?? "",
    trading_concept: initial?.trading_concept ?? "",
    risk_assumptions: initial?.risk_assumptions ?? "",
    category: initial?.category ?? "Uncategorised",
    status: initial?.status ?? "Draft",
    tags: joinList(initial?.tags),
    registry_strategy_id: initial?.registry_strategy_id ?? "",
    instruments: joinList(initial?.instruments),
    timeframes: joinList(initial?.timeframes) || TIMEFRAMES.join(", "),
  });

  const set = (key: keyof typeof form, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  return (
    <Modal
      open
      title={title}
      copy="Research documentation only. This does not change strategy code or execution rules."
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={saving}
            onClick={() =>
              onSubmit({
                title: form.title,
                short_description: form.short_description,
                description: form.description,
                hypothesis: form.hypothesis,
                research_objective: form.research_objective,
                trading_concept: form.trading_concept,
                risk_assumptions: form.risk_assumptions,
                category: form.category,
                status: form.status,
                tags: splitList(form.tags),
                registry_strategy_id: form.registry_strategy_id || null,
                instruments: splitList(form.instruments),
                timeframes: splitList(form.timeframes),
              })
            }
          >
            {submitLabel}
          </Button>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Title" span>
          <input
            className="input"
            value={form.title}
            onChange={(event) => set("title", event.target.value)}
            autoFocus
          />
        </Field>
        <Field label="Short description" span>
          <input
            className="input"
            value={form.short_description}
            onChange={(event) => set("short_description", event.target.value)}
          />
        </Field>
        <Field label="Registry implementation" hint="Optional. Documentation-only records cannot execute.">
          <select
            className="select"
            value={form.registry_strategy_id}
            onChange={(event) => set("registry_strategy_id", event.target.value)}
          >
            <option value="">Documentation only</option>
            {registryOptions.map((strategy) => (
              <option key={strategy.id} value={strategy.id}>
                {strategy.id} · {strategy.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Category">
          <input
            className="input"
            value={form.category}
            onChange={(event) => set("category", event.target.value)}
          />
        </Field>
        <Field label="Research status">
          <select
            className="select"
            value={form.status}
            onChange={(event) => set("status", event.target.value)}
          >
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Tags" hint="Comma separated.">
          <input
            className="input"
            value={form.tags}
            onChange={(event) => set("tags", event.target.value)}
          />
        </Field>
        <Field label="Instruments" hint="Comma separated. Empty means unspecified.">
          <input
            className="input mono"
            value={form.instruments}
            onChange={(event) => set("instruments", event.target.value)}
          />
        </Field>
        <Field label="Timeframes" hint="Comma separated.">
          <input
            className="input mono"
            value={form.timeframes}
            onChange={(event) => set("timeframes", event.target.value)}
          />
        </Field>
        <Field label="Hypothesis" span>
          <textarea
            className="input"
            rows={4}
            value={form.hypothesis}
            onChange={(event) => set("hypothesis", event.target.value)}
            placeholder="State a falsifiable hypothesis. Do not present it as proven."
          />
        </Field>
        <Field label="Research objective" span>
          <textarea
            className="input"
            rows={3}
            value={form.research_objective}
            onChange={(event) => set("research_objective", event.target.value)}
          />
        </Field>
        <Field label="Trading concept" span>
          <textarea
            className="input"
            rows={3}
            value={form.trading_concept}
            onChange={(event) => set("trading_concept", event.target.value)}
          />
        </Field>
        <Field label="Risk assumptions" span>
          <textarea
            className="input"
            rows={3}
            value={form.risk_assumptions}
            onChange={(event) => set("risk_assumptions", event.target.value)}
          />
        </Field>
        <Field label="Detailed description" span>
          <textarea
            className="input"
            rows={4}
            value={form.description}
            onChange={(event) => set("description", event.target.value)}
          />
        </Field>
      </div>
      {error ? <div className="form-error">{error}</div> : null}
    </Modal>
  );
}

interface VariationFormProps {
  title: string;
  initial?: StrategyVariation;
  defaultParameters?: Record<string, number | boolean | string>;
  saving: boolean;
  error: string;
  onSubmit: (payload: Record<string, unknown>) => void;
  onClose: () => void;
}

function VariationForm({
  title,
  initial,
  defaultParameters,
  saving,
  error,
  onSubmit,
  onClose,
}: VariationFormProps) {
  const [form, setForm] = useState({
    title: initial?.title ?? "",
    description: initial?.description ?? "",
    hypothesis: initial?.hypothesis ?? "",
    changes_from_parent: initial?.changes_from_parent ?? "",
    entry_rule_differences: initial?.entry_rule_differences ?? "",
    exit_rule_differences: initial?.exit_rule_differences ?? "",
    filter_differences: initial?.filter_differences ?? "",
    parameter_config: JSON.stringify(
      initial?.parameter_config ?? defaultParameters ?? {},
      null,
      2,
    ),
    zone_ids: joinList(initial?.zone_ids),
    cloned_from: initial?.cloned_from ?? null,
    instruments: joinList(initial?.instruments),
    timeframes: joinList(initial?.timeframes) || TIMEFRAMES.join(", "),
    status: initial?.status ?? "Draft",
    notes: initial?.notes ?? "",
  });
  const [jsonError, setJsonError] = useState("");
  const set = (key: keyof typeof form, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  function submit() {
    try {
      const parameterConfig = parseJsonConfig(form.parameter_config);
      setJsonError("");
      onSubmit({
        title: form.title,
        description: form.description,
        hypothesis: form.hypothesis,
        changes_from_parent: form.changes_from_parent,
        entry_rule_differences: form.entry_rule_differences,
        exit_rule_differences: form.exit_rule_differences,
        filter_differences: form.filter_differences,
        parameter_config: parameterConfig,
        zone_ids: splitList(form.zone_ids),
        instruments: splitList(form.instruments),
        timeframes: splitList(form.timeframes),
        status: form.status,
        notes: form.notes,
        cloned_from: form.cloned_from,
      });
    } catch (reason) {
      setJsonError(reason instanceof Error ? reason.message : "Invalid JSON.");
    }
  }

  return (
    <Modal
      open
      title={title}
      copy="A variation is a separate record. It never changes the parent or the registered implementation."
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" loading={saving} onClick={submit}>
            Save variation
          </Button>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Variation title" span>
          <input
            className="input"
            value={form.title}
            onChange={(event) => set("title", event.target.value)}
            autoFocus
          />
        </Field>
        <Field label="Description" span>
          <textarea
            className="input"
            rows={3}
            value={form.description}
            onChange={(event) => set("description", event.target.value)}
          />
        </Field>
        <Field label="Hypothesis" span>
          <textarea
            className="input"
            rows={3}
            value={form.hypothesis}
            onChange={(event) => set("hypothesis", event.target.value)}
          />
        </Field>
        <Field label="Changes from parent / previous version" span>
          <textarea
            className="input"
            rows={3}
            value={form.changes_from_parent}
            onChange={(event) => set("changes_from_parent", event.target.value)}
          />
        </Field>
        <Field label="Entry-rule differences">
          <textarea
            className="input"
            rows={3}
            value={form.entry_rule_differences}
            onChange={(event) => set("entry_rule_differences", event.target.value)}
          />
        </Field>
        <Field label="Exit-rule differences">
          <textarea
            className="input"
            rows={3}
            value={form.exit_rule_differences}
            onChange={(event) => set("exit_rule_differences", event.target.value)}
          />
        </Field>
        <Field label="Filter differences" span>
          <textarea
            className="input"
            rows={2}
            value={form.filter_differences}
            onChange={(event) => set("filter_differences", event.target.value)}
          />
        </Field>
        <Field label="Parameter configuration (JSON)" span hint="Executable variations must use parameter names accepted by the registered strategy.">
          <textarea
            className="input mono"
            rows={8}
            value={form.parameter_config}
            onChange={(event) => set("parameter_config", event.target.value)}
          />
        </Field>
        <Field label="Zone IDs" hint="Comma separated manual zone IDs; empty uses all eligible zones.">
          <input
            className="input mono"
            value={form.zone_ids}
            onChange={(event) => set("zone_ids", event.target.value)}
          />
        </Field>
        <Field label="Instruments" hint="Comma separated.">
          <input
            className="input mono"
            value={form.instruments}
            onChange={(event) => set("instruments", event.target.value)}
          />
        </Field>
        <Field label="Timeframes" hint="Comma separated.">
          <input
            className="input mono"
            value={form.timeframes}
            onChange={(event) => set("timeframes", event.target.value)}
          />
        </Field>
        <Field label="Variation status">
          <select
            className="select"
            value={form.status}
            onChange={(event) => set("status", event.target.value)}
          >
            {STATUSES.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Notes" span>
          <textarea
            className="input"
            rows={3}
            value={form.notes}
            onChange={(event) => set("notes", event.target.value)}
          />
        </Field>
      </div>
      {jsonError ? <div className="form-error">{jsonError}</div> : null}
      {error ? <div className="form-error">{error}</div> : null}
    </Modal>
  );
}

interface RulesFormProps {
  initial: WorkspaceRules;
  saving: boolean;
  error: string;
  onSubmit: (rules: WorkspaceRules) => void;
  onClose: () => void;
}

function RulesForm({ initial, saving, error, onSubmit, onClose }: RulesFormProps) {
  const [implemented, setImplemented] = useState({
    entry_conditions: rulesLines(initial.implemented?.entry_conditions),
    confirmation_conditions: rulesLines(initial.implemented?.confirmation_conditions),
    exit_conditions: rulesLines(initial.implemented?.exit_conditions),
    stop_loss: initial.implemented?.stop_loss ?? "",
    take_profit: initial.implemented?.take_profit ?? "",
    invalidation: initial.implemented?.invalidation ?? "",
    required_indicators: rulesLines(initial.implemented?.required_indicators),
    required_market_features: rulesLines(initial.implemented?.required_market_features),
    required_zone_configuration:
      initial.implemented?.required_zone_configuration ?? "",
    supported_instruments: rulesLines(initial.implemented?.supported_instruments),
    supported_timeframes: rulesLines(initial.implemented?.supported_timeframes),
  });
  const [proposed, setProposed] = useState(rulesLines(initial.proposed));
  const [experimental, setExperimental] = useState(rulesLines(initial.experimental));
  const set = (key: keyof typeof implemented, value: string) =>
    setImplemented((current) => ({ ...current, [key]: value }));

  return (
    <Modal
      open
      title="Edit strategy rules"
      copy="Implemented rules must reflect the current code. Proposed and experimental rules are documentation only."
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={saving}
            onClick={() =>
              onSubmit({
                implemented: {
                  entry_conditions: implemented.entry_conditions.split("\n").filter(Boolean),
                  confirmation_conditions: implemented.confirmation_conditions.split("\n").filter(Boolean),
                  exit_conditions: implemented.exit_conditions.split("\n").filter(Boolean),
                  stop_loss: implemented.stop_loss,
                  take_profit: implemented.take_profit,
                  invalidation: implemented.invalidation,
                  required_indicators: implemented.required_indicators.split("\n").filter(Boolean),
                  required_market_features: implemented.required_market_features.split("\n").filter(Boolean),
                  required_zone_configuration: implemented.required_zone_configuration,
                  supported_instruments: implemented.supported_instruments.split("\n").filter(Boolean),
                  supported_timeframes: implemented.supported_timeframes.split("\n").filter(Boolean),
                },
                proposed: proposed.split("\n").filter(Boolean),
                experimental: experimental.split("\n").filter(Boolean),
              })
            }
          >
            Save rules
          </Button>
        </>
      }
    >
      <div className="form-grid">
        <Field label="Entry conditions (one per line)" span>
          <textarea className="input" rows={3} value={implemented.entry_conditions} onChange={(event) => set("entry_conditions", event.target.value)} />
        </Field>
        <Field label="Confirmation conditions (one per line)" span>
          <textarea className="input" rows={3} value={implemented.confirmation_conditions} onChange={(event) => set("confirmation_conditions", event.target.value)} />
        </Field>
        <Field label="Exit conditions (one per line)" span>
          <textarea className="input" rows={3} value={implemented.exit_conditions} onChange={(event) => set("exit_conditions", event.target.value)} />
        </Field>
        <Field label="Stop-loss logic">
          <textarea className="input" rows={2} value={implemented.stop_loss} onChange={(event) => set("stop_loss", event.target.value)} />
        </Field>
        <Field label="Take-profit logic">
          <textarea className="input" rows={2} value={implemented.take_profit} onChange={(event) => set("take_profit", event.target.value)} />
        </Field>
        <Field label="Invalidation conditions" span>
          <textarea className="input" rows={2} value={implemented.invalidation} onChange={(event) => set("invalidation", event.target.value)} />
        </Field>
        <Field label="Required indicators (one per line)">
          <textarea className="input" rows={2} value={implemented.required_indicators} onChange={(event) => set("required_indicators", event.target.value)} />
        </Field>
        <Field label="Required market features (one per line)">
          <textarea className="input" rows={2} value={implemented.required_market_features} onChange={(event) => set("required_market_features", event.target.value)} />
        </Field>
        <Field label="Required zone configuration" span>
          <input className="input" value={implemented.required_zone_configuration} onChange={(event) => set("required_zone_configuration", event.target.value)} />
        </Field>
        <Field label="Supported instruments (one per line)">
          <textarea className="input mono" rows={2} value={implemented.supported_instruments} onChange={(event) => set("supported_instruments", event.target.value)} />
        </Field>
        <Field label="Supported timeframes (one per line)">
          <textarea className="input mono" rows={2} value={implemented.supported_timeframes} onChange={(event) => set("supported_timeframes", event.target.value)} />
        </Field>
        <Field label="Proposed rules (one per line)" span>
          <textarea className="input" rows={3} value={proposed} onChange={(event) => setProposed(event.target.value)} />
        </Field>
        <Field label="Experimental rules (one per line)" span>
          <textarea className="input" rows={3} value={experimental} onChange={(event) => setExperimental(event.target.value)} />
        </Field>
      </div>
      {error ? <div className="form-error">{error}</div> : null}
    </Modal>
  );
}

export function StrategyWorkspacePage({
  refreshKey,
  initialStrategyId,
  onSelectStrategy,
  onRunExperiment,
}: {
  refreshKey: number;
  initialStrategyId: string | null;
  onSelectStrategy: (id: string | null) => void;
  onRunExperiment: (preset: WorkspaceRunPreset) => void;
}) {
  const { notify } = useToast();
  const [rows, setRows] = useState<StrategyWorkspaceSummary[]>([]);
  const [registryOptions, setRegistryOptions] = useState<StrategySummary[]>([]);
  const [detail, setDetail] = useState<StrategyWorkspaceDetail | null>(null);
  const [dashboard, setDashboard] = useState<ResearchDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sort, setSort] = useState("recent");
  const [tab, setTab] = useState<"overview" | "rules" | "notes" | "variations" | "experiments" | "comparison">("overview");
  const [selectedVariationId, setSelectedVariationId] = useState<string>("");
  const [showCreateStrategy, setShowCreateStrategy] = useState(false);
  const [editStrategy, setEditStrategy] = useState(false);
  const [variationModal, setVariationModal] = useState<{ mode: "create" | "edit"; variation?: StrategyVariation } | null>(null);
  const [showRules, setShowRules] = useState(false);
  const [noteBody, setNoteBody] = useState("");
  const [editingNote, setEditingNote] = useState<StrategyNote | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [labReady, setLabReady] = useState(false);

  const loadList = useCallback(() => {
    setLoading(true);
    Promise.all([
      workspaceApi.list({ query, status: statusFilter || undefined, sort }),
      api.strategies(),
      workspaceDashboardApi.get(),
    ])
      .then(([strategies, catalogue, dashboardData]) => {
        setRows(strategies);
        setRegistryOptions(catalogue);
        setDashboard(dashboardData);
        setError("");
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, [query, statusFilter, sort]);

  useEffect(() => {
    const timer = window.setTimeout(loadList, 220);
    return () => window.clearTimeout(timer);
  }, [loadList, refreshKey]);

  const loadDetail = useCallback((id: string) => {
    setLoading(true);
    workspaceApi
      .get(id)
      .then((value) => {
        setDetail(value);
        setSelectedVariationId((current) => {
          if (value.variations.some((item) => item.id === current)) return current;
          return value.baseline_variation_id ?? value.variations[0]?.id ?? "";
        });
        setError("");
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (initialStrategyId) loadDetail(initialStrategyId);
    else setDetail(null);
  }, [initialStrategyId, loadDetail, refreshKey]);

  useEffect(() => {
    setLabReady(Boolean(detail?.registry_strategy_id));
  }, [detail?.registry_strategy_id]);

  const selectedVariation = detail?.variations.find(
    (item) => item.id === selectedVariationId,
  );
  function openStrategy(id: string) {
    onSelectStrategy(id);
    setTab("overview");
    setActionError("");
  }

  function closeStrategy() {
    onSelectStrategy(null);
    setDetail(null);
    setTab("overview");
  }

  async function runAction(
    action: () => Promise<StrategyWorkspaceDetail>,
    success: string,
  ): Promise<boolean> {
    setBusy(true);
    setActionError("");
    try {
      const updated = await action();
      setDetail(updated);
      notify(success);
      return true;
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "Action failed.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  function startVariationRun(variation: StrategyVariation) {
    if (!detail || !labReady || variation.implementation_status !== "implemented") return;
    onRunExperiment({
      strategy_record_id: detail.id,
      strategy_id: detail.registry_strategy_id ?? "",
      variation_id: variation.id,
      variation_title: variation.title,
      parameters: variation.parameter_config,
      zone_ids: variation.zone_ids ?? [],
      instrument: variation.instruments[0],
      timeframe: variation.timeframes[0],
      hypothesis: variation.hypothesis,
      experiment_kind: "auto",
    });
  }

  if (loading && !detail && !rows.length) {
    return <LoadingState label="Loading strategy workspace" />;
  }
  if (error && !detail) {
    return (
      <ErrorState
        message={error}
        action={
          <Button icon={<RefreshCw size={14} />} onClick={() => (initialStrategyId ? loadDetail(initialStrategyId) : loadList())}>
            Retry
          </Button>
        }
      />
    );
  }

  if (!detail) {
    return (
      <div className="stack">
        <PageHeader
          eyebrow="Research management · strategy workspace"
          title="Keep the hypothesis, before the result."
          subtitle="Document strategies, isolate variations, preserve notes, and link experiments to immutable backtest runs. Documentation never becomes executable by accident."
          actions={
            <Button variant="primary" icon={<Plus size={14} />} onClick={() => setShowCreateStrategy(true)}>
              New strategy
            </Button>
          }
        />
        {dashboard ? (
          <Panel kicker="Research dashboard" title="The research estate">
            <div className="quality-grid">
              <div className="quality-cell"><div className="quality-label">Strategies</div><div className="quality-value">{dashboard.strategy_count}</div></div>
              <div className="quality-cell"><div className="quality-label">Variations</div><div className="quality-value">{dashboard.variation_count}</div></div>
              <div className="quality-cell"><div className="quality-label">Experiments</div><div className="quality-value">{dashboard.experiment_count}</div></div>
              <div className="quality-cell"><div className="quality-label">Outstanding</div><div className={`quality-value ${dashboard.outstanding_experiments ? "warn" : ""}`}>{dashboard.outstanding_experiments}</div></div>
              <div className="quality-cell"><div className="quality-label">Validation failures</div><div className={`quality-value ${dashboard.validation_failures ? "danger" : ""}`}>{dashboard.validation_failures}</div></div>
              <div className="quality-cell"><div className="quality-label">Datasets warning</div><div className={`quality-value ${dashboard.dataset_warning_count ? "warn" : ""}`}>{dashboard.dataset_warning_count}/{dashboard.dataset_count}</div></div>
            </div>
            <div className="divider" />
            <div className="detail-list">
              {Object.entries(dashboard.strategy_status_counts).map(([status, count]) => (
                <div className="detail-row" key={status}><span className="detail-key">{status}</span><span className="detail-value">{count}</span></div>
              ))}
              {Object.entries(dashboard.experiment_status_counts).filter(([, count]) => count > 0).map(([status, count]) => (
                <div className="detail-row" key={`exp-${status}`}><span className="detail-key">Experiments · {status}</span><span className="detail-value">{count}</span></div>
              ))}
            </div>
            {dashboard.recent_experiments.length ? (
              <>
                <div className="divider" />
                <p className="panel-kicker">Recent experiments</p>
                {dashboard.recent_experiments.slice(0, 5).map((experiment) => (
                  <div className="detail-row" key={experiment.id}>
                    <span className="detail-key">{experiment.name}</span>
                    <span className="detail-value">{experiment.status} · {formatR(experiment.net_results?.expectancy ?? experiment.gross_results?.expectancy ?? null)}</span>
                  </div>
                ))}
              </>
            ) : null}
          </Panel>
        ) : null}
        <div className="workspace-toolbar">
          <Field label="Search">
            <div className="workspace-search">
              <Search size={13} strokeWidth={1.5} />
              <input
                className="input"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Title, ID, tag or description"
              />
            </div>
          </Field>
          <Field label="Research status">
            <select className="select" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">All strategies</option>
              {STATUSES.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Sort">
            <select className="select" value={sort} onChange={(event) => setSort(event.target.value)}>
              <option value="recent">Last modified</option>
              <option value="experiments">Last experiment</option>
              <option value="title">Title</option>
            </select>
          </Field>
          <div className="workspace-toolbar-spacer" />
          <span className="field-hint">{rows.length} recorded strateg{rows.length === 1 ? "y" : "ies"}</span>
        </div>

        {rows.length ? (
          <div className="workspace-grid">
            {rows.map((row) => (
              <button className="workspace-card" key={row.id} onClick={() => openStrategy(row.id)}>
                <div className="workspace-card-head">
                  <span className="tag">{row.category}</span>
                  <StatusPill tone={workspaceTone(row.status)}>{row.status}</StatusPill>
                </div>
                <h2>{row.title}</h2>
                <p className="workspace-card-id mono">{row.registry_strategy_id ?? row.id}</p>
                <p className="workspace-card-copy">{row.short_description}</p>
                <div className="workspace-card-meta">
                  <span>{row.variation_count} variation{row.variation_count === 1 ? "" : "s"}</span>
                  <span>{row.linked_run_count} linked run{row.linked_run_count === 1 ? "" : "s"}</span>
                  <span>Updated {formatDate(row.updated_at)}</span>
                </div>
                <div className="workspace-card-tags">
                  {row.instruments.slice(0, 4).map((item) => (
                    <span key={item} className="tag">{item}</span>
                  ))}
                  {row.timeframes.slice(0, 3).map((item) => (
                    <span key={item} className="tag">{item}</span>
                  ))}
                </div>
                {row.latest_experiment ? (
                  <div className="workspace-card-foot">
                    Latest experiment · {formatDate(row.latest_experiment.executed_at)} ·{" "}
                    {row.latest_experiment.metrics.total_trades ?? 0} trades ·{" "}
                    {metricText(row.latest_experiment.metrics.expectancy, 3)}R expectancy
                  </div>
                ) : (
                  <div className="workspace-card-foot">No experiment linked yet.</div>
                )}
                <span className="workspace-card-open">
                  Open workspace <ChevronRight size={12} />
                </span>
              </button>
            ))}
          </div>
        ) : (
          <Panel kicker="Empty workspace" title="No strategy records">
            <EmptyState
              title="Start with a hypothesis"
              copy="Create a strategy record, document its rules, and add variations. Existing registered strategies are seeded automatically on first use."
              action={<Button size="sm" variant="ghost" onClick={() => setShowCreateStrategy(true)}>Create strategy</Button>}
            />
          </Panel>
        )}

        {showCreateStrategy ? (
          <StrategyForm
            title="Create strategy record"
            submitLabel="Create strategy"
            registryOptions={registryOptions}
            saving={busy}
            error={actionError}
            onClose={() => setShowCreateStrategy(false)}
            onSubmit={async (payload) => {
              setBusy(true);
              setActionError("");
              try {
                const created = await workspaceApi.create(payload);
                setShowCreateStrategy(false);
                openStrategy(created.id);
                notify("Strategy record created.");
                loadList();
              } catch (reason) {
                setActionError(reason instanceof Error ? reason.message : "Could not create strategy.");
              } finally {
                setBusy(false);
              }
            }}
          />
        ) : null}
      </div>
    );
  }

  const baseline = detail.variations.find((item) => item.id === detail.baseline_variation_id);
  const comparisonGroups = detail.comparison;

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Strategy workspace · strategy focus"
        title={detail.title}
        subtitle={detail.short_description}
        actions={
          <>
            <Button variant="ghost" icon={<ArrowLeft size={14} />} onClick={closeStrategy}>
              All strategies
            </Button>
            <Button variant="ghost" icon={<Pencil size={14} />} onClick={() => setEditStrategy(true)}>
              Edit
            </Button>
            <Button
              variant="ghost"
              icon={<Archive size={14} />}
              onClick={() => {
                if (!window.confirm(`Archive “${detail.title}”? Experiments are preserved.`)) return;
                runAction(() => workspaceApi.archive(detail.id), "Strategy archived.");
              }}
              disabled={busy || detail.status === "Archived"}
            >
              Archive
            </Button>
          </>
        }
      />

      <div className="workspace-context">
        <div>
          <span className="workspace-context-label">Strategy</span>
          <strong>{detail.title}</strong>
          <span className="mono faint">{detail.registry_strategy_id ?? "documentation only"}</span>
        </div>
        <div>
          <span className="workspace-context-label">Selected variation</span>
          <select
            className="select"
            value={selectedVariationId}
            onChange={(event) => setSelectedVariationId(event.target.value)}
          >
            {detail.variations.map((variation) => (
              <option key={variation.id} value={variation.id}>
                {variation.title}{variation.is_baseline ? " · baseline" : ""}
              </option>
            ))}
          </select>
        </div>
        <div>
          <span className="workspace-context-label">Status</span>
          <StatusPill tone={workspaceTone(detail.status)}>{detail.status}</StatusPill>
        </div>
        <div>
          <span className="workspace-context-label">Last experiment</span>
          <strong>{detail.last_experiment_at ? formatDateTime(detail.last_experiment_at) : "None"}</strong>
        </div>
        <div>
          <span className="workspace-context-label">Linked runs</span>
          <strong>{detail.linked_run_count}</strong>
        </div>
        {selectedVariation ? (
          <div className="workspace-context-run">
            <Button
              variant="primary"
              size="sm"
              icon={<FlaskConical size={13} />}
              disabled={
                busy ||
                !labReady ||
                selectedVariation.implementation_status !== "implemented" ||
                selectedVariation.status === "Archived"
              }
              onClick={() => startVariationRun(selectedVariation)}
            >
              Run experiment
            </Button>
            {selectedVariation.implementation_status !== "implemented" ? (
              <span className="field-hint">Documentation-only variation; no executable implementation is linked.</span>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="workspace-tabs" role="tablist" aria-label="Strategy workspace sections">
        {([
          ["overview", "Overview"],
          ["rules", "Rules"],
          ["notes", `Notes${detail.notes.length ? ` (${detail.notes.length})` : ""}`],
          ["variations", `Variations (${detail.variations.length})`],
          ["experiments", `Experiments (${detail.experiments.length})`],
          ["comparison", "Comparison"],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            className={`workspace-tab ${tab === id ? "active" : ""}`}
            onClick={() => setTab(id)}
            role="tab"
            aria-selected={tab === id}
          >
            {label}
          </button>
        ))}
      </div>

      {actionError ? <div className="form-error">{actionError}</div> : null}

      {tab === "overview" ? (
        <div className="grid-2">
          <Panel kicker="Overview" title="Research identity">
            <div className="detail-list">
              <div className="detail-row"><span className="detail-key">Strategy ID</span><span className="detail-value mono">{detail.id}</span></div>
              <div className="detail-row"><span className="detail-key">Registry ID</span><span className="detail-value mono">{detail.registry_strategy_id ?? "none"}</span></div>
              <div className="detail-row"><span className="detail-key">Category</span><span className="detail-value">{detail.category}</span></div>
              <div className="detail-row"><span className="detail-key">Status</span><span className="detail-value">{detail.status}</span></div>
              <div className="detail-row"><span className="detail-key">Created</span><span className="detail-value">{formatDateTime(detail.created_at)}</span></div>
              <div className="detail-row"><span className="detail-key">Last updated</span><span className="detail-value">{formatDateTime(detail.updated_at)}</span></div>
              <div className="detail-row"><span className="detail-key">Baseline</span><span className="detail-value">{baseline?.title ?? "—"}</span></div>
              <div className="detail-row"><span className="detail-key">Tags</span><span className="detail-value">{detail.tags.join(" · ") || "—"}</span></div>
            </div>
          </Panel>
          <Panel kicker="Research framing" title="Hypothesis and objective">
            <p className="workspace-prose">{detail.hypothesis || "No hypothesis recorded yet."}</p>
            <div className="divider" />
            <p className="workspace-prose">{detail.research_objective || "No research objective recorded yet."}</p>
            <div className="divider" />
            <p className="workspace-prose"><strong>Trading concept:</strong> {detail.trading_concept || "—"}</p>
            <p className="workspace-prose"><strong>Risk assumptions:</strong> {detail.risk_assumptions || "—"}</p>
            <div className="divider" />
            <div className="detail-list">
              <div className="detail-row"><span className="detail-key">Instruments</span><span className="detail-value">{detail.instruments.join(", ") || "—"}</span></div>
              <div className="detail-row"><span className="detail-key">Timeframes</span><span className="detail-value">{detail.timeframes.join(", ") || "—"}</span></div>
              <div className="detail-row"><span className="detail-key">Variations</span><span className="detail-value">{detail.variation_count}</span></div>
            </div>
          </Panel>
          <Panel kicker="Description" title="Strategy record" className="span-2">
            <p className="workspace-prose">{detail.description || "No detailed description recorded yet."}</p>
          </Panel>
        </div>
      ) : null}

      {tab === "rules" ? (
        <div className="stack">
          <div className="workspace-section-head">
            <div>
              <h2>Strategy rules</h2>
              <p className="panel-subtitle">Implemented rules describe current code. Proposed and experimental rules are documentation, not execution behavior.</p>
            </div>
            <Button variant="ghost" size="sm" icon={<Pencil size={13} />} onClick={() => setShowRules(true)}>Edit rules</Button>
          </div>
          <div className="workspace-rule-grid">
            <Panel kicker="Implemented" title="Current behavior">
              <div className="workspace-rule-list">
                {([
                  ["Entry", detail.rules.implemented?.entry_conditions],
                  ["Confirmation", detail.rules.implemented?.confirmation_conditions],
                  ["Exit", detail.rules.implemented?.exit_conditions],
                ] as const).map(([label, values]) => (
                  <div key={label}><strong>{label}</strong><span>{values?.length ? values.join(" ") : "—"}</span></div>
                ))}
                <div><strong>Stop loss</strong><span>{detail.rules.implemented?.stop_loss || "—"}</span></div>
                <div><strong>Take profit</strong><span>{detail.rules.implemented?.take_profit || "—"}</span></div>
                <div><strong>Invalidation</strong><span>{detail.rules.implemented?.invalidation || "—"}</span></div>
                <div><strong>Indicators</strong><span>{detail.rules.implemented?.required_indicators?.join(", ") || "—"}</span></div>
                <div><strong>Market features</strong><span>{detail.rules.implemented?.required_market_features?.join(", ") || "—"}</span></div>
                <div><strong>Zone configuration</strong><span>{detail.rules.implemented?.required_zone_configuration || "—"}</span></div>
                <div><strong>Instruments</strong><span>{detail.rules.implemented?.supported_instruments?.join(", ") || "—"}</span></div>
                <div><strong>Timeframes</strong><span>{detail.rules.implemented?.supported_timeframes?.join(", ") || "—"}</span></div>
              </div>
            </Panel>
            <Panel kicker="Not executed" title="Proposed rules">
              <RuleBullets values={detail.rules.proposed} empty="No proposed changes recorded." />
              <div className="divider" />
              <p className="panel-kicker">Experimental</p>
              <RuleBullets values={detail.rules.experimental} empty="No experimental rules recorded." />
            </Panel>
          </div>
        </div>
      ) : null}

      {tab === "notes" ? (
        <div className="stack">
          <Panel kicker="Research notes" title="Persistent observations">
            <div className="workspace-note-form">
              <textarea
                className="input"
                rows={4}
                value={noteBody}
                onChange={(event) => setNoteBody(event.target.value)}
                placeholder="Record an observation, problem, decision or future experiment."
              />
              <Button
                variant="primary"
                size="sm"
                disabled={busy || !noteBody.trim()}
                onClick={async () => {
                  const body = noteBody;
                  setBusy(true);
                  setActionError("");
                  try {
                    await workspaceApi.addNote(detail.id, body);
                    setDetail(await workspaceApi.get(detail.id));
                    setNoteBody("");
                    notify("Note added.");
                  } catch (reason) {
                    setActionError(reason instanceof Error ? reason.message : "Could not add note.");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Add note
              </Button>
            </div>
            <div className="divider" />
            {detail.notes.length ? (
              <div className="workspace-note-list">
                {[...detail.notes].reverse().map((note) => (
                  <article className="workspace-note" key={note.id}>
                    <div className="workspace-note-head">
                      <span className="mono">{formatDateTime(note.created_at)}</span>
                      <div className="workspace-inline-actions">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setEditingNote(note);
                          }}
                        >
                          Edit
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={async () => {
                            if (!window.confirm("Delete this note? This does not delete experiments or runs.")) return;
                            setBusy(true);
                            setActionError("");
                            try {
                              await workspaceApi.deleteNote(detail.id, note.id);
                              setDetail(await workspaceApi.get(detail.id));
                              notify("Note deleted.");
                            } catch (reason) {
                              setActionError(reason instanceof Error ? reason.message : "Could not delete note.");
                            } finally {
                              setBusy(false);
                            }
                          }}
                        >
                          Delete
                        </Button>
                      </div>
                    </div>
                    <p className="workspace-prose">{note.body}</p>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState title="No notes yet" copy="Record the reasoning that should survive the next experiment." />
            )}
          </Panel>
        </div>
      ) : null}

      {tab === "variations" ? (
        <div className="stack">
          <div className="workspace-section-head">
            <div>
              <h2>Variations</h2>
              <p className="panel-subtitle">Each variation has its own configuration, version, status and experiment history.</p>
            </div>
            <Button variant="primary" size="sm" icon={<Plus size={13} />} onClick={() => setVariationModal({ mode: "create" })}>
              New variation
            </Button>
          </div>
          <div className="workspace-variation-grid">
            {detail.variations.map((variation) => {
              const experiments = detail.experiments.filter((item) => item.variation_id === variation.id);
              const locked = variation.is_baseline && experiments.length > 0;
              return (
                <Panel
                  key={variation.id}
                  kicker={variation.is_baseline ? "Baseline" : `Configuration v${variation.configuration_version}`}
                  title={variation.title}
                  action={<StatusPill tone={workspaceTone(variation.status)}>{variation.status}</StatusPill>}
                  className={`workspace-variation ${selectedVariationId === variation.id ? "selected" : ""}`.trim()}
                >
                  <p className="workspace-prose">{variation.description || "No description."}</p>
                  {variation.hypothesis ? <p className="workspace-prose"><strong>Hypothesis:</strong> {variation.hypothesis}</p> : null}
                  <div className="detail-list">
                    <div className="detail-row"><span className="detail-key">Variation ID</span><span className="detail-value mono">{variation.id}</span></div>
                    <div className="detail-row"><span className="detail-key">Implementation</span><span className="detail-value">{variation.implementation_status === "implemented" ? "Executable · linked to registry" : "Documentation only"}</span></div>
                    <div className="detail-row"><span className="detail-key">Configuration version</span><span className="detail-value">{variation.configuration_version}</span></div>
                    <div className="detail-row"><span className="detail-key">Linked runs</span><span className="detail-value">{experiments.length}</span></div>
                    <div className="detail-row"><span className="detail-key">Parameters</span><span className="detail-value mono">{JSON.stringify(variation.parameter_config)}</span></div>
                    <div className="detail-row"><span className="detail-key">Zones</span><span className="detail-value mono">{variation.zone_ids?.join(", ") || "all eligible"}</span></div>
                    <div className="detail-row"><span className="detail-key">Created</span><span className="detail-value">{formatDateTime(variation.created_at)}</span></div>
                    {variation.changes_from_parent ? <div className="detail-row"><span className="detail-key">Changes</span><span className="detail-value">{variation.changes_from_parent}</span></div> : null}
                    {variation.entry_rule_differences ? <div className="detail-row"><span className="detail-key">Entry differences</span><span className="detail-value">{variation.entry_rule_differences}</span></div> : null}
                    {variation.exit_rule_differences ? <div className="detail-row"><span className="detail-key">Exit differences</span><span className="detail-value">{variation.exit_rule_differences}</span></div> : null}
                    {variation.filter_differences ? <div className="detail-row"><span className="detail-key">Filter differences</span><span className="detail-value">{variation.filter_differences}</span></div> : null}
                    {variation.notes ? <div className="detail-row"><span className="detail-key">Notes</span><span className="detail-value">{variation.notes}</span></div> : null}
                  </div>
                  <div className="workspace-inline-actions">
                    <Button size="sm" variant="ghost" onClick={() => setSelectedVariationId(variation.id)}>Select</Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={busy || locked}
                      onClick={() => setVariationModal({ mode: "edit", variation })}
                    >
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      icon={<Copy size={12} />}
                      disabled={busy}
                      onClick={() => {
                        setVariationModal({
                          mode: "create",
                          variation: {
                            ...variation,
                            id: "",
                            title: `${variation.title} — copy`,
                            is_baseline: false,
                            cloned_from: variation.id,
                          },
                        });
                      }}
                    >
                      Clone
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={busy || variation.is_baseline || variation.status === "Archived"}
                      onClick={() => runAction(() => workspaceApi.archiveVariation(detail.id, variation.id), "Variation archived.")}
                    >
                      Archive
                    </Button>
                    <Button
                      size="sm"
                      variant="primary"
                      icon={<FlaskConical size={12} />}
                      disabled={!labReady || variation.implementation_status !== "implemented" || variation.status === "Archived"}
                      onClick={() => startVariationRun(variation)}
                    >
                      Run
                    </Button>
                  </div>
                  {locked ? <p className="field-hint">Baseline locked after experiments. Clone it for a versioned change.</p> : null}
                </Panel>
              );
            })}
          </div>
        </div>
      ) : null}

      {tab === "experiments" ? (
        <div className="stack">
          <Panel
            kicker="Experiment history"
            title="Linked backtest runs"
            subtitle="Every row references a real archived run. No run is created here and no result is inferred from documentation."
          >
            {detail.experiments.length ? (
              <ExperimentTable
                experiments={detail.experiments}
                variations={detail.variations}
                onReproduce={async (experiment) => {
                  setBusy(true);
                  setActionError("");
                  try {
                    const result = await workspaceIntegrityApi.reproduceExperiment(detail.id, experiment.id);
                    setDetail(await workspaceApi.get(detail.id));
                    notify(
                      result.reproduction.comparison.matches
                        ? "Reproduced exactly from the immutable snapshot."
                        : "Reproduction completed; comparison differs — inspect the record.",
                    );
                  } catch (reason) {
                    setActionError(reason instanceof Error ? reason.message : "Reproduction failed.");
                  } finally {
                    setBusy(false);
                  }
                }}
                onAmend={async (experiment) => {
                  const note = window.prompt("Append an amendment note (original record stays unchanged):");
                  if (!note) return;
                  setBusy(true);
                  setActionError("");
                  try {
                    await workspaceIntegrityApi.amendExperiment(detail.id, experiment.id, {
                      notes: note,
                      author: "local-user",
                      reason: "UI amendment",
                    });
                    setDetail(await workspaceApi.get(detail.id));
                    notify("Amendment appended; original experiment unchanged.");
                  } catch (reason) {
                    setActionError(reason instanceof Error ? reason.message : "Amendment failed.");
                  } finally {
                    setBusy(false);
                  }
                }}
              />
            ) : (
              <EmptyState
                title="No experiments linked"
                copy="Select an executable variation and run it through Strategy Lab. REX will attach the resulting run to this workspace."
              />
            )}
          </Panel>
        </div>
      ) : null}

      {tab === "comparison" ? (
        <div className="stack">
          <Panel
            kicker="Comparison"
            title="Variations under comparable conditions"
            subtitle="Only experiments sharing dataset, instrument, timeframe and date range are grouped. No ranking is applied; missing metrics remain unavailable."
          >
            {comparisonGroups.length ? (
              <ComparisonTables groups={comparisonGroups} />
            ) : (
              <EmptyState
                title="No comparable experiments"
                copy="Link at least two variations with real runs on the same dataset, instrument, timeframe and date range."
              />
            )}
          </Panel>
        </div>
      ) : null}

      {editStrategy ? (
        <StrategyForm
          title="Edit strategy record"
          submitLabel="Save strategy"
          initial={detail}
          registryOptions={registryOptions}
          saving={busy}
          error={actionError}
          onClose={() => setEditStrategy(false)}
          onSubmit={async (payload) => {
            if (await runAction(() => workspaceApi.update(detail.id, payload), "Strategy updated.")) {
              setEditStrategy(false);
            }
          }}
        />
      ) : null}

      {showRules ? (
        <RulesForm
          initial={detail.rules}
          saving={busy}
          error={actionError}
          onClose={() => setShowRules(false)}
          onSubmit={async (rules) => {
            if (await runAction(() => workspaceApi.update(detail.id, { rules }), "Rules saved.")) {
              setShowRules(false);
            }
          }}
        />
      ) : null}

      {variationModal ? (
        <VariationForm
          title={variationModal.mode === "create" ? "Create variation" : "Edit variation"}
          initial={variationModal.variation}
          defaultParameters={baseline?.parameter_config}
          saving={busy}
          error={actionError}
          onClose={() => setVariationModal(null)}
          onSubmit={async (payload) => {
            const ok = variationModal.mode === "edit" && variationModal.variation
              ? await runAction(
                  () => workspaceApi.updateVariation(detail.id, variationModal.variation!.id, payload),
                  "Variation updated.",
                )
              : await runAction(
                  () => workspaceApi.createVariation(detail.id, payload),
                  "Variation created.",
                );
            if (ok) setVariationModal(null);
          }}
        />
      ) : null}

      {editingNote ? (
        <Modal
          open
          title="Edit note"
          onClose={() => setEditingNote(null)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setEditingNote(null)}>Cancel</Button>
              <Button
                variant="primary"
                loading={busy}
                onClick={async () => {
                  setBusy(true);
                  setActionError("");
                  try {
                    await workspaceApi.updateNote(detail.id, editingNote.id, editingNote.body);
                    setDetail(await workspaceApi.get(detail.id));
                    setEditingNote(null);
                    notify("Note updated.");
                  } catch (reason) {
                    setActionError(reason instanceof Error ? reason.message : "Could not update note.");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Save note
              </Button>
            </>
          }
        >
          <textarea
            className="input"
            rows={8}
            value={editingNote.body}
            onChange={(event) => setEditingNote({ ...editingNote, body: event.target.value })}
          />
        </Modal>
      ) : null}
    </div>
  );
}

function RuleBullets({ values, empty }: { values: string[] | undefined; empty: string }) {
  if (!values?.length) return <p className="workspace-prose">{empty}</p>;
  return (
    <ul className="workspace-rule-bullets">
      {values.map((value) => <li key={value}>{value}</li>)}
    </ul>
  );
}

function ExperimentTable({
  experiments,
  variations,
  onReproduce,
  onAmend,
}: {
  experiments: StrategyExperiment[];
  variations: StrategyVariation[];
  onReproduce: (experiment: StrategyExperiment) => void;
  onAmend: (experiment: StrategyExperiment) => void;
}) {
  const columns: Column<StrategyExperiment>[] = [
    {
      key: "name",
      header: "Experiment",
      render: (row) => (
        <div>
          <div className="primary-cell">{row.name}</div>
          <div className="faint mono" style={{ fontSize: 9 }}>{row.run_id}</div>
        </div>
      ),
    },
    {
      key: "variation",
      header: "Variation",
      render: (row) => variations.find((item) => item.id === row.variation_id)?.title ?? "—",
    },
    {
      key: "conditions",
      header: "Dataset / frame",
      render: (row) => (
        <span className="mono" style={{ fontSize: 9 }}>
          {row.dataset_id}<br />{row.timeframe} · {row.start_date} → {row.end_date}
        </span>
      ),
    },
    { key: "status", header: "Status", render: (row) => <StatusPill tone={row.status === "Completed" ? "ok" : row.status === "Failed" ? "danger" : "neutral"}>{row.status}</StatusPill> },
    { key: "kind", header: "Kind", render: (row) => <span className="tag">{row.kind}</span> },
    { key: "trades", header: "Trades", align: "right", render: (row) => formatInteger(row.metrics.total_trades) },
    { key: "gross", header: "Gross exp.", align: "right", render: (row) => formatR(row.metrics.expectancy) },
    { key: "net", header: "Net exp.", align: "right", render: (row) => formatR(row.net_results?.expectancy ?? null) },
    { key: "cost", header: "Cost R", align: "right", render: (row) => formatR(row.result_reference?.total_cost_r ?? null) },
    { key: "validation", header: "Validation", render: (row) => <span className="mono" style={{ fontSize: 9 }}>{row.validation_status}</span> },
    { key: "run", header: "Run", render: (row) => <span className="mono" style={{ fontSize: 9 }}>{row.run_available ? "available" : "missing"}</span> },
    {
      key: "integrity",
      header: "Integrity",
      render: (row) => (
        <div className="workspace-inline-actions">
          <Button size="sm" variant="ghost" onClick={() => onReproduce(row)}>Reproduce</Button>
          <Button size="sm" variant="ghost" onClick={() => onAmend(row)}>Amend</Button>
        </div>
      ),
    },
  ];
  return <DataTable columns={columns} rows={[...experiments].reverse()} getKey={(row) => row.id} />;
}

function ComparisonTables({ groups }: { groups: ComparisonGroup[] }) {
  return (
    <div className="stack">
      {groups.map((group) => {
        const columns: Column<ComparisonRow>[] = [
          { key: "variation", header: "Variation", render: (row) => row.variation_title },
          { key: "kind", header: "Kind", render: (row) => <span className="tag">{row.kind}</span> },
          { key: "trades", header: "Trades", align: "right", render: (row) => formatInteger(row.trade_count) },
          { key: "wr", header: "Win rate", align: "right", render: (row) => formatPercent(row.win_rate) },
          { key: "pf", header: "Profit factor", align: "right", render: (row) => metricText(row.profit_factor) },
          { key: "exp", header: "Expectancy", align: "right", render: (row) => formatR(row.expectancy) },
          { key: "dd", header: "Max DD", align: "right", render: (row) => row.max_drawdown_r === null ? "—" : `${formatDecimal(row.max_drawdown_r, 2)}R` },
          { key: "total", header: "Gross total R", align: "right", render: (row) => row.total_r === null ? "—" : formatR(row.total_r) },
          { key: "net", header: "Net expectancy", align: "right", render: (row) => formatR(row.net_expectancy) },
          { key: "net_total", header: "Net total R", align: "right", render: (row) => formatR(row.net_total_r) },
          { key: "cost", header: "Costs", align: "right", render: (row) => formatR(row.total_cost_r) },
          { key: "validation", header: "Validation", render: (row) => <span className="mono" style={{ fontSize: 9 }}>{row.validation_status ?? "—"}</span> },
          { key: "hold", header: "Avg hold", align: "right", render: (row) => row.avg_holding_duration === null ? "—" : formatDecimal(row.avg_holding_duration, 1) },
          { key: "run", header: "Run", render: (row) => <span className="mono" style={{ fontSize: 9 }}>{row.run_available ? "available" : "missing"}</span> },
        ];
        return (
          <Panel
            key={`${group.dataset_id}-${group.timeframe}-${group.start_date}-${group.end_date}`}
            kicker="Comparable group"
            title={`${group.dataset_id} · ${group.timeframe}`}
            subtitle={`${group.instrument} · ${group.start_date} → ${group.end_date} · gross R-multiples, costs not applied.`}
          >
            <DataTable columns={columns} rows={group.rows} getKey={(row) => row.experiment_id} />
            {group.rows.some((row) => row.sample_size_warning) ? (
              <p className="field-hint">One or more entries have fewer than 100 trades. Treat differences as provisional.</p>
            ) : null}
          </Panel>
        );
      })}
    </div>
  );
}
