"use client";

import { api, type ScenarioItem } from "@/lib/api";
import { ConfigViewer } from "@/components/ConfigViewer";
import { FundingPanel } from "@/components/FundingPanel";
import { CorrelationMatrixEditor } from "@/components/CorrelationMatrixEditor";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VAInput, VASelect, VASpinner, useToast } from "@/components/ui";
import { Nav } from "@/components/nav";
import { EntityTimeline } from "@/components/EntityTimeline";
import { CommentThread } from "@/components/CommentThread";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function BaselineDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const { toast } = useToast();
  const [config, setConfig] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [runCreating, setRunCreating] = useState(false);
  const [editLoading, setEditLoading] = useState(false);

  // Version history
  const [versions, setVersions] = useState<{ baseline_version: string; is_active: boolean; status: string; created_at: string | null }[]>([]);
  const [diffVersionA, setDiffVersionA] = useState("");
  const [diffVersionB, setDiffVersionB] = useState("");
  const [diffResult, setDiffResult] = useState<{ key: string; valueA: unknown; valueB: unknown }[] | null>(null);
  const [diffing, setDiffing] = useState(false);

  // Run config form
  const [showRunForm, setShowRunForm] = useState(false);
  const [scenarioId, setScenarioId] = useState("");
  const [mcEnabled, setMcEnabled] = useState(false);
  const [numSims, setNumSims] = useState("1000");
  const [seed, setSeed] = useState("42");
  const [wacc, setWacc] = useState("");
  const [termGrowth, setTermGrowth] = useState("");
  const [scenarios, setScenarios] = useState<ScenarioItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
      try {
        const res = await api.baselines.get(ctx.tenantId, id);
        if (!cancelled) setConfig(res.model_config);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
      try {
        const scRes = await api.scenarios.list(ctx.tenantId, { baseline_id: id });
        if (!cancelled) setScenarios(scRes.items ?? []);
      } catch { /* scenarios optional */ }
      try {
        const vRes = await api.baselines.listVersions(ctx.tenantId, id);
        if (!cancelled) setVersions(vRes.items ?? []);
      } catch { /* versions optional */ }
    })();
    return () => {
      cancelled = true;
    };
  }, [router, id]);

  async function createRun() {
    if (!tenantId) return;
    setRunCreating(true);
    try {
      const opts: Parameters<typeof api.runs.create>[2] = {};
      if (scenarioId) opts.scenarioId = scenarioId;
      if (mcEnabled) {
        opts.mcEnabled = true;
        opts.numSimulations = parseInt(numSims, 10) || 1000;
        opts.seed = parseInt(seed, 10) || 42;
      }
      if (wacc || termGrowth) {
        opts.valuationConfig = {
          ...(wacc ? { wacc: parseFloat(wacc) } : {}),
          ...(termGrowth ? { terminal_growth_rate: parseFloat(termGrowth) } : {}),
        };
      }
      const res = await api.runs.create(tenantId, id, opts);
      toast.success("Run created");
      router.push(`/runs/${res.run_id}`);
      router.refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(msg);
      setError(msg);
    } finally {
      setRunCreating(false);
    }
  }

  async function handleEditConfig() {
    if (!tenantId) return;
    setEditLoading(true);
    try {
      const draftsRes = await api.drafts.list(tenantId, {
        status: "active",
        parent_baseline_id: id,
      });
      if (draftsRes.items.length > 0) {
        router.push(`/drafts/${draftsRes.items[0].draft_session_id}?tab=funding`);
      } else {
        const newDraft = await api.drafts.create(tenantId, { parent_baseline_id: id });
        router.push(`/drafts/${newDraft.draft_session_id}?tab=funding`);
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to open editor");
    } finally {
      setEditLoading(false);
    }
  }

  async function handleDiff() {
    if (!tenantId || !diffVersionA || !diffVersionB) return;
    setDiffing(true);
    try {
      const [a, b] = await Promise.all([
        api.baselines.getVersion(tenantId, id, diffVersionA),
        api.baselines.getVersion(tenantId, id, diffVersionB),
      ]);
      const configA = (a.model_config as Record<string, unknown>) ?? {};
      const configB = (b.model_config as Record<string, unknown>) ?? {};
      const allKeys = Array.from(new Set([...Object.keys(configA), ...Object.keys(configB)]));
      const diffs = allKeys
        .filter((k) => JSON.stringify(configA[k]) !== JSON.stringify(configB[k]))
        .map((k) => ({ key: k, valueA: configA[k], valueB: configB[k] }));
      setDiffResult(diffs);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDiffing(false);
    }
  }

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link
            href="/baselines"
            className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded"
          >
            ← Baselines
          </Link>
        </div>
        <div className="mb-6 flex items-center justify-between">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Baseline {id}
          </h1>
          <div className="flex items-center gap-3">
            <VAButton variant="secondary" onClick={handleEditConfig} disabled={editLoading}>
              {editLoading ? "Opening\u2026" : "Edit Configuration"}
            </VAButton>
            <VAButton
              type="button"
              variant={showRunForm ? "ghost" : "primary"}
              onClick={() => setShowRunForm((v) => !v)}
              disabled={!config}
            >
              {showRunForm ? "Cancel" : "Run model"}
            </VAButton>
          </div>
        </div>
        {showRunForm && !!config && (
          <VACard className="mb-6 space-y-4 p-4">
            <h2 className="font-brand text-lg font-medium text-va-text">Run configuration</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">Scenario (optional)</label>
                <VASelect value={scenarioId} onChange={(e) => setScenarioId(e.target.value)}>
                  <option value="">None — baseline only</option>
                  {scenarios.map((s) => (
                    <option key={s.scenario_id} value={s.scenario_id}>{s.label}</option>
                  ))}
                </VASelect>
              </div>
              <div className="flex items-end gap-3">
                <label className="flex items-center gap-2 text-sm text-va-text">
                  <input
                    type="checkbox"
                    checked={mcEnabled}
                    onChange={(e) => setMcEnabled(e.target.checked)}
                    className="h-4 w-4 rounded border-va-border bg-va-surface text-va-blue focus:ring-va-blue"
                  />
                  Monte Carlo simulation
                </label>
              </div>
            </div>
            {mcEnabled && (
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">Simulations</label>
                  <VAInput type="number" value={numSims} onChange={(e) => setNumSims(e.target.value)} placeholder="1000" />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">Seed</label>
                  <VAInput type="number" value={seed} onChange={(e) => setSeed(e.target.value)} placeholder="42" />
                </div>
              </div>
            )}
            <details className="text-sm">
              <summary className="cursor-pointer text-xs text-va-text2 hover:text-va-text">Valuation config (optional)</summary>
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">WACC (%)</label>
                  <VAInput type="number" value={wacc} onChange={(e) => setWacc(e.target.value)} placeholder="e.g. 0.10" />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">Terminal growth rate</label>
                  <VAInput type="number" value={termGrowth} onChange={(e) => setTermGrowth(e.target.value)} placeholder="e.g. 0.02" />
                </div>
              </div>
            </details>
            <VAButton type="button" variant="primary" onClick={createRun} disabled={runCreating}>
              {runCreating ? "Creating run…" : "Create run"}
            </VAButton>
          </VACard>
        )}
        {error && (
          <div
            className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
            role="alert"
          >
            {error}
          </div>
        )}
        {loading ? (
          <VASpinner label="Loading…" />
        ) : config ? (
          <div>
            <p className="mb-4 text-sm text-va-text2">
              Model config loaded. Use &quot;Run model&quot; to execute and view
              statements and KPIs.
            </p>

            {/* Funding panel */}
            {!!(config as Record<string, unknown>).assumptions && (
              <VACard className="mb-6 p-4">
                <h2 className="mb-3 font-brand text-lg font-medium text-va-text">Funding</h2>
                <FundingPanel
                  funding={
                    ((config as Record<string, unknown>).assumptions as Record<string, unknown>)
                      ?.funding as Record<string, unknown> | null | undefined
                  }
                />
              </VACard>
            )}

            {/* Correlation matrix */}
            {Array.isArray((config as Record<string, unknown>).distributions) &&
              ((config as Record<string, unknown>).distributions as unknown[]).length >= 2 && (
              <VACard className="mb-6 p-4">
                <h2 className="mb-3 font-brand text-lg font-medium text-va-text">Driver Correlations</h2>
                <CorrelationMatrixEditor
                  distributions={(config as Record<string, unknown>).distributions as { ref: string; family: string }[]}
                  correlationMatrix={
                    ((config as Record<string, unknown>).correlation_matrix as { ref_a: string; ref_b: string; rho: number }[]) ?? []
                  }
                />
              </VACard>
            )}

            {/* Revenue streams with business line info */}
            {!!(config as Record<string, unknown>).assumptions && (() => {
              const assumptions = (config as Record<string, unknown>).assumptions as Record<string, unknown>;
              const streams = (assumptions?.revenue_streams ?? []) as Record<string, unknown>[];
              const hasSegments = streams.some((s) => s.business_line || s.launch_month != null);
              if (!hasSegments) return null;
              return (
                <VACard className="mb-6 p-4">
                  <h2 className="mb-3 font-brand text-lg font-medium text-va-text">Revenue Streams</h2>
                  <div className="overflow-x-auto rounded-va-lg border border-va-border">
                    <table className="w-full text-sm text-va-text">
                      <thead>
                        <tr className="border-b border-va-border bg-va-surface">
                          <th className="px-3 py-2 text-left font-medium">Label</th>
                          <th className="px-3 py-2 text-left font-medium">Type</th>
                          <th className="px-3 py-2 text-left font-medium">Business Line</th>
                          <th className="px-3 py-2 text-left font-medium">Market</th>
                          <th className="px-3 py-2 text-right font-medium">Launch</th>
                          <th className="px-3 py-2 text-right font-medium">Ramp</th>
                          <th className="px-3 py-2 text-left font-medium">Curve</th>
                        </tr>
                      </thead>
                      <tbody>
                        {streams.map((s, i) => (
                          <tr key={i} className="border-b border-va-border/50">
                            <td className="px-3 py-2 font-medium">{String(s.label ?? "")}</td>
                            <td className="px-3 py-2 text-va-text2">{String(s.stream_type ?? "").replace(/_/g, " ")}</td>
                            <td className="px-3 py-2">{String(s.business_line ?? "—")}</td>
                            <td className="px-3 py-2 text-va-text2">{String(s.market ?? "—")}</td>
                            <td className="px-3 py-2 text-right font-mono">{s.launch_month != null ? `M${s.launch_month}` : "—"}</td>
                            <td className="px-3 py-2 text-right font-mono">{s.ramp_up_months != null ? `${s.ramp_up_months}mo` : "—"}</td>
                            <td className="px-3 py-2 text-va-text2">{s.ramp_curve ? String(s.ramp_curve).replace(/_/g, " ") : "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </VACard>
              );
            })()}

            <ConfigViewer config={config as Record<string, unknown>} />
          </div>
        ) : (
          <p className="text-va-text2">Baseline not found.</p>
        )}

        {versions.length > 1 && !loading && (
          <VACard className="mt-6 p-4">
            <h2 className="mb-3 font-brand text-lg font-medium text-va-text">
              Version history ({versions.length} versions)
            </h2>
            <ul className="mb-4 space-y-1">
              {versions.map((v) => (
                <li key={v.baseline_version} className="flex items-center justify-between text-sm">
                  <span className={`font-mono ${v.is_active ? "text-va-blue font-medium" : "text-va-text2"}`}>
                    {v.baseline_version}
                    {v.is_active && " (active)"}
                  </span>
                  <span className="text-xs text-va-text2">
                    {v.created_at ? new Date(v.created_at).toLocaleDateString() : "—"}
                  </span>
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap items-end gap-3 border-t border-va-border pt-4">
              <div>
                <label className="mb-1 block text-xs text-va-text2">Version A</label>
                <VASelect value={diffVersionA} onChange={(e) => setDiffVersionA(e.target.value)}>
                  <option value="">Select…</option>
                  {versions.map((v) => (
                    <option key={v.baseline_version} value={v.baseline_version}>{v.baseline_version}</option>
                  ))}
                </VASelect>
              </div>
              <div>
                <label className="mb-1 block text-xs text-va-text2">Version B</label>
                <VASelect value={diffVersionB} onChange={(e) => setDiffVersionB(e.target.value)}>
                  <option value="">Select…</option>
                  {versions.map((v) => (
                    <option key={v.baseline_version} value={v.baseline_version}>{v.baseline_version}</option>
                  ))}
                </VASelect>
              </div>
              <VAButton
                type="button"
                variant="secondary"
                onClick={handleDiff}
                disabled={!diffVersionA || !diffVersionB || diffVersionA === diffVersionB || diffing}
              >
                {diffing ? "Diffing…" : "Compare versions"}
              </VAButton>
            </div>
            {diffResult && (
              <div className="mt-4">
                {diffResult.length === 0 ? (
                  <p className="text-sm text-va-text2">No differences found.</p>
                ) : (
                  <div className="overflow-x-auto rounded-va-lg border border-va-border">
                    <table className="w-full text-xs text-va-text">
                      <thead>
                        <tr className="border-b border-va-border bg-va-surface">
                          <th className="px-3 py-2 text-left font-medium">Key</th>
                          <th className="px-3 py-2 text-left font-medium">{diffVersionA}</th>
                          <th className="px-3 py-2 text-left font-medium">{diffVersionB}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {diffResult.map((d) => (
                          <tr key={d.key} className="border-b border-va-border/50">
                            <td className="px-3 py-2 font-mono font-medium">{d.key}</td>
                            <td className="px-3 py-2 font-mono text-va-danger/80">
                              <pre className="whitespace-pre-wrap">{JSON.stringify(d.valueA, null, 2) ?? "—"}</pre>
                            </td>
                            <td className="px-3 py-2 font-mono text-green-400/80">
                              <pre className="whitespace-pre-wrap">{JSON.stringify(d.valueB, null, 2) ?? "—"}</pre>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </VACard>
        )}

        {tenantId && !loading && (
          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <VACard className="p-4">
              <h2 className="mb-3 font-brand text-lg font-medium text-va-text">
                History
              </h2>
              <EntityTimeline
                tenantId={tenantId}
                resourceType="baseline"
                resourceId={id}
              />
            </VACard>
            <VACard className="p-4">
              <h2 className="mb-3 font-brand text-lg font-medium text-va-text">
                Comments
              </h2>
              {userId && (
                <CommentThread
                  tenantId={tenantId}
                  userId={userId}
                  entityType="baseline"
                  entityId={id}
                />
              )}
            </VACard>
          </div>
        )}
      </main>
    </div>
  );
}
