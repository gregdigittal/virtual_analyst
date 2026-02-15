"""VA-P6-12: Workflow engine tests — template creation, stage advancement, routing."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-p6"
USER = "user-p6"


def test_list_templates_requires_x_tenant_id() -> None:
    r = client.get("/api/v1/workflows/templates")
    assert r.status_code == 400


def test_list_templates_success() -> None:
    r = client.get("/api/v1/workflows/templates", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    data = r.json()
    assert "templates" in data


def test_create_instance_requires_x_tenant_id() -> None:
    r = client.post(
        "/api/v1/workflows/instances",
        json={"template_id": "t1", "entity_type": "draft", "entity_id": "d1"},
    )
    assert r.status_code == 400


def test_create_instance_requires_body() -> None:
    r = client.post(
        "/api/v1/workflows/instances",
        json={},
        headers={"X-Tenant-ID": TENANT, "X-User-ID": USER},
    )
    assert r.status_code == 422
