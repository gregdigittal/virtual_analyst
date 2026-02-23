"""H-01: CSV import API tests — file upload, validation, draft+scenario creation."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.deps import get_artifact_store
from apps.api.app.main import app

TENANT = "tenant-h01"
USER = "user-h01"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": USER}


def _mock_tenant_conn(_tenant_id: str):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value="baseline-1")
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    conn.transaction = MagicMock(return_value=MagicMock(
        __aenter__=AsyncMock(), __aexit__=AsyncMock(return_value=None),
    ))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _cleanup():
    app.dependency_overrides.pop(get_artifact_store, None)


def test_import_requires_tenant() -> None:
    client = TestClient(app)
    r = client.post(
        "/api/v1/import/csv?parent_baseline_id=b1",
        files={"file": ("data.csv", b"col1,col2\n1,2", "text/csv")},
    )
    assert r.status_code == 400


def test_import_non_csv_rejected() -> None:
    mock_store = MagicMock()
    app.dependency_overrides[get_artifact_store] = lambda: mock_store
    client = TestClient(app)
    try:
        with patch("apps.api.app.routers.import_csv.tenant_conn", side_effect=_mock_tenant_conn):
            r = client.post(
                "/api/v1/import/csv?parent_baseline_id=b1",
                files={"file": ("data.txt", b"hello", "text/plain")},
                headers=HEADERS,
            )
        assert r.status_code == 400
    finally:
        _cleanup()


def test_import_success() -> None:
    mock_store = MagicMock()
    mock_store.save = MagicMock(return_value="path")
    app.dependency_overrides[get_artifact_store] = lambda: mock_store
    client = TestClient(app)
    try:
        with (
            patch("apps.api.app.routers.import_csv.tenant_conn", side_effect=_mock_tenant_conn),
            patch("apps.api.app.routers.import_csv.ensure_tenant", new_callable=AsyncMock),
            patch("apps.api.app.routers.import_csv.create_audit_event", new_callable=AsyncMock),
        ):
            r = client.post(
                "/api/v1/import/csv?parent_baseline_id=b1",
                files={"file": ("data.csv", b"revenue,cost\n100,50", "text/csv")},
                headers=HEADERS,
            )
        assert r.status_code == 201
        data = r.json()
        assert "draft_session_id" in data
        assert "scenario_id" in data
    finally:
        _cleanup()
