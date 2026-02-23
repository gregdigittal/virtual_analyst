"""H-01: Notifications API tests — list and mark read."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-h01"
USER = "user-h01"


def _mock_tenant_conn(_tenant_id: str):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value={"n": 0})
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def test_list_notifications_requires_tenant() -> None:
    r = client.get("/api/v1/notifications")
    assert r.status_code == 400


def test_list_notifications_success() -> None:
    with patch("apps.api.app.routers.notifications.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get(
            "/api/v1/notifications",
            headers={"X-Tenant-ID": TENANT, "X-User-ID": USER},
        )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert data["unread_count"] == 0


def test_mark_read_not_found() -> None:
    def _conn_no_row(_tid: str):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.notifications.tenant_conn", side_effect=_conn_no_row):
        r = client.patch(
            "/api/v1/notifications/notif-999",
            headers={"X-Tenant-ID": TENANT, "X-User-ID": USER},
        )
    assert r.status_code == 404


def test_mark_read_wrong_user() -> None:
    def _conn_with_row(_tid: str):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"id": "n1", "user_id": "other-user", "read_at": None})
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.notifications.tenant_conn", side_effect=_conn_with_row):
        r = client.patch(
            "/api/v1/notifications/n1",
            headers={"X-Tenant-ID": TENANT, "X-User-ID": USER},
        )
    assert r.status_code == 403
