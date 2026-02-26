"use client";

import { api, type KpiItem, type RunSummary } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VASelect, VASpinner } from "@/components/ui";
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
  const [mode, setMode] = useState<"entity" | "run">("entity");

  // Run comparison state
  const [runIdA, setRunIdA] = useState("");
  const [runIdB, setRunIdB] = useState("");
  const [runKpisA, setRunKpisA] = useState<KpiItem[]>([]);
  const [runKpisB, setRunKpisB] = useState<KpiItem[]>([]);
  const [runComparing, setRunComparing] = useState(false);
  const [availableRuns, setAvailableRuns] = useState<RunSummary[]>([]);

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
      try {
        const runsRes = await api.runs.list(ctx.tenantId, { status: "completed", limit: 50 });
        if (!cancelled) setAvailableRuns(runsRes.items ?? []);
      } catch { /* optional */ }
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
          // Fetch entity details to get baseline_ids for scoping runs
          const orgDetail = await api.orgStructures.get(tenantId, entity.org_id);
          const entityBaselines = (orgDetail.entities as { baseline_id?: string | null }[])
            .map((e) => e.baseline_id)
            .filter((id): id is string => !!id);

          let latestRun: RunSummary | undefined;
          if (entityBaselines.length > 0) {
            const runsRes = await api.runs.list(tenantId, { status: "completed", limit: 50 });
            latestRun = (runsRes.items ?? []).find((r) =>
              entityBaselines.includes(r.baseline_id)
            );
          }

          if (!latestRun) {
            results.set(entity.org_id, {
              entity,
              kpis: null,
              runId: null,
              loading: false,
              error: entityBaselines.length === 0
                ? "No baselines linked to entity"
                : "No completed runs for this entity",
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

  async function compareRuns() {
    if (!tenantId || !runIdA || !runIdB) return;
    setRunComparing(true);
    setError(null);
    try {
      const [kA, kB] = await Promise.all([
        api.runs.getKpis(tenantId, runIdA),
        api.runs.getKpis(tenantId, runIdB),
      ]);
      setRunKpisA(Array.isArray(kA) ? kA : []);
      setRunKpisB(Array.isArray(kB) ? kB : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunComparing(false);
    }
  }

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
    <main className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="font-brand mb-4 text-2xl font-semibold tracking-tight text-va-text">
          Comparison
        </h1>
        <div className="mb-6 flex gap-2">
          <VAButton type="button" variant={mode === "entity" ? "primary" : "ghost"} onClick={() => setMode("entity")}>
            Entity comparison
          </VAButton>
          <VAButton type="button" variant={mode === "run" ? "primary" : "ghost"} onClick={() => setMode("run")}>
            Run comparison
          </VAButton>
        </div>

        {error && (
          <div className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger">
            {error}
          </div>
        )}

        {mode === "entity" && (
          loadingEntities ? (
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
          )
        )}

        {mode === "run" && (
          <>
            <VACard className="mb-6 p-4">
              <h2 className="mb-3 text-sm font-medium text-va-text">Select two runs to compare</h2>
              <div className="flex flex-wrap items-end gap-4">
                <div className="min-w-[200px]">
                  <label className="mb-1 block text-sm text-va-text2">Run A</label>
                  <VASelect value={runIdA} onChange={(e) => setRunIdA(e.target.value)}>
                    <option value="">Select run…</option>
                    {availableRuns.map((r) => (
                      <option key={r.run_id} value={r.run_id}>{r.run_id}</option>
                    ))}
                  </VASelect>
                </div>
                <div className="min-w-[200px]">
                  <label className="mb-1 block text-sm text-va-text2">Run B</label>
                  <VASelect value={runIdB} onChange={(e) => setRunIdB(e.target.value)}>
                    <option value="">Select run…</option>
                    {availableRuns.map((r) => (
                      <option key={r.run_id} value={r.run_id}>{r.run_id}</option>
                    ))}
                  </VASelect>
                </div>
                <VAButton
                  type="button"
                  variant="primary"
                  onClick={compareRuns}
                  disabled={!runIdA || !runIdB || runIdA === runIdB || runComparing}
                >
                  {runComparing ? "Comparing…" : "Compare runs"}
                </VAButton>
              </div>
            </VACard>

            {runKpisA.length > 0 && runKpisB.length > 0 && (
              <VACard className="overflow-x-auto p-4">
                <h2 className="mb-3 text-sm font-medium text-va-text">KPI comparison (terminal period)</h2>
                <RunKpiComparisonTable
                  runIdA={runIdA}
                  runIdB={runIdB}
                  kpisA={runKpisA[runKpisA.length - 1]}
                  kpisB={runKpisB[runKpisB.length - 1]}
                />
              </VACard>
            )}
          </>
        )}
    </main>
  );
}

function RunKpiComparisonTable({
  runIdA, runIdB, kpisA, kpisB,
}: {
  runIdA: string; runIdB: string;
  kpisA: KpiItem; kpisB: KpiItem;
}) {
  const { period: _pA, ...restA } = kpisA;
  const { period: _pB, ...restB } = kpisB;
  const allKeys = Array.from(new Set([...Object.keys(restA), ...Object.keys(restB)]));

  return (
    <table className="w-full min-w-[500px] text-sm text-va-text">
      <thead>
        <tr className="border-b border-va-border">
          <th className="px-3 py-2 text-left font-medium">Metric</th>
          <th className="px-3 py-2 text-right font-medium font-mono">{runIdA.slice(0, 12)}</th>
          <th className="px-3 py-2 text-right font-medium font-mono">{runIdB.slice(0, 12)}</th>
          <th className="px-3 py-2 text-right font-medium">Variance</th>
        </tr>
      </thead>
      <tbody>
        {allKeys.map((key) => {
          const valA = typeof restA[key] === "number" ? (restA[key] as number) : null;
          const valB = typeof restB[key] === "number" ? (restB[key] as number) : null;
          const variance = valA != null && valB != null ? valB - valA : null;
          const pct = valA != null && valA !== 0 && variance != null ? (variance / Math.abs(valA)) * 100 : null;
          return (
            <tr key={key} className="border-b border-va-border/50">
              <td className="px-3 py-2 capitalize">{key.replace(/_/g, " ")}</td>
              <td className="px-3 py-2 text-right font-mono">{valA != null ? valA.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—"}</td>
              <td className="px-3 py-2 text-right font-mono">{valB != null ? valB.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—"}</td>
              <td className={`px-3 py-2 text-right font-mono text-xs ${variance != null && variance > 0 ? "text-green-400" : variance != null && variance < 0 ? "text-va-danger" : ""}`}>
                {variance != null
                  ? `${variance > 0 ? "+" : ""}${variance.toLocaleString(undefined, { maximumFractionDigits: 0 })}${pct != null ? ` (${pct > 0 ? "+" : ""}${pct.toFixed(1)}%)` : ""}`
                  : "—"}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
