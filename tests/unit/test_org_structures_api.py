"""H-01: Org structures API tests — CRUD for orgs, entities, ownership, intercompany, hierarchy, validate."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.deps import get_artifact_store
from apps.api.app.main import app

TENANT = "tenant-h01"
USER = "user-h01"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": USER}
ORG = "og-test1"


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


def _cleanup():
    app.dependency_overrides.pop(get_artifact_store, None)


# ----- Org structure CRUD -----

def test_create_org_requires_admin() -> None:
    r = TestClient(app).post(
        "/api/v1/org-structures",
        json={"group_name": "Test Group"},
        headers=HEADERS,
    )
    assert r.status_code == 403


def test_create_org_success() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.org_structures.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.org_structures.ensure_tenant", new_callable=AsyncMock),
    ):
        r = TestClient(app).post(
            "/api/v1/org-structures",
            json={"group_name": "Holdings Ltd"},
            headers=HEADERS,
        )
    assert r.status_code == 201
    assert "org_id" in r.json()


def test_list_orgs_success() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.org_structures.tenant_conn", side_effect=_mock_tenant_conn),
    ):
        r = TestClient(app).get("/api/v1/org-structures", headers=HEADERS)
    assert r.status_code == 200
    assert "items" in r.json()


def test_get_org_not_found() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.org_structures.tenant_conn", side_effect=_mock_tenant_conn),
    ):
        r = TestClient(app).get(f"/api/v1/org-structures/{ORG}", headers=HEADERS)
    assert r.status_code == 404


def test_delete_org_not_found() -> None:
    def _conn_delete_0(_tid: str):
        conn = MagicMock()
        conn.execute = AsyncMock(return_value="DELETE 0")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.org_structures.tenant_conn", side_effect=_conn_delete_0),
    ):
        r = TestClient(app).delete(f"/api/v1/org-structures/{ORG}", headers=HEADERS)
    assert r.status_code == 404


# ----- Entity CRUD -----

def test_create_entity_org_not_found() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.org_structures.tenant_conn", side_effect=_mock_tenant_conn),
    ):
        r = TestClient(app).post(
            f"/api/v1/org-structures/{ORG}/entities",
            json={"name": "OpCo"},
            headers=HEADERS,
        )
    assert r.status_code == 404


def test_create_entity_success() -> None:
    def _conn_with_org(_tid: str):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={"org_id": ORG})
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.org_structures.tenant_conn", side_effect=_conn_with_org),
    ):
        r = TestClient(app).post(
            f"/api/v1/org-structures/{ORG}/entities",
            json={"name": "OpCo UK", "currency": "GBP", "country_iso": "GB"},
            headers=HEADERS,
        )
    assert r.status_code == 201
    assert "entity_id" in r.json()


def test_list_entities_success() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.org_structures.tenant_conn", side_effect=_mock_tenant_conn),
    ):
        r = TestClient(app).get(f"/api/v1/org-structures/{ORG}/entities", headers=HEADERS)
    assert r.status_code == 200
    assert "items" in r.json()


# ----- Ownership -----

def test_create_ownership_parent_equals_child() -> None:
    with patch("apps.api.app.deps.ROLE_ANALYST", "owner"):
        r = TestClient(app).post(
            f"/api/v1/org-structures/{ORG}/ownership",
            json={"parent_entity_id": "e1", "child_entity_id": "e1", "ownership_pct": 100},
            headers=HEADERS,
        )
    assert r.status_code == 400


def test_create_ownership_over_100_rejected() -> None:
    """Total ownership for child would exceed 100%."""
    def _conn_existing_80(_tid: str):
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[{"ownership_pct": 80}])
        conn.execute = AsyncMock()
        conn.transaction = MagicMock(return_value=MagicMock(
            __aenter__=AsyncMock(), __aexit__=AsyncMock(return_value=None),
        ))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.org_structures.tenant_conn", side_effect=_conn_existing_80),
    ):
        r = TestClient(app).post(
            f"/api/v1/org-structures/{ORG}/ownership",
            json={"parent_entity_id": "e1", "child_entity_id": "e2", "ownership_pct": 30},
            headers=HEADERS,
        )
    assert r.status_code == 400


def test_list_ownership_success() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.org_structures.tenant_conn", side_effect=_mock_tenant_conn),
    ):
        r = TestClient(app).get(f"/api/v1/org-structures/{ORG}/ownership", headers=HEADERS)
    assert r.status_code == 200
    assert "items" in r.json()


# ----- Intercompany -----

def test_create_intercompany_same_entity() -> None:
    with patch("apps.api.app.deps.ROLE_ANALYST", "owner"):
        r = TestClient(app).post(
            f"/api/v1/org-structures/{ORG}/intercompany",
            json={"from_entity_id": "e1", "to_entity_id": "e1"},
            headers=HEADERS,
        )
    assert r.status_code == 400


def test_list_intercompany_success() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.org_structures.tenant_conn", side_effect=_mock_tenant_conn),
    ):
        r = TestClient(app).get(f"/api/v1/org-structures/{ORG}/intercompany", headers=HEADERS)
    assert r.status_code == 200
    assert "items" in r.json()


# ----- Hierarchy -----

def test_hierarchy_empty() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.org_structures.tenant_conn", side_effect=_mock_tenant_conn),
    ):
        r = TestClient(app).get(f"/api/v1/org-structures/{ORG}/hierarchy", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["roots"] == []


# ----- Validate -----

def test_validate_no_entities() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.org_structures.tenant_conn", side_effect=_mock_tenant_conn),
    ):
        r = TestClient(app).post(f"/api/v1/org-structures/{ORG}/validate", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "failed"  # no root entity


# ----- Consolidated runs -----

def test_list_consolidated_runs() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.org_structures.tenant_conn", side_effect=_mock_tenant_conn),
    ):
        r = TestClient(app).get(f"/api/v1/org-structures/{ORG}/runs", headers=HEADERS)
    assert r.status_code == 200
    assert "items" in r.json()
