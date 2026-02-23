"""Database connection helper with connection pooling."""

from __future__ import annotations

from contextlib import asynccontextmanager

import asyncpg
import structlog

from apps.api.app.core.settings import get_settings

_pool: asyncpg.Pool | None = None


@asynccontextmanager
async def tenant_conn(tenant_id: str):
    if _pool is not None:
        conn = await _pool.acquire()
    else:
        settings = get_settings()
        conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute("SET app.tenant_id = $1", tenant_id)
        yield conn
    finally:
        try:
            await conn.execute("SET app.tenant_id = ''")
        except Exception as exc:
            structlog.get_logger().warning("tenant_conn_cleanup_failed", error=str(exc))
        if _pool is not None:
            await _pool.release(conn)
        else:
            await conn.close()


async def init_pool() -> None:
    """Create the connection pool (call at app startup)."""
    global _pool
    if _pool is not None:
        return
    settings = get_settings()
    _pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=settings.pool_min_size,
        max_size=settings.pool_max_size,
        command_timeout=60,
    )


async def close_pool() -> None:
    """Close the connection pool (call at app shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool | None:
    """Return the connection pool (None if not yet initialized). Call init_pool() at app startup."""
    return _pool


async def get_conn() -> asyncpg.Connection:
    """Return a connection from the pool, or a new connection if pool not initialized."""
    if _pool is not None:
        return await _pool.acquire()
    settings = get_settings()
    return await asyncpg.connect(settings.database_url)


async def ensure_tenant(conn: asyncpg.Connection, tenant_id: str, name: str | None = None) -> None:
    await conn.execute(
        "INSERT INTO tenants (id, name) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET name = COALESCE(EXCLUDED.name, tenants.name)",
        tenant_id,
        name or tenant_id,
    )
