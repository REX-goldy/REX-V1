import type { ReactNode } from "react";
import {
  Archive,
  BookOpen,
  Database,
  FlaskConical,
  Layers,
  LayoutDashboard,
  Settings2,
  MapPin,
} from "lucide-react";

export type PageId =
  | "overview"
  | "data"
  | "zones"
  | "research"
  | "workspace"
  | "runs"
  | "handbook"
  | "system";

const NAV: Array<{
  id: PageId;
  label: string;
  index: string;
  icon: typeof LayoutDashboard;
}> = [
  { id: "overview", label: "Overview", index: "01", icon: LayoutDashboard },
  { id: "data", label: "Market Data", index: "02", icon: Database },
  { id: "zones", label: "Zone Manager", index: "03", icon: MapPin },
  { id: "research", label: "Strategy Lab", index: "04", icon: FlaskConical },
  { id: "workspace", label: "Strategy Workspace", index: "05", icon: Layers },
  { id: "runs", label: "Run Archive", index: "06", icon: Archive },
  { id: "handbook", label: "Help & Handbook", index: "07", icon: BookOpen },
  { id: "system", label: "System", index: "08", icon: Settings2 },
];

const ROUTE_LABEL: Record<PageId, string> = {
  overview: "Research Overview",
  data: "Historical Data",
  zones: "Zone Manager",
  research: "Strategy Lab",
  workspace: "Strategy Workspace",
  runs: "Run Archive",
  handbook: "Help & Handbook",
  system: "System & Limits",
};

export function AppShell({
  page,
  onNavigate,
  children,
  datasetCount,
  warningCount,
  providerReady,
  clock,
}: {
  page: PageId;
  onNavigate: (page: PageId) => void;
  children: ReactNode;
  datasetCount: number;
  warningCount: number;
  providerReady: boolean;
  clock: string;
}) {
  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="sidebar-brand">
          <div className="brand-mark" aria-hidden="true">
            R
          </div>
          <div className="brand-copy">
            <p className="brand-name">REX</p>
            <p className="brand-sub">Quant Research Terminal</p>
          </div>
        </div>

        <div className="sidebar-section-label">Workspace</div>
        <nav className="sidebar-nav">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={`nav-item ${page === item.id ? "active" : ""}`}
                onClick={() => onNavigate(item.id)}
                aria-current={page === item.id ? "page" : undefined}
              >
                <Icon />
                <span className="nav-label">{item.label}</span>
                <span className="nav-index">{item.index}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="provider-card">
            <div className="provider-card-title">
              <span>Twelve Data</span>
              <span className={`status-dot ${providerReady ? "ok" : "warn"}`} />
            </div>
            <div className="provider-card-meta">
              {providerReady ? "Key present · backend only" : "Key not configured"}
            </div>
          </div>
          <div className="sidebar-footnote">
            Evidence before conviction.
            <br />
            No live trading · no broker orders.
          </div>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div className="topbar-route">
            <span className="topbar-route-index">
              {NAV.find((item) => item.id === page)?.index ?? "00"}
            </span>
            <span className="topbar-route-name">{ROUTE_LABEL[page]}</span>
          </div>
          <div className="topbar-spacer" />
          <div className="topbar-status">
            <span className="topbar-status-item">
              <span className={`status-dot ${providerReady ? "ok" : "warn"}`} />
              {providerReady ? "Provider ready" : "Provider unset"}
            </span>
            <span className="topbar-status-item">
              <span className={`status-dot ${datasetCount ? "ok" : "neutral"}`} />
              {datasetCount} dataset{datasetCount === 1 ? "" : "s"}
            </span>
            {warningCount > 0 ? (
              <span className="topbar-status-item">
                <span className="status-dot warn" />
                {warningCount} warning{warningCount === 1 ? "" : "s"}
              </span>
            ) : null}
            <span className="clock">{clock} UTC</span>
          </div>
        </header>
        <main className="content">
          <div className="page-enter">{children}</div>
        </main>
      </div>
    </div>
  );
}
