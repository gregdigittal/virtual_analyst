"""Database connection helper."""

from __future__ import annotations

import asyncpg

from apps.api.app.core.settings import get_settings


async def get_conn() -> asyncpg.Connection:
    settings = get_settings()
    return await asyncpg.connect(settings.database_url)


async def ensure_tenant(conn: asyncpg.Connection, tenant_id: str, name: str | None = None) -> None:
    await conn.execute(
        "INSERT INTO tenants (id, name) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET name = COALESCE(EXCLUDED.name, tenants.name)",
        tenant_id,
        name or tenant_id,
    )
