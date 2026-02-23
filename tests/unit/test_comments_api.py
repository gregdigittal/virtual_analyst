"""H-01: Comments API tests — create, list, delete, @mention."""
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
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": USER}


def test_create_comment_requires_tenant() -> None:
    r = client.post("/api/v1/comments", json={"entity_type": "run", "entity_id": "r1", "body": "hi"})
    assert r.status_code == 400


def test_create_comment_invalid_entity_type() -> None:
    with patch("apps.api.app.routers.comments.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.post(
            "/api/v1/comments",
            json={"entity_type": "invalid_type", "entity_id": "r1", "body": "hi"},
            headers=HEADERS,
        )
    assert r.status_code == 400


def test_create_comment_success() -> None:
    with patch("apps.api.app.routers.comments.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.post(
            "/api/v1/comments",
            json={"entity_type": "run", "entity_id": "r1", "body": "looks good"},
            headers=HEADERS,
        )
    assert r.status_code == 201
    data = r.json()
    assert data["entity_type"] == "run"
    assert "comment_id" in data


def test_list_comments_requires_entity_params() -> None:
    r = client.get("/api/v1/comments", headers=HEADERS)
    assert r.status_code == 422


def test_list_comments_success() -> None:
    with patch("apps.api.app.routers.comments.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get(
            "/api/v1/comments?entity_type=baseline&entity_id=b1",
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert "items" in r.json()


def test_delete_comment_not_found() -> None:
    with patch("apps.api.app.routers.comments.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.delete("/api/v1/comments/cmt-999", headers=HEADERS)
    assert r.status_code == 404


def test_delete_comment_wrong_user() -> None:
    def _conn_with_row(_tid: str):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"created_by": "other-user"})
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.comments.tenant_conn", side_effect=_conn_with_row):
        r = client.delete("/api/v1/comments/cmt-1", headers=HEADERS)
    assert r.status_code == 403
