from __future__ import annotations

import asyncpg
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from apps.api.app.core.settings import get_settings

router = APIRouter()


@router.get("/health/live")
async def liveness() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    settings = get_settings()
    checks = {"database": "ok", "redis": "ok"}

    try:
        conn = await asyncpg.connect(settings.database_url)
        await conn.execute("SELECT 1")
        await conn.close()
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
