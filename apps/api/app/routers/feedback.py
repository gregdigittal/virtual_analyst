"""Learning feedback API (VA-P6-06): list change summaries for author, acknowledge."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from apps.api.app.db import tenant_conn

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.get("")
async def list_feedback(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    unacknowledged_only: bool = Query(False, description="Only return feedback not yet acknowledged"),
) -> dict[str, Any]:
    """List change summaries for assignments where the current user is the assignee (author). VA-P6-06."""
    if not x_tenant_id or not x_user_id:
        raise HTTPException(400, "X-Tenant-ID and X-User-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """
            SELECT cs.summary_id, cs.review_id, cs.summary_text, cs.learning_points_json,
                   cs.acknowledged_at, cs.created_at,
                   r.assignment_id, r.decision, r.corrections_json
            FROM change_summaries cs
            JOIN reviews r ON r.tenant_id = cs.tenant_id AND r.review_id = cs.review_id
            JOIN task_assignments ta ON ta.tenant_id = r.tenant_id AND ta.assignment_id = r.assignment_id
            WHERE cs.tenant_id = $1 AND ta.assignee_user_id = $2
              AND ($3::boolean = false OR cs.acknowledged_at IS NULL)
            ORDER BY cs.created_at DESC
            LIMIT $4 OFFSET $5
            """,
            x_tenant_id,
            x_user_id,
            unacknowledged_only,
            limit,
            offset,
        )
    items = []
    for r in rows:
        points = r["learning_points_json"]
        if not isinstance(points, list):
            points = json.loads(points or "[]") if points else []
        items.append({
            "summary_id": r["summary_id"],
            "review_id": r["review_id"],
            "assignment_id": r["assignment_id"],
            "summary_text": r["summary_text"],
            "learning_points": points,
            "acknowledged_at": r["acknowledged_at"].isoformat() if r["acknowledged_at"] else None,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "decision": r["decision"],
            "corrections": r["corrections_json"] if isinstance(r["corrections_json"], list) else json.loads(r["corrections_json"] or "[]"),
        })
    return {"items": items, "limit": limit, "offset": offset}


@router.post("/{summary_id}/acknowledge", status_code=200)
async def acknowledge_feedback(
    summary_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Mark a change summary as acknowledged by the assignee (author). VA-P6-06."""
    if not x_tenant_id or not x_user_id:
        raise HTTPException(400, "X-Tenant-ID and X-User-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        # Only allow assignee of the assignment linked to this summary to acknowledge
        row = await conn.fetchrow(
            """
            SELECT cs.summary_id, cs.acknowledged_at
            FROM change_summaries cs
            JOIN reviews r ON r.tenant_id = cs.tenant_id AND r.review_id = cs.review_id
            JOIN task_assignments ta ON ta.tenant_id = r.tenant_id AND ta.assignment_id = r.assignment_id
            WHERE cs.tenant_id = $1 AND cs.summary_id = $2 AND ta.assignee_user_id = $3
            """,
            x_tenant_id,
            summary_id,
            x_user_id,
        )
        if not row:
            raise HTTPException(404, "Feedback not found or you are not the author")
        await conn.execute(
            """UPDATE change_summaries SET acknowledged_at = now() WHERE tenant_id = $1 AND summary_id = $2""",
            x_tenant_id,
            summary_id,
        )
    return {"summary_id": summary_id, "acknowledged": True}
