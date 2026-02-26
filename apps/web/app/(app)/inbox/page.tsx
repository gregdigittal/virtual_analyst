"use client";

import { api, type AssignmentItem } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VACard, VAButton, VAEmptyState, VAListToolbar, VASpinner } from "@/components/ui";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type Tab = "my_tasks" | "team_pool" | "all";

function AssignmentCard({
  a,
  tenantId,
  userId,
  onClaim,
  onSubmit,
  isPool,
}: {
  a: AssignmentItem;
  tenantId: string;
  userId: string;
  onClaim?: () => void;
  onSubmit?: () => void;
  isPool?: boolean;
}) {
  const deadlineStr = a.deadline
    ? new Date(a.deadline).toLocaleString(undefined, {
        dateStyle: "short",
        timeStyle: "short",
      })
    : null;
  const isOverdue = a.deadline && new Date(a.deadline) < new Date();
  const canSubmit =
    a.assignee_user_id === userId &&
    (a.status === "assigned" || a.status === "in_progress");

  return (
    <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <Link
            href={`/inbox/${a.assignment_id}`}
            className="font-medium text-va-text hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue rounded"
          >
            {a.entity_type} — {a.entity_id}
          </Link>
          <p className="mt-1 text-sm text-va-text2">
            Status: <span className="capitalize">{a.status.replace("_", " ")}</span>
            {deadlineStr && (
              <span className={isOverdue ? " text-va-danger" : ""}>
                {" "}
                · Due {deadlineStr}
              </span>
            )}
          </p>
          {a.instructions && (
            <p className="mt-1 line-clamp-2 text-sm text-va-text2/90">
              {a.instructions}
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          {isPool && onClaim && (
            <VAButton onClick={onClaim} aria-label="Claim assignment">
              Claim
            </VAButton>
          )}
          {canSubmit && onSubmit && (
            <VAButton onClick={onSubmit} aria-label="Submit for review">
              Submit
            </VAButton>
          )}
          <Link href={`/inbox/${a.assignment_id}`}>
            <VAButton variant="secondary" aria-label="View detail">
              View
            </VAButton>
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function InboxPage() {
  const [tab, setTab] = useState<Tab>("my_tasks");
  const [assignments, setAssignments] = useState<AssignmentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      if (tab === "my_tasks" && userId) {
        const res = await api.assignments.list(
          tenantId,
          { assignee_user_id: "me" },
          userId
        );
        setAssignments(res.assignments);
      } else if (tab === "team_pool") {
        const res = await api.assignments.listPool(tenantId);
        setAssignments(res.assignments);
      } else {
        const res = await api.assignments.list(tenantId);
        setAssignments(res.assignments);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setAssignments([]);
    } finally {
      setLoading(false);
    }
  }, [tenantId, userId, tab]);

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
    load();
  }, [load]);

  async function handleClaim(assignmentId: string) {
    if (!tenantId || !userId) return;
    setError(null);
    try {
      await api.assignments.claim(tenantId, userId, assignmentId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleSubmit(assignmentId: string) {
    if (!tenantId || !userId) return;
    setError(null);
    try {
      await api.assignments.submit(tenantId, userId, assignmentId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const filteredAssignments = assignments.filter((a) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      a.entity_id.toLowerCase().includes(q) ||
      a.entity_type.toLowerCase().includes(q) ||
      a.assignment_id.toLowerCase().includes(q) ||
      a.status.toLowerCase().includes(q) ||
      (a.instructions ?? "").toLowerCase().includes(q)
    );
  });

  if (!tenantId && !loading) return null;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Task Inbox
        </h1>
        <Link href="/assignments/new">
          <VAButton>New assignment</VAButton>
        </Link>
      </div>

      <div className="mb-4 flex gap-2 border-b border-va-border">
        {(
          [
            ["my_tasks", "My Tasks"],
            ["team_pool", "Team Pool"],
            ["all", "All"],
          ] as const
        ).map(([t, label]) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`border-b-2 px-3 py-2 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue rounded-t ${
              tab === t
                ? "border-va-blue text-va-text"
                : "border-transparent text-va-text2 hover:text-va-text"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {assignments.length > 0 && (
        <VAListToolbar
          searchValue={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search assignments..."
        />
      )}

      {error && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}

      {loading ? (
        <VASpinner label="Loading…" />
      ) : assignments.length === 0 ? (
        <VAEmptyState
          icon="inbox"
          title="Inbox is empty"
          description={
            tab === "my_tasks"
              ? "No tasks assigned to you. Items requiring your attention will appear here."
              : tab === "team_pool"
                ? "No pool tasks to claim. Items requiring your attention will appear here."
                : "Items requiring your attention will appear here."
          }
        />
      ) : filteredAssignments.length === 0 ? (
        <VAEmptyState
          variant="no-results"
          title="No matching assignments"
          description="Try a different search term."
        />
      ) : (
        <ul className="space-y-3">
          {filteredAssignments.map((a) => (
            <li key={a.assignment_id}>
              <AssignmentCard
                a={a}
                tenantId={tenantId!}
                userId={userId!}
                onClaim={
                  tab === "team_pool"
                    ? () => handleClaim(a.assignment_id)
                    : undefined
                }
                onSubmit={() => handleSubmit(a.assignment_id)}
                isPool={tab === "team_pool"}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
