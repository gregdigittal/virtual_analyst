"use client";

import { api, type WorkflowTemplate, type WorkflowInstance } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VAInput, VASelect, VASpinner, useToast } from "@/components/ui";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function WorkflowsPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [instances, setInstances] = useState<WorkflowInstance[]>([]);

  // Create form
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [entityType, setEntityType] = useState("");
  const [entityId, setEntityId] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      try {
        const [tRes, iRes] = await Promise.all([
          api.workflows.listTemplates(ctx.tenantId),
          api.workflows.listInstances(ctx.tenantId),
        ]);
        if (!cancelled) {
          setTemplates(tRes.templates ?? []);
          setInstances(iRes.instances ?? []);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [router]);

  async function handleCreateInstance() {
    if (!tenantId || !selectedTemplateId || !entityType || !entityId) return;
    setCreating(true);
    try {
      const res = await api.workflows.createInstance(tenantId, {
        template_id: selectedTemplateId,
        entity_type: entityType,
        entity_id: entityId,
      });
      toast.success(`Workflow started: ${res.instance_id}`);
      router.push(`/workflows/${res.instance_id}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  }

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="font-brand mb-6 text-2xl font-semibold tracking-tight text-va-text">
          Workflows
        </h1>
        {error && (
          <div className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger" role="alert">
            {error}
          </div>
        )}
        {loading ? (
          <VASpinner label="Loading workflows…" />
        ) : (
          <div className="space-y-8">
            {/* Templates */}
            <section>
              <h2 className="font-brand mb-3 text-lg font-medium text-va-text">Templates</h2>
              {templates.length === 0 ? (
                <p className="text-sm text-va-text2">No workflow templates found.</p>
              ) : (
                <div className="overflow-x-auto rounded-va-lg border border-va-border">
                  <table className="w-full text-sm text-va-text">
                    <thead>
                      <tr className="border-b border-va-border bg-va-surface">
                        <th className="px-3 py-2 text-left font-medium">Name</th>
                        <th className="px-3 py-2 text-left font-medium">Stages</th>
                        <th className="px-3 py-2 text-left font-medium">Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {templates.map((t) => (
                        <tr key={t.template_id} className="border-b border-va-border/50">
                          <td className="px-3 py-2 font-medium">{t.name}</td>
                          <td className="px-3 py-2 text-va-text2">{t.stages.length}</td>
                          <td className="px-3 py-2 text-va-text2">{t.description ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* Create instance */}
            <section>
              <h2 className="font-brand mb-3 text-lg font-medium text-va-text">Start workflow</h2>
              <VACard className="space-y-4 p-4">
                <div className="grid gap-4 sm:grid-cols-3">
                  <div>
                    <label className="mb-1 block text-sm font-medium text-va-text">Template</label>
                    <VASelect value={selectedTemplateId} onChange={(e) => setSelectedTemplateId(e.target.value)}>
                      <option value="">Select template</option>
                      {templates.map((t) => (
                        <option key={t.template_id} value={t.template_id}>{t.name}</option>
                      ))}
                    </VASelect>
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-va-text">Entity type</label>
                    <VASelect value={entityType} onChange={(e) => setEntityType(e.target.value)}>
                      <option value="">Select type</option>
                      <option value="budget">Budget</option>
                      <option value="run">Run</option>
                      <option value="baseline">Baseline</option>
                      <option value="draft">Draft</option>
                    </VASelect>
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-va-text">Entity ID</label>
                    <VAInput value={entityId} onChange={(e) => setEntityId(e.target.value)} placeholder="e.g. bgt_xxx" />
                  </div>
                </div>
                <VAButton
                  type="button"
                  variant="primary"
                  onClick={handleCreateInstance}
                  disabled={creating || !selectedTemplateId || !entityType || !entityId}
                >
                  {creating ? "Starting…" : "Start workflow"}
                </VAButton>
              </VACard>
            </section>

            {/* Active instances */}
            <section>
              <h2 className="font-brand mb-3 text-lg font-medium text-va-text">Instances</h2>
              {instances.length === 0 ? (
                <p className="text-sm text-va-text2">No workflow instances yet.</p>
              ) : (
                <div className="overflow-x-auto rounded-va-lg border border-va-border">
                  <table className="w-full text-sm text-va-text">
                    <thead>
                      <tr className="border-b border-va-border bg-va-surface">
                        <th className="px-3 py-2 text-left font-medium">Instance</th>
                        <th className="px-3 py-2 text-left font-medium">Template</th>
                        <th className="px-3 py-2 text-left font-medium">Entity</th>
                        <th className="px-3 py-2 text-left font-medium">Stage</th>
                        <th className="px-3 py-2 text-left font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {instances.map((inst) => {
                        const tpl = templates.find((t) => t.template_id === inst.template_id);
                        return (
                          <tr key={inst.instance_id} className="border-b border-va-border/50">
                            <td className="px-3 py-2">
                              <Link href={`/workflows/${inst.instance_id}`} className="text-va-blue hover:underline">
                                {inst.instance_id}
                              </Link>
                            </td>
                            <td className="px-3 py-2 text-va-text2">{tpl?.name ?? inst.template_id}</td>
                            <td className="px-3 py-2 text-va-text2">{inst.entity_type}: {inst.entity_id}</td>
                            <td className="px-3 py-2 text-va-text2">{inst.current_stage_index + 1}</td>
                            <td className="px-3 py-2">
                              <span className={`rounded-full px-2 py-0.5 text-xs ${
                                inst.status === "completed" ? "bg-green-900/40 text-green-300" :
                                inst.status === "cancelled" ? "bg-red-900/40 text-red-300" :
                                "bg-yellow-900/40 text-yellow-300"
                              }`}>
                                {inst.status}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
