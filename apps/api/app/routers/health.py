from __future__ import annotations

import re

import asyncpg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from apps.api.app.core.settings import get_settings
from apps.api.app.db.connection import get_pool

router = APIRouter()


def _mask_url(url: str) -> str:
    """Mask password in connection URL for safe diagnostics."""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)


@router.get("/health/live")
async def liveness() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    settings = get_settings()
    checks: dict[str, str] = {}
    errors: dict[str, str] = {}

    try:
        pool = get_pool()
        if pool is not None:
            conn = await pool.acquire()
            try:
                await conn.execute("SELECT 1")
            finally:
                await pool.release(conn)
        else:
            conn = await asyncpg.connect(settings.database_url, timeout=10)
            try:
                await conn.execute("SELECT 1")
            finally:
                await conn.close()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = "error"
        errors["database"] = f"{type(e).__name__}: {e}"

    try:
        redis_client = Redis.from_url(settings.redis_url)
        try:
            await redis_client.ping()
            checks["redis"] = "ok"
        finally:
            await redis_client.close()
    except Exception as e:
        checks["redis"] = "error"
        errors["redis"] = f"{type(e).__name__}: {e}"

    all_ok = all(value == "ok" for value in checks.values())
    status_code = 200 if all_ok else 503

    content: dict = {"status": "ok" if all_ok else "degraded", "checks": checks}
    if errors:
        content["errors"] = errors
        content["hints"] = {
            "database_url": _mask_url(settings.database_url) if settings.database_url else "(not set)",
            "redis_url": _mask_url(settings.redis_url) if settings.redis_url else "(not set)",
        }

    return JSONResponse(status_code=status_code, content=content)


@router.get("/health/debug-auth")
async def debug_auth(request: Request) -> JSONResponse:
    """Temporary diagnostic endpoint: check auth state + user row (no auth required, read-only)."""
    from apps.api.app.db.connection import tenant_conn

    result: dict = {
        "has_role": hasattr(request.state, "role"),
        "role": getattr(request.state, "role", None),
        "has_tenant_id": hasattr(request.state, "tenant_id"),
        "tenant_id": getattr(request.state, "tenant_id", None),
    }

    auth_header = request.headers.get("Authorization", "")
    result["has_auth_header"] = bool(auth_header)

    x_tenant = request.headers.get("X-Tenant-ID", "")
    x_user = request.headers.get("X-User-ID", "")
    result["x_tenant_id_header"] = x_tenant
    result["x_user_id_header"] = x_user

    # Check if user and tenant exist in DB
    if x_tenant:
        try:
            async with tenant_conn(x_tenant) as conn:
                tenant_row = await conn.fetchrow(
                    "SELECT id, name FROM tenants WHERE id = $1", x_tenant
                )
                result["tenant_exists"] = tenant_row is not None
                if tenant_row:
                    result["tenant_name"] = tenant_row["name"]

                user_row = await conn.fetchrow(
                    "SELECT id, email, role, tenant_id FROM users WHERE tenant_id = $1",
                    x_tenant,
                )
                result["user_exists"] = user_row is not None
                if user_row:
                    result["user_id"] = user_row["id"]
                    result["user_email"] = user_row["email"]
                    result["user_role"] = user_row["role"]
                    result["user_tenant_id"] = user_row["tenant_id"]
        except Exception as e:
            result["db_error"] = f"{type(e).__name__}: {e}"

    return JSONResponse(status_code=200, content=result)
