from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from apps.api.app.core.settings import get_settings
from apps.api.app.db.connection import get_conn

router = APIRouter()


@router.get("/health/live")
async def liveness() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    settings = get_settings()
    checks = {"database": "ok", "redis": "ok"}

    try:
        conn = await get_conn()
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.release() if hasattr(conn, "release") else await conn.close()
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    try:
        redis = Redis.from_url(settings.redis_url)
        await redis.ping()
        await redis.close()
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    all_ok = all(value == "ok" for value in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
    )
