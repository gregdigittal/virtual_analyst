"""H-01: Health API tests — liveness and readiness."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)


def _make_mock_pool(*, fail: bool = False):
    """Return a mock asyncpg pool with acquire/release."""
    mock_conn = MagicMock()
    if fail:
        mock_conn.execute = AsyncMock(side_effect=OSError("Connection refused"))
    else:
        mock_conn.execute = AsyncMock(return_value="SELECT 1")

    mock_pool = MagicMock()
    mock_pool.acquire = AsyncMock(return_value=mock_conn)
    mock_pool.release = AsyncMock()
    return mock_pool


def test_liveness() -> None:
    r = client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readiness_all_ok() -> None:
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock()
    mock_redis.close = AsyncMock()
    with (
        patch("apps.api.app.routers.health.get_pool", return_value=_make_mock_pool()),
        patch("apps.api.app.routers.health.Redis") as mock_redis_cls,
    ):
        mock_redis_cls.from_url.return_value = mock_redis
        r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["redis"] == "ok"


def test_readiness_degraded_db() -> None:
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock()
    mock_redis.close = AsyncMock()
    with (
        patch("apps.api.app.routers.health.get_pool", return_value=_make_mock_pool(fail=True)),
        patch("apps.api.app.routers.health.Redis") as mock_redis_cls,
    ):
        mock_redis_cls.from_url.return_value = mock_redis
        r = client.get("/api/v1/health/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
    assert r.json()["checks"]["database"] == "error"
