"use client";

import { api, type ScenarioItem } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import { useEffect, useState } from "react";

export default function ScenariosPage() {
  const [items, setItems] = useState<ScenarioItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [compareBaselineId, setCompareBaselineId] = useState("");
  const [compareScenarioIdsRaw, setCompareScenarioIdsRaw] = useState("");
  const [compareResult, setCompareResult] = useState<{ scenarios: Record<string, unknown>[] } | null>(null);

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
        const res = await api.scenarios.list(tid);
        if (!cancelled) setItems(res.items ?? []);
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
  }, []);

  async function handleCompare() {
    if (!tenantId || !compareBaselineId) return;
    setCompareResult(null);
    const scenarioIds = compareScenarioIdsRaw.split(",").map((x) => x.trim()).filter(Boolean);
    try {
      const res = await api.scenarios.compare(tenantId, {
        baseline_id: compareBaselineId,
        scenario_ids: scenarioIds,
      });
      setCompareResult({ scenarios: res.scenarios ?? [] });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-background">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="mb-6 text-2xl font-semibold tracking-tight">
          Scenarios
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
          <p className="text-muted-foreground">Loading scenarios…</p>
        ) : (
          <div className="space-y-8">
            <section>
              <h2 className="mb-3 text-lg font-medium">Scenario list</h2>
              {items.length === 0 ? (
                <p className="text-sm text-muted-foreground">No scenarios yet. Create one from a baseline.</p>
              ) : (
                <div className="overflow-x-auto rounded-lg border border-border">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border bg-muted/50">
                        <th className="px-3 py-2 text-left font-medium">Label</th>
                        <th className="px-3 py-2 text-left font-medium">Baseline</th>
                        <th className="px-3 py-2 text-left font-medium">Overrides</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((s) => (
                        <tr key={s.scenario_id} className="border-b border-border/50">
                          <td className="px-3 py-2 font-medium">{s.label}</td>
                          <td className="px-3 py-2">{s.baseline_id} (v{s.baseline_version})</td>
                          <td className="px-3 py-2">{Array.isArray(s.overrides) ? s.overrides.length : 0} override(s)</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
            <section>
              <h2 className="mb-3 text-lg font-medium">Compare scenarios</h2>
              <div className="flex flex-wrap items-end gap-4 rounded-lg border border-border bg-card p-4">
                <div>
                  <label className="mb-1 block text-sm font-medium">Baseline ID</label>
                  <input
                    type="text"
                    value={compareBaselineId}
                    onChange={(e) => setCompareBaselineId(e.target.value)}
                    placeholder="e.g. bl_xxx"
                    className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">Scenario IDs (comma-separated)</label>
                  <input
                    type="text"
                    value={compareScenarioIdsRaw}
                    onChange={(e) => setCompareScenarioIdsRaw(e.target.value)}
                    placeholder="sc_xxx, sc_yyy"
                    className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                  />
                </div>
                <button
                  type="button"
                  onClick={handleCompare}
                  className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                >
                  Compare
                </button>
              </div>
              {compareResult && compareResult.scenarios.length > 0 && (
                <div className="mt-4 overflow-x-auto rounded-lg border border-border">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border bg-muted/50">
                        <th className="px-3 py-2 text-left font-medium">Metric</th>
                        {compareResult.scenarios.map((row: Record<string, unknown>) => (
                          <th key={String(row.label)} className="px-3 py-2 text-right font-medium">{String(row.label)}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {["revenue", "ebitda", "net_income", "fcf"].map((metric) => (
                        <tr key={metric} className="border-b border-border/50">
                          <td className="px-3 py-2 font-medium capitalize">{metric.replaceAll("_", " ")}</td>
                          {compareResult.scenarios.map((row: Record<string, unknown>) => (
                            <td key={String(row.label)} className="px-3 py-2 text-right">
                              {typeof row[metric] === "number"
                                ? (row[metric] as number).toLocaleString(undefined, { maximumFractionDigits: 0 })
                                : "—"}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
