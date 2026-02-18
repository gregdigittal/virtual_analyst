"""Comments API (VA-P5-04): create, list, delete; @mentions create notifications."""

from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.db.notifications import create_notification
from apps.api.app.deps import require_role, ROLES_CAN_WRITE

router = APIRouter(prefix="/comments", tags=["comments"], dependencies=[require_role(*ROLES_CAN_WRITE)])

ENTITY_TYPES = frozenset({"run", "draft_session", "memo_pack", "baseline", "scenario", "venture", "assumption"})
UUID_PATTERN = re.compile(
    r"@([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


class CreateCommentBody(BaseModel):
    entity_type: str = Field(..., description="Entity type (run, draft_session, etc.)")
    entity_id: str = Field(..., description="Target entity ID")
    body: str = Field(..., min_length=1, max_length=10000, description="Comment text; @user_id creates mention notification")
    parent_comment_id: str | None = Field(default=None, description="Optional parent for threading")


def _mentioned_user_ids(body: str) -> set[str]:
    return set(UUID_PATTERN.findall(body))


@router.post("", status_code=201)
async def create_comment(
    body: CreateCommentBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a comment. @mention user IDs (e.g. @550e8400-e29b-41d4-a716-446655440000) trigger notifications."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.entity_type not in ENTITY_TYPES:
        raise HTTPException(400, f"entity_type must be one of: {sorted(ENTITY_TYPES)}")
    if not body.entity_id.strip():
        raise HTTPException(400, "entity_id required")

    comment_id = f"cmt_{uuid.uuid4().hex[:16]}"
    mentioned = _mentioned_user_ids(body.body)

    async with tenant_conn(x_tenant_id) as conn:
        if body.parent_comment_id:
            parent = await conn.fetchrow(
                """SELECT 1 FROM comments WHERE tenant_id = $1 AND comment_id = $2""",
                x_tenant_id,
                body.parent_comment_id,
            )
            if not parent:
                raise HTTPException(400, "parent_comment_id not found")

        await conn.execute(
            """INSERT INTO comments (tenant_id, comment_id, entity_type, entity_id, parent_comment_id, body, created_by)
             VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            x_tenant_id,
            comment_id,
            body.entity_type,
            body.entity_id.strip(),
            body.parent_comment_id,
            body.body,
            x_user_id or None,
        )

        if mentioned:
            existing = await conn.fetch(
                """SELECT id FROM users WHERE id = ANY($1::text[])""",
                list(mentioned),
            )
            valid_user_ids = {r["id"] for r in existing}
            for user_id in valid_user_ids:
                if user_id == x_user_id:
                    continue
                await create_notification(
                    conn,
                    x_tenant_id,
                    type_="comment_mention",
                    title="You were mentioned in a comment",
                    body=body.body[:200] + ("..." if len(body.body) > 200 else ""),
                    entity_type=body.entity_type,
                    entity_id=body.entity_id.strip(),
                    user_id=user_id,
                )

    return {
        "comment_id": comment_id,
        "entity_type": body.entity_type,
        "entity_id": body.entity_id.strip(),
        "parent_comment_id": body.parent_comment_id,
        "body": body.body,
        "created_by": x_user_id,
    }


@router.get("")
async def list_comments(
    entity_type: str = Query(..., description="Entity type"),
    entity_id: str = Query(..., description="Entity ID"),
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List comments for an entity (flat list; parent_comment_id indicates threading)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if entity_type not in ENTITY_TYPES:
        raise HTTPException(400, f"entity_type must be one of: {sorted(ENTITY_TYPES)}")

    async with tenant_conn(x_tenant_id) as conn:
        total = await conn.fetchval(
            """SELECT count(*) FROM comments
               WHERE tenant_id = $1 AND entity_type = $2 AND entity_id = $3""",
            x_tenant_id,
            entity_type,
            entity_id,
        )
        rows = await conn.fetch(
            """SELECT comment_id, entity_type, entity_id, parent_comment_id, body, created_at, created_by
               FROM comments
               WHERE tenant_id = $1 AND entity_type = $2 AND entity_id = $3
               ORDER BY created_at ASC
               LIMIT $4 OFFSET $5""",
            x_tenant_id,
            entity_type,
            entity_id,
            limit,
            offset,
        )

    items = [
        {
            "comment_id": r["comment_id"],
            "entity_type": r["entity_type"],
            "entity_id": r["entity_id"],
            "parent_comment_id": r["parent_comment_id"],
            "body": r["body"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "created_by": r["created_by"],
        }
        for r in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> None:
    """Delete a comment (only by author). Replies cascade-delete via FK."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if not x_user_id:
        raise HTTPException(400, "X-User-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT created_by FROM comments WHERE tenant_id = $1 AND comment_id = $2""",
            x_tenant_id,
            comment_id,
        )
        if not row:
            raise HTTPException(404, "Comment not found")
        if row["created_by"] != x_user_id:
            raise HTTPException(403, "Only the comment author can delete this comment")
        await conn.execute(
            """DELETE FROM comments WHERE tenant_id = $1 AND comment_id = $2""",
            x_tenant_id,
            comment_id,
        )
