"""H-01: Activity feed API tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-h01"


def _mock_tenant_conn(_tenant_id: str):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def test_activity_requires_tenant() -> None:
    r = client.get("/api/v1/activity")
    assert r.status_code == 400


def test_activity_success() -> None:
    with patch("apps.api.app.routers.activity.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get("/api/v1/activity", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert data["total"] == 0


def test_activity_invalid_since() -> None:
    with patch("apps.api.app.routers.activity.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get(
            "/api/v1/activity?since=not-a-date",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 400
