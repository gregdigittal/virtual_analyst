"""H-01: Feedback API tests — list and acknowledge."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-h01"
USER = "user-h01"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": USER}


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


def test_list_feedback_requires_headers() -> None:
    r = client.get("/api/v1/feedback")
    assert r.status_code == 400


def test_list_feedback_success() -> None:
    with patch("apps.api.app.routers.feedback.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get("/api/v1/feedback", headers=HEADERS)
    assert r.status_code == 200
    assert "items" in r.json()


def test_acknowledge_not_found() -> None:
    with patch("apps.api.app.routers.feedback.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.post("/api/v1/feedback/sum-999/acknowledge", headers=HEADERS)
    assert r.status_code == 404


def test_acknowledge_success() -> None:
    def _conn_with_row(_tid: str):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"summary_id": "sum-1", "acknowledged_at": None})
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.feedback.tenant_conn", side_effect=_conn_with_row):
        r = client.post("/api/v1/feedback/sum-1/acknowledge", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["acknowledged"] is True
