"use client";

import { api, type BaselineSummary, type RunSummary } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VAListSkeleton, VAPagination, VAEmptyState, VAListToolbar, VAErrorAlert } from "@/components/ui";
import { SoftGateBanner } from "@/components/SoftGateBanner";
import { formatDateTime } from "@/lib/format";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const PAGE_SIZE = 20;

export default function RunsPage() {
  const router = useRouter();
  const [items, setItems] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [baselineFilter, setBaselineFilter] = useState("");
  const [search, setSearch] = useState("");
  const [baselines, setBaselines] = useState<BaselineSummary[]>([]);
  const [retryCount, setRetryCount] = useState(0);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.runs.list(tenantId, {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        ...(statusFilter && { status: statusFilter }),
        ...(baselineFilter && { baseline_id: baselineFilter }),
      });
      setItems(res.items);
      setHasMore(res.items.length === PAGE_SIZE);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, page, statusFilter, baselineFilter, retryCount]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      try {
        const blRes = await api.baselines.list(ctx.tenantId);
        setBaselines(blRes.items ?? []);
      } catch { /* baselines list is optional for filter */ }
    })();
  }, [router]);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

  useEffect(() => {
    setPage(1);
  }, [statusFilter, baselineFilter]);

  const displayed = search
    ? items.filter((r) =>
        r.run_id.toLowerCase().includes(search.toLowerCase())
      )
    : items;

  if (!tenantId && !loading) return null;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Runs
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            View run results, statements, and KPIs.
          </p>
        </div>
        {baselines.length > 0 && (
          <Link href="/baselines">
            <VAButton aria-label="New run">New Run</VAButton>
          </Link>
        )}
      </div>

      {!loading && baselines.length === 0 && (
        <SoftGateBanner
          message="No baselines found — create a baseline before running simulations."
          actionLabel="Create baseline"
          actionHref="/marketplace"
        />
      )}

      <VAListToolbar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by run ID…"
        filters={[
          {
            key: "status",
            label: "Status",
            options: [
              { value: "", label: "All statuses" },
              { value: "succeeded", label: "Succeeded" },
              { value: "failed", label: "Failed" },
              { value: "running", label: "Running" },
              { value: "pending", label: "Pending" },
            ],
          },
          {
            key: "baseline_id",
            label: "Baseline",
            options: [
              { value: "", label: "All baselines" },
              ...baselines.map((b) => ({
                value: b.baseline_id,
                label: `${b.baseline_id} (v${b.baseline_version})`,
              })),
            ],
          },
        ]}
        filterValues={{ status: statusFilter, baseline_id: baselineFilter }}
        onFilterChange={(key, value) => {
          if (key === "status") setStatusFilter(value);
          if (key === "baseline_id") setBaselineFilter(value);
        }}
        className="mb-4"
      />

      {error && (
        <VAErrorAlert
          message={error}
          onRetry={() => setRetryCount((c) => c + 1)}
          className="mb-4"
        />
      )}
      {loading ? (
        <VAListSkeleton count={4} />
      ) : items.length === 0 ? (
        <VAEmptyState
          icon="play"
          title="No runs yet"
          description="Run a baseline to generate financial projections."
          actionLabel="View baselines"
          actionHref="/baselines"
          variant="empty"
        />
      ) : displayed.length === 0 ? (
        <VAEmptyState
          title="No runs match your search"
          actionLabel="Clear search"
          onAction={() => setSearch("")}
          variant="no-results"
        />
      ) : (
        <>
          <ul className="space-y-2">
            {displayed.map((r) => (
              <li key={r.run_id}>
                <Link
                  href={`/runs/${r.run_id}`}
                  className="block rounded-va-lg border border-va-border bg-va-panel/80 p-4 transition hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-va-text">{r.run_id}</span>
                    <span
                      className={`text-sm ${
                        r.status === "succeeded"
                          ? "text-va-success"
                          : r.status === "failed"
                            ? "text-va-danger"
                            : "text-va-text2"
                      }`}
                    >
                      {r.status}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-va-text2">
                    Baseline {r.baseline_id}
                    {r.scenario_id ? ` · Scenario ${r.scenario_id}` : ""}
                  </p>
                  {r.created_at && (
                    <p className="mt-0.5 text-xs text-va-text2">
                      {formatDateTime(r.created_at)}
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
          <VAPagination
            page={page}
            pageSize={PAGE_SIZE}
            hasMore={hasMore}
            onPageChange={setPage}
          />
        </>
      )}
    </main>
  );
}
