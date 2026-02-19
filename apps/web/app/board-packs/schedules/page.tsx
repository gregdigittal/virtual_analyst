"use client";

import { Nav } from "@/components/nav";
import { VAButton, VACard, VAInput, VASpinner, VAPagination, useToast } from "@/components/ui";
import {
  api,
  type BoardPackHistoryItem,
  type BoardPackSchedule,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { useCallback, useEffect, useState } from "react";

const PAGE_SIZE = 20;

export default function BoardPackSchedulesPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | undefined>(undefined);
  const [schedules, setSchedules] = useState<BoardPackSchedule[]>([]);
  const [history, setHistory] = useState<BoardPackHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();
  const [form, setForm] = useState({
    label: "",
    run_id: "",
    cron_expr: "",
    distribution_emails: "",
  });
  const [busyId, setBusyId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalSchedules, setTotalSchedules] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [totalHistory, setTotalHistory] = useState(0);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const [schedRes, historyRes] = await Promise.all([
        api.boardPackSchedules.list(tenantId, {
          limit: PAGE_SIZE,
          offset: (page - 1) * PAGE_SIZE,
        }),
        api.boardPackSchedules.history(tenantId, {
          limit: PAGE_SIZE,
          offset: (historyPage - 1) * PAGE_SIZE,
        }),
      ]);
      setSchedules(schedRes.items ?? []);
      setTotalSchedules(schedRes.total);
      setHistory(historyRes.items ?? []);
      setTotalHistory(historyRes.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, page, historyPage]);

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
      await api.boardPackSchedules.create(tenantId, userId, {
        label: form.label,
        run_id: form.run_id,
        cron_expr: form.cron_expr,
        distribution_emails: form.distribution_emails
          .split(",")
          .map((e) => e.trim())
          .filter(Boolean),
      });
      setForm({ label: "", run_id: "", cron_expr: "", distribution_emails: "" });
      toast.success("Schedule created");
      await load();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  async function handleRunNow(scheduleId: string) {
    if (!tenantId) return;
    setBusyId(scheduleId);
    setError(null);
    try {
      await api.boardPackSchedules.runNow(tenantId, userId, scheduleId);
      toast.success("Board pack generation started");
      await load();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="mb-6">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Board Pack Schedules
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Schedule recurring board packs and track distribution history.
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
          <h2 className="text-lg font-medium text-va-text">Create schedule</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-4">
            <VAInput
              placeholder="Label"
              value={form.label}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, label: e.target.value }))
              }
            />
            <VAInput
              placeholder="Run ID"
              value={form.run_id}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, run_id: e.target.value }))
              }
            />
            <VAInput
              placeholder="Cron expression"
              value={form.cron_expr}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, cron_expr: e.target.value }))
              }
            />
            <VAInput
              placeholder="Emails (comma-separated)"
              value={form.distribution_emails}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  distribution_emails: e.target.value,
                }))
              }
            />
          </div>
          <VAButton className="mt-3" onClick={handleCreate}>
            Create schedule
          </VAButton>
        </VACard>

        {loading ? (
          <VASpinner label="Loading schedules…" className="mt-4" />
        ) : schedules.length === 0 ? (
          <VACard className="mt-4 p-6 text-center text-va-text2">
            No schedules yet.
          </VACard>
        ) : (
          <>
            <div className="mt-4 space-y-3">
              {schedules.map((s) => (
                <VACard key={s.schedule_id} className="p-4">
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div>
                      <h3 className="text-base font-medium text-va-text">
                        {s.label}
                      </h3>
                      <p className="text-sm text-va-text2">
                        Run: {s.run_id} · Cron: {s.cron_expr}
                      </p>
                      <p className="text-xs text-va-text2">
                        Next run:{" "}
                        {formatDateTime(s.next_run_at)}
                      </p>
                    </div>
                    <VAButton
                      variant="secondary"
                      onClick={() => handleRunNow(s.schedule_id)}
                      disabled={busyId === s.schedule_id}
                    >
                      Run now
                    </VAButton>
                  </div>
                </VACard>
              ))}
            </div>
            <VAPagination
              page={page}
              pageSize={PAGE_SIZE}
              total={totalSchedules}
              onPageChange={setPage}
            />
          </>
        )}

        <VACard className="mt-6 p-5">
          <h2 className="text-lg font-medium text-va-text">Run history</h2>
          {history.length === 0 ? (
            <p className="mt-2 text-sm text-va-text2">No history yet.</p>
          ) : (
            <>
              <div className="mt-3 overflow-x-auto rounded-va-lg border border-va-border">
                <table className="w-full text-sm text-va-text">
                  <thead>
                    <tr className="border-b border-va-border bg-va-surface">
                      <th className="px-3 py-2 text-left font-medium">Pack</th>
                      <th className="px-3 py-2 text-left font-medium">Run</th>
                      <th className="px-3 py-2 text-left font-medium">Status</th>
                      <th className="px-3 py-2 text-left font-medium">Generated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((h) => (
                      <tr key={h.history_id} className="border-b border-va-border/50">
                        <td className="px-3 py-2 text-va-text2">{h.pack_id}</td>
                        <td className="px-3 py-2 text-va-text2">{h.run_id}</td>
                        <td className="px-3 py-2">{h.status}</td>
                        <td className="px-3 py-2 text-va-text2">
                          {formatDateTime(h.generated_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <VAPagination
                page={historyPage}
                pageSize={PAGE_SIZE}
                total={totalHistory}
                onPageChange={setHistoryPage}
              />
            </>
          )}
        </VACard>
      </main>
    </div>
  );
}
