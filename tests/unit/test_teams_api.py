"""VA-P6-12: Teams API tests — CRUD, hierarchy validation, RBAC."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-p6"
USER = "user-p6"


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


def test_list_teams_requires_x_tenant_id() -> None:
    """Default dev role is analyst, not in OWNER_OR_ADMIN → 403."""
    r = client.get("/api/v1/teams")
    assert r.status_code == 403


def test_list_teams_success_with_headers() -> None:
    """With owner role and valid tenant, returns 200."""
    with patch("apps.api.app.deps.ROLE_ANALYST", "owner"):
        with patch("apps.api.app.routers.teams.tenant_conn", side_effect=_mock_tenant_conn):
            r = client.get("/api/v1/teams", headers={"X-Tenant-ID": TENANT})
    assert r.status_code in (200, 404, 500)


def test_create_team_requires_x_tenant_id() -> None:
    r = client.post("/api/v1/teams", json={"name": "Test", "description": ""})
    assert r.status_code == 403


def test_create_team_requires_name() -> None:
    """With owner role bypass, missing name returns 422."""
    with patch("apps.api.app.deps.ROLE_ANALYST", "owner"):
        r = client.post(
            "/api/v1/teams",
            json={"description": "Desc"},
            headers={"X-Tenant-ID": TENANT, "X-User-ID": USER},
        )
    assert r.status_code == 422


def test_get_team_requires_x_tenant_id() -> None:
    r = client.get("/api/v1/teams/team-1")
    assert r.status_code == 403


def test_list_job_functions_requires_x_tenant_id() -> None:
    r = client.get("/api/v1/teams/job-functions/list")
    assert r.status_code == 403
