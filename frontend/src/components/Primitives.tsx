import type { ReactNode } from "react";
import { AlertTriangle, Inbox, LoaderCircle } from "lucide-react";

export type Tone = "ok" | "warn" | "danger" | "neutral" | "gold";

export function StatusPill({
  tone = "neutral",
  children,
}: {
  tone?: Tone;
  children: ReactNode;
}) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

export function Metric({
  label,
  value,
  meta,
  tone,
  small = false,
  className = "",
}: {
  label: string;
  value: ReactNode;
  meta?: ReactNode;
  tone?: "positive" | "negative" | "gold";
  small?: boolean;
  className?: string;
}) {
  return (
    <div className={`metric ${className}`.trim()}>
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${small ? "small" : ""} ${tone ?? ""}`.trim()}>
        {value}
      </div>
      {meta ? <div className="metric-meta">{meta}</div> : null}
    </div>
  );
}

export function Panel({
  kicker,
  title,
  subtitle,
  action,
  children,
  flush = false,
  className = "",
}: {
  kicker?: string;
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  flush?: boolean;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`.trim()}>
      {title || kicker || action ? (
        <div className="panel-head">
          <div className="panel-head-copy">
            {kicker ? <p className="panel-kicker">{kicker}</p> : null}
            {title ? <h2 className="panel-title">{title}</h2> : null}
            {subtitle ? <p className="panel-subtitle">{subtitle}</p> : null}
          </div>
          {action ? <div className="panel-action">{action}</div> : null}
        </div>
      ) : null}
      <div className={`panel-body ${flush ? "flush" : ""}`.trim()}>{children}</div>
    </section>
  );
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow: string;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="page-title">{title}</h1>
        {subtitle ? <p className="page-subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function Field({
  label,
  hint,
  children,
  span = false,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  span?: boolean;
}) {
  return (
    <label className={`field ${span ? "span-2" : ""}`.trim()}>
      <span className="field-label">{label}</span>
      {children}
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

export function EmptyState({
  title,
  copy,
  action,
}: {
  title: string;
  copy: string;
  action?: ReactNode;
}) {
  return (
    <div className="state-block">
      <div className="state-icon">
        <Inbox size={18} strokeWidth={1.4} />
      </div>
      <h3 className="state-title">{title}</h3>
      <p className="state-copy">{copy}</p>
      {action}
    </div>
  );
}

export function LoadingState({ label = "Reading research state" }: { label?: string }) {
  return (
    <div className="state-block">
      <LoaderCircle size={18} strokeWidth={1.4} className="gold" />
      <p className="state-copy">{label}</p>
      <div className="loading-line" />
    </div>
  );
}

export function ErrorState({
  title = "The research service did not answer",
  message,
  action,
}: {
  title?: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div className="state-block">
      <div className="state-icon">
        <AlertTriangle size={18} strokeWidth={1.4} />
      </div>
      <h3 className="state-title">{title}</h3>
      <p className="state-copy">{message}</p>
      {action}
    </div>
  );
}

