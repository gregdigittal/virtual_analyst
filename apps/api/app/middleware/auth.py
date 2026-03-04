"""Auth middleware: verify Supabase JWT and set X-Tenant-ID / X-User-ID from token (C1)."""

from __future__ import annotations

import time

import httpx
import structlog
from starlette.requests import Request
from starlette.responses import JSONResponse

from apps.api.app.core.settings import get_settings

try:
    from jose import jwt as jose_jwt
except ImportError:
    jose_jwt = None  # type: ignore[assignment]

logger = structlog.get_logger()

# ──────────────────────────────────────────────────────────────────────
# JWKS cache for ES256 verification (Supabase migrated JWT signing keys)
# ──────────────────────────────────────────────────────────────────────
_jwks_cache: dict | None = None
_jwks_cache_time: float = 0.0
_JWKS_CACHE_TTL = 3600  # refresh JWKS every hour


def _get_jwks(supabase_url: str) -> dict:
    """Fetch and cache JWKS from Supabase for ES256 token verification."""
    global _jwks_cache, _jwks_cache_time
    now = time.monotonic()
    if _jwks_cache and (now - _jwks_cache_time) < _JWKS_CACHE_TTL:
        return _jwks_cache
    jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    try:
        resp = httpx.get(jwks_url, timeout=10.0)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cache_time = now
        logger.info("jwks_fetched", url=jwks_url, keys=len(_jwks_cache.get("keys", [])))
        return _jwks_cache
    except Exception as e:
        logger.error("jwks_fetch_failed", url=jwks_url, error=str(e))
        if _jwks_cache:
            return _jwks_cache  # return stale cache on failure
        raise


def _find_jwk_for_kid(jwks: dict, kid: str) -> dict | None:
    """Find a JWK matching the given key ID."""
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None

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
    # Allow CORS preflight requests through without auth so CORSMiddleware can handle them
    if request.method == "OPTIONS":
        return await call_next(request)

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

    alg = "unknown"
    try:
        # Peek at the token header to determine the algorithm.
        # Supabase projects may use legacy HS256 or migrated ES256 signing keys.
        unverified_header = jose_jwt.get_unverified_header(token)
        alg = unverified_header.get("alg", "HS256")

        if alg == "ES256":
            # ES256 (ECDSA) — fetch public key from Supabase JWKS endpoint
            kid = unverified_header.get("kid")
            if not kid:
                raise ValueError("ES256 token missing kid in header")
            jwks = _get_jwks(settings.supabase_url)
            jwk_data = _find_jwk_for_kid(jwks, kid)
            if not jwk_data:
                # Force refresh cache in case keys rotated
                global _jwks_cache_time
                _jwks_cache_time = 0.0
                jwks = _get_jwks(settings.supabase_url)
                jwk_data = _find_jwk_for_kid(jwks, kid)
            if not jwk_data:
                raise ValueError(f"No JWKS key found for kid={kid}")
            payload = jose_jwt.decode(
                token,
                jwk_data,
                algorithms=["ES256"],
                options={"verify_exp": True, "verify_aud": False},
            )
        else:
            # Legacy HS256 — use the shared JWT secret
            payload = jose_jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_exp": True, "verify_aud": False},
            )

        # Verify audience for both algorithm paths
        token_aud = payload.get("aud")
        allowed_audiences = {"authenticated", "va-saml"}
        if isinstance(token_aud, list):
            if not set(token_aud) & allowed_audiences:
                raise ValueError("Invalid audience")
        elif token_aud not in allowed_audiences:
            raise ValueError("Invalid audience")
    except Exception as e:
        logger.warning("auth_jwt_invalid", path=path, alg=alg, error=str(e))
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
    tenant_id = app_meta.get("tenant_id") or user_meta.get("tenant_id")
    if not tenant_id:
        # Fallback: use user_id as tenant_id for single-tenant-per-user setups.
        # Auth Hooks can inject tenant_id into app_metadata for multi-tenant use.
        tenant_id = user_id
        logger.info("auth_tenant_fallback", user_id=user_id, msg="Using user_id as tenant_id")
    if not isinstance(tenant_id, str):
        tenant_id = str(tenant_id) if tenant_id else user_id

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
