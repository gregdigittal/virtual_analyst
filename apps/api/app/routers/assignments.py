"""Task assignment API (VA-P6-04): create, list, claim (pool), submit."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.db.connection import get_pool
from apps.api.app.db.notifications import create_notification
from apps.api.app.deps import get_llm_router, require_role, ROLES_CAN_WRITE
from apps.api.app.services.llm.router import LLMRouter

router = APIRouter(prefix="/assignments", tags=["assignments"])


def _serialize_row(r: Any) -> dict[str, Any]:
    return {
        "assignment_id": r["assignment_id"],
        "workflow_instance_id": r["workflow_instance_id"],
        "entity_type": r["entity_type"],
        "entity_id": r["entity_id"],
        "assignee_user_id": r["assignee_user_id"],
        "assigned_by_user_id": r["assigned_by_user_id"],
        "status": r["status"],
        "deadline": r["deadline"].isoformat() if r["deadline"] else None,
        "instructions": r["instructions"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "submitted_at": r["submitted_at"].isoformat() if r["submitted_at"] else None,
    }


class CreateAssignmentBody(BaseModel):
    entity_type: str = Field(..., min_length=1)
    entity_id: str = Field(..., min_length=1)
    assignee_user_id: str | None = Field(default=None, description="Null = pool (unassigned)")
    workflow_instance_id: str | None = None
    instructions: str | None = None
    deadline: datetime | str | None = None


class UpdateAssignmentBody(BaseModel):
    status: str | None = Field(default=None, description="New status")
    instructions: str | None = None
    deadline: datetime | str | None = None


@router.post("", status_code=201)
async def create_assignment(
    body: CreateAssignmentBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> dict[str, Any]:
    """Create a task assignment (top-down: assigner assigns to assignee or pool)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    entity_type = body.entity_type
    entity_id = body.entity_id
    assignee_user_id = body.assignee_user_id
    workflow_instance_id = body.workflow_instance_id
    instructions = body.instructions
    deadline = body.deadline
    if isinstance(deadline, str):
        deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
    assignment_id = f"asn_{uuid.uuid4().hex[:12]}"
    status = "assigned" if assignee_user_id else "draft"
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO task_assignments
               (tenant_id, assignment_id, workflow_instance_id, entity_type, entity_id,
                assignee_user_id, assigned_by_user_id, status, instructions, deadline)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
            x_tenant_id,
            assignment_id,
            workflow_instance_id,
            entity_type,
            entity_id,
            assignee_user_id,
            x_user_id or None,
            status,
            instructions,
            deadline,
        )
        row = await conn.fetchrow(
            """SELECT assignment_id, workflow_instance_id, entity_type, entity_id,
                      assignee_user_id, assigned_by_user_id, status, deadline, instructions, created_at, submitted_at
               FROM task_assignments WHERE tenant_id = $1 AND assignment_id = $2""",
            x_tenant_id,
            assignment_id,
        )
        if assignee_user_id:
            await create_notification(
                conn,
                x_tenant_id,
                "task_assigned",
                "Task assigned to you",
                body=f"Assignment {entity_type} — {entity_id}.",
                entity_type="assignment",
                entity_id=assignment_id,
                user_id=assignee_user_id,
            )
    return _serialize_row(row)


@router.get("")
async def list_assignments(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    assignee_user_id: str | None = Query(None, description="Filter by assignee (use 'me' for X-User-ID)"),
    status: str | None = Query(None),
    entity_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    x_user_id: str = Header("", alias="X-User-ID"),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> dict[str, Any]:
    """List task assignments. assignee_user_id=me uses X-User-ID."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if assignee_user_id == "me":
        assignee_user_id = x_user_id or None
    async with tenant_conn(x_tenant_id) as conn:
        conditions = ["tenant_id = $1"]
        params: list[Any] = [x_tenant_id]
        idx = 2
        if assignee_user_id:
            conditions.append(f"assignee_user_id = ${idx}")
            params.append(assignee_user_id)
            idx += 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if entity_type:
            conditions.append(f"entity_type = ${idx}")
            params.append(entity_type)
            idx += 1
        params.append(limit)
        params.append(offset)
        limit_off = f"LIMIT ${idx} OFFSET ${idx + 1}"
        rows = await conn.fetch(
            f"""SELECT assignment_id, workflow_instance_id, entity_type, entity_id,
                      assignee_user_id, assigned_by_user_id, status, deadline, instructions, created_at, submitted_at
                FROM task_assignments WHERE {" AND ".join(conditions)}
                ORDER BY created_at DESC {limit_off}""",
            *params,
        )
    items = [_serialize_row(r) for r in rows]
    return {"assignments": items, "limit": limit, "offset": offset}


@router.get("/pool")
async def list_pool_assignments(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> dict[str, Any]:
    """List assignments with no assignee (pool: anyone can claim)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT assignment_id, workflow_instance_id, entity_type, entity_id,
                      assignee_user_id, assigned_by_user_id, status, deadline, instructions, created_at, submitted_at
               FROM task_assignments WHERE tenant_id = $1 AND assignee_user_id IS NULL AND status = 'draft'
               ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
            x_tenant_id,
            limit,
            offset,
        )
    return {"assignments": [_serialize_row(r) for r in rows], "limit": limit, "offset": offset}


@router.get("/{assignment_id}")
async def get_assignment(
    assignment_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get a single assignment."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT assignment_id, workflow_instance_id, entity_type, entity_id,
                      assignee_user_id, assigned_by_user_id, status, deadline, instructions, created_at, submitted_at
               FROM task_assignments WHERE tenant_id = $1 AND assignment_id = $2""",
            x_tenant_id,
            assignment_id,
        )
    if not row:
        raise HTTPException(404, "Assignment not found")
    return _serialize_row(row)


@router.post("/{assignment_id}/claim", status_code=200)
async def claim_assignment(
    assignment_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> dict[str, Any]:
    """Claim a pool assignment (assignee was null). Atomic UPDATE to avoid race."""
    if not x_tenant_id or not x_user_id:
        raise HTTPException(400, "X-Tenant-ID and X-User-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            """UPDATE task_assignments
               SET assignee_user_id = $1, status = 'assigned'
               WHERE tenant_id = $2 AND assignment_id = $3
                 AND assignee_user_id IS NULL AND status = 'draft'""",
            x_user_id,
            x_tenant_id,
            assignment_id,
        )
        if result == "UPDATE 0":
            row = await conn.fetchrow(
                """SELECT assignment_id, assignee_user_id, status FROM task_assignments
                   WHERE tenant_id = $1 AND assignment_id = $2""",
                x_tenant_id,
                assignment_id,
            )
            if not row:
                raise HTTPException(404, "Assignment not found")
            if row["assignee_user_id"] is not None:
                raise HTTPException(409, "Assignment already claimed")
            raise HTTPException(400, "Only draft pool assignments can be claimed")
        row = await conn.fetchrow(
            """SELECT assignment_id, workflow_instance_id, entity_type, entity_id,
                      assignee_user_id, assigned_by_user_id, status, deadline, instructions, created_at, submitted_at
               FROM task_assignments WHERE tenant_id = $1 AND assignment_id = $2""",
            x_tenant_id,
            assignment_id,
        )
        await create_notification(
            conn,
            x_tenant_id,
            "task_assigned",
            "You claimed a task",
            body=f"Assignment {row['entity_type']} — {row['entity_id']}.",
            entity_type="assignment",
            entity_id=assignment_id,
            user_id=x_user_id,
        )
    return _serialize_row(row)


@router.post("/{assignment_id}/submit", status_code=200)
async def submit_assignment(
    assignment_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> dict[str, Any]:
    """Submit assignment for review (assignee only)."""
    if not x_tenant_id or not x_user_id:
        raise HTTPException(400, "X-Tenant-ID and X-User-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT assignee_user_id, assigned_by_user_id, status FROM task_assignments
               WHERE tenant_id = $1 AND assignment_id = $2""",
            x_tenant_id,
            assignment_id,
        )
        if not row:
            raise HTTPException(404, "Assignment not found")
        if row["assignee_user_id"] != x_user_id:
            raise HTTPException(403, "Only the assignee can submit")
        if row["status"] not in ("assigned", "in_progress"):
            raise HTTPException(400, "Only assigned or in_progress assignments can be submitted")
        assigned_by = row["assigned_by_user_id"]
        await conn.execute(
            """UPDATE task_assignments SET status = 'submitted', submitted_at = $1
               WHERE tenant_id = $2 AND assignment_id = $3""",
            datetime.now(UTC),
            x_tenant_id,
            assignment_id,
        )
        row = await conn.fetchrow(
            """SELECT assignment_id, workflow_instance_id, entity_type, entity_id,
                      assignee_user_id, assigned_by_user_id, status, deadline, instructions, created_at, submitted_at
               FROM task_assignments WHERE tenant_id = $1 AND assignment_id = $2""",
            x_tenant_id,
            assignment_id,
        )
        if assigned_by:
            await create_notification(
                conn,
                x_tenant_id,
                "task_submitted",
                "Assignment submitted for review",
                body=f"Assignment {row['entity_type']} — {row['entity_id']} was submitted for review.",
                entity_type="assignment",
                entity_id=assignment_id,
                user_id=assigned_by,
            )
    return _serialize_row(row)


@router.patch("/{assignment_id}")
async def update_assignment(
    assignment_id: str,
    body: UpdateAssignmentBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> dict[str, Any]:
    """Update assignment (status to in_progress, or other fields)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    updates = []
    params: list[Any] = [x_tenant_id, assignment_id]
    idx = 3
    if body.status is not None:
        s = body.status
        if s not in ("draft", "assigned", "in_progress", "submitted", "approved", "returned", "completed"):
            raise HTTPException(400, "Invalid status")
        updates.append(f"status = ${idx}")
        params.append(s)
        idx += 1
        if s == "submitted":
            updates.append("submitted_at = now()")
    if body.instructions is not None:
        updates.append(f"instructions = ${idx}")
        params.append(body.instructions)
        idx += 1
    if body.deadline is not None:
        updates.append(f"deadline = ${idx}")
        d = body.deadline
        params.append(datetime.fromisoformat(d.replace("Z", "+00:00")) if isinstance(d, str) else d)
        idx += 1
    if not updates:
        raise HTTPException(400, "No fields to update")
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            f"""UPDATE task_assignments SET {", ".join(updates)} WHERE tenant_id = $1 AND assignment_id = $2""",
            *params,
        )
        row = await conn.fetchrow(
            """SELECT assignment_id, workflow_instance_id, entity_type, entity_id,
                      assignee_user_id, assigned_by_user_id, status, deadline, instructions, created_at, submitted_at
               FROM task_assignments WHERE tenant_id = $1 AND assignment_id = $2""",
            x_tenant_id,
            assignment_id,
        )
    if not row:
        raise HTTPException(404, "Assignment not found")
    return _serialize_row(row)


# --- VA-P6-05: Review & correction pipeline ---

class CorrectionItem(BaseModel):
    path: str = Field(..., min_length=1)
    old_value: str | None = None
    new_value: str | None = None
    reason: str | None = None


class SubmitReviewBody(BaseModel):
    decision: str = Field(..., description="approved | request_changes | rejected")
    notes: str | None = None
    corrections: list[CorrectionItem] = Field(default_factory=list)


def _build_summary_from_corrections(corrections: list[CorrectionItem]) -> str:
    if not corrections:
        return "No corrections."
    parts = []
    for i, c in enumerate(corrections, 1):
        part = f"{i}. {c.path}: "
        if c.old_value is not None or c.new_value is not None:
            old_display = c.old_value if c.old_value is not None else "(empty)"
            new_display = c.new_value if c.new_value is not None else "(empty)"
            part += f"{old_display} → {new_display}"
        if c.reason:
            part += f" ({c.reason})"
        parts.append(part)
    return "\n".join(parts)


# VA-P6-06: LLM schema for review_summary (learning points from corrections)
REVIEW_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "learning_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string", "description": "Brief learning point for the author"},
                    "category": {"type": "string", "description": "Optional category e.g. methodology, assumption, formatting"},
                },
                "required": ["point"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["learning_points"],
    "additionalProperties": False,
}


async def _generate_learning_points(
    tenant_id: str,
    summary_id: str,
    summary_text: str,
    corrections: list[CorrectionItem],
    llm: LLMRouter,
) -> None:
    """Background task: call LLM for learning points and update change_summaries. R6-06."""
    try:
        prompt = (
            "You are helping an analyst learn from review feedback. Based on the following change summary and corrections, "
            "suggest 1-5 brief, actionable learning points for the author. Be factual and specific; do not fabricate. "
            "Each point should be one short sentence.\n\nChange summary:\n" + summary_text
        )
        resp = await llm.complete_with_routing(
            tenant_id=tenant_id,
            messages=[{"role": "user", "content": prompt}],
            response_schema=REVIEW_SUMMARY_SCHEMA,
            task_label="review_summary",
            max_tokens=1024,
            temperature=0.2,
        )
        points = resp.content.get("learning_points") or []
        if isinstance(points, list) and points:
            async with tenant_conn(tenant_id) as conn:
                await conn.execute(
                    """UPDATE change_summaries SET learning_points_json = $1::jsonb
                       WHERE tenant_id = $2 AND summary_id = $3""",
                    json.dumps(points),
                    tenant_id,
                    summary_id,
                )
    except Exception as e:
        import structlog
        structlog.get_logger().warning("learning_points_update_failed", tenant_id=tenant_id, error=str(e))


@router.post("/{assignment_id}/review", status_code=201)
async def submit_review(
    assignment_id: str,
    body: SubmitReviewBody,
    background_tasks: BackgroundTasks,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm: LLMRouter = Depends(get_llm_router),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> dict[str, Any]:
    """Submit a review decision (approve / request_changes / reject). VA-P6-05. VA-P6-06: generates LLM learning points when corrections present."""
    if not x_tenant_id or not x_user_id:
        raise HTTPException(400, "X-Tenant-ID and X-User-ID required")
    if body.decision not in ("approved", "request_changes", "rejected"):
        raise HTTPException(400, "decision must be approved, request_changes, or rejected")
    review_id = f"rev_{uuid.uuid4().hex[:12]}"
    new_status = "completed" if body.decision == "approved" else "returned"
    corrections_json = [c.model_dump() for c in body.corrections]
    summary_id: str | None = None
    summary_text: str | None = None
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT assignment_id, assignee_user_id, status FROM task_assignments
               WHERE tenant_id = $1 AND assignment_id = $2""",
            x_tenant_id,
            assignment_id,
        )
        if not row:
            raise HTTPException(404, "Assignment not found")
        if row["assignee_user_id"] == x_user_id:
            raise HTTPException(403, "Cannot review your own assignment")
        if row["status"] != "submitted":
            raise HTTPException(400, "Only submitted assignments can be reviewed")
        await conn.execute(
            """INSERT INTO reviews (tenant_id, review_id, assignment_id, reviewer_user_id, decision, notes, corrections_json)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)""",
            x_tenant_id,
            review_id,
            assignment_id,
            x_user_id,
            body.decision,
            body.notes,
            json.dumps(corrections_json),
        )
        await conn.execute(
            """UPDATE task_assignments SET status = $1 WHERE tenant_id = $2 AND assignment_id = $3""",
            new_status,
            x_tenant_id,
            assignment_id,
        )
        # VA-P8-07: Create change_summary for request_changes/rejected so author gets LLM learning points
        if body.corrections:
            summary_text = _build_summary_from_corrections(body.corrections)
        elif body.decision in ("request_changes", "rejected") and body.notes:
            summary_text = f"Reviewer notes: {body.notes}"
        else:
            summary_text = None
        if summary_text:
            summary_id = f"cs_{uuid.uuid4().hex[:10]}"
            await conn.execute(
                """INSERT INTO change_summaries (tenant_id, summary_id, review_id, summary_text)
                   VALUES ($1, $2, $3, $4)""",
                x_tenant_id,
                summary_id,
                review_id,
                summary_text,
            )
        else:
            summary_id = None
        rev_row = await conn.fetchrow(
            """SELECT review_id, assignment_id, reviewer_user_id, decision, notes, corrections_json, created_at
               FROM reviews WHERE tenant_id = $1 AND review_id = $2""",
            x_tenant_id,
            review_id,
        )
        assignee_user_id = row["assignee_user_id"]
        if assignee_user_id:
            if body.decision == "approved":
                await create_notification(
                    conn,
                    x_tenant_id,
                    "workflow_completed",
                    "Your work was approved",
                    body=f"Assignment {assignment_id} was approved.",
                    entity_type="assignment",
                    entity_id=assignment_id,
                    user_id=assignee_user_id,
                )
            else:
                title = "Review: changes requested" if body.decision == "request_changes" else "Review: rejected"
                await create_notification(
                    conn,
                    x_tenant_id,
                    "review_decision",
                    title,
                    body=f"Assignment {assignment_id}: {title.lower()}.",
                    entity_type="assignment",
                    entity_id=assignment_id,
                    user_id=assignee_user_id,
                )
    # VA-P6-06 / VA-P8-07: Generate learning points in background when request_changes or rejected with feedback
    if summary_id and summary_text:
        corrections_for_llm = body.corrections if body.corrections else []
        background_tasks.add_task(
            _generate_learning_points,
            x_tenant_id,
            summary_id,
            summary_text,
            corrections_for_llm,
            llm,
        )
    return {
        "review_id": rev_row["review_id"],
        "assignment_id": rev_row["assignment_id"],
        "reviewer_user_id": rev_row["reviewer_user_id"],
        "decision": rev_row["decision"],
        "notes": rev_row["notes"],
        "corrections": rev_row["corrections_json"] if isinstance(rev_row["corrections_json"], list) else json.loads(rev_row["corrections_json"] or "[]"),
        "created_at": rev_row["created_at"].isoformat() if rev_row["created_at"] else None,
    }


@router.get("/{assignment_id}/reviews")
async def list_reviews(
    assignment_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> dict[str, Any]:
    """List reviews for an assignment. VA-P6-05."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM task_assignments WHERE tenant_id = $1 AND assignment_id = $2",
            x_tenant_id,
            assignment_id,
        )
        if not exists:
            raise HTTPException(404, "Assignment not found")
        rows = await conn.fetch(
            """SELECT review_id, assignment_id, reviewer_user_id, decision, notes, corrections_json, created_at
               FROM reviews WHERE tenant_id = $1 AND assignment_id = $2 ORDER BY created_at DESC LIMIT $3 OFFSET $4""",
            x_tenant_id,
            assignment_id,
            limit,
            offset,
        )
    reviews_list = [
        {
            "review_id": r["review_id"],
            "assignment_id": r["assignment_id"],
            "reviewer_user_id": r["reviewer_user_id"],
            "decision": r["decision"],
            "notes": r["notes"],
            "corrections": r["corrections_json"] if isinstance(r["corrections_json"], list) else json.loads(r["corrections_json"] or "[]"),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    return {"reviews": reviews_list, "limit": limit, "offset": offset}


# --- VA-P6-07: Deadline reminders (call from cron every 15–60 min) ---

@router.post("/cron/deadline-reminders", status_code=200)
async def cron_deadline_reminders(
    x_cron_secret: str = Header("", alias="X-Cron-Secret"),
) -> dict[str, Any]:
    """Create deadline_approaching (24h/4h) and deadline_overdue notifications. VA-P6-07. Requires X-Cron-Secret when CRON_SECRET is set. R6-03."""
    from datetime import timedelta

    import structlog

    from apps.api.app.core.settings import get_settings

    logger = structlog.get_logger()
    settings = get_settings()
    if settings.cron_secret and x_cron_secret != settings.cron_secret:
        raise HTTPException(403, "Invalid cron secret")

    now_ts = datetime.now(UTC)
    created = 0
    pool = get_pool()
    if pool:
        async with pool.acquire() as conn:
            tenant_rows = await conn.fetch("SELECT id FROM tenants")
    else:
        conn = await asyncpg.connect(settings.database_url)
        try:
            tenant_rows = await conn.fetch("SELECT id FROM tenants")
        finally:
            await conn.close()

    for trow in tenant_rows:
        tenant_id = trow["id"]
        try:
            async with tenant_conn(tenant_id) as tconn:
                for window_name, type_, delta_start, delta_end in [
                    ("24h", "deadline_approaching_24h", timedelta(hours=23), timedelta(hours=25)),
                    ("4h", "deadline_approaching_4h", timedelta(hours=3), timedelta(hours=5)),
                ]:
                    start = now_ts + delta_start
                    end = now_ts + delta_end
                    rows = await tconn.fetch(
                        """SELECT ta.assignment_id, ta.entity_type, ta.entity_id, ta.assignee_user_id
                           FROM task_assignments ta
                           WHERE ta.tenant_id = $1 AND ta.deadline IS NOT NULL AND ta.assignee_user_id IS NOT NULL
                             AND ta.status IN ('draft', 'assigned', 'in_progress', 'submitted')
                             AND ta.deadline > $2 AND ta.deadline <= $3
                             AND NOT EXISTS (
                               SELECT 1 FROM notifications n
                               WHERE n.tenant_id = $1 AND n.type = $4
                                 AND n.entity_type = 'assignment' AND n.entity_id = ta.assignment_id
                                 AND n.created_at > now() - interval '48 hours'
                             )""",
                        tenant_id,
                        start,
                        end,
                        type_,
                    )
                    for r in rows:
                        await create_notification(
                            tconn,
                            tenant_id,
                            type_,
                            f"Deadline in {window_name}",
                            body=f"Assignment {r['entity_type']} — {r['entity_id']} is due in {window_name}.",
                            entity_type="assignment",
                            entity_id=r["assignment_id"],
                            user_id=r["assignee_user_id"],
                        )
                        created += 1
                overdue_rows = await tconn.fetch(
                    """SELECT ta.assignment_id, ta.entity_type, ta.entity_id, ta.assignee_user_id
                       FROM task_assignments ta
                       WHERE ta.tenant_id = $1 AND ta.deadline IS NOT NULL AND ta.assignee_user_id IS NOT NULL
                         AND ta.status IN ('draft', 'assigned', 'in_progress', 'submitted')
                         AND ta.deadline < $2
                         AND NOT EXISTS (
                           SELECT 1 FROM notifications n
                           WHERE n.tenant_id = $1 AND n.type = 'deadline_overdue'
                             AND n.entity_type = 'assignment' AND n.entity_id = ta.assignment_id
                             AND n.created_at > now() - interval '7 days'
                         )""",
                    tenant_id,
                    now_ts,
                )
                for r in overdue_rows:
                    await create_notification(
                        tconn,
                        tenant_id,
                        "deadline_overdue",
                        "Deadline passed",
                        body=f"Assignment {r['entity_type']} — {r['entity_id']} is overdue.",
                        entity_type="assignment",
                        entity_id=r["assignment_id"],
                        user_id=r["assignee_user_id"],
                    )
                    created += 1
        except Exception as e:
            logger.error("cron_deadline_tenant_error", tenant_id=tenant_id, error=str(e))
            continue
    return {"created": created}
