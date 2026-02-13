from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-1"


def test_create_changeset_requires_x_tenant_id() -> None:
    r = client.post("/api/v1/changesets", json={"baseline_id": "bl_1", "base_version": "v1", "overrides": []})
    assert r.status_code == 400


def test_create_changeset_requires_baseline_id() -> None:
    r = client.post(
        "/api/v1/changesets",
        json={"base_version": "v1", "overrides": []},
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 400
