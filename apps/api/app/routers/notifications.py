"""In-app notifications: list and mark read."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from apps.api.app.db import tenant_conn

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        if unread_only:
            rows = await conn.fetch(
                """SELECT id, tenant_id, user_id, type, title, body, entity_type, entity_id, read_at, created_at
                   FROM notifications WHERE tenant_id = $1 AND read_at IS NULL
                   ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
                x_tenant_id,
                limit,
                offset,
            )
        else:
            rows = await conn.fetch(
                """SELECT id, tenant_id, user_id, type, title, body, entity_type, entity_id, read_at, created_at
                   FROM notifications WHERE tenant_id = $1
                   ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
                x_tenant_id,
                limit,
                offset,
            )
        unread_count_row = await conn.fetchrow(
            "SELECT count(*)::int AS n FROM notifications WHERE tenant_id = $1 AND read_at IS NULL",
            x_tenant_id,
        )
        unread_count = unread_count_row["n"] if unread_count_row else 0
        items = [
            {
                "id": str(r["id"]),
                "tenant_id": r["tenant_id"],
                "user_id": r["user_id"],
                "type": r["type"],
                "title": r["title"],
                "body": r["body"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "read_at": r["read_at"].isoformat() if r["read_at"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return {"items": items, "unread_count": unread_count, "limit": limit, "offset": offset}


@router.patch("/{notification_id}")
async def mark_notification_read(
    notification_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """UPDATE notifications SET read_at = now() WHERE id = $1::uuid AND tenant_id = $2""",
            notification_id,
            x_tenant_id,
        )
        row = await conn.fetchrow(
            "SELECT id, read_at FROM notifications WHERE id = $1::uuid AND tenant_id = $2",
            notification_id,
            x_tenant_id,
        )
        if not row:
            raise HTTPException(404, "Notification not found")
        return {
            "id": notification_id,
            "read_at": row["read_at"].isoformat() if row["read_at"] else None,
        }
