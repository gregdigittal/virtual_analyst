"use client";

import { VAButton, VACard, VAInput, VASelect, VASpinner, VAPagination, VAEmptyState, VAListToolbar, useToast } from "@/components/ui";
import { api, type MemoSummary, type RunSummary } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { useCallback, useEffect, useState } from "react";

const PAGE_SIZE = 20;

const MEMO_TYPES = [
  "investment_committee",
  "credit_memo",
  "valuation_note",
];

export default function MemosPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | undefined>(undefined);
  const [items, setItems] = useState<MemoSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    run_id: "",
    memo_type: MEMO_TYPES[0],
    title: "",
  });
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const { toast } = useToast();
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [memoTypeFilter, setMemoTypeFilter] = useState("");

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.memos.list(tenantId, {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        ...(memoTypeFilter && { memo_type: memoTypeFilter }),
      });
      setItems(res.items ?? []);
      setTotal(res.total);
      try {
        const runsRes = await api.runs.list(tenantId);
        setRuns(runsRes.items ?? []);
      } catch { /* runs list is optional */ }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, page, memoTypeFilter]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
    })();
  }, []);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

  useEffect(() => {
    setPage(1);
  }, [memoTypeFilter]);

  async function handleCreate() {
    if (!tenantId) return;
    if (!form.run_id) { toast.error("Select a run to generate a memo"); return; }
    setError(null);
    try {
      await api.memos.create(tenantId, userId, {
        run_id: form.run_id,
        memo_type: form.memo_type,
        title: form.title || undefined,
      });
      setForm((prev) => ({ ...prev, title: "" }));
      await load();
      toast.success("Memo created");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Memos
        </h1>
        <p className="mt-1 text-sm text-va-text2">
          Generate and download memo packs from run results.
        </p>
      </div>

      {error && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}

      <VACard className="p-5">
        <h2 className="text-lg font-medium text-va-text">Create memo</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <VASelect
            value={form.run_id}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, run_id: e.target.value }))
            }
          >
            <option value="">Select a run</option>
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id} {r.status ? `(${r.status})` : ""}
              </option>
            ))}
          </VASelect>
          <VASelect
            value={form.memo_type}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, memo_type: e.target.value }))
            }
          >
            {MEMO_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </VASelect>
          <VAInput
            placeholder="Title (optional)"
            value={form.title}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, title: e.target.value }))
            }
          />
        </div>
        <VAButton className="mt-3" onClick={handleCreate}>
          Generate memo
        </VAButton>
      </VACard>

      <VAListToolbar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search memos…"
        filters={[
          {
            key: "memo_type",
            label: "Memo type",
            options: [
              { label: "All memo types", value: "" },
              ...MEMO_TYPES.map((t) => ({ label: t, value: t })),
            ],
          },
        ]}
        filterValues={{ memo_type: memoTypeFilter }}
        onFilterChange={(key, value) => {
          if (key === "memo_type") setMemoTypeFilter(value);
        }}
        onClearFilters={() => { setMemoTypeFilter(""); setSearch(""); }}
        className="mt-4 mb-4"
      />

      {loading ? (
        <VASpinner label="Loading memos…" />
      ) : items.length === 0 && !search ? (
        <VAEmptyState
          icon="file-text"
          title="No memos yet"
          description="Generate a memo using the form above."
          variant="empty"
        />
      ) : (() => {
        const displayed = search
          ? items.filter((i) => i.title.toLowerCase().includes(search.toLowerCase()))
          : items;
        return displayed.length === 0 ? (
          <VAEmptyState
            title="No matching memos"
            description="Try a different search term or filter."
            actionLabel="Clear search"
            onAction={() => setSearch("")}
            variant="no-results"
          />
        ) : (
        <>
          <div className="overflow-x-auto rounded-va-lg border border-va-border">
            <table className="w-full text-sm text-va-text">
              <thead>
                <tr className="border-b border-va-border bg-va-surface">
                  <th className="px-3 py-2 text-left font-medium">Title</th>
                  <th className="px-3 py-2 text-left font-medium">Type</th>
                  <th className="px-3 py-2 text-left font-medium">Created</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {displayed.map((memo) => (
                  <tr
                    key={memo.memo_id}
                    className="border-b border-va-border/50"
                  >
                    <td className="px-3 py-2">{memo.title}</td>
                    <td className="px-3 py-2 text-va-text2">
                      {memo.memo_type}
                    </td>
                    <td className="px-3 py-2 text-va-text2">
                      {formatDateTime(memo.created_at)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <a
                        className="text-va-blue hover:underline"
                        href={api.memos.downloadUrl(memo.memo_id, "pdf")}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Download PDF
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <VAPagination
            page={page}
            pageSize={PAGE_SIZE}
            total={total}
            onPageChange={setPage}
          />
        </>
        );
      })()}
    </main>
  );
}
