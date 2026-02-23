"""H-01: Compliance API tests — GDPR export and anonymize."""
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
    conn.transaction = MagicMock(return_value=MagicMock(
        __aenter__=AsyncMock(), __aexit__=AsyncMock(return_value=None),
    ))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def test_export_requires_admin() -> None:
    r = client.get(f"/api/v1/compliance/export?user_id={USER}", headers=HEADERS)
    assert r.status_code == 403


def test_export_self_only() -> None:
    """Cannot export another user's data."""
    with patch("apps.api.app.deps.ROLE_ANALYST", "owner"):
        r = client.get(
            "/api/v1/compliance/export?user_id=other-user",
            headers=HEADERS,
        )
    assert r.status_code == 403


def test_export_success() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.compliance.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.compliance.list_audit_events", new_callable=AsyncMock, return_value=[]),
        patch("apps.api.app.routers.compliance.create_audit_event", new_callable=AsyncMock),
    ):
        r = client.get(f"/api/v1/compliance/export?user_id={USER}", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["user_id"] == USER
    assert "audit_events" in data
    assert "drafts" in data


def test_anonymize_requires_admin() -> None:
    r = client.post(f"/api/v1/compliance/anonymize-user?user_id={USER}", headers=HEADERS)
    assert r.status_code == 403


def test_anonymize_self_only() -> None:
    with patch("apps.api.app.deps.ROLE_ANALYST", "owner"):
        r = client.post(
            "/api/v1/compliance/anonymize-user?user_id=other-user",
            headers=HEADERS,
        )
    assert r.status_code == 403


def test_anonymize_success() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.compliance.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.compliance.create_audit_event", new_callable=AsyncMock),
    ):
        r = client.post(f"/api/v1/compliance/anonymize-user?user_id={USER}", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "anonymized"
