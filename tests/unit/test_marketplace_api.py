"""H-01: Marketplace API tests — list templates, get template, use template."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.deps import get_llm_router
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


def _cleanup():
    app.dependency_overrides.pop(get_llm_router, None)


def test_list_templates_requires_tenant() -> None:
    r = TestClient(app).get("/api/v1/marketplace/templates")
    assert r.status_code == 400


def test_list_templates_success() -> None:
    with patch("apps.api.app.routers.marketplace.tenant_conn", side_effect=_mock_tenant_conn):
        r = TestClient(app).get("/api/v1/marketplace/templates", headers=HEADERS)
    assert r.status_code == 200
    assert "items" in r.json()


def test_get_template_not_found() -> None:
    with patch("apps.api.app.routers.marketplace.tenant_conn", side_effect=_mock_tenant_conn):
        r = TestClient(app).get("/api/v1/marketplace/templates/tpl-999", headers=HEADERS)
    assert r.status_code == 404


def test_use_template_not_found() -> None:
    mock_llm = MagicMock()
    app.dependency_overrides[get_llm_router] = lambda: mock_llm
    try:
        with patch("apps.api.app.routers.marketplace.tenant_conn", side_effect=_mock_tenant_conn):
            r = TestClient(app).post(
                "/api/v1/marketplace/templates/tpl-999/use",
                json={"label": "Test", "fiscal_year": "FY26"},
                headers=HEADERS,
            )
        assert r.status_code == 404
    finally:
        _cleanup()


def test_use_template_model_501() -> None:
    """Model template type returns 501 (not yet implemented)."""
    def _conn_model_template(_tid: str):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"template_id": "tpl-1", "name": "Test", "template_type": "model"})
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetch = AsyncMock(return_value=[])
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    mock_llm = MagicMock()
    app.dependency_overrides[get_llm_router] = lambda: mock_llm
    try:
        with patch("apps.api.app.routers.marketplace.tenant_conn", side_effect=_conn_model_template):
            r = TestClient(app).post(
                "/api/v1/marketplace/templates/tpl-1/use",
                json={"label": "Test", "fiscal_year": "FY26"},
                headers=HEADERS,
            )
        assert r.status_code == 501
    finally:
        _cleanup()
