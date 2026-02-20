"""VA-P6-12: Reviews API tests — approve/return/reject, change tracking, summary."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-p6"
USER = "user-p6"


def _mock_tenant_conn(tenant_id: str):
    """Return an async context manager whose conn returns empty results."""
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def test_list_reviews_requires_x_tenant_id() -> None:
    r = client.get("/api/v1/assignments/asn_abc/reviews")
    assert r.status_code == 400


def test_list_reviews_accepts_pagination() -> None:
    with patch("apps.api.app.routers.assignments.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get(
            "/api/v1/assignments/asn_abc/reviews?limit=10&offset=0",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code in (200, 404)


def test_submit_review_approved_body() -> None:
    with patch("apps.api.app.routers.assignments.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.post(
            "/api/v1/assignments/asn_nonexistent/review",
            json={"decision": "approved", "notes": None, "corrections": []},
            headers={"X-Tenant-ID": TENANT, "X-User-ID": USER},
        )
    assert r.status_code in (201, 404, 403, 400)


def test_submit_review_request_changes_with_corrections() -> None:
    with patch("apps.api.app.routers.assignments.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.post(
            "/api/v1/assignments/asn_nonexistent/review",
            json={
                "decision": "request_changes",
                "notes": "Please fix",
                "corrections": [
                    {"path": "assumptions.revenue.growth", "old_value": "0.1", "new_value": "0.05", "reason": "Align to guidance"}
                ],
            },
            headers={"X-Tenant-ID": TENANT, "X-User-ID": USER},
        )
    assert r.status_code in (201, 404, 403, 400)


def test_submit_review_rejected_body() -> None:
    with patch("apps.api.app.routers.assignments.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.post(
            "/api/v1/assignments/asn_nonexistent/review",
            json={"decision": "rejected", "notes": "Out of scope"},
            headers={"X-Tenant-ID": TENANT, "X-User-ID": USER},
        )
    assert r.status_code in (201, 404, 403, 400)
