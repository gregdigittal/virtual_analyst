"""N-04: Rate-limiting tests for slowapi middleware."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.app.middleware.security import init_rate_limiting


class _TenantMiddleware(BaseHTTPMiddleware):
    """Simulate auth middleware: copy X-Tenant-ID header into request.state."""

    async def dispatch(self, request: Request, call_next):
        tid = request.headers.get("x-tenant-id")
        if tid:
            request.state.tenant_id = tid
        return await call_next(request)


def _make_app(limit: str = "100/minute") -> FastAPI:
    """Create a minimal FastAPI app with rate limiting configured."""
    test_app = FastAPI()
    init_rate_limiting(test_app, limit)
    # Added AFTER init_rate_limiting so it wraps the outer layer
    # and runs BEFORE SlowAPIMiddleware sees the request.
    test_app.add_middleware(_TenantMiddleware)

    @test_app.get("/ping")
    async def ping():
        return {"status": "ok"}

    return test_app


def test_rate_limit_allows_normal_traffic() -> None:
    """Send 5 requests — all should return 200 under 100/minute limit."""
    app = _make_app("100/minute")
    client = TestClient(app)
    for _ in range(5):
        r = client.get("/ping", headers={"X-Tenant-ID": "tenant-a"})
        assert r.status_code == 200


def test_rate_limit_returns_429() -> None:
    """With a 2/minute limit, the third request should return 429."""
    app = _make_app("2/minute")
    client = TestClient(app)
    headers = {"X-Tenant-ID": "tenant-a"}
    r1 = client.get("/ping", headers=headers)
    r2 = client.get("/ping", headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    r3 = client.get("/ping", headers=headers)
    assert r3.status_code == 429


def test_rate_limit_per_tenant() -> None:
    """Different X-Tenant-ID headers should have independent rate limit buckets."""
    app = _make_app("2/minute")
    client = TestClient(app)

    # Exhaust tenant A's limit
    client.get("/ping", headers={"X-Tenant-ID": "tenant-a"})
    client.get("/ping", headers={"X-Tenant-ID": "tenant-a"})
    r_a = client.get("/ping", headers={"X-Tenant-ID": "tenant-a"})
    assert r_a.status_code == 429

    # Tenant B should still be allowed
    r_b = client.get("/ping", headers={"X-Tenant-ID": "tenant-b"})
    assert r_b.status_code == 200


def test_rate_limit_429_body() -> None:
    """429 response should contain a rate limit exceeded error message."""
    app = _make_app("1/minute")
    client = TestClient(app)
    headers = {"X-Tenant-ID": "tenant-a"}
    client.get("/ping", headers=headers)
    r = client.get("/ping", headers=headers)
    assert r.status_code == 429
    body = r.json()
    assert "error" in body or "detail" in body or "Rate limit exceeded" in r.text


def test_rate_limit_on_post_endpoint() -> None:
    """Rate limiting should apply to POST endpoints, not just GET."""
    test_app = FastAPI()
    init_rate_limiting(test_app, "2/minute")
    test_app.add_middleware(_TenantMiddleware)

    @test_app.post("/write")
    async def write():
        return {"status": "written"}

    client = TestClient(test_app)
    headers = {"X-Tenant-ID": "tenant-post"}
    r1 = client.post("/write", headers=headers)
    r2 = client.post("/write", headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    r3 = client.post("/write", headers=headers)
    assert r3.status_code == 429


def test_rate_limit_no_tenant_id_still_applies() -> None:
    """Requests without X-Tenant-ID should still be rate-limited (fallback key)."""
    app = _make_app("2/minute")
    client = TestClient(app)
    # No X-Tenant-ID header — rate limiter falls back to IP-based key
    r1 = client.get("/ping")
    r2 = client.get("/ping")
    assert r1.status_code == 200
    assert r2.status_code == 200
    r3 = client.get("/ping")
    assert r3.status_code == 429


def test_rate_limit_different_tenants_independent_post() -> None:
    """POST requests from different tenants should have independent limits."""
    test_app = FastAPI()
    init_rate_limiting(test_app, "1/minute")
    test_app.add_middleware(_TenantMiddleware)

    @test_app.post("/action")
    async def action():
        return {"done": True}

    client = TestClient(test_app)
    # Exhaust tenant-x on POST
    client.post("/action", headers={"X-Tenant-ID": "tenant-x"})
    r_x = client.post("/action", headers={"X-Tenant-ID": "tenant-x"})
    assert r_x.status_code == 429

    # tenant-y still has quota
    r_y = client.post("/action", headers={"X-Tenant-ID": "tenant-y"})
    assert r_y.status_code == 200
