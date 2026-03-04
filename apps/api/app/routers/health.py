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


## debug-auth endpoint REMOVED (2026-03-04)
## Was leaking PII (tenant_id, user_email, user_role) without authentication.
## See review finding S1 in docs/reviews/2026-03-04-comprehensive-platform-review.md
