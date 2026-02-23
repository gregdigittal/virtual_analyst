"""H-01: Health API tests — liveness and readiness."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)


def _mock_tenant_conn(_tenant_id: str):
    conn = MagicMock()
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def test_liveness() -> None:
    r = client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_readiness_all_ok() -> None:
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock()
    mock_redis.close = AsyncMock()
    with (
        patch("apps.api.app.routers.health.tenant_conn", side_effect=_mock_tenant_conn),
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
    def _failing_conn(_tid: str):
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(side_effect=OSError("Connection refused"))
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock()
    mock_redis.close = AsyncMock()
    with (
        patch("apps.api.app.routers.health.tenant_conn", side_effect=_failing_conn),
        patch("apps.api.app.routers.health.Redis") as mock_redis_cls,
    ):
        mock_redis_cls.from_url.return_value = mock_redis
        r = client.get("/api/v1/health/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
    assert r.json()["checks"]["database"] == "error"
