"use client";

import { VAButton, VACard, VAConfirmDialog, VAInput, VASelect, VASpinner, VAPagination, useToast } from "@/components/ui";
import {
  api,
  type ExcelConnection,
  type ExcelPullValue,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useCallback, useEffect, useState } from "react";

const PAGE_SIZE = 20;

export default function ExcelConnectionsPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | undefined>(undefined);
  const [connections, setConnections] = useState<ExcelConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    label: "",
    mode: "readonly",
    target_json: "{\"baseline_id\":\"\", \"baseline_version\":\"v1\", \"run_id\":\"\"}",
    bindings_json: "[]",
  });
  const [pullResults, setPullResults] = useState<Record<string, ExcelPullValue[]>>({});
  const [pushInputs, setPushInputs] = useState<Record<string, string>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const { toast } = useToast();
  const [confirmAction, setConfirmAction] = useState<{ action: () => void; title: string; description: string } | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.excelConnections.list(tenantId, {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      setConnections(res.items ?? []);
      setTotal(res.total);
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
      setUserId(ctx.userId);
    })();
  }, []);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

  async function handleCreate() {
    if (!tenantId) return;
    const errors: Record<string, string> = {};
    try { JSON.parse(form.target_json); } catch { errors.target_json = "Invalid JSON in target"; }
    try { JSON.parse(form.bindings_json); } catch { errors.bindings_json = "Invalid JSON in bindings"; }
    if (Object.keys(errors).length > 0) { setFieldErrors(errors); return; }
    setFieldErrors({});
    setError(null);
    try {
      const target = JSON.parse(form.target_json);
      const bindings = JSON.parse(form.bindings_json);
      await api.excelConnections.create(tenantId, userId, {
        label: form.label || undefined,
        mode: form.mode,
        target_json: target,
        bindings_json: Array.isArray(bindings) ? bindings : [],
      });
      await load();
      toast.success("Connection created");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  async function handlePull(connectionId: string) {
    if (!tenantId) return;
    setError(null);
    try {
      const res = await api.excelConnections.pull(tenantId, userId, connectionId);
      setPullResults((prev) => ({ ...prev, [connectionId]: res.values ?? [] }));
      toast.success("Pull complete");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  async function handlePush(connectionId: string) {
    if (!tenantId) return;
    setError(null);
    const changesRaw = pushInputs[connectionId] || "[]";
    try { JSON.parse(changesRaw); } catch { toast.error("Invalid JSON in push changes"); return; }
    try {
      const changes = JSON.parse(changesRaw);
      await api.excelConnections.push(tenantId, connectionId, changes);
      toast.success("Push sent");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  async function handleDelete(connectionId: string) {
    if (!tenantId) return;
    setError(null);
    try {
      await api.excelConnections.delete(tenantId, connectionId);
      await load();
      toast.success("Connection deleted");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Excel Connections
        </h1>
        <p className="mt-1 text-sm text-va-text2">
          Create persistent Excel sync connections for runs and baselines.
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
        <h2 className="text-lg font-medium text-va-text">Create connection</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <VAInput
            placeholder="Label"
            value={form.label}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, label: e.target.value }))
            }
          />
          <VASelect
            value={form.mode}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, mode: e.target.value }))
            }
          >
            <option value="readonly">Read-only</option>
            <option value="readwrite">Read-write</option>
          </VASelect>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div>
            <textarea
              className={`min-h-[120px] w-full rounded-va-xs border bg-va-surface px-3 py-2 text-sm text-va-text ${fieldErrors.target_json ? "border-va-danger" : "border-va-border"}`}
              value={form.target_json}
              onChange={(e) => {
                setForm((prev) => ({ ...prev, target_json: e.target.value }));
                setFieldErrors((prev) => ({ ...prev, target_json: "" }));
              }}
            />
            {fieldErrors.target_json && <p className="mt-1 text-xs text-va-danger">{fieldErrors.target_json}</p>}
          </div>
          <div>
            <textarea
              className={`min-h-[120px] w-full rounded-va-xs border bg-va-surface px-3 py-2 text-sm text-va-text ${fieldErrors.bindings_json ? "border-va-danger" : "border-va-border"}`}
              value={form.bindings_json}
              onChange={(e) => {
                setForm((prev) => ({ ...prev, bindings_json: e.target.value }));
                setFieldErrors((prev) => ({ ...prev, bindings_json: "" }));
              }}
            />
            {fieldErrors.bindings_json && <p className="mt-1 text-xs text-va-danger">{fieldErrors.bindings_json}</p>}
          </div>
        </div>
        <VAButton className="mt-3" onClick={handleCreate}>
          Create connection
        </VAButton>
      </VACard>

      {loading ? (
        <VASpinner label="Loading connections…" className="mt-4" />
      ) : connections.length === 0 ? (
        <VACard className="mt-4 p-6 text-center text-va-text2">
          No Excel connections yet. Create a connection to sync data between your models and Excel.
        </VACard>
      ) : (
        <>
          <div className="mt-4 space-y-4">
            {connections.map((conn) => (
              <VACard key={conn.excel_connection_id} className="p-5">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <h3 className="text-base font-medium text-va-text">
                      {conn.label || conn.excel_connection_id}
                    </h3>
                    <p className="text-sm text-va-text2">
                      Mode: {conn.mode} · Status: {conn.status ?? "active"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <VAButton
                      variant="secondary"
                      onClick={() => handlePull(conn.excel_connection_id)}
                    >
                      Pull
                    </VAButton>
                    <VAButton
                      variant="secondary"
                      onClick={() => handlePush(conn.excel_connection_id)}
                    >
                      Push
                    </VAButton>
                    <VAButton
                      variant="danger"
                      onClick={() => setConfirmAction({
                      action: () => handleDelete(conn.excel_connection_id),
                      title: "Delete this Excel connection?",
                      description: "This action cannot be undone.",
                    })}
                    >
                      Delete
                    </VAButton>
                  </div>
                </div>
                <div className="mt-3">
                  <label className="mb-1 block text-xs font-medium text-va-text2">
                    Push changes (JSON)
                  </label>
                  <textarea
                    className="min-h-[80px] w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-xs text-va-text"
                    value={pushInputs[conn.excel_connection_id] ?? "[]"}
                    onChange={(e) =>
                      setPushInputs((prev) => ({
                        ...prev,
                        [conn.excel_connection_id]: e.target.value,
                      }))
                    }
                  />
                </div>
                {pullResults[conn.excel_connection_id]?.length ? (
                  <div className="mt-3 rounded-va-lg border border-va-border p-3 text-xs text-va-text2">
                    {pullResults[conn.excel_connection_id]
                      .slice(0, 5)
                      .map((v) => (
                        <div key={v.binding_id}>
                          {v.binding_id}: {String(v.value)}
                        </div>
                      ))}
                  </div>
                ) : null}
              </VACard>
            ))}
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
