"""H-01: Documents API tests — upload, list, get, delete (file upload + artifact store DI)."""
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
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _make_client_with_store(mock_store: MagicMock) -> TestClient:
    app.dependency_overrides[get_artifact_store] = lambda: mock_store
    return TestClient(app)


def _cleanup():
    app.dependency_overrides.pop(get_artifact_store, None)


def test_upload_requires_tenant() -> None:
    client = TestClient(app)
    r = client.post(
        "/api/v1/documents?entity_type=run&entity_id=r1",
        files={"file": ("test.pdf", b"data", "application/pdf")},
    )
    assert r.status_code == 400


def test_upload_invalid_entity_type() -> None:
    mock_store = MagicMock()
    client = _make_client_with_store(mock_store)
    try:
        with patch("apps.api.app.routers.documents.tenant_conn", side_effect=_mock_tenant_conn):
            r = client.post(
                "/api/v1/documents?entity_type=bogus&entity_id=r1",
                files={"file": ("test.pdf", b"data", "application/pdf")},
                headers=HEADERS,
            )
        assert r.status_code == 400
    finally:
        _cleanup()


def test_upload_success() -> None:
    mock_store = MagicMock()
    mock_store.save = MagicMock(return_value="path/to/doc")
    client = _make_client_with_store(mock_store)
    try:
        with patch("apps.api.app.routers.documents.tenant_conn", side_effect=_mock_tenant_conn):
            r = client.post(
                "/api/v1/documents?entity_type=run&entity_id=r1",
                files={"file": ("test.pdf", b"pdf-content", "application/pdf")},
                headers=HEADERS,
            )
        assert r.status_code == 201
        data = r.json()
        assert "document_id" in data
        assert data["filename"] == "test.pdf"
    finally:
        _cleanup()


def test_list_documents_success() -> None:
    with patch("apps.api.app.routers.documents.tenant_conn", side_effect=_mock_tenant_conn):
        client = TestClient(app)
        r = client.get(
            "/api/v1/documents?entity_type=run&entity_id=r1",
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert "items" in r.json()


def test_get_document_not_found() -> None:
    mock_store = MagicMock()
    client = _make_client_with_store(mock_store)
    try:
        with patch("apps.api.app.routers.documents.tenant_conn", side_effect=_mock_tenant_conn):
            r = client.get("/api/v1/documents/doc-999", headers=HEADERS)
        assert r.status_code == 404
    finally:
        _cleanup()


def test_delete_document_not_found() -> None:
    mock_store = MagicMock()
    client = _make_client_with_store(mock_store)
    try:
        with patch("apps.api.app.routers.documents.tenant_conn", side_effect=_mock_tenant_conn):
            r = client.delete("/api/v1/documents/doc-999", headers=HEADERS)
        assert r.status_code == 404
    finally:
        _cleanup()
