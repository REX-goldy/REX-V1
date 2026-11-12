"""FastAPI application for the REX research terminal."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from historical.exceptions import (
    HistoricalConfigurationError,
    HistoricalDownloadError,
)
from server import provider_keys
from server import research_service as service
from server import strategy_workspace as workspace
from backtests.costs import CostProfileError, get_cost_profiles
from backtests.validation import validate_run
from historical.quality import DatasetQualityError, build_dataset_quality_report
from server.preflight import validate_backtest
from server import zone_store

logger = logging.getLogger("rex.api")
ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"

app = FastAPI(title="REX Research Terminal", version="0.1.0")
# Dev app: accept any origin (the shared preview URL changes per session).
# Credentials are deliberately disabled so the wildcard is valid.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DownloadRequest(BaseModel):
    provider: str = Field(pattern="^(twelve_data|dukascopy)$")
    symbol: str
    timeframe: str = "M1"
    start_date: date
    end_date: date


class ProviderKeyRequest(BaseModel):
    api_key: str


class WorkspacePayload(BaseModel):
    """Flexible additive payload for the research workspace routes."""

    title: str | None = None
    short_description: str | None = None
    description: str | None = None
    hypothesis: str | None = None
    research_objective: str | None = None
    trading_concept: str | None = None
    risk_assumptions: str | None = None
    category: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    registry_strategy_id: str | None = None
    implemented_rules: dict[str, Any] | None = None
    proposed_rules: list[str] | None = None
    experimental_rules: list[str] | None = None
    rules: dict[str, Any] | None = None
    baseline_title: str | None = None
    baseline_description: str | None = None
    baseline_hypothesis: str | None = None
    baseline_parameters: dict[str, Any] | None = None
    baseline_notes: str | None = None
    instruments: list[str] | None = None
    timeframes: list[str] | None = None
    body: str | None = None
    variation_id: str | None = None
    changes_from_parent: str | None = None
    entry_rule_differences: str | None = None
    exit_rule_differences: str | None = None
    filter_differences: str | None = None
    parameter_config: dict[str, Any] | None = None
    notes: str | None = None
    cloned_from: str | None = None
    run_id: str | None = None
    name: str | None = None
    experiment_kind: str | None = None
    dataset_id: str | None = None
    timeframe: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    research_objective: str | None = None
    expected_outcome: str | None = None
    actual_outcome: str | None = None
    next_steps: str | None = None
    hypothesis_supported: bool | None = None
    author: str | None = None
    reason: str | None = None
    cost_profile: dict[str, Any] | None = None
    zone_ids: list[str] | None = None
    equity: float | None = None
    risk_fraction: float | None = None
    r_multiple: float | None = None


class BacktestRequest(BaseModel):
    dataset_id: str
    strategy_id: str
    timeframe: str = "M1"
    parameters: dict[str, Any] = Field(default_factory=dict)
    start_date: date | None = None
    end_date: date | None = None
    r_multiple: float = Field(default=2.0, gt=0, le=100)
    equity: float = Field(default=100_000.0, gt=0)
    risk_fraction: float = Field(default=0.01, gt=0, le=0.1)
    cost_profile_id: str = "zero_costs"
    zone_ids: list[str] = Field(default_factory=list)


class ZonePayload(BaseModel):
    dataset_id: str | None = None
    source_timeframe: str | None = None
    zone_type: str | None = None
    low: float | None = None
    high: float | None = None
    start_timestamp: str | None = None
    effective_timestamp: str | None = None
    invalidation_timestamp: str | None = None
    status: str | None = None
    strength: int | None = None
    notes: str | None = None
    strategy_id: str | None = None
    variation_id: str | None = None
    historical_import: bool | None = None
    import_source: str | None = None
    import_operator: str | None = None


def _fail(exc: Exception) -> HTTPException:
    if isinstance(exc, workspace.WorkspaceNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, workspace.ReproductionError):
        return HTTPException(
            status_code=409,
            detail=f"{exc.code}: {exc}",
        )
    if isinstance(exc, workspace.WorkspaceConflict):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, workspace.WorkspaceValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, workspace.WorkspaceStoreError):
        logger.warning("Strategy workspace store failure: %s", exc)
        return HTTPException(status_code=500, detail="Strategy workspace store error")
    if isinstance(exc, zone_store.ZoneNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, zone_store.ZoneStoreError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, CostProfileError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, provider_keys.UnknownProviderError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, provider_keys.InvalidProviderKeyError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, provider_keys.ProviderKeyStoreError):
        logger.warning("Provider key store failure: %s", exc)
        return HTTPException(status_code=500, detail="Provider key store error")
    if isinstance(exc, service.DatasetNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, service.DownloadBusyError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, HistoricalConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, HistoricalDownloadError):
        return HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    logger.exception("Unhandled API error")
    return HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "rex-research-terminal"}


@app.get("/api/settings/providers")
def settings_providers() -> list[dict[str, Any]]:
    try:
        return provider_keys.list_provider_credentials()
    except Exception as exc:
        raise _fail(exc) from exc


@app.put("/api/settings/providers/{provider_id}")
def save_settings_provider(
    provider_id: str, payload: ProviderKeyRequest
) -> dict[str, Any]:
    try:
        return provider_keys.set_provider_key(provider_id, payload.api_key)
    except Exception as exc:
        raise _fail(exc) from exc


@app.delete("/api/settings/providers/{provider_id}")
def delete_settings_provider(provider_id: str) -> dict[str, Any]:
    try:
        return provider_keys.delete_provider_key(provider_id)
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/overview")
def overview() -> dict[str, Any]:
    try:
        return service.overview()
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise _fail(exc) from exc


@app.get("/api/strategies")
def strategies() -> list[dict[str, Any]]:
    return service.list_strategies()


@app.get("/api/cost-profiles")
def cost_profiles() -> list[dict[str, Any]]:
    try:
        return [profile.to_dict() for profile in get_cost_profiles()]
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/zones")
def zones(symbol: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    try:
        return zone_store.list_zones(symbol=symbol, status=status)
    except Exception as exc:
        raise _fail(exc) from exc


@app.post("/api/zones")
def create_zone(payload: ZonePayload) -> dict[str, Any]:
    try:
        return zone_store.create_zone(payload.model_dump(exclude_unset=True))
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/zones/{zone_id}")
def get_zone(zone_id: str) -> dict[str, Any]:
    try:
        return zone_store.get_zone(zone_id)
    except Exception as exc:
        raise _fail(exc) from exc


@app.patch("/api/zones/{zone_id}")
def update_zone(zone_id: str, payload: ZonePayload) -> dict[str, Any]:
    try:
        return zone_store.update_zone(zone_id, payload.model_dump(exclude_unset=True))
    except Exception as exc:
        raise _fail(exc) from exc


@app.delete("/api/zones/{zone_id}")
def archive_zone(zone_id: str) -> dict[str, Any]:
    try:
        return zone_store.archive_zone(zone_id)
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/dataset-quality")
def dataset_quality(dataset_id: str) -> dict[str, Any]:
    try:
        return build_dataset_quality_report(dataset_id)
    except DatasetQualityError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/datasets")
def datasets() -> list[dict[str, Any]]:
    try:
        return service.list_datasets()
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/dataset")
def dataset(dataset_id: str, timeframe: str = "M1") -> dict[str, Any]:
    try:
        return service.dataset_detail(dataset_id, timeframe=timeframe)
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/frame")
def frame(dataset_id: str, timeframe: str = "M1") -> dict[str, Any]:
    try:
        return service.frame_detail(dataset_id, timeframe=timeframe)
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/range")
def range_summary(
    dataset_id: str,
    timeframe: str = "M1",
    start: date | None = None,
    end: date | None = None,
) -> dict[str, Any]:
    try:
        return service.range_summary(
            dataset_id, timeframe=timeframe, start=start, end=end
        )
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/bars")
def bars(
    dataset_id: str,
    timeframe: str = "M1",
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(default=600, ge=1, le=5000),
) -> list[dict[str, Any]]:
    try:
        return service.dataset_bars(
            dataset_id, timeframe=timeframe, start=start, end=end, limit=limit
        )
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/runs")
def runs(limit: int = Query(default=25, ge=1, le=100)) -> list[dict[str, Any]]:
    return service.list_runs(limit=limit)


@app.get("/api/runs/{run_id}")
def run(run_id: str) -> dict[str, Any]:
    try:
        return service.get_run(run_id)
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/runs/{run_id}/validation")
def validate_run_endpoint(run_id: str) -> dict[str, Any]:
    try:
        return validate_run(service.get_run(run_id))
    except Exception as exc:
        raise _fail(exc) from exc


@app.post("/api/validation/backtest")
def validate_backtest_endpoint(payload: BacktestRequest) -> dict[str, Any]:
    try:
        return validate_backtest(
            dataset_id=payload.dataset_id,
            strategy_id=payload.strategy_id,
            timeframe=payload.timeframe,
            parameters=payload.parameters,
            start=payload.start_date,
            end=payload.end_date,
            r_multiple=payload.r_multiple,
            equity=payload.equity,
            risk_fraction=payload.risk_fraction,
            cost_profile_id=payload.cost_profile_id,
            zone_ids=payload.zone_ids,
        )
    except Exception as exc:
        raise _fail(exc) from exc


@app.post("/api/backtests")
def backtest(payload: BacktestRequest) -> dict[str, Any]:
    try:
        return service.run_backtest(
            dataset_id=payload.dataset_id,
            strategy_id=payload.strategy_id,
            timeframe=payload.timeframe,
            parameters=payload.parameters,
            start=payload.start_date,
            end=payload.end_date,
            r_multiple=payload.r_multiple,
            equity=payload.equity,
            risk_fraction=payload.risk_fraction,
            cost_profile_id=payload.cost_profile_id,
            zone_ids=payload.zone_ids,
        )
    except Exception as exc:
        raise _fail(exc) from exc


@app.post("/api/downloads")
def download(payload: DownloadRequest) -> list[dict[str, Any]]:
    try:
        return service.download_dataset(
            provider=payload.provider,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            start=payload.start_date,
            end=payload.end_date,
        )
    except Exception as exc:
        raise _fail(exc) from exc


# ---------------------------------------------------------------------------
# Strategy research workspace
# ---------------------------------------------------------------------------


def _workspace_payload(payload: WorkspacePayload) -> dict[str, Any]:
    return payload.model_dump(exclude_unset=True)


@app.get("/api/workspace/dashboard")
def workspace_dashboard() -> dict[str, Any]:
    try:
        return workspace.dashboard()
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/workspace/strategies")
def workspace_strategies(
    query: str = "",
    status: str | None = None,
    category: str | None = None,
    sort: str = "recent",
) -> list[dict[str, Any]]:
    try:
        return workspace.list_strategies(
            query=query, status=status, category=category, sort=sort
        )
    except Exception as exc:
        raise _fail(exc) from exc


@app.post("/api/workspace/strategies")
def create_workspace_strategy(payload: WorkspacePayload) -> dict[str, Any]:
    try:
        return workspace.create_strategy(_workspace_payload(payload))
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/workspace/strategies/{strategy_id}")
def workspace_strategy(strategy_id: str) -> dict[str, Any]:
    try:
        return workspace.get_strategy(strategy_id)
    except Exception as exc:
        raise _fail(exc) from exc


@app.patch("/api/workspace/strategies/{strategy_id}")
def update_workspace_strategy(
    strategy_id: str, payload: WorkspacePayload
) -> dict[str, Any]:
    try:
        return workspace.update_strategy(strategy_id, _workspace_payload(payload))
    except Exception as exc:
        raise _fail(exc) from exc


@app.delete("/api/workspace/strategies/{strategy_id}")
def archive_workspace_strategy(strategy_id: str) -> dict[str, Any]:
    try:
        return workspace.archive_strategy(strategy_id)
    except Exception as exc:
        raise _fail(exc) from exc


@app.post("/api/workspace/strategies/{strategy_id}/notes")
def add_workspace_note(
    strategy_id: str, payload: WorkspacePayload
) -> dict[str, Any]:
    try:
        return workspace.add_note(strategy_id, payload.body or "")
    except Exception as exc:
        raise _fail(exc) from exc


@app.patch("/api/workspace/strategies/{strategy_id}/notes/{note_id}")
def update_workspace_note(
    strategy_id: str, note_id: str, payload: WorkspacePayload
) -> dict[str, Any]:
    try:
        return workspace.update_note(strategy_id, note_id, payload.body or "")
    except Exception as exc:
        raise _fail(exc) from exc


@app.delete("/api/workspace/strategies/{strategy_id}/notes/{note_id}")
def delete_workspace_note(strategy_id: str, note_id: str) -> dict[str, Any]:
    try:
        return workspace.delete_note(strategy_id, note_id)
    except Exception as exc:
        raise _fail(exc) from exc


@app.post("/api/workspace/strategies/{strategy_id}/variations")
def create_workspace_variation(
    strategy_id: str, payload: WorkspacePayload
) -> dict[str, Any]:
    try:
        return workspace.create_variation(strategy_id, _workspace_payload(payload))
    except Exception as exc:
        raise _fail(exc) from exc


@app.patch("/api/workspace/strategies/{strategy_id}/variations/{variation_id}")
def update_workspace_variation(
    strategy_id: str, variation_id: str, payload: WorkspacePayload
) -> dict[str, Any]:
    try:
        return workspace.update_variation(
            strategy_id, variation_id, _workspace_payload(payload)
        )
    except Exception as exc:
        raise _fail(exc) from exc


@app.delete("/api/workspace/strategies/{strategy_id}/variations/{variation_id}")
def archive_workspace_variation(strategy_id: str, variation_id: str) -> dict[str, Any]:
    try:
        return workspace.archive_variation(strategy_id, variation_id)
    except Exception as exc:
        raise _fail(exc) from exc


@app.post("/api/workspace/strategies/{strategy_id}/variations/{variation_id}/clone")
def clone_workspace_variation(
    strategy_id: str, variation_id: str, payload: WorkspacePayload
) -> dict[str, Any]:
    try:
        return workspace.clone_variation(
            strategy_id, variation_id, _workspace_payload(payload)
        )
    except Exception as exc:
        raise _fail(exc) from exc


@app.post("/api/workspace/strategies/{strategy_id}/experiments")
def record_workspace_experiment(
    strategy_id: str, payload: WorkspacePayload
) -> dict[str, Any]:
    try:
        return workspace.record_experiment(strategy_id, _workspace_payload(payload))
    except Exception as exc:
        raise _fail(exc) from exc


@app.post("/api/workspace/strategies/{strategy_id}/experiments/plan")
def plan_workspace_experiment(
    strategy_id: str, payload: WorkspacePayload
) -> dict[str, Any]:
    try:
        return workspace.create_planned_experiment(strategy_id, _workspace_payload(payload))
    except Exception as exc:
        raise _fail(exc) from exc


@app.patch("/api/workspace/strategies/{strategy_id}/experiments/{experiment_id}")
def update_workspace_experiment(
    strategy_id: str, experiment_id: str, payload: WorkspacePayload
) -> dict[str, Any]:
    try:
        return workspace.update_experiment(strategy_id, experiment_id, _workspace_payload(payload))
    except Exception as exc:
        raise _fail(exc) from exc


@app.post("/api/workspace/strategies/{strategy_id}/experiments/{experiment_id}/reproduce")
def reproduce_workspace_experiment(strategy_id: str, experiment_id: str) -> dict[str, Any]:
    try:
        return workspace.reproduce_experiment(strategy_id, experiment_id)
    except Exception as exc:
        raise _fail(exc) from exc


@app.post("/api/workspace/strategies/{strategy_id}/experiments/{experiment_id}/amendments")
def amend_workspace_experiment(
    strategy_id: str, experiment_id: str, payload: WorkspacePayload
) -> dict[str, Any]:
    try:
        return workspace.amend_experiment(strategy_id, experiment_id, _workspace_payload(payload))
    except Exception as exc:
        raise _fail(exc) from exc


@app.delete("/api/workspace/strategies/{strategy_id}/experiments/{experiment_id}")
def archive_workspace_experiment(strategy_id: str, experiment_id: str) -> dict[str, Any]:
    try:
        return workspace.delete_experiment(strategy_id, experiment_id)
    except Exception as exc:
        raise _fail(exc) from exc


@app.get("/api/workspace/strategies/{strategy_id}/comparison")
def workspace_comparison(strategy_id: str) -> list[dict[str, Any]]:
    try:
        return workspace.get_strategy(strategy_id)["comparison"]
    except Exception as exc:
        raise _fail(exc) from exc


if (DIST / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def frontend() -> FileResponse:
        return FileResponse(DIST / "index.html")
else:

    @app.get("/")
    def api_root() -> dict[str, str]:
        return {
            "service": "rex-research-terminal",
            "docs": "/docs",
            "note": "Build frontend/ (npm run build) to serve the UI from this process.",
        }
