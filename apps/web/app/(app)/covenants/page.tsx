"use client";

import { VAButton, VACard, VAConfirmDialog, VAInput, VASelect, VASpinner, VAPagination, useToast } from "@/components/ui";
import {
  api,
  type CovenantDefinition,
  type CovenantMetricRefs,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useCallback, useEffect, useState } from "react";

const PAGE_SIZE = 20;

export default function CovenantsPage() {
  const { toast } = useToast();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [items, setItems] = useState<CovenantDefinition[]>([]);
  const [refs, setRefs] = useState<CovenantMetricRefs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<{ action: () => void; title: string; description: string } | null>(null);
  const [form, setForm] = useState({
    label: "",
    metric_ref: "",
    operator: ">=",
    threshold_value: "",
  });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const [listRes, refsRes] = await Promise.all([
        api.covenants.list(tenantId, {
          limit: PAGE_SIZE,
          offset: (page - 1) * PAGE_SIZE,
        }),
        api.covenants.metricRefs(tenantId),
      ]);
      setItems(listRes.items ?? []);
      setTotal(listRes.total);
      setRefs(refsRes);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, page]);

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
    const errors: Record<string, string> = {};
    if (!form.label.trim()) errors.label = "Label is required";
    if (!form.metric_ref) errors.metric_ref = "Select a metric ref";
    if (!form.threshold_value.trim() || !Number.isFinite(Number(form.threshold_value)))
      errors.threshold_value = "Enter a valid number";
    if (Object.keys(errors).length > 0) { setFieldErrors(errors); return; }
    setFieldErrors({});
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
      toast.success("Covenant created");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  async function handleDelete(id: string) {
    if (!tenantId) return;
    setError(null);
    try {
      await api.covenants.delete(tenantId, id);
      await load();
      toast.success("Covenant deleted");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  return (
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
            onChange={(e) => {
              setForm((prev) => ({ ...prev, label: e.target.value }));
              setFieldErrors((prev) => ({ ...prev, label: "" }));
            }}
            error={fieldErrors.label}
          />
          <VASelect
            value={form.metric_ref}
            onChange={(e) => {
              setForm((prev) => ({ ...prev, metric_ref: e.target.value }));
              setFieldErrors((prev) => ({ ...prev, metric_ref: "" }));
            }}
            error={fieldErrors.metric_ref}
          >
            <option value="">Metric ref</option>
            {refs?.metric_refs?.map((ref) => (
              <option key={ref} value={ref}>
                {ref}
              </option>
            ))}
          </VASelect>
          <VASelect
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
          </VASelect>
          <VAInput
            placeholder="Threshold"
            value={form.threshold_value}
            onChange={(e) => {
              setForm((prev) => ({
                ...prev,
                threshold_value: e.target.value,
              }));
              setFieldErrors((prev) => ({ ...prev, threshold_value: "" }));
            }}
            error={fieldErrors.threshold_value}
          />
        </div>
        <VAButton className="mt-3" onClick={handleCreate}>
          Add covenant
        </VAButton>
      </VACard>

      {loading ? (
        <VASpinner label="Loading covenants…" className="mt-4" />
      ) : items.length === 0 ? (
        <VACard className="mt-4 p-6 text-center text-va-text2">
          No covenants defined yet. Use the form above to create your first covenant threshold.
        </VACard>
      ) : (
        <>
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
                        onClick={() => setConfirmAction({
                          action: () => handleDelete(c.covenant_id),
                          title: `Delete covenant "${c.label}"?`,
                          description: "This action cannot be undone.",
                        })}
                      >
                        Delete
                      </VAButton>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <VAPagination
            page={page}
            pageSize={PAGE_SIZE}
            total={total}
            onPageChange={setPage}
          />
        </>
      )}
      <VAConfirmDialog
        open={!!confirmAction}
        title={confirmAction?.title ?? ""}
        description={confirmAction?.description}
        onConfirm={() => { confirmAction?.action(); setConfirmAction(null); }}
        onCancel={() => setConfirmAction(null)}
      />
    </main>
  );
}
