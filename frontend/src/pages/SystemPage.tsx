import { useCallback, useEffect, useState } from "react";
import { RefreshCw, ShieldCheck, Terminal } from "lucide-react";
import { api } from "../api";
import type { Overview, ProviderCredential } from "../types";
import { Button } from "../components/Button";
import { formatDateTime } from "../lib/format";
import {
  ErrorState,
  LoadingState,
  PageHeader,
  Panel,
  StatusPill,
} from "../components/Primitives";

const SETUP = [
  "python -m pip install -r requirements.txt",
  "export TWELVE_DATA_API_KEY=...",
  "python -m uvicorn server.main:app --host 0.0.0.0 --port 16901",
  "cd frontend && npm install && npm run dev -- --port 16900",
];

type Feedback = { id: string; tone: "ok" | "danger"; text: string };

function providerStatus(provider: ProviderCredential): {
  tone: "ok" | "warn" | "neutral";
  label: string;
} {
  if (provider.configured) {
    return {
      tone: "ok",
      label:
        provider.source === "stored"
          ? "configured · stored"
          : "configured · environment",
    };
  }
  return provider.required
    ? { tone: "warn", label: "none · required" }
    : { tone: "neutral", label: "optional · not set" };
}

export function SystemPage({ onRefresh }: { onRefresh?: () => void } = {}) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [providers, setProviders] = useState<ProviderCredential[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([api.overview(), api.providers()])
      .then(([overviewData, providerList]) => {
        if (cancelled) return;
        setOverview(overviewData);
        setProviders(providerList);
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
  }, [reloadKey]);

  const refreshData = useCallback(async () => {
    const [providerList, overviewData] = await Promise.all([
      api.providers(),
      api.overview(),
    ]);
    setProviders(providerList);
    setOverview(overviewData);
  }, []);

  const setDraft = useCallback((id: string, value: string) => {
    setDrafts((current) => ({ ...current, [id]: value }));
  }, []);

  const handleSave = async (provider: ProviderCredential) => {
    const apiKey = (drafts[provider.id] ?? "").trim();
    if (!apiKey) {
      setFeedback({
        id: provider.id,
        tone: "danger",
        text: "Enter an API key before saving.",
      });
      return;
    }
    setSavingId(provider.id);
    setFeedback(null);
    // Drop the secret from component state as soon as it is submitted.
    setDraft(provider.id, "");
    try {
      await api.saveProvider(provider.id, apiKey);
      await refreshData();
      setFeedback({
        id: provider.id,
        tone: "ok",
        text: `${provider.name} key stored server-side.`,
      });
      onRefresh?.();
    } catch (reason) {
      setFeedback({
        id: provider.id,
        tone: "danger",
        text: (reason as Error).message || "Could not save the key.",
      });
    } finally {
      setSavingId(null);
    }
  };

  const handleDelete = async (provider: ProviderCredential) => {
    setDeletingId(provider.id);
    setFeedback(null);
    setDraft(provider.id, "");
    try {
      await api.deleteProvider(provider.id);
      await refreshData();
      setFeedback({
        id: provider.id,
        tone: "ok",
        text: `Stored ${provider.name} key removed. An environment fallback still applies if set.`,
      });
      onRefresh?.();
    } catch (reason) {
      setFeedback({
        id: provider.id,
        tone: "danger",
        text: (reason as Error).message || "Could not remove the stored key.",
      });
    } finally {
      setDeletingId(null);
    }
  };

  if (loading && (!overview || !providers)) {
    return <LoadingState label="Reading system posture" />;
  }
  if (error && (!overview || !providers)) {
    return (
      <ErrorState
        message={error}
        action={
          <Button
            icon={<RefreshCw size={14} />}
            onClick={() => setReloadKey((current) => current + 1)}
          >
            Retry
          </Button>
        }
      />
    );
  }
  if (!overview || !providers) {
    return <LoadingState label="Reading system posture" />;
  }

  const twelveData = providers.find((provider) => provider.id === "twelve_data");
  const twelveDataStatus = twelveData?.configured
    ? twelveData.source === "stored"
      ? "configured (stored)"
      : "configured (environment)"
    : "absent";

  return (
    <div className="stack">
      <PageHeader
        eyebrow="System · operating envelope"
        title="Precision includes limits."
        subtitle="REX is a research kernel with a thin presentation layer. These are the boundaries that keep its numbers honest and its credentials server-side."
      />

      <div className="grid-main">
        <Panel
          kicker="Runtime"
          title="Setup and launch"
          subtitle="The UI talks to a FastAPI service on port 16901; Vite proxies /api from port 16900."
        >
          <div className="notice-list">
            <div className="notice-row">
              <Terminal size={13} strokeWidth={1.5} />
              <span className="mono" style={{ fontSize: 10 }}>
                {SETUP[0]}
              </span>
            </div>
            <div className="notice-row">
              <ShieldCheck size={13} strokeWidth={1.5} />
              <span className="mono" style={{ fontSize: 10 }}>
                {SETUP[1]}
              </span>
            </div>
            <div className="notice-row">
              <Terminal size={13} strokeWidth={1.5} />
              <span className="mono" style={{ fontSize: 10 }}>
                {SETUP[2]}
              </span>
            </div>
            <div className="notice-row">
              <Terminal size={13} strokeWidth={1.5} />
              <span className="mono" style={{ fontSize: 10 }}>
                {SETUP[3]}
              </span>
            </div>
          </div>
          <div className="divider" />
          <div className="detail-list">
            <div className="detail-row">
              <span className="detail-key">Data root</span>
              <span className="detail-value">{overview.data_root}</span>
            </div>
            <div className="detail-row">
              <span className="detail-key">Twelve Data key</span>
              <span className="detail-value">{twelveDataStatus}</span>
            </div>
            <div className="detail-row">
              <span className="detail-key">Download window</span>
              <span className="detail-value">
                {overview.capabilities.download_max_days} days per UI request
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-key">Trade simulation</span>
              <span className="detail-value">
                {overview.capabilities.trade_simulation.join(", ") || "none"}
              </span>
            </div>
          </div>
        </Panel>

        <Panel
          kicker="Boundary"
          title="What this terminal does not do"
          subtitle="Unavailable capabilities are stated, not simulated."
        >
          <div className="notice-list">
            <div className="notice-row">
              <span className="mono" style={{ color: "var(--gold)" }}>
                —
              </span>
              <span>No live trading, broker orders, or portfolio management.</span>
            </div>
            <div className="notice-row">
              <span className="mono" style={{ color: "var(--gold)" }}>
                —
              </span>
              <span>No transaction costs, spread, slippage, or financing in P&amp;L.</span>
            </div>
            <div className="notice-row">
              <span className="mono" style={{ color: "var(--gold)" }}>
                —
              </span>
              <span>No currency equity or compounding; results are R-multiples.</span>
            </div>
            <div className="notice-row">
              <span className="mono" style={{ color: "var(--gold)" }}>
                —
              </span>
              <span>No out-of-sample or walk-forward protocol is enforced yet.</span>
            </div>
            <div className="notice-row">
              <span className="mono" style={{ color: "var(--gold)" }}>
                —
              </span>
              <span>No authentication or multi-user isolation; run this locally.</span>
            </div>
          </div>
          <div className="divider" />
          <div className="kv">
            <span className="kv-key">Research mode</span>
            <span className="kv-value">causal · deterministic · local</span>
          </div>
        </Panel>
      </div>

      <Panel
        kicker="Credentials"
        title="Provider API keys"
        subtitle="Store, replace, or remove data-provider keys. Values are written on the server and only a masked hint ever reaches the browser."
      >
        {providers.length === 0 ? (
          <p className="field-hint">No providers are registered on the server.</p>
        ) : (
          <div className="provider-list">
            {providers.map((provider) => {
              const status = providerStatus(provider);
              const busy = savingId === provider.id || deletingId === provider.id;
              const draft = drafts[provider.id] ?? "";
              return (
                <article className="provider-key-card" key={provider.id}>
                  <div className="provider-head">
                    <div>
                      <h3 className="provider-name">{provider.name}</h3>
                      <p className="provider-env mono">{provider.env_var}</p>
                    </div>
                    <StatusPill tone={status.tone}>{status.label}</StatusPill>
                  </div>

                  <p className="provider-desc">{provider.description}</p>

                  <div className="provider-meta">
                    <span className="provider-meta-label">Masked key</span>
                    <span className="mono">
                      {provider.configured ? provider.hint : "not set"}
                    </span>
                    <span className="provider-meta-label">Source</span>
                    <span>{provider.source}</span>
                    <span className="provider-meta-label">Updated</span>
                    <span>{provider.updated_at ? formatDateTime(provider.updated_at) : "—"}</span>
                  </div>

                  {!provider.required ? (
                    <p className="field-hint">
                      The current adapter does not require a key, but an optional
                      reservation can be stored for future use.
                    </p>
                  ) : null}

                  <form
                    className="provider-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void handleSave(provider);
                    }}
                  >
                    <label className="field provider-field">
                      <span className="field-label">
                        {provider.source === "stored" ? "New key" : "API key"}
                      </span>
                      <input
                        className="input mono"
                        type="password"
                        name={`api-key-${provider.id}`}
                        autoComplete="off"
                        spellCheck={false}
                        value={draft}
                        placeholder={
                          provider.source === "stored"
                            ? "Enter a replacement key"
                            : "Paste the provider key"
                        }
                        onChange={(event) => setDraft(provider.id, event.target.value)}
                        disabled={busy}
                      />
                    </label>
                    <div className="provider-actions">
                      <Button
                        type="submit"
                        variant="primary"
                        size="sm"
                        loading={savingId === provider.id}
                        disabled={deletingId === provider.id}
                      >
                        {provider.source === "stored" ? "Update key" : "Save key"}
                      </Button>
                      {provider.source === "stored" ? (
                        <Button
                          type="button"
                          variant="danger"
                          size="sm"
                          loading={deletingId === provider.id}
                          disabled={savingId === provider.id}
                          onClick={() => void handleDelete(provider)}
                        >
                          Remove stored key
                        </Button>
                      ) : null}
                    </div>
                  </form>

                  {feedback && feedback.id === provider.id ? (
                    <p className={`provider-feedback ${feedback.tone}`} role="status">
                      {feedback.text}
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}

        <div className="divider" />
        <p className="field-hint">
          Keys are stored server-side in{" "}
          <span className="mono">data/provider_keys.json</span> with{" "}
          <span className="mono">0600</span> permissions and are never returned to the
          browser — the API only exposes a masked hint. Environment variables remain a
          supported fallback when no stored key exists.
        </p>
        <p className="field-hint">
          Optional providers may reserve a key even when the current adapter does not need
          one. New providers are added to the server registry in{" "}
          <span className="mono">server/provider_keys.py</span> and appear here
          automatically.
        </p>
      </Panel>

      <div className="grid-2">
        <Panel kicker="Security" title="Key handling">
          <div className="detail-list">
            <div className="detail-row">
              <span className="detail-key">Client exposure</span>
              <span className="detail-value">none</span>
            </div>
            <div className="detail-row">
              <span className="detail-key">Run artifacts</span>
              <span className="detail-value">no credentials</span>
            </div>
            <div className="detail-row">
              <span className="detail-key">Logs</span>
              <span className="detail-value">redacted provider errors</span>
            </div>
          </div>
          <div className="divider" />
          <p className="field-hint">
            Submitted keys are held only long enough to reach the API, then cleared from
            browser state. They are never written to local storage, URL parameters, or
            the console.
          </p>
        </Panel>

        <Panel kicker="Data policy" title="Provider posture">
          <div className="detail-list">
            <div className="detail-row">
              <span className="detail-key">Twelve Data</span>
              <span className="detail-value">
                free tier · internal research only
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-key">Dukascopy</span>
              <span className="detail-value">legacy adapter · personal use</span>
            </div>
            <div className="detail-row">
              <span className="detail-key">Commercial use</span>
              <span className="detail-value">requires a provider licence</span>
            </div>
          </div>
          <div className="divider" />
          <div className="notice-list">
            <div className="notice-row">
              <span className="mono" style={{ color: "var(--gold)" }}>
                !
              </span>
              <span>
                Free-tier data is for internal research. Do not redistribute or present
                it as a commercial data feed without a licence.
              </span>
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <StatusPill tone={overview.capabilities.twelve_data ? "ok" : "warn"}>
              {overview.capabilities.twelve_data
                ? "Twelve Data configured"
                : "Twelve Data unset"}
            </StatusPill>
          </div>
        </Panel>
      </div>

      <Panel kicker="Architecture" title="Separation of concerns">
        <div className="detail-list">
          <div className="detail-row">
            <span className="detail-key">Research kernel</span>
            <span className="detail-value">
              historical/ · strategies/ · execution/ · backtests/
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-key">API composition</span>
            <span className="detail-value">server/research_service.py</span>
          </div>
          <div className="detail-row">
            <span className="detail-key">Presentation</span>
            <span className="detail-value">frontend/ · React + Vite</span>
          </div>
          <div className="detail-row">
            <span className="detail-key">Run artifacts</span>
            <span className="detail-value">research/outputs/ui_runs/*.json</span>
          </div>
        </div>
        <p className="field-hint" style={{ marginTop: 14 }}>
          The frontend never calculates strategy metrics. It renders backend results and
          labels their assumptions. The UI cannot change strategy behavior.
        </p>
      </Panel>
    </div>
  );
}
