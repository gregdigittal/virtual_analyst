"use client";

import { api, type AssignmentItem } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VACard, VAButton, VASpinner } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function AssignmentDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [assignment, setAssignment] = useState<AssignmentItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [settingInProgress, setSettingInProgress] = useState(false);

  const load = useCallback(async () => {
    if (!tenantId || !id) return;
    setError(null);
    try {
      const a = await api.assignments.get(tenantId, id);
      setAssignment(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setAssignment(null);
    } finally {
      setLoading(false);
    }
  }, [tenantId, id]);

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

  async function handleSubmit() {
    if (!tenantId || !userId) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.assignments.submit(tenantId, userId, id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSetInProgress() {
    if (!tenantId) return;
    setSettingInProgress(true);
    setError(null);
    try {
      await api.assignments.update(tenantId, id, { status: "in_progress" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSettingInProgress(false);
    }
  }

  if (!tenantId && !loading) return null;
  if (loading && !assignment) {
    return <VASpinner label="Loading assignment…" />;
  }
  if (!assignment) {
    return (
      <div>
        <p className="text-va-danger">Assignment not found.</p>
        <Link href="/inbox" className="mt-2 inline-block text-va-blue hover:underline">
          Back to inbox
        </Link>
      </div>
    );
  }

  const isAssignee = assignment.assignee_user_id === userId;
  const canSubmit =
    isAssignee && (assignment.status === "assigned" || assignment.status === "in_progress");
  const canSetInProgress = isAssignee && assignment.status === "assigned";
  const canReview =
    !isAssignee && assignment.status === "submitted";
  const workspaceLink =
    assignment.entity_type === "draft"
      ? `/drafts/${assignment.entity_id}`
      : assignment.entity_type === "baseline"
        ? `/baselines/${assignment.entity_id}`
        : assignment.entity_type === "run"
          ? `/runs/${assignment.entity_id}`
          : null;

  return (
    <div>
      <div className="mb-4">
        <Link href="/inbox" className="text-sm text-va-blue hover:underline">
          ← Back to inbox
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
        <h2 className="text-lg font-medium text-va-text">
          {assignment.entity_type} — {assignment.entity_id}
        </h2>
        <dl className="mt-4 grid gap-2 text-sm">
          <div>
            <dt className="text-va-text2">Status</dt>
            <dd className="capitalize text-va-text">{assignment.status.replace("_", " ")}</dd>
          </div>
          {assignment.deadline && (
            <div>
              <dt className="text-va-text2">Deadline</dt>
              <dd className="text-va-text">
                {formatDateTime(assignment.deadline)}
              </dd>
            </div>
          )}
          {assignment.assignee_user_id && (
            <div>
              <dt className="text-va-text2">Assignee</dt>
              <dd className="font-mono text-va-text text-xs">{assignment.assignee_user_id}</dd>
            </div>
          )}
        </dl>
        {assignment.instructions && (
          <div className="mt-4">
            <h3 className="text-sm font-medium text-va-text2">Instructions</h3>
            <p className="mt-1 whitespace-pre-wrap text-va-text">{assignment.instructions}</p>
          </div>
        )}
        <div className="mt-6 flex flex-wrap gap-2">
          {workspaceLink && (
            <Link href={workspaceLink}>
              <VAButton variant="secondary">Open workspace</VAButton>
            </Link>
          )}
          {canSetInProgress && (
            <VAButton
              variant="secondary"
              onClick={handleSetInProgress}
              disabled={settingInProgress}
            >
              {settingInProgress ? "Updating…" : "Start working"}
            </VAButton>
          )}
          {canSubmit && (
            <VAButton onClick={handleSubmit} disabled={submitting}>
              {submitting ? "Submitting…" : "Submit for review"}
            </VAButton>
          )}
          {canReview && (
            <Link href={`/inbox/${id}/review`}>
              <VAButton variant="secondary">Review</VAButton>
            </Link>
          )}
        </div>
      </VACard>
    </div>
  );
}
