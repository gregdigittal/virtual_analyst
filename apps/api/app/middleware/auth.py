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

# Paths that do not require or override tenant/user (health, metrics, public docs, cron, SAML, Stripe webhook, public catalog)
SKIP_AUTH_PATHS = (
    "/",
    "/api/v1/health",
    "/api/v1/assignments/cron/deadline-reminders",
    "/api/v1/auth/saml/login",
    "/api/v1/auth/saml/acs",
    "/api/v1/billing/webhook",
    "/api/v1/billing/plans",
    "/openapi.json",
    "/docs",
    "/redoc",
)


def _should_skip_auth(path: str) -> bool:
    if path in SKIP_AUTH_PATHS:
        return True
    if path.startswith("/api/v1/health") or path.startswith("/docs") or path.startswith("/redoc"):
        return True
    # Only skip auth for SAML login and ACS, NOT config (R11-03)
    if path in ("/api/v1/auth/saml/login", "/api/v1/auth/saml/acs"):
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
        # python-jose 3.x requires audience as a string; decode without audience
        # check first, then verify manually to support both "authenticated" and "va-saml".
        payload = jose_jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_exp": True, "verify_aud": False},
        )
        token_aud = payload.get("aud")
        allowed_audiences = {"authenticated", "va-saml"}
        if isinstance(token_aud, list):
            if not set(token_aud) & allowed_audiences:
                raise ValueError("Invalid audience")
        elif token_aud not in allowed_audiences:
            raise ValueError("Invalid audience")
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
    settings = get_settings()
    tenant_id = app_meta.get("tenant_id") or user_meta.get("tenant_id")
    if not tenant_id:
        if settings.environment in ("development", "test"):
            tenant_id = user_id
        else:
            return JSONResponse(status_code=403, content={"error": "No tenant_id in token"})
    if not isinstance(tenant_id, str):
        if settings.environment in ("development", "test"):
            tenant_id = str(tenant_id) if tenant_id else user_id
        else:
            return JSONResponse(status_code=403, content={"error": "Invalid tenant_id type in token"})

    # Overwrite request scope headers so downstream Header() deps see verified values
    headers = list(request.scope.get("headers") or [])
    headers = [(k, v) for (k, v) in headers if k.lower() not in (b"x-tenant-id", b"x-user-id")]
    headers.append((b"x-tenant-id", tenant_id.encode("utf-8")))
    headers.append((b"x-user-id", user_id.encode("utf-8")))
    request.scope["headers"] = headers
    request.state.tenant_id = tenant_id

    structlog.contextvars.bind_contextvars(
        tenant_id=tenant_id,
        user_id=user_id,
    )

    # Load role from users table for RBAC; fallback to investor if no row (e.g. dev without sync)
    try:
        from apps.api.app.db.connection import tenant_conn

        async with tenant_conn(tenant_id) as conn:
            row = await conn.fetchrow(
                "SELECT role FROM users WHERE id = $1 AND tenant_id = $2",
                user_id,
                tenant_id,
            )
        request.state.role = row["role"] if row else "investor"
    except Exception as e:
        logger.warning("auth_role_lookup_failed", user_id=user_id, error=str(e))
        request.state.role = "investor"

    return await call_next(request)
