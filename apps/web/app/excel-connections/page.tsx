"use client";

import { Nav } from "@/components/nav";
import { VAButton, VACard, VAInput } from "@/components/ui";
import {
  api,
  type ExcelConnection,
  type ExcelPullValue,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useCallback, useEffect, useState } from "react";

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

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.excelConnections.list(tenantId, { limit: 50, offset: 0 });
      setConnections(res.items ?? []);
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
      setUserId(ctx.userId);
    })();
  }, []);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

  async function handleCreate() {
    if (!tenantId) return;
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
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handlePull(connectionId: string) {
    if (!tenantId) return;
    setError(null);
    try {
      const res = await api.excelConnections.pull(tenantId, userId, connectionId);
      setPullResults((prev) => ({ ...prev, [connectionId]: res.values ?? [] }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handlePush(connectionId: string) {
    if (!tenantId) return;
    setError(null);
    try {
      const changesRaw = pushInputs[connectionId] || "[]";
      const changes = JSON.parse(changesRaw);
      await api.excelConnections.push(tenantId, connectionId, changes);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleDelete(connectionId: string) {
    if (!tenantId) return;
    setError(null);
    try {
      await api.excelConnections.delete(tenantId, connectionId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
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
            <select
              className="w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text"
              value={form.mode}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, mode: e.target.value }))
              }
            >
              <option value="readonly">Read-only</option>
              <option value="readwrite">Read-write</option>
            </select>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <textarea
              className="min-h-[120px] w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text"
              value={form.target_json}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, target_json: e.target.value }))
              }
            />
            <textarea
              className="min-h-[120px] w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text"
              value={form.bindings_json}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, bindings_json: e.target.value }))
              }
            />
          </div>
          <VAButton className="mt-3" onClick={handleCreate}>
            Create connection
          </VAButton>
        </VACard>

        {loading ? (
          <p className="mt-4 text-va-text2">Loading connections…</p>
        ) : connections.length === 0 ? (
          <VACard className="mt-4 p-6 text-center text-va-text2">
            No Excel connections yet.
          </VACard>
        ) : (
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
                      onClick={() => handleDelete(conn.excel_connection_id)}
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
        )}
      </main>
    </div>
  );
}
