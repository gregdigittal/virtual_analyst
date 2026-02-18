"use client";

import { api, type TeamDetail, type TeamMember, type JobFunction } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VAConfirmDialog, VAInput, VASelect, useToast } from "@/components/ui";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

function HierarchyTree({
  members,
  jobFunctions,
  onRemove,
  onEdit,
}: {
  members: TeamMember[];
  jobFunctions: JobFunction[];
  onRemove: (userId: string) => void;
  onEdit: (m: TeamMember) => void;
}) {
  const byManager = new Map<string | null, TeamMember[]>();
  for (const m of members) {
    const key = m.reports_to ?? null;
    if (!byManager.has(key)) byManager.set(key, []);
    byManager.get(key)!.push(m);
  }
  const jfMap = new Map(jobFunctions.map((j) => [j.job_function_id, j.name]));

  function Node({ userId }: { userId: string | null }) {
    const children = userId === null ? byManager.get(null) ?? [] : byManager.get(userId) ?? [];
    return (
      <ul className="list-none pl-0">
        {children.map((m) => (
          <li key={m.user_id} className="mt-2">
            <div className="flex items-center gap-2 rounded-va-xs border border-va-border bg-va-panel/60 px-3 py-2">
              <span className="font-mono text-xs text-va-text2">
                {m.user_id.slice(0, 8)}…
              </span>
              <span className="text-sm text-va-text">
                {jfMap.get(m.job_function_id) ?? m.job_function_id}
              </span>
              <div className="ml-auto flex gap-1">
                <button
                  type="button"
                  onClick={() => onEdit(m)}
                  className="text-xs text-va-blue hover:underline"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => onRemove(m.user_id)}
                  className="text-xs text-va-danger hover:underline"
                >
                  Remove
                </button>
              </div>
            </div>
            {byManager.get(m.user_id)?.length ? (
              <div className="ml-4 border-l border-va-border pl-3">
                <Node userId={m.user_id} />
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    );
  }

  return <Node userId={null} />;
}

export default function TeamDetailPage() {
  const params = useParams();
  const teamId = params.teamId as string;
  const [team, setTeam] = useState<TeamDetail | null>(null);
  const [jobFunctions, setJobFunctions] = useState<JobFunction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editing, setEditing] = useState(false);
  const [showAddMember, setShowAddMember] = useState(false);
  const [addUserId, setAddUserId] = useState("");
  const [addJobFunctionId, setAddJobFunctionId] = useState("");
  const [addReportsTo, setAddReportsTo] = useState("");
  const [adding, setAdding] = useState(false);
  const [editMember, setEditMember] = useState<TeamMember | null>(null);
  const [editMemberJf, setEditMemberJf] = useState("");
  const [editMemberReportsTo, setEditMemberReportsTo] = useState("");
  const [savingMember, setSavingMember] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  const { toast } = useToast();
  const [confirmAction, setConfirmAction] = useState<{ action: () => void; title: string; description: string } | null>(null);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setError(null);
    try {
      const [teamRes, jfRes] = await Promise.all([
        api.teams.get(tenantId, teamId),
        api.teams.listJobFunctions(tenantId),
      ]);
      setTeam(teamRes);
      setEditName(teamRes.name);
      setEditDescription(teamRes.description ?? "");
      setJobFunctions(jfRes.job_functions);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, teamId]);

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
    if (tenantId) load();
  }, [tenantId, load]);

  useEffect(() => {
    if (jobFunctions.length && !addJobFunctionId) {
      setAddJobFunctionId(jobFunctions[0].job_function_id);
    }
  }, [jobFunctions, addJobFunctionId]);

  async function handleUpdateTeam(e: React.FormEvent) {
    e.preventDefault();
    if (!tenantId || !team) return;
    setEditing(true);
    setError(null);
    try {
      const updated = await api.teams.update(tenantId, teamId, {
        name: editName.trim(),
        description: editDescription.trim() || null,
      });
      setTeam(updated);
      toast.success("Team updated");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setEditing(false);
    }
  }

  async function handleAddMember(e: React.FormEvent) {
    e.preventDefault();
    if (!tenantId || !addUserId.trim() || !addJobFunctionId) return;
    setAdding(true);
    setError(null);
    try {
      await api.teams.addMember(tenantId, teamId, {
        user_id: addUserId.trim(),
        job_function_id: addJobFunctionId,
        reports_to: addReportsTo.trim() || null,
      });
      await load();
      setShowAddMember(false);
      setAddUserId("");
      setAddReportsTo("");
      toast.success("Member added");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setAdding(false);
    }
  }

  async function handleUpdateMember(e: React.FormEvent) {
    e.preventDefault();
    if (!tenantId || !editMember) return;
    setSavingMember(true);
    setError(null);
    try {
      await api.teams.updateMember(tenantId, teamId, editMember.user_id, {
        job_function_id: editMemberJf,
        reports_to: editMemberReportsTo.trim() || null,
      });
      await load();
      setEditMember(null);
      toast.success("Member updated");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    } finally {
      setSavingMember(false);
    }
  }

  async function handleRemoveMember(memberUserId: string) {
    if (!tenantId) return;
    setError(null);
    try {
      await api.teams.removeMember(tenantId, teamId, memberUserId);
      await load();
      toast.success("Member removed");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  if (!tenantId && !loading) return null;
  if (loading && !team) {
    return <p className="text-va-text2">Loading team…</p>;
  }
  if (!team) {
    return (
      <div>
        <p className="text-va-danger">Team not found.</p>
        <Link href="/settings/teams" className="mt-2 inline-block text-va-blue hover:underline">
          Back to teams
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4">
        <Link
          href="/settings/teams"
          className="text-sm text-va-blue hover:underline"
        >
          ← Back to teams
        </Link>
      </div>

      {error && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}

      <VACard className="mb-6 p-6">
        <h2 className="mb-4 text-lg font-medium text-va-text">Team details</h2>
        <form onSubmit={handleUpdateTeam} className="space-y-4">
          <div>
            <label htmlFor="team-name" className="mb-1 block text-sm font-medium text-va-text2">
              Name
            </label>
            <VAInput
              id="team-name"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              maxLength={255}
              className="w-full"
            />
          </div>
          <div>
            <label htmlFor="team-desc" className="mb-1 block text-sm font-medium text-va-text2">
              Description
            </label>
            <textarea
              id="team-desc"
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              maxLength={2000}
              rows={2}
              className="w-full rounded-va-xs border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text placeholder:text-va-text2/70 focus:border-va-blue focus:outline-none focus:ring-1 focus:ring-va-blue"
            />
          </div>
          <VAButton type="submit" disabled={editing}>
            {editing ? "Saving…" : "Save changes"}
          </VAButton>
        </form>
      </VACard>

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-medium text-va-text">Members & hierarchy</h2>
        <VAButton onClick={() => setShowAddMember(true)} disabled={loading}>
          Add member
        </VAButton>
      </div>

      {showAddMember && (
        <VACard className="mb-6 p-6">
          <h3 className="mb-4 text-md font-medium text-va-text">Add member</h3>
          <form onSubmit={handleAddMember} className="space-y-4">
            <div>
              <label htmlFor="add-user-id" className="mb-1 block text-sm font-medium text-va-text2">
                User ID (e.g. Supabase auth user UUID)
              </label>
              <VAInput
                id="add-user-id"
                value={addUserId}
                onChange={(e) => setAddUserId(e.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                required
                className="w-full font-mono text-sm"
              />
            </div>
            <div>
              <label htmlFor="add-jf" className="mb-1 block text-sm font-medium text-va-text2">
                Job function
              </label>
              <VASelect
                id="add-jf"
                value={addJobFunctionId}
                onChange={(e) => setAddJobFunctionId(e.target.value)}
              >
                {jobFunctions.map((j) => (
                  <option key={j.job_function_id} value={j.job_function_id}>
                    {j.name}
                  </option>
                ))}
              </VASelect>
            </div>
            <div>
              <label htmlFor="add-reports-to" className="mb-1 block text-sm font-medium text-va-text2">
                Reports to (user ID, optional)
              </label>
              <VASelect
                id="add-reports-to"
                value={addReportsTo}
                onChange={(e) => setAddReportsTo(e.target.value)}
              >
                <option value="">— None —</option>
                {team.members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.user_id.slice(0, 8)}… — {jobFunctions.find((j) => j.job_function_id === m.job_function_id)?.name ?? m.job_function_id}
                  </option>
                ))}
              </VASelect>
            </div>
            <div className="flex gap-2">
              <VAButton type="submit" disabled={adding}>
                {adding ? "Adding…" : "Add"}
              </VAButton>
              <VAButton
                type="button"
                variant="secondary"
                onClick={() => {
                  setShowAddMember(false);
                  setAddUserId("");
                  setAddReportsTo("");
                  setError(null);
                }}
                disabled={adding}
              >
                Cancel
              </VAButton>
            </div>
          </form>
        </VACard>
      )}

      {editMember && (
        <VACard className="mb-6 p-6">
          <h3 className="mb-4 text-md font-medium text-va-text">Edit member</h3>
          <form onSubmit={handleUpdateMember} className="space-y-4">
            <p className="text-sm text-va-text2 font-mono">{editMember.user_id}</p>
            <div>
              <label className="mb-1 block text-sm font-medium text-va-text2">Job function</label>
              <VASelect
                value={editMemberJf}
                onChange={(e) => setEditMemberJf(e.target.value)}
              >
                {jobFunctions.map((j) => (
                  <option key={j.job_function_id} value={j.job_function_id}>
                    {j.name}
                  </option>
                ))}
              </VASelect>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-va-text2">Reports to</label>
              <VASelect
                value={editMemberReportsTo}
                onChange={(e) => setEditMemberReportsTo(e.target.value)}
              >
                <option value="">— None —</option>
                {team.members
                  .filter((m) => m.user_id !== editMember.user_id)
                  .map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.user_id.slice(0, 8)}… — {jobFunctions.find((j) => j.job_function_id === m.job_function_id)?.name ?? m.job_function_id}
                    </option>
                  ))}
              </VASelect>
            </div>
            <div className="flex gap-2">
              <VAButton type="submit" disabled={savingMember}>
                {savingMember ? "Saving…" : "Save"}
              </VAButton>
              <VAButton
                type="button"
                variant="secondary"
                onClick={() => setEditMember(null)}
                disabled={savingMember}
              >
                Cancel
              </VAButton>
            </div>
          </form>
        </VACard>
      )}

      {team.members.length === 0 ? (
        <VACard className="p-6 text-center text-va-text2">
          No members yet. Add a member to build your hierarchy.
        </VACard>
      ) : (
        <VACard className="p-6">
          <HierarchyTree
            members={team.members}
            jobFunctions={jobFunctions}
            onRemove={(uid) => setConfirmAction({
              action: () => handleRemoveMember(uid),
              title: "Remove this member?",
              description: "They will be removed from the team.",
            })}
            onEdit={(m) => {
              setEditMember(m);
              setEditMemberJf(m.job_function_id);
              setEditMemberReportsTo(m.reports_to ?? "");
            }}
          />
        </VACard>
      )}
      <VAConfirmDialog
        open={!!confirmAction}
        title={confirmAction?.title ?? ""}
        description={confirmAction?.description}
        confirmLabel="Remove"
        onConfirm={() => { confirmAction?.action(); setConfirmAction(null); }}
        onCancel={() => setConfirmAction(null)}
      />
    </div>
  );
}
