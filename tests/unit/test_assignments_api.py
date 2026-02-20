"""VA-P6-12: Assignments API tests — create, claim, submit, status transitions."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-p6"
USER = "user-p6"


def test_list_assignments_requires_x_tenant_id() -> None:
    r = client.get("/api/v1/assignments")
    assert r.status_code == 400


def test_create_assignment_requires_x_tenant_id() -> None:
    r = client.post(
        "/api/v1/assignments",
        json={"entity_type": "draft", "entity_id": "d1"},
    )
    assert r.status_code == 400


def test_create_assignment_requires_entity_type() -> None:
    r = client.post(
        "/api/v1/assignments",
        json={"entity_id": "d1"},
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 422


def test_claim_assignment_requires_x_user_id() -> None:
    r = client.post(
        "/api/v1/assignments/asn_abc123/claim",
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 400


def test_submit_assignment_requires_x_user_id() -> None:
    r = client.post(
        "/api/v1/assignments/asn_abc123/submit",
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 400


def test_submit_review_requires_x_user_id() -> None:
    r = client.post(
        "/api/v1/assignments/asn_abc123/review",
        json={"decision": "approved"},
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 400


def test_submit_review_requires_valid_decision() -> None:
    r = client.post(
        "/api/v1/assignments/asn_abc123/review",
        json={"decision": "invalid"},
        headers={"X-Tenant-ID": TENANT, "X-User-ID": USER},
    )
    assert r.status_code == 400


def test_list_feedback_requires_x_user_id() -> None:
    r = client.get("/api/v1/feedback", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 400


def test_pool_requires_x_tenant_id() -> None:
    r = client.get("/api/v1/assignments/pool")
    assert r.status_code == 400
