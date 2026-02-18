"use client";

import { Nav } from "@/components/nav";
import { VAButton, VACard, VAInput } from "@/components/ui";
import {
  api,
  type CovenantDefinition,
  type CovenantMetricRefs,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useCallback, useEffect, useState } from "react";

export default function CovenantsPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [items, setItems] = useState<CovenantDefinition[]>([]);
  const [refs, setRefs] = useState<CovenantMetricRefs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    label: "",
    metric_ref: "",
    operator: ">=",
    threshold_value: "",
  });

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const [listRes, refsRes] = await Promise.all([
        api.covenants.list(tenantId, { limit: 50, offset: 0 }),
        api.covenants.metricRefs(tenantId),
      ]);
      setItems(listRes.items ?? []);
      setRefs(refsRes);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
    })();
  }, []);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

  async function handleCreate() {
    if (!tenantId) return;
    setError(null);
    try {
      await api.covenants.create(tenantId, {
        label: form.label,
        metric_ref: form.metric_ref,
        operator: form.operator,
        threshold_value: Number(form.threshold_value),
      });
      setForm((prev) => ({ ...prev, label: "", threshold_value: "" }));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleDelete(id: string) {
    if (!tenantId) return;
    setError(null);
    try {
      await api.covenants.delete(tenantId, id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="mb-6">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Covenants
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Define covenant thresholds to flag breaches on run results.
          </p>
        </div>

        {error && (
          <div
            className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
            role="alert"
          >
            {error}
          </div>
        )}

        <VACard className="p-5">
          <h2 className="text-lg font-medium text-va-text">Create covenant</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <VAInput
              placeholder="Label"
              value={form.label}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, label: e.target.value }))
              }
            />
            <select
              className="w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text"
              value={form.metric_ref}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, metric_ref: e.target.value }))
              }
            >
              <option value="">Metric ref</option>
              {refs?.metric_refs?.map((ref) => (
                <option key={ref} value={ref}>
                  {ref}
                </option>
              ))}
            </select>
            <select
              className="w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text"
              value={form.operator}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, operator: e.target.value }))
              }
            >
              {(refs?.operators ?? [">=", ">", "<=", "<"]).map((op) => (
                <option key={op} value={op}>
                  {op}
                </option>
              ))}
            </select>
            <VAInput
              placeholder="Threshold"
              value={form.threshold_value}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  threshold_value: e.target.value,
                }))
              }
            />
          </div>
          <VAButton className="mt-3" onClick={handleCreate}>
            Add covenant
          </VAButton>
        </VACard>

        {loading ? (
          <p className="mt-4 text-va-text2">Loading covenants…</p>
        ) : items.length === 0 ? (
          <VACard className="mt-4 p-6 text-center text-va-text2">
            No covenants defined yet.
          </VACard>
        ) : (
          <div className="mt-4 overflow-x-auto rounded-va-lg border border-va-border">
            <table className="w-full text-sm text-va-text">
              <thead>
                <tr className="border-b border-va-border bg-va-surface">
                  <th className="px-3 py-2 text-left font-medium">Label</th>
                  <th className="px-3 py-2 text-left font-medium">Metric</th>
                  <th className="px-3 py-2 text-left font-medium">Operator</th>
                  <th className="px-3 py-2 text-left font-medium">Threshold</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr key={c.covenant_id} className="border-b border-va-border/50">
                    <td className="px-3 py-2">{c.label}</td>
                    <td className="px-3 py-2 text-va-text2">{c.metric_ref}</td>
                    <td className="px-3 py-2">{c.operator}</td>
                    <td className="px-3 py-2">{c.threshold_value}</td>
                    <td className="px-3 py-2 text-right">
                      <VAButton
                        variant="ghost"
                        onClick={() => handleDelete(c.covenant_id)}
                      >
                        Delete
                      </VAButton>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
