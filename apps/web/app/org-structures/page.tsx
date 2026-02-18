"use client";

import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
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
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCurrency, setNewCurrency] = useState("USD");

  useEffect(() => {
    let cancelled = false;
    (async () => {
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
  }, []);

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

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
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
          <div
            className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
            role="alert"
          >
            {error}
          </div>
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
                <input
                  id="org-name"
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Consolidated Group"
                  className="w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-va-text focus:border-va-blue focus:outline-none focus:ring-1 focus:ring-va-blue"
                />
              </div>
              <div>
                <label
                  htmlFor="org-currency"
                  className="mb-1 block text-sm text-va-text2"
                >
                  Reporting currency
                </label>
                <input
                  id="org-currency"
                  type="text"
                  value={newCurrency}
                  onChange={(e) => setNewCurrency(e.target.value.toUpperCase().slice(0, 3))}
                  placeholder="USD"
                  maxLength={3}
                  className="w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-va-text focus:border-va-blue focus:outline-none focus:ring-1 focus:ring-va-blue uppercase"
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
                  {creating ? "Creating…" : "Create"}
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
          <p className="text-va-text2">Loading…</p>
        ) : items.length === 0 ? (
          <VACard className="p-6 text-center text-va-text2">
            No group structures yet. Click &quot;Create New&quot; to add one.
          </VACard>
        ) : (
          <ul className="space-y-2">
            {items.map((o) => (
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
                      Created {new Date(o.created_at).toLocaleString()}
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
