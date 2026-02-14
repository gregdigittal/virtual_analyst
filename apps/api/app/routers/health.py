from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from apps.api.app.core.settings import get_settings
from apps.api.app.db.connection import tenant_conn

router = APIRouter()


@router.get("/health/live")
async def liveness() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    settings = get_settings()
    checks: dict[str, str] = {}

    try:
        async with tenant_conn("") as conn:
            await conn.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        redis_client = Redis.from_url(settings.redis_url)
        try:
            await redis_client.ping()
            checks["redis"] = "ok"
        finally:
            await redis_client.close()
    except Exception:
        checks["redis"] = "error"

    all_ok = all(value == "ok" for value in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
    )
