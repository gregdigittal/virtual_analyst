"use client";

import { Nav } from "@/components/nav";
import { VAButton, VACard, VAConfirmDialog, VAInput, VASpinner, useToast } from "@/components/ui";
import { api, type BenchmarkSummary, type BenchmarkOptIn } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useCallback, useEffect, useState } from "react";

export default function BenchmarkPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [optIn, setOptIn] = useState<BenchmarkOptIn | null>(null);
  const [summary, setSummary] = useState<BenchmarkSummary | null>(null);
  const [form, setForm] = useState({ industry_segment: "general", size_segment: "general" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();
  const [confirmAction, setConfirmAction] = useState<{ action: () => void; title: string; description: string } | null>(null);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const optInRes = await api.benchmark.getOptIn(tenantId);
      setOptIn(optInRes);
      if (optInRes.opted_in) {
        const summaryRes = await api.benchmark.getSummary(tenantId);
        setSummary(summaryRes);
      } else {
        setSummary(null);
      }
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

  async function handleOptIn() {
    if (!tenantId) return;
    setError(null);
    try {
      await api.benchmark.setOptIn(tenantId, {
        industry_segment: form.industry_segment,
        size_segment: form.size_segment,
      });
      await load();
      toast.success("Opted in to benchmarking");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  async function handleOptOut() {
    if (!tenantId) return;
    setError(null);
    try {
      await api.benchmark.deleteOptIn(tenantId);
      await load();
      toast.success("Opted out of benchmarking");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="mb-6">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Benchmarking
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Compare your KPIs to anonymized peer aggregates.
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

        {loading ? (
          <VASpinner label="Loading benchmark data…" />
        ) : optIn?.opted_in ? (
          <div className="space-y-6">
            <VACard className="p-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-medium text-va-text">
                    Opted in
                  </h2>
                  <p className="text-sm text-va-text2">
                    Segment: {optIn.industry_segment} · {optIn.size_segment}
                  </p>
                </div>
                <VAButton variant="ghost" onClick={() => setConfirmAction({
                  action: handleOptOut,
                  title: "Opt out of benchmarking?",
                  description: "Your anonymized data will no longer be shared with peers.",
                })}>
                  Opt out
                </VAButton>
              </div>
            </VACard>

            <VACard className="p-5">
              <h2 className="text-lg font-medium text-va-text">
                Peer summary
              </h2>
              {summary?.metrics?.length ? (
                <div className="mt-4 overflow-x-auto rounded-va-lg border border-va-border">
                  <table className="w-full text-sm text-va-text">
                    <thead>
                      <tr className="border-b border-va-border bg-va-surface">
                        <th className="px-3 py-2 text-left font-medium">
                          Metric
                        </th>
                        <th className="px-3 py-2 text-left font-medium">
                          P25
                        </th>
                        <th className="px-3 py-2 text-left font-medium">
                          Median
                        </th>
                        <th className="px-3 py-2 text-left font-medium">
                          P75
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {summary.metrics.map((m) => (
                        <tr key={m.metric_name} className="border-b border-va-border/50">
                          <td className="px-3 py-2">{m.metric_name}</td>
                          <td className="px-3 py-2 text-va-text2">
                            {m.p25 ?? "—"}
                          </td>
                          <td className="px-3 py-2">{m.median}</td>
                          <td className="px-3 py-2 text-va-text2">
                            {m.p75 ?? "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="mt-2 text-sm text-va-text2">
                  No benchmark aggregates available yet.
                </p>
              )}
            </VACard>
          </div>
        ) : (
          <VACard className="p-5">
            <h2 className="text-lg font-medium text-va-text">Opt in</h2>
            <p className="mt-1 text-sm text-va-text2">
              Opt in to share anonymized data and view peer benchmarks.
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <VAInput
                placeholder="Industry segment"
                value={form.industry_segment}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    industry_segment: e.target.value,
                  }))
                }
              />
              <VAInput
                placeholder="Size segment"
                value={form.size_segment}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    size_segment: e.target.value,
                  }))
                }
              />
            </div>
            <VAButton className="mt-3" onClick={handleOptIn}>
              Opt in
            </VAButton>
          </VACard>
        )}
      <VAConfirmDialog
        open={!!confirmAction}
        title={confirmAction?.title ?? ""}
        description={confirmAction?.description}
        confirmLabel="Opt out"
        variant="warning"
        onConfirm={() => { confirmAction?.action(); setConfirmAction(null); }}
        onCancel={() => setConfirmAction(null)}
      />
      </main>
    </div>
  );
}
