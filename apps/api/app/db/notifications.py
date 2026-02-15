"""Create in-app notifications for key events."""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg


async def create_notification(
    conn: asyncpg.Connection,
    tenant_id: str,
    type_: str,
    title: str,
    body: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    user_id: str | None = None,
) -> str:
    """Insert a notification and return its id (ntf_ prefix for consistency). R6-08, R7-10."""
    notification_id = f"ntf_{uuid.uuid4().hex[:12]}"
    await conn.execute(
        """INSERT INTO notifications (id, tenant_id, user_id, type, title, body, entity_type, entity_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
        notification_id,
        tenant_id,
        user_id,
        type_,
        title,
        body,
        entity_type,
        entity_id,
    )
    return notification_id
