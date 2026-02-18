"use client";

import { api, type TeamSummary } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VACard, VAButton, VAInput, useToast } from "@/components/ui";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function TeamsPage() {
  const [teams, setTeams] = useState<TeamSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (cancelled) return;
      if (!ctx) {
        api.setAccessToken(null);
        return;
      }
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
      api.setAccessToken(ctx.accessToken);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!tenantId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api.teams.list(tenantId);
        if (!cancelled) setTeams(res.teams);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenantId]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!tenantId || !userId || !createName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await api.teams.create(tenantId, userId, {
        name: createName.trim(),
        description: createDescription.trim() || null,
      });
      const res = await api.teams.list(tenantId);
      setTeams(res.teams);
      toast.success("Team created");
      setShowCreate(false);
      setCreateName("");
      setCreateDescription("");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setCreating(false);
    }
  }

  if (!tenantId && !loading) return null;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Teams
        </h1>
        <VAButton
          onClick={() => setShowCreate(true)}
          disabled={loading}
          aria-label="Create team"
        >
          Create team
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
        <VACard className="mb-6 p-6">
          <h2 className="mb-4 text-lg font-medium text-va-text">
            New team
          </h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label
                htmlFor="team-name"
                className="mb-1 block text-sm font-medium text-va-text2"
              >
                Name
              </label>
              <VAInput
                id="team-name"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="e.g. Finance"
                required
                maxLength={255}
                className="w-full"
              />
            </div>
            <div>
              <label
                htmlFor="team-desc"
                className="mb-1 block text-sm font-medium text-va-text2"
              >
                Description (optional)
              </label>
              <textarea
                id="team-desc"
                value={createDescription}
                onChange={(e) => setCreateDescription(e.target.value)}
                placeholder="Brief description"
                maxLength={2000}
                rows={2}
                className="w-full rounded-va-xs border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text placeholder:text-va-text2/70 focus:border-va-blue focus:outline-none focus:ring-1 focus:ring-va-blue"
              />
            </div>
            <div className="flex gap-2">
              <VAButton type="submit" disabled={creating}>
                {creating ? "Creating…" : "Create"}
              </VAButton>
              <VAButton
                type="button"
                variant="secondary"
                onClick={() => {
                  setShowCreate(false);
                  setCreateName("");
                  setCreateDescription("");
                  setError(null);
                }}
                disabled={creating}
              >
                Cancel
              </VAButton>
            </div>
          </form>
        </VACard>
      )}

      {loading ? (
        <p className="text-va-text2">Loading teams…</p>
      ) : teams.length === 0 && !showCreate ? (
        <VACard className="p-6 text-center text-va-text2">
          No teams yet. Create one to get started.
        </VACard>
      ) : (
        <ul className="space-y-2">
          {teams.map((t) => (
            <li key={t.team_id}>
              <Link
                href={`/settings/teams/${t.team_id}`}
                className="block rounded-va-lg border border-va-border bg-va-panel/80 p-4 transition hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-va-text">{t.name}</span>
                </div>
                {t.description && (
                  <p className="mt-1 text-sm text-va-text2">{t.description}</p>
                )}
                {t.created_at && (
                  <p className="mt-1 text-xs text-va-text2/80">
                    Created {new Date(t.created_at).toLocaleString()}
                  </p>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
