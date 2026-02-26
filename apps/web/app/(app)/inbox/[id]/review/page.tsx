"use client";

import { api, type AssignmentItem } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VACard, VAButton, VAInput, VASpinner } from "@/components/ui";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

interface CorrectionRow {
  path: string;
  old_value: string;
  new_value: string;
  reason: string;
}

export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [assignment, setAssignment] = useState<AssignmentItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [decision, setDecision] = useState<"approved" | "request_changes" | "rejected">("approved");
  const [notes, setNotes] = useState("");
  const [corrections, setCorrections] = useState<CorrectionRow[]>([
    { path: "", old_value: "", new_value: "", reason: "" },
  ]);
  const [submitting, setSubmitting] = useState(false);

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

  function addCorrection() {
    setCorrections((prev) => [...prev, { path: "", old_value: "", new_value: "", reason: "" }]);
  }

  function updateCorrection(i: number, field: keyof CorrectionRow, value: string) {
    setCorrections((prev) => {
      const next = [...prev];
      next[i] = { ...next[i], [field]: value };
      return next;
    });
  }

  function removeCorrection(i: number) {
    setCorrections((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!tenantId || !userId) return;
    setSubmitting(true);
    setError(null);
    try {
      const correctionPayload = corrections
        .filter((c) => c.path.trim())
        .map((c) => ({
          path: c.path.trim(),
          old_value: c.old_value.trim() || null,
          new_value: c.new_value.trim() || null,
          reason: c.reason.trim() || null,
        }));
      await api.assignments.submitReview(tenantId, userId, id, {
        decision,
        notes: notes.trim() || null,
        corrections: correctionPayload,
      });
      router.push(`/inbox/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  if (!tenantId && !loading) return null;
  if (loading && !assignment) {
    return <VASpinner label="Loading…" />;
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
  if (assignment.status !== "submitted") {
    return (
      <div>
        <p className="text-va-text2">This assignment is not awaiting review.</p>
        <Link href={`/inbox/${id}`} className="mt-2 inline-block text-va-blue hover:underline">
          Back to assignment
        </Link>
      </div>
    );
  }
  if (assignment.assignee_user_id === userId) {
    return (
      <div>
        <p className="text-va-text2">You cannot review your own submission.</p>
        <Link href={`/inbox/${id}`} className="mt-2 inline-block text-va-blue hover:underline">
          Back to assignment
        </Link>
      </div>
    );
  }

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
        <Link href={`/inbox/${id}`} className="text-sm text-va-blue hover:underline">
          ← Back to assignment
        </Link>
      </div>

      <h1 className="mb-6 font-brand text-2xl font-semibold tracking-tight text-va-text">
        Review: {assignment.entity_type} — {assignment.entity_id}
      </h1>

      {error && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <VACard className="p-6">
          <h2 className="text-sm font-medium text-va-text2">Context</h2>
          {assignment.instructions && (
            <p className="mt-2 whitespace-pre-wrap text-sm text-va-text">
              {assignment.instructions}
            </p>
          )}
          {workspaceLink && (
            <Link href={workspaceLink} className="mt-4 inline-block text-sm text-va-blue hover:underline">
              Open workspace →
            </Link>
          )}
        </VACard>

        <VACard className="p-6">
          <h2 className="text-sm font-medium text-va-text2">Review decision</h2>
          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-va-text2">Decision</label>
              <select
                value={decision}
                onChange={(e) => setDecision(e.target.value as "approved" | "request_changes" | "rejected")}
                className="w-full rounded-va-xs border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text focus:border-va-blue focus:outline-none focus:ring-1 focus:ring-va-blue"
              >
                <option value="approved">Approve</option>
                <option value="request_changes">Request changes</option>
                <option value="rejected">Reject</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-va-text2">Notes</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                className="w-full rounded-va-xs border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text placeholder:text-va-text2/70 focus:border-va-blue focus:outline-none focus:ring-1 focus:ring-va-blue"
                placeholder="Feedback for the assignee"
              />
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-va-text2">Corrections (optional)</label>
                <button
                  type="button"
                  onClick={addCorrection}
                  className="text-xs text-va-blue hover:underline"
                >
                  + Add
                </button>
              </div>
              <div className="space-y-3">
                {corrections.map((c, i) => (
                  <div
                    key={i}
                    className="rounded-va-xs border border-va-border bg-va-panel/60 p-3 space-y-2"
                  >
                    <VAInput
                      placeholder="Path (e.g. assumptions.revenue_growth)"
                      value={c.path}
                      onChange={(e) => updateCorrection(i, "path", e.target.value)}
                      className="text-sm"
                    />
                    <div className="grid grid-cols-2 gap-2">
                      <VAInput
                        placeholder="Old value"
                        value={c.old_value}
                        onChange={(e) => updateCorrection(i, "old_value", e.target.value)}
                        className="text-sm"
                      />
                      <VAInput
                        placeholder="New value"
                        value={c.new_value}
                        onChange={(e) => updateCorrection(i, "new_value", e.target.value)}
                        className="text-sm"
                      />
                    </div>
                    <VAInput
                      placeholder="Reason"
                      value={c.reason}
                      onChange={(e) => updateCorrection(i, "reason", e.target.value)}
                      className="text-sm"
                    />
                    {corrections.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeCorrection(i)}
                        className="text-xs text-va-danger hover:underline"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <VAButton type="submit" disabled={submitting}>
                {submitting ? "Submitting…" : "Submit review"}
              </VAButton>
              <Link href={`/inbox/${id}`}>
                <VAButton type="button" variant="secondary" disabled={submitting}>
                  Cancel
                </VAButton>
              </Link>
            </div>
          </form>
        </VACard>
      </div>
    </div>
  );
}
