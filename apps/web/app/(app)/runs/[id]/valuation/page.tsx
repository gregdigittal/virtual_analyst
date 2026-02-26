"use client";

import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VACard, VASpinner } from "@/components/ui";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function RunValuationPage() {
  const params = useParams();
  const router = useRouter();
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
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      try {
        const res = await api.runs.getValuation(ctx.tenantId, runId);
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
  }, [router, runId]);

  if (!tenantId && !loading) return null;

  const dcf = data?.dcf as Record<string, unknown> | undefined;
  const mult = data?.multiples as Record<string, unknown> | undefined;
  const evRange = mult?.implied_ev_range as [number, number] | undefined;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex items-center gap-4">
        <Link
          href="/runs"
          className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded"
        >
          ← Runs
        </Link>
        <Link
          href={`/runs/${runId}`}
          className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded"
        >
          Run {runId}
        </Link>
      </div>
      <h1 className="font-brand mb-4 text-2xl font-semibold tracking-tight text-va-text">
        Valuation
      </h1>
      {error && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}
      {loading ? (
        <VASpinner label="Loading valuation…" />
      ) : data ? (
        <div className="grid gap-6 sm:grid-cols-2">
          {dcf && (
            <VACard className="p-4">
              <h2 className="font-brand mb-3 text-lg font-medium text-va-text">
                DCF
              </h2>
              <dl className="space-y-2 text-sm text-va-text">
                <div className="flex justify-between">
                  <dt className="text-va-text2">Enterprise value</dt>
                  <dd className="font-medium font-mono">
                    {typeof dcf.enterprise_value === "number"
                      ? dcf.enterprise_value.toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })
                      : "—"}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-va-text2">PV explicit</dt>
                  <dd className="font-mono">
                    {typeof dcf.pv_explicit === "number"
                      ? dcf.pv_explicit.toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })
                      : "—"}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-va-text2">PV terminal</dt>
                  <dd className="font-mono">
                    {typeof dcf.pv_terminal === "number"
                      ? dcf.pv_terminal.toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })
                      : "—"}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-va-text2">WACC</dt>
                  <dd className="font-mono">
                    {typeof dcf.wacc === "number"
                      ? `${(dcf.wacc * 100).toFixed(1)}%`
                      : "—"}
                  </dd>
                </div>
              </dl>
            </VACard>
          )}
          {mult && (
            <VACard className="p-4">
              <h2 className="font-brand mb-3 text-lg font-medium text-va-text">
                Multiples
              </h2>
              <dl className="space-y-2 text-sm text-va-text">
                {evRange && (
                  <div className="flex justify-between">
                    <dt className="text-va-text2">Implied EV range</dt>
                    <dd className="font-medium font-mono">
                      {evRange[0].toLocaleString(undefined, {
                        maximumFractionDigits: 0,
                      })}{" "}
                      –{" "}
                      {evRange[1].toLocaleString(undefined, {
                        maximumFractionDigits: 0,
                      })}
                    </dd>
                  </div>
                )}
              </dl>
            </VACard>
          )}
          {!dcf && !mult && (
            <p className="text-va-text2">
              No valuation data for this run.
            </p>
          )}
        </div>
      ) : (
        <p className="text-va-text2">No valuation data for this run.</p>
      )}
    </main>
  );
}
