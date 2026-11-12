import type {
  BacktestPayload,
  BarPoint,
  DatasetSummary,
  Overview,
  ProviderCredential,
  RangeSummary,
  RunDetail,
  RunSummary,
  StrategyWorkspaceDetail,
  StrategyWorkspaceSummary,
  StrategyVariation,
  StrategyNote,
  StrategyExperiment,
  WorkspaceRunPreset,
  StrategySummary,
} from "./types";

const API = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {
      /* keep the status message */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export interface DownloadPayload {
  provider: "twelve_data" | "dukascopy";
  symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
}

export const api = {
  overview: () => request<Overview>("/overview"),
  datasets: () => request<DatasetSummary[]>("/datasets"),
  dataset: (dataset_id: string, timeframe = "M1") =>
    request<DatasetSummary>(
      `/dataset?dataset_id=${encodeURIComponent(dataset_id)}&timeframe=${encodeURIComponent(timeframe)}`,
    ),
  frame: (dataset_id: string, timeframe = "M1") =>
    request<DatasetSummary>(
      `/frame?dataset_id=${encodeURIComponent(dataset_id)}&timeframe=${encodeURIComponent(timeframe)}`,
    ),
  range: (dataset_id: string, timeframe: string, start?: string, end?: string) => {
    const params = new URLSearchParams({ dataset_id, timeframe });
    if (start) params.set("start", start);
    if (end) params.set("end", end);
    return request<RangeSummary>(`/range?${params.toString()}`);
  },
  strategies: () => request<StrategySummary[]>("/strategies"),
  bars: (
    dataset_id: string,
    timeframe = "M1",
    limit = 600,
    start?: string,
    end?: string,
  ) => {
    const params = new URLSearchParams({
      dataset_id,
      timeframe,
      limit: String(limit),
    });
    if (start) params.set("start", start);
    if (end) params.set("end", end);
    return request<BarPoint[]>(`/bars?${params.toString()}`);
  },
  runs: (limit = 25) => request<RunSummary[]>(`/runs?limit=${limit}`),
  run: (id: string) => request<RunDetail>(`/runs/${encodeURIComponent(id)}`),
  backtest: (payload: BacktestPayload) =>
    request<RunDetail>("/backtests", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  download: (payload: DownloadPayload) =>
    request<DatasetSummary[]>("/downloads", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  providers: () => request<ProviderCredential[]>("/settings/providers"),
  saveProvider: (id: string, apiKey: string) =>
    request<ProviderCredential>(`/settings/providers/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify({ api_key: apiKey }),
    }),
  deleteProvider: (id: string) =>
    request<ProviderCredential>(`/settings/providers/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
};

export interface StrategyWorkspacePayload {
  [key: string]: unknown;
}

export interface WorkspaceExperimentPayload {
  variation_id: string;
  run_id: string;
  name?: string;
  hypothesis?: string;
  experiment_kind?: string;
  notes?: string;
}

const workspaceBase = "/workspace/strategies";

export const workspaceApi = {
  list: (params: { query?: string; status?: string; category?: string; sort?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.query) search.set("query", params.query);
    if (params.status) search.set("status", params.status);
    if (params.category) search.set("category", params.category);
    if (params.sort) search.set("sort", params.sort);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<StrategyWorkspaceSummary[]>(`${workspaceBase}${suffix}`);
  },
  get: (id: string) =>
    request<StrategyWorkspaceDetail>(`${workspaceBase}/${encodeURIComponent(id)}`),
  create: (payload: StrategyWorkspacePayload) =>
    request<StrategyWorkspaceDetail>(workspaceBase, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (id: string, payload: StrategyWorkspacePayload) =>
    request<StrategyWorkspaceDetail>(`${workspaceBase}/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  archive: (id: string) =>
    request<StrategyWorkspaceDetail>(`${workspaceBase}/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  addNote: (id: string, body: string) =>
    request<StrategyNote>(`${workspaceBase}/${encodeURIComponent(id)}/notes`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }),
  updateNote: (id: string, noteId: string, body: string) =>
    request<StrategyNote>(
      `${workspaceBase}/${encodeURIComponent(id)}/notes/${encodeURIComponent(noteId)}`,
      { method: "PATCH", body: JSON.stringify({ body }) },
    ),
  deleteNote: (id: string, noteId: string) =>
    request<{ deleted: string }>(
      `${workspaceBase}/${encodeURIComponent(id)}/notes/${encodeURIComponent(noteId)}`,
      { method: "DELETE" },
    ),
  createVariation: (id: string, payload: StrategyWorkspacePayload) =>
    request<StrategyWorkspaceDetail>(
      `${workspaceBase}/${encodeURIComponent(id)}/variations`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  updateVariation: (id: string, variationId: string, payload: StrategyWorkspacePayload) =>
    request<StrategyWorkspaceDetail>(
      `${workspaceBase}/${encodeURIComponent(id)}/variations/${encodeURIComponent(variationId)}`,
      { method: "PATCH", body: JSON.stringify(payload) },
    ),
  archiveVariation: (id: string, variationId: string) =>
    request<StrategyWorkspaceDetail>(
      `${workspaceBase}/${encodeURIComponent(id)}/variations/${encodeURIComponent(variationId)}`,
      { method: "DELETE" },
    ),
  cloneVariation: (id: string, variationId: string, payload: StrategyWorkspacePayload = {}) =>
    request<StrategyWorkspaceDetail>(
      `${workspaceBase}/${encodeURIComponent(id)}/variations/${encodeURIComponent(variationId)}/clone`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  recordExperiment: (id: string, payload: WorkspaceExperimentPayload) =>
    request<StrategyWorkspaceDetail>(
      `${workspaceBase}/${encodeURIComponent(id)}/experiments`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
  comparison: (id: string) =>
    request<StrategyWorkspaceDetail["comparison"]>(
      `${workspaceBase}/${encodeURIComponent(id)}/comparison`,
    ),
};

export type { StrategyVariation, StrategyExperiment, WorkspaceRunPreset };

export const p1Api = {
  costProfiles: () => request<import("./types").CostProfile[]>("/cost-profiles"),
  datasetQuality: (dataset_id: string) =>
    request<import("./types").DatasetQualityReport>(
      `/dataset-quality?dataset_id=${encodeURIComponent(dataset_id)}`,
    ),
  validateBacktest: (payload: import("./types").BacktestPayload & {
    start_date?: string;
    end_date?: string;
  }) =>
    request<import("./types").PreflightResult>("/validation/backtest", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  validateRun: (runId: string) =>
    request<import("./types").RunValidation>(
      `/runs/${encodeURIComponent(runId)}/validation`,
    ),
};

export const zoneApi = {
  list: (params: { symbol?: string; status?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.symbol) search.set("symbol", params.symbol);
    if (params.status) search.set("status", params.status);
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return request<import("./types").ManualZone[]>(`/zones${suffix}`);
  },
  get: (id: string) =>
    request<import("./types").ManualZone>(`/zones/${encodeURIComponent(id)}`),
  create: (payload: import("./types").ZonePayload) =>
    request<import("./types").ManualZone>("/zones", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (id: string, payload: import("./types").ZonePayload) =>
    request<import("./types").ManualZone>(`/zones/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  archive: (id: string) =>
    request<import("./types").ManualZone>(`/zones/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
};

export const workspaceDashboardApi = {
  get: () => request<import("./types").ResearchDashboard>("/workspace/dashboard"),
};

export const workspaceIntegrityApi = {
  reproduceExperiment: (strategyId: string, experimentId: string) =>
    request<{ experiment: import("./types").StrategyExperiment; reproduction: import("./types").ReproductionRecord }>(
      `/workspace/strategies/${encodeURIComponent(strategyId)}/experiments/${encodeURIComponent(experimentId)}/reproduce`,
      { method: "POST" },
    ),
  amendExperiment: (
    strategyId: string,
    experimentId: string,
    payload: { notes?: string; actual_outcome?: string; hypothesis_supported?: boolean; next_steps?: string; author?: string; reason?: string },
  ) =>
    request<import("./types").StrategyWorkspaceDetail>(
      `/workspace/strategies/${encodeURIComponent(strategyId)}/experiments/${encodeURIComponent(experimentId)}/amendments`,
      { method: "POST", body: JSON.stringify(payload) },
    ),
};
