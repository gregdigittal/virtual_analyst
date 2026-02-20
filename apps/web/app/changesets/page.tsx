"use client";

import { api, type BaselineSummary } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import {
  VAButton,
  VACard,
  VAInput,
  VASelect,
  VASpinner,
  VAPagination,
  useToast,
} from "@/components/ui";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const PAGE_SIZE = 20;

interface ChangesetRow {
  changeset_id: string;
  baseline_id: string;
  base_version: string;
  status: string;
  label?: string;
  created_at: string | null;
  overrides: unknown[];
}

export default function ChangesetsPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [items, setItems] = useState<ChangesetRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [baselines, setBaselines] = useState<BaselineSummary[]>([]);
  const [newBaselineId, setNewBaselineId] = useState("");
  const [newBaseVersion, setNewBaseVersion] = useState("v1");
  const [newLabel, setNewLabel] = useState("");
  const [overrides, setOverrides] = useState<{ path: string; value: string }[]>(
    []
  );
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.changesets.list(tenantId, {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      setItems(res.items ?? []);
      setHasMore((res.items ?? []).length === PAGE_SIZE);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, page]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) {
        router.replace("/login");
        return;
      }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
      try {
        const blRes = await api.baselines.list(ctx.tenantId);
        setBaselines(blRes.items ?? []);
      } catch {
        /* baselines list is optional */
      }
    })();
  }, [router]);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

  function addOverride() {
    setOverrides((prev) => [...prev, { path: "", value: "" }]);
  }

  function removeOverride(index: number) {
    setOverrides((prev) => prev.filter((_, i) => i !== index));
  }

  function updateOverride(index: number, key: "path" | "value", val: string) {
    setOverrides((prev) =>
      prev.map((o, i) => (i === index ? { ...o, [key]: val } : o))
    );
  }

  async function handleCreate() {
    if (!tenantId || !newBaselineId) return;
    setCreating(true);
    setError(null);
    try {
      const parsedOverrides = overrides
        .filter((o) => o.path && o.value)
        .map((o) => {
          let parsed: unknown;
          try {
            parsed = JSON.parse(o.value);
          } catch {
            parsed = o.value;
          }
          return { path: o.path, value: parsed };
        });
      const res = await api.changesets.create(tenantId, userId ?? undefined, {
        baseline_id: newBaselineId,
        base_version: newBaseVersion || "v1",
        label: newLabel || undefined,
        overrides: parsedOverrides.length > 0 ? parsedOverrides : undefined,
      });
      toast.success(`Changeset ${res.changeset_id} created`);
      setNewLabel("");
      setNewBaselineId("");
      setNewBaseVersion("v1");
      setOverrides([]);
      setShowCreate(false);
      router.push(`/changesets/${res.changeset_id}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(msg);
      setError(msg);
    } finally {
      setCreating(false);
    }
  }

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Changesets
          </h1>
          <VAButton
            type="button"
            variant={showCreate ? "ghost" : "primary"}
            onClick={() => setShowCreate((v) => !v)}
          >
            {showCreate ? "Cancel" : "New changeset"}
          </VAButton>
        </div>

        {error && (
          <div
            className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
            role="alert"
          >
            {error}
          </div>
        )}

        {/* Create form */}
        {showCreate && (
          <VACard className="mb-6 space-y-4 p-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">
                  Baseline *
                </label>
                <VASelect
                  value={newBaselineId}
                  onChange={(e) => setNewBaselineId(e.target.value)}
                >
                  <option value="">Select a baseline</option>
                  {baselines.map((b) => (
                    <option key={b.baseline_id} value={b.baseline_id}>
                      {b.baseline_id} ({b.baseline_version})
                    </option>
                  ))}
                </VASelect>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">
                  Base version
                </label>
                <VAInput
                  value={newBaseVersion}
                  onChange={(e) => setNewBaseVersion(e.target.value)}
                  placeholder="v1"
                />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-va-text">
                Label (optional)
              </label>
              <VAInput
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                placeholder="e.g. Increase growth rate to 7%"
              />
            </div>

            {/* Overrides */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-va-text">
                  Overrides ({overrides.length})
                </label>
                <VAButton type="button" variant="ghost" onClick={addOverride}>
                  + Add override
                </VAButton>
              </div>
              {overrides.map((o, i) => (
                <div key={i} className="mb-2 flex items-center gap-2">
                  <VAInput
                    placeholder="Path (e.g. revenue.growth_rate)"
                    value={o.path}
                    onChange={(e) => updateOverride(i, "path", e.target.value)}
                    className="flex-1"
                  />
                  <VAInput
                    placeholder="Value (JSON)"
                    value={o.value}
                    onChange={(e) => updateOverride(i, "value", e.target.value)}
                    className="flex-1"
                  />
                  <VAButton
                    type="button"
                    variant="ghost"
                    onClick={() => removeOverride(i)}
                  >
                    ✕
                  </VAButton>
                </div>
              ))}
            </div>

            <VAButton
              type="button"
              variant="primary"
              onClick={handleCreate}
              disabled={creating || !newBaselineId}
            >
              {creating ? "Creating..." : "Create changeset"}
            </VAButton>
          </VACard>
        )}

        {/* Changeset list */}
        {loading ? (
          <VASpinner label="Loading changesets..." />
        ) : items.length === 0 ? (
          <p className="text-sm text-va-text2">
            No changesets yet. Create one to propose targeted assumption changes.
          </p>
        ) : (
          <>
            <div className="overflow-x-auto rounded-va-lg border border-va-border">
              <table className="w-full text-sm text-va-text">
                <thead>
                  <tr className="border-b border-va-border bg-va-surface">
                    <th className="px-3 py-2 text-left font-medium">ID</th>
                    <th className="px-3 py-2 text-left font-medium">Label</th>
                    <th className="px-3 py-2 text-left font-medium">
                      Baseline
                    </th>
                    <th className="px-3 py-2 text-left font-medium">Status</th>
                    <th className="px-3 py-2 text-left font-medium">
                      Overrides
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((cs) => (
                    <tr
                      key={cs.changeset_id}
                      className="border-b border-va-border/50"
                    >
                      <td className="px-3 py-2">
                        <Link
                          href={`/changesets/${cs.changeset_id}`}
                          className="text-va-blue hover:underline"
                        >
                          {cs.changeset_id}
                        </Link>
                      </td>
                      <td className="px-3 py-2 text-va-text2">
                        {cs.label ?? "\u2014"}
                      </td>
                      <td className="px-3 py-2 text-va-text2">
                        {cs.baseline_id} ({cs.base_version})
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs ${
                            cs.status === "merged"
                              ? "bg-green-900/40 text-green-300"
                              : cs.status === "draft"
                                ? "bg-yellow-900/40 text-yellow-300"
                                : "bg-va-surface text-va-text2"
                          }`}
                        >
                          {cs.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-va-text2">
                        {Array.isArray(cs.overrides)
                          ? cs.overrides.length
                          : 0}
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
      </main>
    </div>
  );
}
