"""Connectors API tests — list and get connector metadata (no DB)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.main import app
from apps.api.app.routers.connectors import CONNECTOR_REGISTRY

client = TestClient(app)
TENANT = "tenant-test"


def test_list_connectors_requires_tenant() -> None:
    r = client.get("/api/v1/connectors")
    assert r.status_code == 400


def test_list_connectors_success() -> None:
    r = client.get("/api/v1/connectors", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    data = r.json()
    assert "connectors" in data
    assert data["connectors"] == CONNECTOR_REGISTRY


def test_get_connector_not_found() -> None:
    r = client.get(
        "/api/v1/connectors/nonexistent",
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 404


def test_get_connector_success() -> None:
    valid_id = CONNECTOR_REGISTRY[0]["connector_id"]
    r = client.get(
        f"/api/v1/connectors/{valid_id}",
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["connector_id"] == valid_id
    assert "name" in data
    assert "config_schema" in data
