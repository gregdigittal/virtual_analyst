"use client";

import { VAButton, VACard, VAConfirmDialog, VAInput, VASpinner, useToast } from "@/components/ui";
import { api, type IntegrationConnection, type IntegrationSnapshot } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { useCallback, useEffect, useState } from "react";

type SnapshotState = Record<string, IntegrationSnapshot[]>;

function healthLabel(connection: IntegrationConnection): { label: string; tone: string } {
  if (connection.status !== "connected") {
    return { label: connection.status, tone: "text-va-warning" };
  }
  if (!connection.last_sync_at) {
    return { label: "Never synced", tone: "text-va-warning" };
  }
  const last = new Date(connection.last_sync_at).getTime();
  const days = (Date.now() - last) / (1000 * 60 * 60 * 24);
  if (days > 30) return { label: "Stale", tone: "text-va-warning" };
  return { label: "Healthy", tone: "text-va-success" };
}

export default function IntegrationsPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | undefined>(undefined);
  const [connections, setConnections] = useState<IntegrationConnection[]>([]);
  const [snapshots, setSnapshots] = useState<SnapshotState>({});
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const { toast } = useToast();
  const [confirmAction, setConfirmAction] = useState<{ action: () => void; title: string; description: string } | null>(null);

  const loadConnections = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.integrations.list(tenantId, { limit: 50, offset: 0 });
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
    if (tenantId) loadConnections();
  }, [tenantId, loadConnections]);

  async function handleConnect(provider: "xero" | "quickbooks") {
    if (!tenantId) return;
    setBusyId(provider);
    setError(null);
    try {
      const res = await api.integrations.initiate(tenantId, userId, provider);
      window.location.href = res.authorize_url;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setBusyId(null);
    }
  }

  async function handleSync(connectionId: string) {
    if (!tenantId) return;
    setBusyId(connectionId);
    setError(null);
    try {
      await api.integrations.sync(tenantId, connectionId, {});
      await loadConnections();
      toast.success("Sync started");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setBusyId(null);
    }
  }

  async function handleSnapshots(connectionId: string) {
    if (!tenantId) return;
    setBusyId(connectionId);
    setError(null);
    try {
      const res = await api.integrations.snapshots(tenantId, connectionId, {
        limit: 10,
        offset: 0,
      });
      setSnapshots((prev) => ({ ...prev, [connectionId]: res.snapshots ?? [] }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  }

  async function handleDisconnect(connectionId: string) {
    if (!tenantId) return;
    setBusyId(connectionId);
    setError(null);
    try {
      await api.integrations.disconnect(tenantId, connectionId);
      await loadConnections();
      toast.success("Integration disconnected");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setBusyId(null);
    }
  }

  const filtered = connections.filter((c) =>
    filter
      ? `${c.provider} ${c.org_name ?? ""}`
          .toLowerCase()
          .includes(filter.toLowerCase())
      : true
  );

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Integrations
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Connect Xero or QuickBooks and manage sync snapshots.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <VAButton
            variant="secondary"
            onClick={() => handleConnect("xero")}
            disabled={busyId === "xero"}
          >
            Connect Xero
          </VAButton>
          <VAButton
            variant="secondary"
            onClick={() => handleConnect("quickbooks")}
            disabled={busyId === "quickbooks"}
          >
            Connect QuickBooks
          </VAButton>
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

      <div className="mb-4 max-w-sm">
        <VAInput
          placeholder="Filter by provider or org..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      {loading ? (
        <VASpinner label="Loading integrations…" />
      ) : filtered.length === 0 ? (
        <VACard className="p-6 text-center text-va-text2">
          No connections yet. Connect your ERP to start syncing.
        </VACard>
      ) : (
        <div className="space-y-4">
          {filtered.map((conn) => {
            const health = healthLabel(conn);
            const snapshotList = snapshots[conn.connection_id] ?? [];
            return (
              <VACard key={conn.connection_id} className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-medium text-va-text">
                      {conn.provider.toUpperCase()}{" "}
                      <span className="text-sm text-va-text2">
                        {conn.org_name ? `· ${conn.org_name}` : ""}
                      </span>
                    </h2>
                    <div className="mt-1 text-sm text-va-text2">
                      Status:{" "}
                      <span className={health.tone}>{health.label}</span>
                    </div>
                    <div className="text-xs text-va-text2">
                      Last sync:{" "}
                      {formatDateTime(conn.last_sync_at)}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <VAButton
                      variant="secondary"
                      onClick={() => handleSync(conn.connection_id)}
                      disabled={busyId === conn.connection_id}
                    >
                      Sync now
                    </VAButton>
                    <VAButton
                      variant="ghost"
                      onClick={() => handleSnapshots(conn.connection_id)}
                      disabled={busyId === conn.connection_id}
                    >
                      View snapshots
                    </VAButton>
                    <VAButton
                      variant="danger"
                      onClick={() => setConfirmAction({
                      action: () => handleDisconnect(conn.connection_id),
                      title: "Disconnect this integration?",
                      description: "You will need to re-authenticate to reconnect.",
                    })}
                      disabled={busyId === conn.connection_id}
                    >
                      Disconnect
                    </VAButton>
                  </div>
                </div>
                {snapshotList.length > 0 && (
                  <div className="mt-4 rounded-va-lg border border-va-border">
                    <table className="w-full text-sm text-va-text">
                      <thead>
                        <tr className="border-b border-va-border bg-va-surface">
                          <th className="px-3 py-2 text-left font-medium">
                            Snapshot ID
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            As of
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Period
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {snapshotList.map((snap) => (
                          <tr
                            key={snap.snapshot_id}
                            className="border-b border-va-border/50"
                          >
                            <td className="px-3 py-2 text-xs text-va-text2">
                              {snap.snapshot_id}
                            </td>
                            <td className="px-3 py-2">
                              {formatDateTime(snap.as_of)}
                            </td>
                            <td className="px-3 py-2 text-va-text2">
                              {snap.period_start || "—"} →{" "}
                              {snap.period_end || "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </VACard>
            );
          })}
        </div>
      )}
    <VAConfirmDialog
      open={!!confirmAction}
      title={confirmAction?.title ?? ""}
      description={confirmAction?.description}
      confirmLabel="Disconnect"
      onConfirm={() => { confirmAction?.action(); setConfirmAction(null); }}
      onCancel={() => setConfirmAction(null)}
    />
    </main>
  );
}
