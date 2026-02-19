"use client";

import { api } from "@/lib/api";
import { VAButton, VACard, VASpinner } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

interface SensitivityDriver {
  ref: string;
  impact_low: number;
  impact_high: number;
}

interface SensitivityData {
  base_fcf: number;
  pct: number;
  drivers: SensitivityDriver[];
}

const PCT_OPTIONS = [0.05, 0.1, 0.2] as const;

function fmtNum(n: number): string {
  if (Number.isNaN(n)) return "\u2014";
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

export default function SensitivityPage() {
  const params = useParams();
  const runId = params.id as string;
  const [data, setData] = useState<SensitivityData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pct, setPct] = useState(0.1);
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
      setLoading(true);
      setError(null);
      try {
        const res = await api.runs.getSensitivity(tid, runId, pct);
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
  }, [runId, pct]);

  const sorted = [...(data?.drivers ?? [])].sort(
    (a, b) =>
      Math.abs(b.impact_low) +
      Math.abs(b.impact_high) -
      (Math.abs(a.impact_low) + Math.abs(a.impact_high))
  );

  const maxImpact = sorted.reduce(
    (m, d) => Math.max(m, Math.abs(d.impact_low), Math.abs(d.impact_high)),
    1
  );

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link
            href="/runs"
            className="rounded text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
          >
            &larr; Runs
          </Link>
          <Link
            href={`/runs/${runId}`}
            className="rounded text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
          >
            Run {runId}
          </Link>
        </div>

        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Sensitivity Analysis
          </h1>
          <div className="flex gap-2">
            {PCT_OPTIONS.map((p) => (
              <VAButton
                key={p}
                type="button"
                variant={pct === p ? "primary" : "ghost"}
                onClick={() => setPct(p)}
                className="!py-1.5"
              >
                &plusmn;{(p * 100).toFixed(0)}%
              </VAButton>
            ))}
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

        {loading ? (
          <VASpinner label="Loading sensitivity\u2026" />
        ) : data && sorted.length > 0 ? (
          <VACard className="p-4">
            {data.base_fcf != null && (
              <p className="mb-4 text-sm text-va-text2">
                Base FCF:{" "}
                <span className="font-mono text-va-text">
                  {fmtNum(data.base_fcf)}
                </span>
              </p>
            )}

            <div className="space-y-2">
              {sorted.map((d) => {
                const lowPct =
                  (Math.abs(d.impact_low) / maxImpact) * 100;
                const highPct =
                  (Math.abs(d.impact_high) / maxImpact) * 100;
                return (
                  <div key={d.ref} className="flex items-center gap-2">
                    <div
                      className="w-40 shrink-0 truncate text-right text-sm text-va-text"
                      title={d.ref}
                    >
                      {d.ref}
                    </div>
                    <div className="flex flex-1 items-center">
                      {/* Low scenario (left half) */}
                      <div className="flex w-1/2 justify-end">
                        <div
                          className={`h-6 rounded-l ${d.impact_low < 0 ? "bg-va-danger/70" : "bg-va-blue/70"}`}
                          style={{
                            width: `${lowPct}%`,
                            minWidth: lowPct > 0 ? "2px" : "0",
                          }}
                        />
                      </div>
                      {/* Center line */}
                      <div className="h-8 w-px bg-va-text2/40" />
                      {/* High scenario (right half) */}
                      <div className="flex w-1/2">
                        <div
                          className={`h-6 rounded-r ${d.impact_high < 0 ? "bg-va-danger/70" : "bg-va-blue/70"}`}
                          style={{
                            width: `${highPct}%`,
                            minWidth: highPct > 0 ? "2px" : "0",
                          }}
                        />
                      </div>
                    </div>
                    <div className="w-28 shrink-0 font-mono text-xs text-va-text2">
                      {fmtNum(d.impact_low)} / {fmtNum(d.impact_high)}
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-4 flex justify-center gap-6 text-xs text-va-text2">
              <span className="flex items-center gap-1">
                <span className="inline-block h-3 w-3 rounded-sm bg-va-danger/70" />{" "}
                Negative impact
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-3 w-3 rounded-sm bg-va-blue/70" />{" "}
                Positive impact
              </span>
            </div>
          </VACard>
        ) : (
          <VACard className="p-6 text-center text-va-text2">
            No sensitivity data for this run.
          </VACard>
        )}
      </main>
    </div>
  );
}
