"use client";

import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VAEmptyState, VAErrorAlert, VAInput, VAListSkeleton, VAListToolbar } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

interface OrgStructureItem {
  org_id: string;
  group_name: string;
  reporting_currency: string;
  status: string;
  entity_count: number;
  created_at: string | null;
}

export default function OrgStructuresPage() {
  const router = useRouter();
  const [items, setItems] = useState<OrgStructureItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | undefined>(undefined);
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [newName, setNewName] = useState("");
  const [newCurrency, setNewCurrency] = useState("USD");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
      try {
        const res = await api.orgStructures.list(ctx.tenantId);
        if (!cancelled) setItems(res.items);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [retryCount]);

  async function handleCreate() {
    if (!tenantId || !newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const res = await api.orgStructures.create(tenantId, userId, {
        group_name: newName.trim(),
        reporting_currency: newCurrency || undefined,
      });
      router.push(`/org-structures/${res.org_id}`);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  }

  const filteredItems = search
    ? items.filter((o) =>
        o.group_name.toLowerCase().includes(search.toLowerCase()),
      )
    : items;

  if (!tenantId && !loading) return null;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Group Structures
        </h1>
        <VAButton
          type="button"
          variant="primary"
          onClick={() => setShowCreate(true)}
        >
          Create New
        </VAButton>
      </div>
      {error && (
        <VAErrorAlert
          message={error}
          onRetry={() => setRetryCount((c) => c + 1)}
          className="mb-4"
        />
      )}
      {showCreate && (
        <VACard className="mb-6 p-4">
          <h2 className="mb-3 text-lg font-medium text-va-text">
            New group structure
          </h2>
          <div className="space-y-3">
            <div>
              <label
                htmlFor="org-name"
                className="mb-1 block text-sm text-va-text2"
              >
                Group name
              </label>
              <VAInput
                id="org-name"
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Consolidated Group"
              />
            </div>
            <div>
              <label
                htmlFor="org-currency"
                className="mb-1 block text-sm text-va-text2"
              >
                Reporting currency
              </label>
              <VAInput
                id="org-currency"
                type="text"
                value={newCurrency}
                onChange={(e) => setNewCurrency(e.target.value.toUpperCase().slice(0, 3))}
                placeholder="USD"
                maxLength={3}
                className="uppercase"
                style={{ textTransform: "uppercase" }}
              />
            </div>
            <div className="flex gap-2">
              <VAButton
                type="button"
                variant="primary"
                onClick={handleCreate}
                disabled={creating || !newName.trim()}
              >
                {creating ? "Creating..." : "Create"}
              </VAButton>
              <VAButton
                type="button"
                variant="secondary"
                onClick={() => {
                  setShowCreate(false);
                  setNewName("");
                  setNewCurrency("USD");
                }}
              >
                Cancel
              </VAButton>
            </div>
          </div>
        </VACard>
      )}
      {loading ? (
        <VAListSkeleton count={4} />
      ) : items.length === 0 ? (
        <VAEmptyState
          icon="users"
          title="No groups yet"
          description="Create a group to organize your entities."
          actionLabel="Create group"
          onAction={() => setShowCreate(true)}
        />
      ) : (
        <>
          <VAListToolbar
            searchValue={search}
            onSearchChange={setSearch}
            searchPlaceholder="Search groups..."
          />
          {filteredItems.length === 0 ? (
            <VAEmptyState
              variant="no-results"
              title="No matching groups"
              description="Try adjusting your search term."
              onAction={() => setSearch("")}
              actionLabel="Clear search"
            />
          ) : (
            <ul className="space-y-2">
              {filteredItems.map((o) => (
                <li key={o.org_id}>
                  <Link
                    href={`/org-structures/${o.org_id}`}
                    className="block rounded-va-lg border border-va-border bg-va-panel/80 p-4 transition hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-va-text">
                        {o.group_name}
                      </span>
                      <span className="text-sm text-va-text2">
                        {o.status} · {o.entity_count} entities · {o.reporting_currency}
                      </span>
                    </div>
                    {o.created_at && (
                      <p className="mt-1 text-sm text-va-text2">
                        Created {formatDateTime(o.created_at)}
                      </p>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </main>
  );
}
