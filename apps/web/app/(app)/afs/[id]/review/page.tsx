"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  api,
  type AFSReview,
  type AFSReviewComment,
  type AFSEngagement,
  type AFSSection,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import {
  VAButton,
  VACard,
  VABadge,
  VASpinner,
  VAEmptyState,
  useToast,
} from "@/components/ui";

const STAGES = [
  { key: "preparer_review", label: "Preparer Review" },
  { key: "manager_review", label: "Manager Review" },
  { key: "partner_signoff", label: "Partner Sign-off" },
] as const;

type StageKey = (typeof STAGES)[number]["key"];

function stageBadgeVariant(review: AFSReview | undefined) {
  if (!review) return "default" as const;
  if (review.status === "approved") return "success" as const;
  if (review.status === "rejected") return "danger" as const;
  if (review.status === "pending") return "warning" as const;
  return "default" as const;
}

function stageBadgeLabel(review: AFSReview | undefined) {
  if (!review) return "Not submitted";
  return review.status.charAt(0).toUpperCase() + review.status.slice(1);
}

function formatTimestamp(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-ZA", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ReviewWorkflowPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const engagementId = params.id as string;

  const [tenantId, setTenantId] = useState<string | null>(null);
  const [engagement, setEngagement] = useState<AFSEngagement | null>(null);
  const [sections, setSections] = useState<AFSSection[]>([]);
  const [reviews, setReviews] = useState<AFSReview[]>([]);
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null);
  const [comments, setComments] = useState<AFSReviewComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [rejectText, setRejectText] = useState("");
  const [rejectingId, setRejectingId] = useState<string | null>(null);

  /* ------------------------------------------------------------------ */
  /*  Data helpers                                                       */
  /* ------------------------------------------------------------------ */

  const reviewByStage = useCallback(
    (stage: StageKey): AFSReview | undefined =>
      reviews.find((r) => r.stage === stage),
    [reviews],
  );

  const approvedStages: StageKey[] = reviews
    .filter((r) => r.status === "approved")
    .map((r) => r.stage as StageKey);

  const allApproved =
    STAGES.every((s) => approvedStages.includes(s.key));

  function getNextStage(): StageKey | null {
    for (const s of STAGES) {
      if (!approvedStages.includes(s.key)) return s.key;
    }
    return null;
  }

  const hasDraftSections = sections.some(
    (s) => s.status === "draft" || s.status === "unlocked",
  );

  const pendingReview = reviews.find((r) => r.status === "pending");

  /* ------------------------------------------------------------------ */
  /*  Initial data load                                                  */
  /* ------------------------------------------------------------------ */

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) {
        router.replace("/login");
        return;
      }
      api.setAccessToken(ctx.accessToken);
      if (!cancelled) setTenantId(ctx.tenantId);
      try {
        const [eng, secs, revs] = await Promise.all([
          api.afs.getEngagement(ctx.tenantId, engagementId),
          api.afs.listSections(ctx.tenantId, engagementId),
          api.afs.listReviews(ctx.tenantId, engagementId),
        ]);
        if (!cancelled) {
          setEngagement(eng);
          setSections(secs.items ?? []);
          setReviews(revs.items ?? []);
        }
      } catch {
        if (!cancelled) toast.error("Failed to load review data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [engagementId, router, toast]);

  /* ------------------------------------------------------------------ */
  /*  Load comments when a review is selected                            */
  /* ------------------------------------------------------------------ */

  useEffect(() => {
    if (!tenantId || !selectedReviewId) {
      setComments([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await api.afs.listReviewComments(
          tenantId,
          engagementId,
          selectedReviewId,
        );
        if (!cancelled) {
          setComments(
            (res.items ?? []).sort(
              (a, b) =>
                new Date(a.created_at).getTime() -
                new Date(b.created_at).getTime(),
            ),
          );
        }
      } catch {
        if (!cancelled) toast.error("Failed to load comments");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenantId, engagementId, selectedReviewId, toast]);

  /* ------------------------------------------------------------------ */
  /*  Handlers                                                           */
  /* ------------------------------------------------------------------ */

  async function handleSubmitReview() {
    const nextStage = getNextStage();
    if (!tenantId || !nextStage) return;
    setSubmitting(true);
    try {
      const review = await api.afs.submitReview(tenantId, engagementId, {
        stage: nextStage,
      });
      setReviews((prev) => [...prev, review]);
      toast.success("Review submitted successfully");
    } catch {
      toast.error("Failed to submit review");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleApprove(reviewId: string) {
    if (!tenantId) return;
    setSubmitting(true);
    try {
      const updated = await api.afs.approveReview(
        tenantId,
        engagementId,
        reviewId,
      );
      setReviews((prev) =>
        prev.map((r) => (r.review_id === updated.review_id ? updated : r)),
      );
      toast.success("Review approved");
    } catch {
      toast.error("Failed to approve review");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReject(reviewId: string) {
    if (!tenantId || !rejectText.trim()) return;
    setSubmitting(true);
    try {
      const updated = await api.afs.rejectReview(
        tenantId,
        engagementId,
        reviewId,
        { comments: rejectText },
      );
      setReviews((prev) =>
        prev.map((r) => (r.review_id === updated.review_id ? updated : r)),
      );
      setRejectText("");
      setRejectingId(null);
      toast.success("Review rejected");
    } catch {
      toast.error("Failed to reject review");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAddComment() {
    if (!tenantId || !selectedReviewId || !commentText.trim()) return;
    setSubmitting(true);
    try {
      const comment = await api.afs.createReviewComment(
        tenantId,
        engagementId,
        { review_id: selectedReviewId, body: commentText },
      );
      setComments((prev) => [...prev, comment]);
      setCommentText("");
      toast.success("Comment added");
    } catch {
      toast.error("Failed to add comment");
    } finally {
      setSubmitting(false);
    }
  }

  /* ------------------------------------------------------------------ */
  /*  Loading state                                                      */
  /* ------------------------------------------------------------------ */

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <VASpinner />
      </div>
    );
  }

  /* ------------------------------------------------------------------ */
  /*  Render                                                             */
  /* ------------------------------------------------------------------ */

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-va-border px-6 py-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push(`/afs/${engagementId}/sections`)}
            className="text-va-text2 hover:text-va-text"
          >
            &larr;
          </button>
          <h1 className="text-lg font-semibold text-va-text">
            {engagement?.entity_name} — Review Workflow
          </h1>
        </div>
        <div className="flex gap-2">
          <VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/sections`)}>
            Sections
          </VAButton>
          <VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/tax`)}>
            Tax
          </VAButton>
          <VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/consolidation`)}>
            Consolidation
          </VAButton>
          <VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/output`)}>
            Output
          </VAButton>
          <VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/analytics`)}>
            Analytics
          </VAButton>
          <VAButton
            variant="primary"
            onClick={handleSubmitReview}
            disabled={
              submitting ||
              hasDraftSections ||
              allApproved ||
              pendingReview != null ||
              getNextStage() === null
            }
          >
            {submitting ? "Submitting..." : "Submit for Review"}
          </VAButton>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Review stages timeline */}
        <div className="w-96 flex-shrink-0 overflow-y-auto border-r border-va-border bg-va-surface p-6">
          {allApproved ? (
            <div className="flex flex-col items-center justify-center gap-4 py-12 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/20">
                <svg
                  className="h-8 w-8 text-emerald-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-emerald-400">
                Engagement Approved
              </h2>
              <p className="text-sm text-va-text2">
                All review stages have been completed and approved.
              </p>
            </div>
          ) : reviews.length === 0 ? (
            <VAEmptyState
              icon="file-text"
              title="No reviews yet"
              description="Submit your first review once all sections are locked."
            />
          ) : null}

          <div className="space-y-4">
            {STAGES.map((stage, idx) => {
              const review = reviewByStage(stage.key);
              const isSelected =
                review != null && review.review_id === selectedReviewId;
              const isPending = review?.status === "pending";
              const isRejected = review?.status === "rejected";

              return (
                <div key={stage.key} className="relative">
                  {/* Timeline connector */}
                  {idx < STAGES.length - 1 && (
                    <div className="absolute left-5 top-14 h-[calc(100%)] w-px bg-va-border" />
                  )}

                  <VACard
                    className={`relative cursor-pointer p-4 transition-colors ${
                      isSelected
                        ? "border-va-blue bg-va-blue/10"
                        : "hover:border-va-text2"
                    }`}
                    onClick={() =>
                      review
                        ? setSelectedReviewId(review.review_id)
                        : undefined
                    }
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div
                          className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold ${
                            review?.status === "approved"
                              ? "bg-emerald-500/20 text-emerald-400"
                              : isPending
                                ? "bg-amber-500/20 text-amber-400"
                                : isRejected
                                  ? "bg-red-500/20 text-red-400"
                                  : "bg-va-panel text-va-muted"
                          }`}
                        >
                          {idx + 1}
                        </div>
                        <span className="text-sm font-medium text-va-text">
                          {stage.label}
                        </span>
                      </div>
                      <VABadge variant={stageBadgeVariant(review)}>
                        {stageBadgeLabel(review)}
                      </VABadge>
                    </div>

                    {review && (
                      <div className="ml-13 mt-3 space-y-1 pl-[52px] text-xs text-va-text2">
                        {review.submitted_by && (
                          <p>
                            Submitted by{" "}
                            <span className="text-va-text">
                              {review.submitted_by}
                            </span>{" "}
                            on {formatTimestamp(review.submitted_at)}
                          </p>
                        )}
                        {review.reviewed_by && (
                          <p>
                            Reviewed by{" "}
                            <span className="text-va-text">
                              {review.reviewed_by}
                            </span>{" "}
                            on {formatTimestamp(review.reviewed_at)}
                          </p>
                        )}
                      </div>
                    )}

                    {/* Rejection comments */}
                    {isRejected && review?.comments && (
                      <div className="ml-[52px] mt-2 rounded-va-sm border border-red-500/30 bg-red-500/10 p-2">
                        <p className="text-xs font-medium text-red-400">
                          Rejection reason:
                        </p>
                        <p className="mt-1 text-xs text-red-300/80">
                          {review.comments}
                        </p>
                      </div>
                    )}

                    {/* Action buttons for the pending review */}
                    {isPending && review && (
                      <div className="ml-[52px] mt-3 space-y-2">
                        <div className="flex gap-2">
                          <VAButton
                            variant="primary"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleApprove(review.review_id);
                            }}
                            disabled={submitting}
                          >
                            Approve
                          </VAButton>
                          <VAButton
                            variant="secondary"
                            onClick={(e) => {
                              e.stopPropagation();
                              setRejectingId(
                                rejectingId === review.review_id
                                  ? null
                                  : review.review_id,
                              );
                            }}
                            disabled={submitting}
                          >
                            Reject
                          </VAButton>
                        </div>

                        {rejectingId === review.review_id && (
                          <div className="space-y-2">
                            <textarea
                              value={rejectText}
                              onChange={(e) => setRejectText(e.target.value)}
                              placeholder="Provide a reason for rejection..."
                              rows={3}
                              className="w-full rounded-va-sm border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text placeholder:text-va-muted"
                              onClick={(e) => e.stopPropagation()}
                            />
                            <VAButton
                              variant="danger"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleReject(review.review_id);
                              }}
                              disabled={submitting || !rejectText.trim()}
                            >
                              Confirm Rejection
                            </VAButton>
                          </div>
                        )}
                      </div>
                    )}
                  </VACard>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Comments panel */}
        <div className="flex flex-1 flex-col overflow-y-auto p-6">
          {selectedReviewId ? (
            <>
              <h2 className="mb-4 text-lg font-semibold text-va-text">
                Review Comments
              </h2>

              {comments.length === 0 ? (
                <p className="mb-6 text-sm text-va-muted">
                  No comments yet for this review.
                </p>
              ) : (
                <div className="mb-6 space-y-3">
                  {comments.map((c) => (
                    <VACard key={c.comment_id} className="p-4">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-va-text">
                          {c.created_by ?? "Unknown"}
                        </span>
                        <span className="text-xs text-va-muted">
                          {formatTimestamp(c.created_at)}
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-relaxed text-va-text2">
                        {c.body}
                      </p>
                    </VACard>
                  ))}
                </div>
              )}

              {/* Add comment form */}
              <div className="border-t border-va-border pt-4">
                <h3 className="mb-2 text-sm font-medium text-va-text">
                  Add Comment
                </h3>
                <div className="flex gap-3">
                  <textarea
                    value={commentText}
                    onChange={(e) => setCommentText(e.target.value)}
                    placeholder="Write a comment..."
                    rows={3}
                    className="flex-1 rounded-va-sm border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text placeholder:text-va-muted"
                  />
                  <VAButton
                    variant="primary"
                    onClick={handleAddComment}
                    disabled={submitting || !commentText.trim()}
                    className="self-end"
                  >
                    Add Comment
                  </VAButton>
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-full items-center justify-center">
              <p className="text-va-muted">
                Select a review stage to view comments
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
