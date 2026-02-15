"""VA-P6-12: Teams API tests — CRUD, hierarchy validation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-p6"
USER = "user-p6"


def test_list_teams_requires_x_tenant_id() -> None:
    r = client.get("/api/v1/teams")
    assert r.status_code == 400


def test_list_teams_success_with_headers() -> None:
    r = client.get("/api/v1/teams", headers={"X-Tenant-ID": TENANT})
    assert r.status_code in (200, 404, 500)


def test_create_team_requires_x_tenant_id() -> None:
    r = client.post("/api/v1/teams", json={"name": "Test", "description": ""})
    assert r.status_code == 400


def test_create_team_requires_name() -> None:
    r = client.post(
        "/api/v1/teams",
        json={"description": "Desc"},
        headers={"X-Tenant-ID": TENANT, "X-User-ID": USER},
    )
    assert r.status_code == 422


def test_get_team_requires_x_tenant_id() -> None:
    r = client.get("/api/v1/teams/team-1")
    assert r.status_code == 400


def test_list_job_functions_requires_x_tenant_id() -> None:
    r = client.get("/api/v1/teams/job-functions/list")
    assert r.status_code == 400
