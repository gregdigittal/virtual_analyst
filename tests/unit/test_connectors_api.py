"""H-01: Connectors API tests — list and get (static registry, no DB)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-h01"


def test_list_connectors_requires_tenant() -> None:
    r = client.get("/api/v1/connectors")
    assert r.status_code == 400


def test_list_connectors_success() -> None:
    r = client.get("/api/v1/connectors", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    data = r.json()
    assert "connectors" in data
    ids = [c["connector_id"] for c in data["connectors"]]
    assert "quickbooks" in ids
    assert "xero" in ids


def test_get_connector_not_found() -> None:
    r = client.get("/api/v1/connectors/nonexistent", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 404


def test_get_connector_success() -> None:
    r = client.get("/api/v1/connectors/xero", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    data = r.json()
    assert data["connector_id"] == "xero"
    assert "features" in data
