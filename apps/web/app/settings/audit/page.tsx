"use client";

import { Nav } from "@/components/nav";
import { VAButton, VACard, VAInput, VASpinner } from "@/components/ui";
import {
  api,
  type AuditEvent,
  type AuditCatalogResponse,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { useCallback, useEffect, useMemo, useState } from "react";

export default function AuditLogPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [catalog, setCatalog] = useState<AuditCatalogResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    user_id: "",
    event_type: "",
    resource_type: "",
    start_date: "",
    end_date: "",
  });

  const eventTypes = useMemo(() => {
    if (!catalog?.events) return [];
    return catalog.events
      .map((e) => String((e as Record<string, unknown>).event_type ?? ""))
      .filter(Boolean);
  }, [catalog]);

  const loadEvents = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const [catalogRes, listRes] = await Promise.all([
        api.audit.catalog(tenantId),
        api.audit.list(tenantId, {
          user_id: filters.user_id || undefined,
          event_type: filters.event_type || undefined,
          resource_type: filters.resource_type || undefined,
          start_date: filters.start_date || undefined,
          end_date: filters.end_date || undefined,
          limit: 200,
          offset: 0,
        }),
      ]);
      setCatalog(catalogRes);
      setEvents(listRes.events ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, filters]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
    })();
  }, []);

  useEffect(() => {
    if (tenantId) loadEvents();
  }, [tenantId, loadEvents]);

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
              Audit Log
            </h1>
            <p className="mt-1 text-sm text-va-text2">
              Search immutable audit events across your tenant.
            </p>
          </div>
          <div className="flex gap-2">
            <VAButton
              variant="secondary"
              onClick={() =>
                window.open(
                  api.audit.exportUrl({
                    format: "csv",
                    user_id: filters.user_id || undefined,
                    event_type: filters.event_type || undefined,
                    resource_type: filters.resource_type || undefined,
                    start_date: filters.start_date || undefined,
                    end_date: filters.end_date || undefined,
                  }),
                  "_blank"
                )
              }
            >
              Export CSV
            </VAButton>
            <VAButton variant="secondary" onClick={loadEvents}>
              Refresh
            </VAButton>
          </div>
        </div>

        <VACard className="mb-4 p-4">
          <div className="grid gap-3 md:grid-cols-5">
            <div>
              <label className="mb-1 block text-xs font-medium text-va-text2">
                User ID
              </label>
              <VAInput
                value={filters.user_id}
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, user_id: e.target.value }))
                }
                placeholder="User ID"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-va-text2">
                Event type
              </label>
              <select
                className="w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text"
                value={filters.event_type}
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, event_type: e.target.value }))
                }
              >
                <option value="">All</option>
                {eventTypes.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-va-text2">
                Resource type
              </label>
              <VAInput
                value={filters.resource_type}
                onChange={(e) =>
                  setFilters((prev) => ({
                    ...prev,
                    resource_type: e.target.value,
                  }))
                }
                placeholder="resource"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-va-text2">
                Start date
              </label>
              <VAInput
                type="date"
                value={filters.start_date}
                onChange={(e) =>
                  setFilters((prev) => ({
                    ...prev,
                    start_date: e.target.value,
                  }))
                }
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-va-text2">
                End date
              </label>
              <VAInput
                type="date"
                value={filters.end_date}
                onChange={(e) =>
                  setFilters((prev) => ({
                    ...prev,
                    end_date: e.target.value,
                  }))
                }
              />
            </div>
          </div>
        </VACard>

        {error && (
          <div
            className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
            role="alert"
          >
            {error}
          </div>
        )}

        {loading ? (
          <VASpinner label="Loading audit events…" />
        ) : events.length === 0 ? (
          <VACard className="p-6 text-center text-va-text2">
            No events match the selected filters.
          </VACard>
        ) : (
          <div className="overflow-x-auto rounded-va-lg border border-va-border">
            <table className="w-full text-sm text-va-text">
              <thead>
                <tr className="border-b border-va-border bg-va-surface">
                  <th className="px-3 py-2 text-left font-medium">Time</th>
                  <th className="px-3 py-2 text-left font-medium">Type</th>
                  <th className="px-3 py-2 text-left font-medium">Resource</th>
                  <th className="px-3 py-2 text-left font-medium">User</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.audit_event_id} className="border-b border-va-border/50">
                    <td className="px-3 py-2 text-xs text-va-text2">
                      {formatDateTime(ev.timestamp)}
                    </td>
                    <td className="px-3 py-2">{ev.event_type}</td>
                    <td className="px-3 py-2 text-va-text2">
                      {ev.resource_type} {ev.resource_id}
                    </td>
                    <td className="px-3 py-2 text-va-text2">{ev.user_id || "—"}</td>
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
