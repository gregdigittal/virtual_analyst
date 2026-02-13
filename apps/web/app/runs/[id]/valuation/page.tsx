"use client";

import { api } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

export default function RunValuationPage() {
  const params = useParams();
  const runId = params.id as string;
  const [data, setData] = useState<{
    dcf?: Record<string, unknown>;
    multiples?: Record<string, unknown>;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.user?.id) return;
      const tid = session.user.id;
      setTenantId(tid);
      try {
        const res = await api.runs.getValuation(tid, runId);
        if (!cancelled) setData(res);
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  if (!tenantId && !loading) return null;

  const dcf = data?.dcf as Record<string, unknown> | undefined;
  const mult = data?.multiples as Record<string, unknown> | undefined;
  const evRange = mult?.implied_ev_range as [number, number] | undefined;

  return (
    <div className="min-h-screen bg-background">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link
            href="/runs"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Runs
          </Link>
          <Link
            href={`/runs/${runId}`}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Run {runId}
          </Link>
        </div>
        <h1 className="mb-4 text-2xl font-semibold tracking-tight">
          Valuation
        </h1>
        {error && (
          <div
            className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
            role="alert"
          >
            {error}
          </div>
        )}
        {loading ? (
          <p className="text-muted-foreground">Loading valuation…</p>
        ) : data ? (
          <div className="grid gap-6 sm:grid-cols-2">
            {dcf && (
              <div className="rounded-lg border border-border bg-card p-4">
                <h2 className="mb-3 text-lg font-medium">DCF</h2>
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">Enterprise value</dt>
                    <dd className="font-medium">
                      {typeof dcf.enterprise_value === "number"
                        ? dcf.enterprise_value.toLocaleString(undefined, { maximumFractionDigits: 0 })
                        : "—"}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">PV explicit</dt>
                    <dd>{typeof dcf.pv_explicit === "number" ? dcf.pv_explicit.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—"}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">PV terminal</dt>
                    <dd>{typeof dcf.pv_terminal === "number" ? dcf.pv_terminal.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—"}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-muted-foreground">WACC</dt>
                    <dd>{typeof dcf.wacc === "number" ? `${(dcf.wacc * 100).toFixed(1)}%` : "—"}</dd>
                  </div>
                </dl>
              </div>
            )}
            {mult && (
              <div className="rounded-lg border border-border bg-card p-4">
                <h2 className="mb-3 text-lg font-medium">Multiples</h2>
                <dl className="space-y-2 text-sm">
                  {evRange && (
                    <div className="flex justify-between">
                      <dt className="text-muted-foreground">Implied EV range</dt>
                      <dd className="font-medium">
                        {evRange[0].toLocaleString(undefined, { maximumFractionDigits: 0 })} – {evRange[1].toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>
            )}
            {!dcf && !mult && (
              <p className="text-muted-foreground">No valuation data for this run.</p>
            )}
          </div>
        ) : (
          <p className="text-muted-foreground">No valuation data for this run.</p>
        )}
      </main>
    </div>
  );
}
