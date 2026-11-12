import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { Overview } from "./types";
import { AppShell, type PageId } from "./components/AppShell";
import { OverviewPage } from "./pages/OverviewPage";
import { DataPage } from "./pages/DataPage";
import { ResearchPage } from "./pages/ResearchPage";
import { RunsPage } from "./pages/RunsPage";
import { HandbookPage } from "./pages/HandbookPage";
import { SystemPage } from "./pages/SystemPage";
import { StrategyWorkspacePage } from "./pages/StrategyWorkspacePage";
import { ZoneManagerPage } from "./pages/ZoneManagerPage";
import type { WorkspaceRunPreset } from "./types";

function useUtcClock(): string {
  const [clock, setClock] = useState(() => new Date().toISOString().slice(11, 16));
  useEffect(() => {
    const timer = window.setInterval(() => {
      setClock(new Date().toISOString().slice(11, 16));
    }, 30_000);
    return () => window.clearInterval(timer);
  }, []);
  return clock;
}

export default function App() {
  const [page, setPage] = useState<PageId>("overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [handbookArticle, setHandbookArticle] = useState("what-is-rex");
  const [workspaceStrategyId, setWorkspaceStrategyId] = useState<string | null>(null);
  const [labPreset, setLabPreset] = useState<WorkspaceRunPreset | null>(null);
  const clock = useUtcClock();

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
    if (page !== "research") setLabPreset(null);
  }, [page]);

  const refresh = useCallback(() => {
    setRefreshKey((current) => current + 1);
  }, []);

  const openHelp = useCallback((article: string) => {
    setHandbookArticle(article);
    setPage("handbook");
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .overview()
      .then((data) => {
        if (!cancelled) setOverview(data);
      })
      .catch(() => {
        /* individual pages surface their own errors */
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <AppShell
      page={page}
      onNavigate={setPage}
      datasetCount={overview?.datasets.length ?? 0}
      warningCount={overview?.warnings.length ?? 0}
      providerReady={Boolean(overview?.capabilities.twelve_data)}
      clock={clock}
    >
      {page === "overview" ? (
        <OverviewPage onNavigate={setPage} refreshKey={refreshKey} />
      ) : null}
      {page === "data" ? (
        <DataPage refreshKey={refreshKey} onRefresh={refresh} onOpenHelp={openHelp} />
      ) : null}
      {page === "zones" ? <ZoneManagerPage /> : null}
      {page === "research" ? (
        <ResearchPage
          refreshKey={refreshKey}
          onRefresh={refresh}
          onOpenHelp={openHelp}
          workspacePreset={labPreset}
        />
      ) : null}
      {page === "workspace" ? (
        <StrategyWorkspacePage
          refreshKey={refreshKey}
          initialStrategyId={workspaceStrategyId}
          onSelectStrategy={setWorkspaceStrategyId}
          onRunExperiment={(preset) => {
            setLabPreset(preset);
            setPage("research");
          }}
        />
      ) : null}
      {page === "runs" ? (
        <RunsPage refreshKey={refreshKey} onOpenHelp={openHelp} />
      ) : null}
      {page === "handbook" ? (
        <HandbookPage
          initialArticle={handbookArticle}
          onSelectArticle={setHandbookArticle}
        />
      ) : null}
      {page === "system" ? <SystemPage onRefresh={refresh} /> : null}
    </AppShell>
  );
}
