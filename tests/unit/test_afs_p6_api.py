"""Unit tests for AFS Phase 6 API endpoints (custom frameworks + roll-forward)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.deps import get_llm_router
from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-afs-p6"
USER = "user-afs-p6"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": USER}


def _mock_tenant_conn(_tenant_id: str) -> MagicMock:
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _setup_llm() -> MagicMock:
    mock_llm = MagicMock()
    app.dependency_overrides[get_llm_router] = lambda: mock_llm
    return mock_llm


def _cleanup() -> None:
    app.dependency_overrides.pop(get_llm_router, None)


# ---------------------------------------------------------------------------
# POST /frameworks/infer
# ---------------------------------------------------------------------------


def test_infer_framework_requires_tenant() -> None:
    r = client.post(
        "/api/v1/afs/frameworks/infer",
        json={"description": "A small retail company"},
    )
    assert r.status_code == 400


def test_infer_framework_happy_path() -> None:
    """Returns framework_id and items_count when AI inference succeeds."""
    mock_llm = _setup_llm()
    try:
        # Mock the LLM response
        llm_response = MagicMock()
        llm_response.content = {
            "name": "Inferred Framework",
            "disclosure_schema": {"sections": []},
            "statement_templates": {},
            "suggested_items": [
                {"section": "Revenue", "reference": "IFRS 15.1", "description": "Revenue recognition", "required": True},
                {"section": "Tax", "reference": "IAS 12.1", "description": "Deferred tax", "required": True},
            ],
        }
        mock_llm.complete_with_routing = AsyncMock(return_value=llm_response)

        # Mock the framework row returned from DB
        expected_row = {
            "framework_id": "afw_abc123",
            "tenant_id": TENANT,
            "name": "Inferred Framework",
            "standard": "custom",
            "version": "1.0",
            "is_builtin": False,
        }

        def _conn_with_insert(_tenant_id: str) -> MagicMock:
            conn = MagicMock()
            conn.fetchrow = AsyncMock(return_value=expected_row)
            conn.execute = AsyncMock()
            cm = MagicMock()
            cm.__aenter__ = AsyncMock(return_value=conn)
            cm.__aexit__ = AsyncMock(return_value=None)
            return cm

        with (
            patch("apps.api.app.routers.afs.frameworks.tenant_conn", side_effect=_conn_with_insert),
            patch(
                "apps.api.app.services.afs.framework_ai.infer_framework",
                new_callable=AsyncMock,
                return_value=llm_response,
            ),
        ):
            r = client.post(
                "/api/v1/afs/frameworks/infer",
                json={"description": "A small retail company in South Africa", "jurisdiction": "South Africa"},
                headers=HEADERS,
            )

        assert r.status_code == 200
        data = r.json()
        assert data["framework_id"] == "afw_abc123"
        assert data["items_count"] == 2  # 2 suggested items seeded
    finally:
        _cleanup()


def test_infer_framework_no_body_description() -> None:
    """Returns 422 when description is missing (Pydantic validation)."""
    _setup_llm()
    try:
        r = client.post(
            "/api/v1/afs/frameworks/infer",
            json={"jurisdiction": "South Africa"},  # missing description
            headers=HEADERS,
        )
        assert r.status_code == 422
    finally:
        _cleanup()


# ---------------------------------------------------------------------------
# POST /engagements/{id}/rollforward
# ---------------------------------------------------------------------------


def test_rollforward_requires_tenant() -> None:
    r = client.post("/api/v1/afs/engagements/eng-1/rollforward")
    assert r.status_code == 400


def test_rollforward_engagement_not_found() -> None:
    """Returns 404 when engagement does not exist."""
    with patch("apps.api.app.routers.afs.engagements.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.post(
            "/api/v1/afs/engagements/nonexistent/rollforward",
            headers=HEADERS,
        )
    assert r.status_code == 404


def test_rollforward_no_prior_engagement_id() -> None:
    """Returns 400 when engagement has no prior_engagement_id set."""

    def _conn_no_prior(_tenant_id: str) -> MagicMock:
        conn = MagicMock()
        # fetchrow returns engagement with no prior
        conn.fetchrow = AsyncMock(return_value={"engagement_id": "eng-1", "prior_engagement_id": None})
        conn.fetchval = AsyncMock(return_value=None)
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.afs.engagements.tenant_conn", side_effect=_conn_no_prior):
        r = client.post(
            "/api/v1/afs/engagements/eng-1/rollforward",
            headers=HEADERS,
        )
    assert r.status_code == 400
    assert "prior" in r.json()["detail"].lower()


def test_rollforward_prior_not_found() -> None:
    """Returns 404 when the prior engagement referenced does not exist."""

    call_count = 0

    def _conn_missing_prior(_tenant_id: str) -> MagicMock:
        nonlocal call_count
        conn = MagicMock()
        call_count += 1
        # fetchrow returns engagement with prior_id; fetchval returns None (prior not found)
        conn.fetchrow = AsyncMock(return_value={"engagement_id": "eng-1", "prior_engagement_id": "eng-prior"})
        conn.fetchval = AsyncMock(return_value=None)
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.afs.engagements.tenant_conn", side_effect=_conn_missing_prior):
        r = client.post(
            "/api/v1/afs/engagements/eng-1/rollforward",
            headers=HEADERS,
        )
    assert r.status_code == 404


def test_rollforward_happy_path() -> None:
    """Returns sections_copied and comparatives_copied on success."""

    def _conn_with_prior(_tenant_id: str) -> MagicMock:
        conn = MagicMock()
        # fetchrow: engagement with prior_id
        # fetchval: prior engagement exists
        conn.fetchrow = AsyncMock(return_value={"engagement_id": "eng-1", "prior_engagement_id": "eng-prior"})
        conn.fetchval = AsyncMock(return_value="eng-prior")
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    sections_result = {"sections_copied": 3, "sections": [{"section_id": "asc_1", "title": "PP&E", "section_type": "note", "rolled_forward_from": "asc_src"}]}
    comparatives_result = {"comparatives_copied": True, "trial_balance_id": "atb_new"}

    with (
        patch("apps.api.app.routers.afs.engagements.tenant_conn", side_effect=_conn_with_prior),
        patch(
            "apps.api.app.services.afs.rollforward.rollforward_sections",
            new_callable=AsyncMock,
            return_value=sections_result,
        ),
        patch(
            "apps.api.app.services.afs.rollforward.rollforward_comparatives",
            new_callable=AsyncMock,
            return_value=comparatives_result,
        ),
    ):
        r = client.post(
            "/api/v1/afs/engagements/eng-1/rollforward",
            headers=HEADERS,
        )

    assert r.status_code == 200
    data = r.json()
    assert data["sections_copied"] == 3
    assert data["comparatives_copied"] is True
    assert len(data["sections"]) == 1


# ---------------------------------------------------------------------------
# POST /frameworks/{framework_id}/items
# ---------------------------------------------------------------------------


def test_add_disclosure_item_happy_path() -> None:
    """Creates a disclosure item and returns 201."""
    expected_item = {
        "item_id": "adi_abc123",
        "framework_id": "afw_fw1",
        "section": "Revenue",
        "reference": "IFRS 15.1",
        "description": "Revenue recognition policy",
        "required": True,
        "applicable_entity_types": None,
    }

    def _conn_with_framework(_tenant_id: str) -> MagicMock:
        conn = MagicMock()
        conn.fetchval = AsyncMock(return_value="afw_fw1")  # framework exists
        conn.fetchrow = AsyncMock(return_value=expected_item)
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.afs.frameworks.tenant_conn", side_effect=_conn_with_framework):
        r = client.post(
            "/api/v1/afs/frameworks/afw_fw1/items",
            json={"section": "Revenue", "reference": "IFRS 15.1", "description": "Revenue recognition policy", "required": True},
            headers=HEADERS,
        )

    assert r.status_code == 201
    data = r.json()
    assert data["item_id"] == "adi_abc123"
    assert data["section"] == "Revenue"


def test_add_disclosure_item_framework_not_found() -> None:
    """Returns 404 when framework_id does not exist."""

    def _conn_no_fw(_tenant_id: str) -> MagicMock:
        conn = MagicMock()
        conn.fetchval = AsyncMock(return_value=None)  # framework not found
        conn.fetchrow = AsyncMock(return_value=None)
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.afs.frameworks.tenant_conn", side_effect=_conn_no_fw):
        r = client.post(
            "/api/v1/afs/frameworks/nonexistent/items",
            json={"section": "Revenue", "reference": "IFRS 15.1", "description": "Revenue recognition", "required": True},
            headers=HEADERS,
        )
    assert r.status_code == 404
