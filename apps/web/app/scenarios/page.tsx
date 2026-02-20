"use client";

import { api, type BaselineSummary, type ScenarioItem } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VAInput, VASelect, VASpinner, VAPagination, useToast } from "@/components/ui";
import { Nav } from "@/components/nav";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const PAGE_SIZE = 20;

export default function ScenariosPage() {
  const router = useRouter();
  const [items, setItems] = useState<ScenarioItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [compareBaselineId, setCompareBaselineId] = useState("");
  const [compareScenarioIdsRaw, setCompareScenarioIdsRaw] = useState("");
  const [compareResult, setCompareResult] = useState<{
    scenarios: Record<string, unknown>[];
  } | null>(null);
  const [baselines, setBaselines] = useState<BaselineSummary[]>([]);
  const { toast } = useToast();

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newBaselineId, setNewBaselineId] = useState("");
  const [overrides, setOverrides] = useState<{ ref: string; field: string; value: string }[]>([]);
  const [creating, setCreating] = useState(false);

  function addOverride() {
    setOverrides((prev) => [...prev, { ref: "", field: "", value: "" }]);
  }

  function removeOverride(index: number) {
    setOverrides((prev) => prev.filter((_, i) => i !== index));
  }

  function updateOverride(index: number, key: "ref" | "field" | "value", val: string) {
    setOverrides((prev) => prev.map((o, i) => (i === index ? { ...o, [key]: val } : o)));
  }

  async function handleCreate() {
    if (!tenantId || !newLabel || !newBaselineId) return;
    setCreating(true);
    setError(null);
    try {
      const parsedOverrides = overrides
        .filter((o) => o.ref && o.field && o.value)
        .map((o) => ({ ref: o.ref, field: o.field, value: Number(o.value) }));
      await api.scenarios.create(tenantId, {
        baseline_id: newBaselineId,
        label: newLabel,
        description: newDescription || undefined,
        overrides: parsedOverrides.length > 0 ? parsedOverrides : undefined,
      });
      toast.success("Scenario created");
      setNewLabel("");
      setNewDescription("");
      setNewBaselineId("");
      setOverrides([]);
      setShowCreate(false);
      load();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(msg);
      setError(msg);
    } finally {
      setCreating(false);
    }
  }

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.scenarios.list(tenantId, {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      setItems(res.items ?? []);
      setHasMore(res.items.length === PAGE_SIZE);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, page]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      try {
        const blRes = await api.baselines.list(ctx.tenantId);
        setBaselines(blRes.items ?? []);
      } catch { /* baselines list is optional */ }
    })();
  }, [router]);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

  async function handleCompare() {
    if (!tenantId) return;
    if (!compareBaselineId) { toast.error("Select a baseline to compare scenarios"); return; }
    setCompareResult(null);
    const scenarioIds = compareScenarioIdsRaw
      .split(",")
      .map((x) => x.trim())
      .filter(Boolean);
    try {
      const res = await api.scenarios.compare(tenantId, {
        baseline_id: compareBaselineId,
        scenario_ids: scenarioIds,
      });
      setCompareResult({ scenarios: res.scenarios ?? [] });
      toast.success("Comparison complete");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="font-brand mb-6 text-2xl font-semibold tracking-tight text-va-text">
          Scenarios
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
          <VASpinner label="Loading scenarios…" />
        ) : (
          <div className="space-y-8">
            <section>
              <h2 className="font-brand mb-3 text-lg font-medium text-va-text">
                Scenario list
              </h2>
              {items.length === 0 ? (
                <p className="text-sm text-va-text2">
                  No scenarios yet. Create one from a baseline.
                </p>
              ) : (
                <>
                  <div className="overflow-x-auto rounded-va-lg border border-va-border">
                    <table className="w-full text-sm text-va-text">
                      <thead>
                        <tr className="border-b border-va-border bg-va-surface">
                          <th className="px-3 py-2 text-left font-medium">
                            Label
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Baseline
                          </th>
                          <th className="px-3 py-2 text-left font-medium">
                            Overrides
                          </th>
                          <th className="px-3 py-2 text-right font-medium" />
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((s) => (
                          <tr
                            key={s.scenario_id}
                            className="border-b border-va-border/50"
                          >
                            <td className="px-3 py-2 font-medium">
                              {s.label}
                            </td>
                            <td className="px-3 py-2 text-va-text2">
                              {s.baseline_id} (v{s.baseline_version})
                            </td>
                            <td className="px-3 py-2 text-va-text2">
                              {Array.isArray(s.overrides)
                                ? s.overrides.length
                                : 0}{" "}
                              override(s)
                            </td>
                            <td className="px-3 py-2 text-right">
                              <VAButton
                                type="button"
                                variant="ghost"
                                onClick={async () => {
                                  if (!tenantId) return;
                                  try {
                                    await api.scenarios.delete(tenantId, s.scenario_id);
                                    toast.success("Scenario deleted");
                                    load();
                                  } catch (e) {
                                    toast.error(e instanceof Error ? e.message : String(e));
                                  }
                                }}
                              >
                                Delete
                              </VAButton>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <VAPagination
                    page={page}
                    pageSize={PAGE_SIZE}
                    hasMore={hasMore}
                    onPageChange={setPage}
                  />
                </>
              )}
            </section>
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-brand text-lg font-medium text-va-text">
                  Create scenario
                </h2>
                <VAButton
                  type="button"
                  variant={showCreate ? "ghost" : "primary"}
                  onClick={() => setShowCreate((v) => !v)}
                >
                  {showCreate ? "Cancel" : "New scenario"}
                </VAButton>
              </div>
              {showCreate && (
                <VACard className="space-y-4 p-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-sm font-medium text-va-text">Label *</label>
                      <VAInput value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="e.g. Downside stress" />
                    </div>
                    <div>
                      <label className="mb-1 block text-sm font-medium text-va-text">Baseline *</label>
                      <VASelect value={newBaselineId} onChange={(e) => setNewBaselineId(e.target.value)}>
                        <option value="">Select a baseline</option>
                        {baselines.map((b) => (
                          <option key={b.baseline_id} value={b.baseline_id}>
                            {b.baseline_id} ({b.baseline_version})
                          </option>
                        ))}
                      </VASelect>
                    </div>
                  </div>
                  <div>
                    <label className="mb-1 block text-sm font-medium text-va-text">Description</label>
                    <VAInput value={newDescription} onChange={(e) => setNewDescription(e.target.value)} placeholder="Optional description" />
                  </div>
                  <div>
                    <div className="mb-2 flex items-center justify-between">
                      <label className="text-sm font-medium text-va-text">Driver overrides ({overrides.length})</label>
                      <VAButton type="button" variant="ghost" onClick={addOverride}>+ Add override</VAButton>
                    </div>
                    {overrides.map((o, i) => (
                      <div key={i} className="mb-2 flex items-center gap-2">
                        <VAInput placeholder="Driver ref" value={o.ref} onChange={(e) => updateOverride(i, "ref", e.target.value)} className="flex-1" />
                        <VAInput placeholder="Field" value={o.field} onChange={(e) => updateOverride(i, "field", e.target.value)} className="w-32" />
                        <VAInput type="number" placeholder="Value" value={o.value} onChange={(e) => updateOverride(i, "value", e.target.value)} className="w-28" />
                        <VAButton type="button" variant="ghost" onClick={() => removeOverride(i)}>✕</VAButton>
                      </div>
                    ))}
                  </div>
                  <VAButton type="button" variant="primary" onClick={handleCreate} disabled={creating || !newLabel || !newBaselineId}>
                    {creating ? "Creating..." : "Create scenario"}
                  </VAButton>
                </VACard>
              )}
            </section>
            <section>
              <h2 className="font-brand mb-3 text-lg font-medium text-va-text">
                Compare scenarios
              </h2>
              <VACard className="flex flex-wrap items-end gap-4 p-4">
                <div className="min-w-[180px]">
                  <label className="mb-1 block text-sm font-medium text-va-text">
                    Baseline ID
                  </label>
                  <VASelect
                    value={compareBaselineId}
                    onChange={(e) => setCompareBaselineId(e.target.value)}
                  >
                    <option value="">Select a baseline</option>
                    {baselines.map((b) => (
                      <option key={b.baseline_id} value={b.baseline_id}>
                        {b.baseline_id} ({b.baseline_version})
                      </option>
                    ))}
                  </VASelect>
                </div>
                <div className="min-w-[220px]">
                  <label className="mb-1 block text-sm font-medium text-va-text">
                    Scenario IDs (comma-separated)
                  </label>
                  <VAInput
                    type="text"
                    value={compareScenarioIdsRaw}
                    onChange={(e) =>
                      setCompareScenarioIdsRaw(e.target.value)
                    }
                    placeholder="sc_xxx, sc_yyy"
                  />
                </div>
                <VAButton
                  type="button"
                  variant="primary"
                  onClick={handleCompare}
                >
                  Compare
                </VAButton>
              </VACard>
              {compareResult && compareResult.scenarios.length > 0 && (
                <div className="mt-4 overflow-x-auto rounded-va-lg border border-va-border">
                  <table className="w-full text-sm text-va-text">
                    <thead>
                      <tr className="border-b border-va-border bg-va-surface">
                        <th className="px-3 py-2 text-left font-medium">
                          Metric
                        </th>
                        {compareResult.scenarios.map(
                          (row: Record<string, unknown>) => (
                            <th
                              key={String(row.label)}
                              className="px-3 py-2 text-right font-medium font-mono"
                            >
                              {String(row.label)}
                            </th>
                          )
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {["revenue", "ebitda", "net_income", "fcf"].map(
                        (metric) => (
                          <tr
                            key={metric}
                            className="border-b border-va-border/50"
                          >
                            <td className="px-3 py-2 font-medium capitalize">
                              {metric.replaceAll("_", " ")}
                            </td>
                            {compareResult.scenarios.map(
                              (row: Record<string, unknown>) => (
                                <td
                                  key={String(row.label)}
                                  className="px-3 py-2 text-right font-mono"
                                >
                                  {typeof row[metric] === "number"
                                    ? (
                                        row[metric] as number
                                      ).toLocaleString(undefined, {
                                        maximumFractionDigits: 0,
                                      })
                                    : "—"}
                                </td>
                              )
                            )}
                          </tr>
                        )
                      )}
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
