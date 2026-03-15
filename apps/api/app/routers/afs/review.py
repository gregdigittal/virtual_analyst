"""AFS review workflow endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException

from apps.api.app.db import tenant_conn
from apps.api.app.routers.afs._common import (
    VALID_REVIEW_STAGES,
    CreateReviewCommentBody,
    ReviewActionBody,
    SubmitReviewBody,
    _review_comment_id,
    _review_id,
    _validate_engagement,
)

router = APIRouter()


@router.post("/engagements/{engagement_id}/reviews/submit", status_code=201)
async def submit_review(
    engagement_id: str,
    body: SubmitReviewBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Submit engagement for review at a given stage."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.stage not in VALID_REVIEW_STAGES:
        raise HTTPException(400, f"Invalid stage '{body.stage}'. Must be one of: {', '.join(sorted(VALID_REVIEW_STAGES))}")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT * FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        # Verify all sections are reviewed or locked (none in draft)
        draft_count = await conn.fetchval(
            """SELECT count(*) FROM afs_sections
               WHERE tenant_id = $1 AND engagement_id = $2 AND status = 'draft'""",
            x_tenant_id, engagement_id,
        )
        if draft_count and draft_count > 0:
            raise HTTPException(400, f"{draft_count} section(s) still in draft. Review or lock all sections before submitting.")

        # Guard against duplicate pending review for the same stage
        existing = await conn.fetchval(
            """SELECT review_id FROM afs_reviews
               WHERE tenant_id = $1 AND engagement_id = $2 AND stage = $3 AND status = 'pending'""",
            x_tenant_id, engagement_id, body.stage,
        )
        if existing:
            raise HTTPException(409, f"A pending review already exists for stage '{body.stage}'.")

        rid = _review_id()
        row = await conn.fetchrow(
            """INSERT INTO afs_reviews (tenant_id, review_id, engagement_id, stage, status, submitted_by, comments)
               VALUES ($1, $2, $3, $4, 'pending', $5, $6)
               RETURNING *""",
            x_tenant_id, rid, engagement_id, body.stage, x_user_id or None, body.comments,
        )

        # Update engagement status to review
        await conn.execute(
            "UPDATE afs_engagements SET status = 'review', updated_at = now() WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )

        return dict(row)


@router.get("/engagements/{engagement_id}/reviews")
async def list_reviews(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List all reviews for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT * FROM afs_reviews
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY submitted_at DESC""",
            x_tenant_id, engagement_id,
        )
        return {"items": [dict(r) for r in rows]}


@router.post("/engagements/{engagement_id}/reviews/{review_id}/approve")
async def approve_review(
    engagement_id: str,
    review_id: str,
    body: ReviewActionBody | None = None,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Approve a pending review."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        review = await conn.fetchrow(
            "SELECT * FROM afs_reviews WHERE tenant_id = $1 AND review_id = $2 AND engagement_id = $3",
            x_tenant_id, review_id, engagement_id,
        )
        if not review:
            raise HTTPException(404, f"Review {review_id} not found")
        if review["status"] != "pending":
            raise HTTPException(400, f"Review is already '{review['status']}', cannot approve")

        comments = body.comments if body else None
        row = await conn.fetchrow(
            """UPDATE afs_reviews
               SET status = 'approved', reviewed_by = $1, reviewed_at = now(),
                   comments = CASE WHEN $2 IS NOT NULL THEN coalesce(comments || E'\n', '') || $2 ELSE comments END
               WHERE tenant_id = $3 AND review_id = $4
               RETURNING *""",
            x_user_id or None, comments, x_tenant_id, review_id,
        )

        # If partner sign-off approved, update engagement to approved
        if review["stage"] == "partner_signoff":
            await conn.execute(
                "UPDATE afs_engagements SET status = 'approved', updated_at = now() WHERE tenant_id = $1 AND engagement_id = $2",
                x_tenant_id, engagement_id,
            )

        return dict(row)


@router.post("/engagements/{engagement_id}/reviews/{review_id}/reject")
async def reject_review(
    engagement_id: str,
    review_id: str,
    body: ReviewActionBody | None = None,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Reject a pending review."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        review = await conn.fetchrow(
            "SELECT * FROM afs_reviews WHERE tenant_id = $1 AND review_id = $2 AND engagement_id = $3",
            x_tenant_id, review_id, engagement_id,
        )
        if not review:
            raise HTTPException(404, f"Review {review_id} not found")
        if review["status"] != "pending":
            raise HTTPException(400, f"Review is already '{review['status']}', cannot reject")

        comments = body.comments if body else None
        row = await conn.fetchrow(
            """UPDATE afs_reviews
               SET status = 'rejected', reviewed_by = $1, reviewed_at = now(),
                   comments = CASE WHEN $2 IS NOT NULL THEN coalesce(comments || E'\n', '') || $2 ELSE comments END
               WHERE tenant_id = $3 AND review_id = $4
               RETURNING *""",
            x_user_id or None, comments, x_tenant_id, review_id,
        )
        return dict(row)


@router.post("/engagements/{engagement_id}/reviews/comments", status_code=201)
async def create_review_comment(
    engagement_id: str,
    body: CreateReviewCommentBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Add a comment to a review."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        # Verify review belongs to this engagement
        review = await conn.fetchrow(
            "SELECT review_id FROM afs_reviews WHERE tenant_id = $1 AND review_id = $2 AND engagement_id = $3",
            x_tenant_id, body.review_id, engagement_id,
        )
        if not review:
            raise HTTPException(404, f"Review {body.review_id} not found for engagement {engagement_id}")

        cid = _review_comment_id()
        row = await conn.fetchrow(
            """INSERT INTO afs_review_comments
               (tenant_id, comment_id, review_id, section_id, parent_comment_id, body, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               RETURNING *""",
            x_tenant_id, cid, body.review_id, body.section_id, body.parent_comment_id,
            body.body, x_user_id or None,
        )
        return dict(row)


@router.get("/engagements/{engagement_id}/reviews/{review_id}/comments")
async def list_review_comments(
    engagement_id: str,
    review_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List comments for a review."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        # Verify review belongs to this engagement
        review = await conn.fetchrow(
            "SELECT review_id FROM afs_reviews WHERE tenant_id = $1 AND review_id = $2 AND engagement_id = $3",
            x_tenant_id, review_id, engagement_id,
        )
        if not review:
            raise HTTPException(404, f"Review {review_id} not found for engagement {engagement_id}")

        rows = await conn.fetch(
            """SELECT * FROM afs_review_comments
               WHERE tenant_id = $1 AND review_id = $2
               ORDER BY created_at ASC""",
            x_tenant_id, review_id,
        )
        return {"items": [dict(r) for r in rows]}
