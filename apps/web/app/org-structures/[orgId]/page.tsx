"use client";

import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VATabs } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

interface EntityRow {
  entity_id: string;
  name: string;
  entity_type: string;
  currency: string | null;
  country_iso: string | null;
  is_root: boolean;
  baseline_id: string | null;
  status: string | null;
}

interface OwnershipRow {
  parent_entity_id: string;
  child_entity_id: string;
  ownership_pct: number;
  voting_pct: number | null;
  consolidation_method: string | null;
  effective_date: string | null;
}

interface IntercompanyRow {
  link_id: string;
  from_entity_id: string;
  to_entity_id: string;
  link_type: string;
  description: string | null;
}

interface OrgDetail {
  org_id: string;
  group_name: string;
  reporting_currency: string;
  status: string;
  consolidation_method: string | null;
  eliminate_intercompany: boolean;
  minority_interest_treatment: string | null;
  created_at: string | null;
  entities: EntityRow[];
  ownership: OwnershipRow[];
  intercompany: IntercompanyRow[];
}

interface HierarchyNode {
  entity_id: string;
  name: string;
  entity_type: string;
  ownership_pct: number | null;
  children: HierarchyNode[];
}

function HierarchyTree({ nodes, depth = 0 }: { nodes: HierarchyNode[]; depth?: number }) {
  if (!nodes.length) return <p className="text-sm text-va-text2">No hierarchy (add entities and ownership).</p>;
  return (
    <ul className={depth > 0 ? "ml-4 mt-1 border-l border-va-border pl-3" : "space-y-1"}>
      {nodes.map((n) => (
        <li key={n.entity_id} className="py-0.5">
          <span className="font-medium text-va-text">{n.name}</span>
          <span className="ml-2 text-sm text-va-text2">
            {n.entity_type}
            {n.ownership_pct != null && ` · ${n.ownership_pct}%`}
          </span>
          {n.children.length > 0 && (
            <HierarchyTree nodes={n.children} depth={depth + 1} />
          )}
        </li>
      ))}
    </ul>
  );
}

export default function OrgStructureDetailPage() {
  const params = useParams();
  const orgId = params.orgId as string;
  const [data, setData] = useState<OrgDetail | null>(null);
  const [hierarchy, setHierarchy] = useState<{ roots: HierarchyNode[] } | null>(null);
  const [validation, setValidation] = useState<{ status: string; checks: { check: string; status: string; message: string }[] } | null>(null);
  const [runs, setRuns] = useState<{ consolidated_run_id: string; status: string; created_at: string | null }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | undefined>(undefined);
  const [activeTab, setActiveTab] = useState("hierarchy");
  const [runTriggering, setRunTriggering] = useState(false);
  const [validating, setValidating] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsForm, setSettingsForm] = useState({
    consolidation_method: "full",
    eliminate_intercompany: true,
    minority_interest_treatment: "proportional",
  });

  const load = useCallback(async () => {
    if (!tenantId) return;
    try {
      const [orgRes, hierRes, runsRes] = await Promise.all([
        api.orgStructures.get(tenantId, orgId),
        api.orgStructures.hierarchy(tenantId, orgId),
        api.orgStructures.runs(tenantId, orgId),
      ]);
      setData(orgRes as OrgDetail);
      setHierarchy({ roots: hierRes.roots as HierarchyNode[] });
      setRuns(runsRes.items);
      setSettingsForm({
        consolidation_method: (orgRes as OrgDetail).consolidation_method || "full",
        eliminate_intercompany: (orgRes as OrgDetail).eliminate_intercompany ?? true,
        minority_interest_treatment: (orgRes as OrgDetail).minority_interest_treatment || "proportional",
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, orgId]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
    })();
  }, []);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

  async function handleValidate() {
    if (!tenantId) return;
    setValidating(true);
    setError(null);
    try {
      const res = await api.orgStructures.validate(tenantId, orgId);
      setValidation(res as { status: string; checks: { check: string; status: string; message: string }[] });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setValidating(false);
    }
  }

  async function handleRun() {
    if (!tenantId) return;
    setRunTriggering(true);
    setError(null);
    try {
      await api.orgStructures.run(tenantId, userId, orgId);
      const runsRes = await api.orgStructures.runs(tenantId, orgId);
      setRuns(runsRes.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunTriggering(false);
    }
  }

  async function handleSaveSettings() {
    if (!tenantId || !data) return;
    setSettingsSaving(true);
    setError(null);
    try {
      await api.orgStructures.update(tenantId, orgId, {
        consolidation_method: settingsForm.consolidation_method,
        eliminate_intercompany: settingsForm.eliminate_intercompany,
        minority_interest_treatment: settingsForm.minority_interest_treatment,
      });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSettingsSaving(false);
    }
  }

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link
            href="/org-structures"
            className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded"
          >
            ← Group Structures
          </Link>
        </div>
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            {data?.group_name ?? orgId}
          </h1>
          <div className="flex gap-2">
            <VAButton type="button" variant="secondary" onClick={handleValidate} disabled={validating}>
              {validating ? "Validating…" : "Validate"}
            </VAButton>
            {validation && (
              <span
                className={`flex items-center rounded-va-xs px-2 py-1 text-sm ${
                  validation.status === "passed"
                    ? "bg-va-success/20 text-va-success"
                    : validation.status === "failed"
                      ? "bg-va-danger/20 text-va-danger"
                      : "bg-va-warning/20 text-va-warning"
                }`}
              >
                {validation.status}
              </span>
            )}
          </div>
        </div>
        {error && (
          <div
            className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
            role="alert"
          >
            {error}
          </div>
        )}
        {validation && validation.checks.length > 0 && (
          <VACard className="mb-6 p-4">
            <h3 className="mb-2 text-sm font-medium text-va-text">Validation checks</h3>
            <ul className="space-y-1 text-sm">
              {validation.checks.map((c, i) => (
                <li key={i} className={c.status === "failed" ? "text-va-danger" : c.status === "warning" ? "text-va-warning" : "text-va-text2"}>
                  {c.check}: {c.message}
                </li>
              ))}
            </ul>
          </VACard>
        )}
        {loading ? (
          <p className="text-va-text2">Loading…</p>
        ) : !data ? (
          <p className="text-va-text2">Group structure not found.</p>
        ) : (
          <VATabs
            activeId={activeTab}
            onSelect={setActiveTab}
            tabs={[
              {
                id: "hierarchy",
                label: "Hierarchy",
                content: (
                  <div>
                    <h3 className="mb-2 text-sm font-medium text-va-text2">Ownership tree</h3>
                    <HierarchyTree nodes={hierarchy?.roots ?? []} />
                  </div>
                ),
              },
              {
                id: "entities",
                label: "Entities",
                content: (
                  <div>
                    <p className="mb-2 text-sm text-va-text2">{data.entities.length} entities</p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-va-border text-left text-va-text2">
                            <th className="pb-2 pr-4">Name</th>
                            <th className="pb-2 pr-4">Type</th>
                            <th className="pb-2 pr-4">Currency</th>
                            <th className="pb-2 pr-4">Root</th>
                            <th className="pb-2">Baseline</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.entities.map((e) => (
                            <tr key={e.entity_id} className="border-b border-va-border/60">
                              <td className="py-2 pr-4 font-medium text-va-text">{e.name}</td>
                              <td className="py-2 pr-4 text-va-text2">{e.entity_type}</td>
                              <td className="py-2 pr-4 text-va-text2">{e.currency ?? "—"}</td>
                              <td className="py-2 pr-4 text-va-text2">{e.is_root ? "Yes" : "No"}</td>
                              <td className="py-2 text-va-text2">{e.baseline_id ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ),
              },
              {
                id: "intercompany",
                label: "Intercompany",
                content: (
                  <div>
                    <p className="mb-2 text-sm text-va-text2">{data.intercompany.length} links</p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-va-border text-left text-va-text2">
                            <th className="pb-2 pr-4">From</th>
                            <th className="pb-2 pr-4">To</th>
                            <th className="pb-2 pr-4">Type</th>
                            <th className="pb-2">Description</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.intercompany.map((i) => (
                            <tr key={i.link_id} className="border-b border-va-border/60">
                              <td className="py-2 pr-4 text-va-text">{i.from_entity_id}</td>
                              <td className="py-2 pr-4 text-va-text">{i.to_entity_id}</td>
                              <td className="py-2 pr-4 text-va-text2">{i.link_type}</td>
                              <td className="py-2 text-va-text2">{i.description ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ),
              },
              {
                id: "settings",
                label: "Consolidation settings",
                content: (
                  <div className="max-w-md space-y-4">
                    <div>
                      <label className="mb-1 block text-sm text-va-text2">Default consolidation method</label>
                      <select
                        value={settingsForm.consolidation_method}
                        onChange={(e) => setSettingsForm((s) => ({ ...s, consolidation_method: e.target.value }))}
                        className="w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-va-text focus:border-va-blue focus:outline-none focus:ring-1 focus:ring-va-blue"
                      >
                        <option value="full">Full</option>
                        <option value="proportional">Proportional</option>
                        <option value="equity_method">Equity Method</option>
                      </select>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="elim"
                        checked={settingsForm.eliminate_intercompany}
                        onChange={(e) => setSettingsForm((s) => ({ ...s, eliminate_intercompany: e.target.checked }))}
                        className="rounded border-va-border"
                      />
                      <label htmlFor="elim" className="text-sm text-va-text2">Eliminate intercompany</label>
                    </div>
                    <div>
                      <label className="mb-1 block text-sm text-va-text2">Minority interest treatment</label>
                      <select
                        value={settingsForm.minority_interest_treatment}
                        onChange={(e) => setSettingsForm((s) => ({ ...s, minority_interest_treatment: e.target.value }))}
                        className="w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-va-text focus:border-va-blue focus:outline-none focus:ring-1 focus:ring-va-blue"
                      >
                        <option value="proportional">Proportional</option>
                        <option value="full_goodwill">Full goodwill</option>
                      </select>
                    </div>
                    <VAButton type="button" variant="primary" onClick={handleSaveSettings} disabled={settingsSaving}>
                      {settingsSaving ? "Saving…" : "Save"}
                    </VAButton>
                  </div>
                ),
              },
              {
                id: "run",
                label: "Run",
                content: (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2">
                      <VAButton type="button" variant="primary" onClick={handleRun} disabled={runTriggering}>
                        {runTriggering ? "Triggering…" : "Run consolidation"}
                      </VAButton>
                    </div>
                    <div>
                      <h3 className="mb-2 text-sm font-medium text-va-text2">Runs</h3>
                      {runs.length === 0 ? (
                        <p className="text-sm text-va-text2">No runs yet.</p>
                      ) : (
                        <ul className="space-y-2">
                          {runs.map((r) => (
                            <li
                              key={r.consolidated_run_id}
                              className="flex items-center justify-between rounded-va-xs border border-va-border bg-va-surface/50 px-3 py-2 text-sm"
                            >
                              <span className="font-mono text-va-text2">{r.consolidated_run_id}</span>
                              <span
                                className={
                                  r.status === "succeeded"
                                    ? "text-va-success"
                                    : r.status === "failed"
                                      ? "text-va-danger"
                                      : "text-va-text2"
                                }
                              >
                                {r.status}
                              </span>
                              {r.created_at && (
                                <span className="text-va-text2">{new Date(r.created_at).toLocaleString()}</span>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                ),
              },
            ]}
          />
        )}
      </main>
    </div>
  );
}
