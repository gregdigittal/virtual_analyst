"""Create in-app notifications for key events."""

from __future__ import annotations

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
) -> None:
    await conn.execute(
        """INSERT INTO notifications (tenant_id, user_id, type, title, body, entity_type, entity_id)
           VALUES ($1, $2, $3, $4, $5, $6, $7)""",
        tenant_id,
        user_id,
        type_,
        title,
        body,
        entity_type,
        entity_id,
    )
