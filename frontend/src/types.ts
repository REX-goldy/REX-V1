export type DatasetStatus = "ok" | "warning" | "error";

export interface DatasetCoverage {
  start?: string | null;
  end?: string | null;
  requested_start?: string | null;
  requested_end?: string | null;
  actual_start?: string | null;
  actual_end?: string | null;
  retrieved_at?: string | null;
}

export interface DatasetQuality {
  duplicate_count?: number;
  invalid_bar_count?: number;
  timestamp_gap_count?: number | null;
  notes?: string[];
}

export interface DatasetSummary {
  id: string;
  symbol: string;
  timeframe: string;
  year: number;
  provider: string;
  path?: string;
  bar_count: number;
  size_bytes: number;
  status: DatasetStatus;
  warnings: string[];
  coverage: DatasetCoverage;
  quality: DatasetQuality;
  first_timestamp: string | null;
  last_timestamp: string | null;
  derived?: boolean;
  derived_from?: string;
  available_timeframes?: string[];
  error?: string;
  metadata?: Record<string, unknown>;
}

export interface Instrument {
  symbol: string;
  market: string;
  asset_class: string;
  pip_size: number;
  tick_size: number;
  research_enabled: boolean;
  display_name: string;
}

export interface StrategyParameter {
  name: string;
  label: string;
  type: "number" | "integer" | "boolean" | "string";
  default: number | boolean | string;
  min?: number;
  max?: number;
  step?: number;
  help?: string;
}

export interface StrategySummary {
  id: string;
  name: string;
  description: string;
  trade_simulation: boolean;
  requires_zones: boolean;
  parameters: StrategyParameter[];
  note: string;
}

export interface RunSummary {
  id: string;
  created_at: string;
  dataset_id: string;
  timeframe?: string;
  range?: { start: string; end: string; bar_count: number; gap_count: number };
  strategy: { id: string; name: string; description: string };
  metrics: RunMetrics;
  bar_count: number;
  simulated: boolean;
  warning_count: number;
}

export interface RunMetrics {
  total_signals: number;
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  profit_factor: number | null;
  expectancy: number;
  max_drawdown_r: number;
  largest_win: number;
  largest_loss: number;
  ambiguous_exits: number;
  avg_holding_duration: number;
}

export interface TradeRow {
  symbol: string;
  direction: "LONG" | "SHORT";
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  sl_price: number;
  tp_price: number;
  pnl_r: number;
  close_reason: string;
  holding_duration_candles: number;
  strategy_id: string;
  planned_entry_price?: number | null;
  planned_position_size?: number | null;
  planned_risk_amount?: number | null;
  position_size?: number | null;
  realized_risk_amount?: number | null;
  entry_slippage?: number | null;
  execution_assumption?: string;
  spread_cost_r?: number | null;
  slippage_cost_r?: number | null;
  commission_cost_r?: number | null;
  swap_cost_r?: number | null;
  total_cost_r?: number | null;
  net_pnl_r?: number | null;
  cost_profile_id?: string | null;
}

export interface CurvePoint {
  time: number;
  value: number;
}

export interface RunDetail extends RunSummary {
  schema_version: string;
  dataset: DatasetSummary;
  parameters: Record<string, number | boolean | string>;
  request: {
    start: string | null;
    end: string | null;
    timeframe: string;
    r_multiple: number;
    equity: number;
    risk_fraction: number;
  };
  range: {
    start: string;
    end: string;
    bar_count: number;
    gap_count: number;
  };
  reconciliation: Record<string, number>;
  signals: { total: number; by_type: Record<string, number> };
  equity_curve: { equity: CurvePoint[]; drawdown: CurvePoint[] };
  trade_distribution: { date: string; trades: number }[];
  trades: TradeRow[];
  trades_truncated: boolean;
  warnings: string[];
  assumptions: Record<string, string | boolean>;
}

export type ProviderSource = "stored" | "environment" | "none";

export interface ProviderCredential {
  id: string;
  name: string;
  description: string;
  env_var: string;
  required: boolean;
  configured: boolean;
  source: ProviderSource;
  hint: string;
  updated_at: string | null;
}

export interface Overview {
  generated_at: string;
  data_root: string;
  instruments: Instrument[];
  datasets: DatasetSummary[];
  strategies: StrategySummary[];
  runs: RunSummary[];
  warnings: string[];
  capabilities: {
    twelve_data: boolean;
    dukascopy: boolean;
    trade_simulation: string[];
    download_max_days: number;
  };
}

export interface RangeSummary {
  dataset_id: string;
  timeframe: string;
  derived: boolean;
  requested_start: string | null;
  requested_end: string | null;
  first_available: string | null;
  last_available: string | null;
  bar_count: number;
  total_frame_bars: number;
  gap_count: number;
  valid: boolean;
  error: string;
  frame_warnings: string[];
  quality: DatasetQuality;
}

export interface BarPoint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

export interface BacktestPayload {
  dataset_id: string;
  strategy_id: string;
  timeframe: string;
  parameters: Record<string, number | boolean | string>;
  start_date?: string;
  end_date?: string;
  r_multiple: number;
  equity: number;
  risk_fraction: number;
  cost_profile_id?: string;
  zone_ids?: string[];
}

/* -------------------------------------------------------------------------
 * Strategy research workspace
 * ---------------------------------------------------------------------- */

export type StrategyStatus =
  | "Draft"
  | "Research"
  | "Experimental"
  | "Validated"
  | "Archived";

export type ExperimentKind =
  | "baseline"
  | "experiment"
  | "repeat"
  | "out_of_sample";

export interface StrategyNote {
  id: string;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface StrategyRules {
  entry_conditions?: string[];
  confirmation_conditions?: string[];
  exit_conditions?: string[];
  stop_loss?: string;
  take_profit?: string;
  invalidation?: string;
  required_indicators?: string[];
  required_market_features?: string[];
  required_zone_configuration?: string;
  supported_instruments?: string[];
  supported_timeframes?: string[];
}

export interface WorkspaceRules {
  implemented: StrategyRules;
  proposed: string[];
  experimental: string[];
}

export interface StrategyVariation {
  id: string;
  title: string;
  description: string;
  hypothesis: string;
  changes_from_parent: string;
  entry_rule_differences: string;
  exit_rule_differences: string;
  filter_differences: string;
  parameter_config: Record<string, number | boolean | string>;
  zone_ids?: string[];
  instruments: string[];
  timeframes: string[];
  status: StrategyStatus;
  notes: string;
  is_baseline: boolean;
  implementation_status: "implemented" | "documentation_only";
  registry_strategy_id: string | null;
  configuration_version: number;
  cloned_from: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface ExperimentResultReference {
  run_id: string;
  run_created_at: string;
  dataset_id: string;
  bar_count: number;
  metrics: RunMetrics;
  warnings: string[];
  assumptions: Record<string, string | boolean>;
  total_r: number;
  total_cost_r?: number;
  trades_truncated?: boolean;
}

export interface StrategyExperiment {
  id: string;
  strategy_id: string;
  name: string;
  variation_id: string;
  status: "Planned" | "Running" | "Completed" | "Failed" | "Archived";
  research_objective: string;
  expected_outcome: string;
  actual_outcome: string;
  hypothesis_supported: boolean | null;
  next_steps: string;
  dataset_hash: string | null;
  execution_configuration: Record<string, unknown>;
  risk_configuration: Record<string, unknown>;
  gross_results: Partial<RunMetrics>;
  net_results: Partial<RunMetrics>;
  cost_profile: Partial<CostProfile>;
  validation_status: string;
  kind: ExperimentKind;
  experiment_kind: ExperimentKind;
  run_id: string;
  run_available: boolean;
  dataset_id: string;
  instrument: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  executed_at: string;
  variation_version: number;
  hypothesis: string;
  configuration: Record<string, unknown>;
  result_reference: ExperimentResultReference;
  notes: string;
  metrics: RunMetrics;
  total_r: number;
  bar_count: number;
  warnings: string[];
}

export interface StrategyWorkspaceSummary {
  id: string;
  title: string;
  registry_strategy_id: string | null;
  short_description: string;
  description: string;
  hypothesis: string;
  research_objective: string;
  trading_concept: string;
  risk_assumptions: string;
  category: string;
  status: StrategyStatus;
  tags: string[];
  created_at: string;
  updated_at: string;
  variation_count: number;
  baseline_variation_id: string | null;
  instruments: string[];
  timeframes: string[];
  last_experiment_at: string | null;
  linked_run_count: number;
  latest_experiment: StrategyExperiment | null;
}

export interface ComparisonRow {
  experiment_id: string;
  variation_id: string;
  variation_title: string;
  kind: ExperimentKind;
  run_id: string;
  run_available: boolean;
  trade_count: number | null;
  win_rate: number | null;
  profit_factor: number | null;
  expectancy: number | null;
  max_drawdown_r: number | null;
  avg_holding_duration: number | null;
  total_r: number | null;
  net_expectancy: number | null;
  net_total_r: number | null;
  cost_profile_id: string | null;
  total_cost_r: number | null;
  validation_status: string | null;
  sample_size_warning: boolean;
}

export interface ComparisonGroup {
  dataset_id: string;
  instrument: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  comparable: boolean;
  rows: ComparisonRow[];
}

export interface StrategyWorkspaceDetail extends StrategyWorkspaceSummary {
  rules: WorkspaceRules;
  notes: StrategyNote[];
  variations: StrategyVariation[];
  experiments: StrategyExperiment[];
  comparison: ComparisonGroup[];
}

export interface WorkspaceRunPreset {
  strategy_record_id: string;
  strategy_id: string;
  variation_id: string;
  variation_title: string;
  parameters: Record<string, number | boolean | string>;
  zone_ids?: string[];
  instrument?: string;
  timeframe?: string;
  dataset_id?: string;
  hypothesis?: string;
  experiment_kind?: ExperimentKind | "auto";
}

/* P1 — realistic backtesting */

export interface CostProfile {
  id: string;
  name: string;
  description: string;
  kind: string;
  estimated: boolean;
  spread_price: number;
  slippage_price_per_side: number;
  commission_per_round_trip: number;
  swap_per_night_r: number;
  instrument_overrides: Record<string, Record<string, number>>;
  source_note: string;
}

export interface ValidationIssue {
  code: string;
  severity: "error" | "warning" | "info";
  component: string;
  message: string;
  suggestion: string;
  trade_key?: string | null;
}

export interface PreflightResult {
  valid: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
  info: ValidationIssue[];
  details: Record<string, unknown>;
}

export interface RunValidation {
  run_id: string;
  checked_trades: number;
  valid: boolean;
  error_count: number;
  warning_count: number;
  findings: ValidationIssue[];
  independent_metrics: Record<string, number | null>;
}

export interface DatasetQualityReport {
  dataset_id: string;
  symbol: string;
  timeframe: string;
  year: number;
  provider: string;
  coverage: Record<string, string | null>;
  counts: {
    bar_count: number;
    duplicate_timestamp_count: number;
    order_violation_count: number;
    malformed_timestamp_count: number;
    invalid_bar_count: number;
    raw_gap_count: number | null;
    unexpected_gap_count: number;
    missing_open_minutes: number;
    missing_closure_minutes: number;
    bars_in_closure: number;
  };
  gaps: {
    before: string;
    after: string;
    duration_minutes: number;
    missing_open_minutes: number;
    missing_closed_minutes: number;
    unexpected: boolean;
  }[];
  derived: Record<string, {
    status: string;
    emitted_bar_count?: number;
    skipped_incomplete_buckets?: number;
    skipped_closed_buckets?: number;
    completeness_rule?: string;
    first_timestamp?: string | null;
    last_timestamp?: string | null;
    error?: string;
  }>;
  quality: { status: string; errors: string[]; warnings: string[]; notes: string[] };
  provenance: Record<string, unknown>;
  parse_error: string | null;
}

export interface RunDetail {
  net_metrics?: RunMetrics | null;
  cost_profile?: CostProfile | null;
  dataset_quality?: Partial<DatasetQualityReport> | null;
}

/* P2 — manual zone manager */

export interface ManualZone {
  id: string;
  dataset_id: string;
  instrument: string;
  source_timeframe: string;
  zone_type: "supply" | "demand" | "neutral";
  low: number;
  high: number;
  start_timestamp: string | null;
  effective_timestamp: string | null;
  invalidation_timestamp: string | null;
  status: "active" | "invalidated" | "archived";
  strength: number;
  notes: string;
  strategy_id: string | null;
  variation_id: string | null;
  provenance: string;
  source: string;
  version: number;
  created_at: string | null;
  updated_at: string | null;
  legacy: boolean;
  versions: ManualZone[];
  historical_import?: boolean;
  import_source?: string | null;
  import_operator?: string | null;
  imported_at?: string | null;
}

export interface ZonePayload {
  dataset_id?: string;
  source_timeframe?: string;
  zone_type?: string;
  low?: number;
  high?: number;
  start_timestamp?: string;
  effective_timestamp?: string;
  invalidation_timestamp?: string;
  status?: string;
  strength?: number;
  notes?: string;
  strategy_id?: string;
  variation_id?: string;
  historical_import?: boolean;
  import_source?: string;
  import_operator?: string;
}

export interface ResearchDashboard {
  strategy_count: number;
  variation_count: number;
  baseline_count: number;
  strategy_status_counts: Record<string, number>;
  experiment_status_counts: Record<string, number>;
  experiment_count: number;
  recent_experiments: StrategyExperiment[];
  recent_runs: RunSummary[];
  dataset_count: number;
  dataset_warning_count: number;
  outstanding_experiments: number;
  failed_experiments: number;
  validation_failures: number;
}

export interface ReproductionRecord {
  id: string;
  source_experiment_id: string;
  run_id: string;
  created_at: string;
  status: string;
  snapshot_version: number;
  comparison: { matches: boolean | null; differences: string[] };
}

export interface ExperimentAmendment {
  id: string;
  experiment_id: string;
  created_at: string;
  author: string;
  field: string;
  previous_value: unknown;
  new_value: unknown;
  reason: string;
}
