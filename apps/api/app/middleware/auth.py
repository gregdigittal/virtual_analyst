"""Auth middleware: verify Supabase JWT and set X-Tenant-ID / X-User-ID from token (C1)."""

from __future__ import annotations

import structlog
from starlette.requests import Request
from starlette.responses import JSONResponse

from apps.api.app.core.settings import get_settings

try:
    from jose import jwt as jose_jwt
except ImportError:
    jose_jwt = None  # type: ignore[assignment]

logger = structlog.get_logger()

# Paths that do not require or override tenant/user (health, metrics, public docs, cron)
SKIP_AUTH_PATHS = (
    "/",
    "/api/v1/health",
    "/api/v1/assignments/cron/deadline-reminders",
    "/metrics",
    "/openapi.json",
    "/docs",
    "/redoc",
)


def _should_skip_auth(path: str) -> bool:
    if path in SKIP_AUTH_PATHS:
        return True
    if path.startswith("/api/v1/health") or path.startswith("/docs") or path.startswith("/redoc"):
        return True
    return False


async def auth_middleware(request: Request, call_next):
    """When SUPABASE_JWT_SECRET is set, require Authorization: Bearer and verify the JWT;
    set X-Tenant-ID / X-User-ID from the token. Invalid or missing token returns 401.
    """
    path = request.url.path
    if _should_skip_auth(path):
        return await call_next(request)

    settings = get_settings()
    if not settings.supabase_jwt_secret:
        return await call_next(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Authorization header required"},
        )

    token = auth_header[7:].strip()
    if not token:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authorization header required"},
        )

    if jose_jwt is None:
        logger.warning("auth_jose_not_installed", msg="python-jose not installed; JWT verification disabled")
        return JSONResponse(
            status_code=501,
            content={"detail": "JWT verification not available"},
        )

    try:
        payload = jose_jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True},
        )
    except Exception as e:
        logger.warning("auth_jwt_invalid", path=path, error=str(e))
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired token"},
        )

    user_id = payload.get("sub")
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired token"},
        )

    app_meta = payload.get("app_metadata") or {}
    user_meta = payload.get("user_metadata") or {}
    tenant_id = (
        app_meta.get("tenant_id")
        or user_meta.get("tenant_id")
        or user_id
    )
    if not isinstance(tenant_id, str):
        tenant_id = user_id

    # Overwrite request scope headers so downstream Header() deps see verified values
    headers = list(request.scope.get("headers") or [])
    headers = [(k, v) for (k, v) in headers if k.lower() not in (b"x-tenant-id", b"x-user-id")]
    headers.append((b"x-tenant-id", tenant_id.encode("utf-8")))
    headers.append((b"x-user-id", user_id.encode("utf-8")))
    request.scope["headers"] = headers

    return await call_next(request)
