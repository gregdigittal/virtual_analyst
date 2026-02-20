"use client";

import { api, type KpiItem } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VASpinner } from "@/components/ui";
import { Nav } from "@/components/nav";
import { useRouter } from "next/navigation";
import { useEffect, useState, useCallback } from "react";

interface OrgEntity {
  org_id: string;
  group_name: string;
  reporting_currency: string;
  status: string;
  entity_count: number;
  created_at: string | null;
}

interface EntityKpis {
  entity: OrgEntity;
  kpis: KpiItem | null;
  runId: string | null;
  loading: boolean;
  error: string | null;
}

const METRIC_KEYS = [
  { key: "revenue", label: "Revenue" },
  { key: "ebitda", label: "EBITDA" },
  { key: "gross_profit", label: "Gross Profit" },
  { key: "net_income", label: "Net Income" },
  { key: "fcf", label: "FCF" },
  { key: "ebit", label: "EBIT" },
] as const;

function fmtNum(n: unknown): string {
  if (n == null || typeof n !== "number" || Number.isNaN(n)) return "\u2014";
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

export default function ComparePage() {
  const router = useRouter();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [entities, setEntities] = useState<OrgEntity[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [entityKpis, setEntityKpis] = useState<Map<string, EntityKpis>>(
    new Map()
  );
  const [loadingEntities, setLoadingEntities] = useState(true);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      try {
        const res = await api.orgStructures.list(ctx.tenantId);
        if (!cancelled) setEntities(res.items ?? []);
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoadingEntities(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  function toggleEntity(orgId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(orgId)) next.delete(orgId);
      else next.add(orgId);
      return next;
    });
  }

  const compare = useCallback(async () => {
    if (!tenantId || selected.size === 0) return;
    setComparing(true);
    setError(null);

    const results = new Map<string, EntityKpis>();
    const selectedEntities = entities.filter((e) => selected.has(e.org_id));

    for (const entity of selectedEntities) {
      results.set(entity.org_id, {
        entity,
        kpis: null,
        runId: null,
        loading: true,
        error: null,
      });
    }
    setEntityKpis(new Map(results));

    await Promise.all(
      selectedEntities.map(async (entity) => {
        try {
          // TODO: scope runs per entity once baseline_id is exposed on OrgStructureItem
          const runsRes = await api.runs.list(tenantId, { status: "completed", limit: 1 });
          const latestRun = runsRes.items?.[0];
          if (!latestRun) {
            results.set(entity.org_id, {
              entity,
              kpis: null,
              runId: null,
              loading: false,
              error: "No runs found",
            });
            return;
          }
          const kpiRes = await api.runs.getKpis(tenantId, latestRun.run_id);
          const kpiArr = Array.isArray(kpiRes) ? kpiRes : [];
          const terminal = kpiArr.length > 0 ? kpiArr[kpiArr.length - 1] : null;
          results.set(entity.org_id, {
            entity,
            kpis: terminal,
            runId: latestRun.run_id,
            loading: false,
            error: null,
          });
        } catch (e) {
          results.set(entity.org_id, {
            entity,
            kpis: null,
            runId: null,
            loading: false,
            error: e instanceof Error ? e.message : String(e),
          });
        }
      })
    );

    setEntityKpis(new Map(results));
    setComparing(false);
  }, [tenantId, selected, entities]);

  const comparedEntities = Array.from(entityKpis.values()).filter(
    (e) => !e.loading
  );

  const metricMaxes = new Map<string, number>();
  for (const m of METRIC_KEYS) {
    let max = 0;
    for (const ek of comparedEntities) {
      const val = ek.kpis?.[m.key];
      if (typeof val === "number" && val > max) max = val;
    }
    metricMaxes.set(m.key, max || 1);
  }

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="font-brand mb-6 text-2xl font-semibold tracking-tight text-va-text">
          Entity Comparison
        </h1>

        {error && (
          <div className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger">
            {error}
          </div>
        )}

        {loadingEntities ? (
          <VASpinner label="Loading entities\u2026" />
        ) : (
          <>
            {/* Entity selector */}
            <VACard className="mb-6 p-4">
              <h2 className="mb-3 text-sm font-medium text-va-text">
                Select entities to compare
              </h2>
              <div className="flex flex-wrap gap-2">
                {entities.map((e) => (
                  <button
                    key={e.org_id}
                    type="button"
                    onClick={() => toggleEntity(e.org_id)}
                    className={`rounded-va-sm border px-3 py-1.5 text-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue ${
                      selected.has(e.org_id)
                        ? "border-va-blue bg-va-blue/20 text-va-text"
                        : "border-va-border text-va-text2 hover:bg-white/5"
                    }`}
                  >
                    {e.group_name}
                  </button>
                ))}
              </div>
              {entities.length === 0 && (
                <p className="text-sm text-va-text2">
                  No entities found. Create org structures first.
                </p>
              )}
              <div className="mt-3">
                <VAButton
                  type="button"
                  variant="primary"
                  onClick={compare}
                  disabled={selected.size === 0 || comparing}
                >
                  {comparing
                    ? "Comparing\u2026"
                    : `Compare ${selected.size} entit${selected.size === 1 ? "y" : "ies"}`}
                </VAButton>
              </div>
            </VACard>

            {/* Comparison table */}
            {comparedEntities.length > 0 && (
              <VACard className="overflow-x-auto p-4">
                <table className="w-full min-w-[600px] text-sm text-va-text">
                  <thead>
                    <tr className="border-b border-va-border">
                      <th className="px-3 py-2 text-left font-medium">
                        Metric
                      </th>
                      {comparedEntities.map((ek) => (
                        <th
                          key={ek.entity.org_id}
                          className="px-3 py-2 text-right font-medium"
                        >
                          {ek.entity.group_name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {METRIC_KEYS.map((m, mi) => {
                      const max = metricMaxes.get(m.key) ?? 1;
                      return (
                        <tr
                          key={m.key}
                          className={
                            mi % 2 === 0
                              ? "border-b border-va-border/50"
                              : "border-b border-va-border/50 bg-va-surface/50"
                          }
                        >
                          <td className="px-3 py-2 font-medium">{m.label}</td>
                          {comparedEntities.map((ek) => {
                            const val = ek.kpis?.[m.key];
                            const num =
                              typeof val === "number" ? val : null;
                            const barW =
                              num != null && num > 0
                                ? (num / max) * 100
                                : 0;
                            return (
                              <td
                                key={ek.entity.org_id}
                                className="px-3 py-2 text-right"
                              >
                                <div className="flex items-center justify-end gap-2">
                                  <div className="h-3 w-20">
                                    <div
                                      className="h-full rounded-sm bg-va-blue/50"
                                      style={{ width: `${barW}%` }}
                                    />
                                  </div>
                                  <span className="font-mono text-xs">
                                    {fmtNum(num)}
                                  </span>
                                </div>
                                {ek.error && (
                                  <span className="text-xs text-va-danger">
                                    {ek.error}
                                  </span>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </VACard>
            )}
          </>
        )}
      </main>
    </div>
  );
}
