"""Unit tests for ventures API (VA-P2-07): venture wizard and generate-draft."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.api.app.deps import get_artifact_store, get_llm_router
from apps.api.app.main import app
from shared.fm_shared.storage import ArtifactStore

@pytest.fixture(autouse=True)
def ventures_shared_store() -> None:
    store = ArtifactStore(supabase_client=None)
    app.dependency_overrides[get_artifact_store] = lambda: store
    yield
    app.dependency_overrides.pop(get_artifact_store, None)


client = TestClient(app)
TENANT = "tenant-1"


def test_create_venture_requires_x_tenant_id() -> None:
    r = client.post("/api/v1/ventures", json={"template_id": "manufacturing_discrete", "entity_name": "Acme"})
    assert r.status_code == 400


def test_create_venture_returns_404_for_unknown_template() -> None:
    r = client.post(
        "/api/v1/ventures",
        json={"template_id": "nonexistent_template", "entity_name": "Acme"},
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 404


def test_create_venture_success() -> None:
    r = client.post(
        "/api/v1/ventures",
        json={"template_id": "manufacturing_discrete", "entity_name": "Acme Inc"},
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 201
    data = r.json()
    assert "venture_id" in data
    assert data["venture_id"].startswith("vc_")
    assert data["template_id"] == "manufacturing_discrete"
    assert data["entity_name"] == "Acme Inc"
    assert "question_plan" in data
    assert isinstance(data["question_plan"], list)


def test_submit_answers_requires_x_tenant_id() -> None:
    r = client.post("/api/v1/ventures/vc_123/answers", json={"answers": {"rs_1": "One product line."}})
    assert r.status_code == 400


def test_submit_answers_returns_404_for_unknown_venture() -> None:
    r = client.post(
        "/api/v1/ventures/vc_nonexistent/answers",
        json={"answers": {"rs_1": "One product."}},
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 404


def test_submit_answers_merge() -> None:
    create_r = client.post(
        "/api/v1/ventures",
        json={"template_id": "manufacturing_discrete", "entity_name": "Test"},
        headers={"X-Tenant-ID": TENANT},
    )
    assert create_r.status_code == 201
    venture_id = create_r.json()["venture_id"]
    r = client.post(
        f"/api/v1/ventures/{venture_id}/answers",
        json={"answers": {"rs_1": "Single product.", "cap_1": "Machine capacity."}},
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["venture_id"] == venture_id
    assert data["answers"]["rs_1"] == "Single product."
    assert data["answers"]["cap_1"] == "Machine capacity."


def test_generate_draft_requires_x_tenant_id() -> None:
    r = client.post("/api/v1/ventures/vc_123/generate-draft")
    assert r.status_code == 400


def test_generate_draft_returns_404_for_unknown_venture() -> None:
    r = client.post(
        "/api/v1/ventures/vc_nonexistent/generate-draft",
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 404


@patch("apps.api.app.routers.ventures.tenant_conn")
def test_generate_draft_creates_draft_from_questionnaire(mock_tenant_conn: MagicMock) -> None:
    create_r = client.post(
        "/api/v1/ventures",
        json={"template_id": "manufacturing_discrete", "entity_name": "Acme"},
        headers={"X-Tenant-ID": TENANT},
    )
    assert create_r.status_code == 201
    venture_id = create_r.json()["venture_id"]
    client.post(
        f"/api/v1/ventures/{venture_id}/answers",
        json={"answers": {"rs_1": "One product.", "cap_1": "Machine capacity."}},
        headers={"X-Tenant-ID": TENANT},
    )
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_transaction = MagicMock()
    mock_transaction.__aenter__ = AsyncMock(return_value=None)
    mock_transaction.__aexit__ = AsyncMock(return_value=None)
    mock_conn.transaction = MagicMock(return_value=mock_transaction)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_tenant_conn.return_value = mock_cm
    mock_llm = MagicMock()
    mock_llm.complete_with_routing = AsyncMock(
        return_value=MagicMock(
            content={
                "assumptions": {
                    "revenue_streams": [
                        {
                            "stream_id": "rs1",
                            "label": "Product",
                            "stream_type": "unit_sale",
                            "drivers": {
                                "volume": [{"ref": "drv:capacity_units_per_month", "value_type": "constant", "value": 1000}],
                                "pricing": [{"ref": "drv:price_per_unit", "value_type": "constant", "value": 10}],
                                "direct_costs": [{"ref": "drv:material_cost_per_unit", "value_type": "constant", "value": 4}],
                            },
                        }
                    ],
                    "cost_structure": {"variable_costs": [], "fixed_costs": []},
                    "working_capital": {"ar_days": 45, "ap_days": 30, "inv_days": 60},
                }
            }
        )
    )
    app.dependency_overrides[get_llm_router] = lambda: mock_llm
    try:
        r = client.post(
            f"/api/v1/ventures/{venture_id}/generate-draft",
            headers={"X-Tenant-ID": TENANT, "X-User-ID": "user-1"},
        )
    finally:
        app.dependency_overrides.pop(get_llm_router, None)
    assert r.status_code == 200
    data = r.json()
    assert data["venture_id"] == venture_id
    assert "draft_session_id" in data
    assert data["draft_session_id"].startswith("ds_")
    assert data["status"] == "active"
