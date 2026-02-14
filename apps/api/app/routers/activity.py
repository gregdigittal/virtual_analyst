"""Activity feed API (VA-P5-04): recent audit events and comments, filterable."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from apps.api.app.db import tenant_conn

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("")
async def get_activity_feed(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    user_id: str | None = Query(None, description="Filter by user"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    resource_id: str | None = Query(None, description="Filter by resource ID"),
    since: str | None = Query(None, description="ISO datetime; only activity after this time"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Return recent activity: audit events and comments, merged and sorted by time (newest first)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if since:
        try:
            datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(400, "Invalid 'since' parameter; must be ISO 8601 datetime")

    async with tenant_conn(x_tenant_id) as conn:
        conditions_audit = ["tenant_id = $1"]
        params_audit: list[Any] = [x_tenant_id]
        idx = 2
        if user_id:
            conditions_audit.append(f"user_id = ${idx}")
            params_audit.append(user_id)
            idx += 1
        if resource_type:
            conditions_audit.append(f"resource_type = ${idx}")
            params_audit.append(resource_type)
            idx += 1
        if resource_id:
            conditions_audit.append(f"resource_id = ${idx}")
            params_audit.append(resource_id)
            idx += 1
        if since:
            conditions_audit.append(f'"timestamp" >= ${idx}::timestamptz')
            params_audit.append(since)
            idx += 1
        where_audit = " AND ".join(conditions_audit)
        # Fetch 2x limit from each source to reduce gaps after merge + truncate
        params_audit.append(limit * 2)

        audit_rows = await conn.fetch(
            f"""SELECT audit_event_id, user_id, event_type, event_category, "timestamp", resource_type, resource_id, event_data
               FROM audit_log WHERE {where_audit}
               ORDER BY "timestamp" DESC LIMIT ${idx}""",
            *params_audit,
        )

        conditions_cmt = ["tenant_id = $1"]
        params_cmt: list[Any] = [x_tenant_id]
        idx = 2
        if user_id:
            conditions_cmt.append(f"created_by = ${idx}")
            params_cmt.append(user_id)
            idx += 1
        if resource_type:
            conditions_cmt.append(f"entity_type = ${idx}")
            params_cmt.append(resource_type)
            idx += 1
        if resource_id:
            conditions_cmt.append(f"entity_id = ${idx}")
            params_cmt.append(resource_id)
            idx += 1
        if since:
            conditions_cmt.append(f"created_at >= ${idx}::timestamptz")
            params_cmt.append(since)
            idx += 1
        where_cmt = " AND ".join(conditions_cmt)
        params_cmt.append(limit * 2)

        comment_rows = await conn.fetch(
            f"""SELECT comment_id, entity_type, entity_id, body, created_at, created_by
               FROM comments WHERE {where_cmt}
               ORDER BY created_at DESC LIMIT ${idx}""",
            *params_cmt,
        )

    audit_items = [
        {
            "type": "audit",
            "id": r["audit_event_id"],
            "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None,
            "user_id": r["user_id"],
            "resource_type": r["resource_type"],
            "resource_id": r["resource_id"],
            "event_type": r["event_type"],
            "event_category": r["event_category"],
            "summary": r["event_type"],
            "event_data": r["event_data"],
        }
        for r in audit_rows
    ]
    comment_items = [
        {
            "type": "comment",
            "id": r["comment_id"],
            "timestamp": r["created_at"].isoformat() if r["created_at"] else None,
            "user_id": r["created_by"],
            "resource_type": r["entity_type"],
            "resource_id": r["entity_id"],
            "summary": (r["body"] or "")[:120] + ("..." if len(r["body"] or "") > 120 else ""),
            "body": r["body"],
        }
        for r in comment_rows
    ]

    merged = sorted(
        audit_items + comment_items,
        key=lambda x: x["timestamp"] or "",
        reverse=True,
    )[:limit]

    return {"activity": merged, "limit": limit}
