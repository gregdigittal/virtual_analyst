"use client";

import { api, type BudgetSummary } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VASpinner, VAPagination, VAEmptyState, VAListToolbar } from "@/components/ui";
import { SoftGateBanner } from "@/components/SoftGateBanner";
import { formatDateTime } from "@/lib/format";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const PAGE_SIZE = 20;

export default function BudgetsPage() {
  const router = useRouter();
  const [items, setItems] = useState<BudgetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [search, setSearch] = useState("");
  const [hasBaselines, setHasBaselines] = useState(true);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.budgets.list(tenantId, {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      setItems(res.budgets);
      setHasMore(res.budgets.length === PAGE_SIZE);
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
        const blRes = await api.baselines.list(ctx.tenantId, { limit: 1 });
        setHasBaselines((blRes.items ?? []).length > 0);
      } catch { /* baseline check is non-critical */ }
    })();
  }, [router]);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

  const displayed = search
    ? items.filter((b) =>
        b.label.toLowerCase().includes(search.toLowerCase())
      )
    : items;

  if (!tenantId && !loading) return null;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Budgets
        </h1>
        <p className="mt-1 text-sm text-va-text2">
          List budgets with status; open for variance and reforecast.
        </p>
      </div>

      {!loading && !hasBaselines && (
        <SoftGateBanner
          message="No baselines found — create one to start budgeting."
          actionLabel="Create baseline"
          actionHref="/marketplace"
        />
      )}

      <VAListToolbar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by label…"
        className="mb-4"
      />

      {error && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}
      {loading ? (
        <VASpinner label="Loading budgets…" />
      ) : items.length === 0 ? (
        <VAEmptyState
          icon="dollar"
          title="No budgets yet"
          description="Browse templates to create your first budget."
          actionLabel="Browse templates"
          actionHref="/marketplace"
          variant="empty"
        />
      ) : displayed.length === 0 ? (
        <VAEmptyState
          title="No budgets match your search"
          actionLabel="Clear search"
          onAction={() => setSearch("")}
          variant="no-results"
        />
      ) : (
        <>
          <ul className="space-y-2">
            {displayed.map((b) => (
              <li key={b.budget_id}>
                <Link
                  href={`/budgets/${b.budget_id}`}
                  className="block rounded-va-lg border border-va-border bg-va-panel/80 p-4 transition hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-va-text">{b.label}</span>
                    <span
                      className={`text-sm ${
                        b.status === "active"
                          ? "text-va-success"
                          : b.status === "draft"
                            ? "text-va-text2"
                            : "text-va-warning"
                      }`}
                    >
                      {b.status}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-va-text2">
                    {b.fiscal_year}
                  </p>
                  {b.created_at && (
                    <p className="mt-0.5 text-xs text-va-text2">
                      {formatDateTime(b.created_at)}
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
      <p className="mt-4 text-sm text-va-text2">
        <Link href="/dashboard" className="text-va-blue hover:underline">
          Dashboard
        </Link>{" "}
        includes budget KPI widgets (burn rate, runway, utilisation, variance trend).
      </p>
    </main>
  );
}
