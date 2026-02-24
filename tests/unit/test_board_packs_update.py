"""H-04: Board pack PATCH endpoint tests — label, section_order, branding, narrative sections, audit."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-h04"
USER = "user-h04"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": USER}


def _mock_tenant_conn(_tenant_id: str):
    conn = MagicMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.fetchrow = AsyncMock(return_value={"narrative_json": '{"executive_summary": "Old text."}'})
    # Also mock create_audit_event (it uses conn)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


# ---------------------------------------------------------------------------
# Basic field updates
# ---------------------------------------------------------------------------

def test_patch_no_fields_returns_400() -> None:
    with patch("apps.api.app.routers.board_packs.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.patch(
            "/api/v1/board-packs/pk-1",
            json={},
            headers=HEADERS,
        )
    assert r.status_code == 400


def test_patch_label_success() -> None:
    with (
        patch("apps.api.app.routers.board_packs.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.board_packs.create_audit_event", new_callable=AsyncMock) as mock_audit,
    ):
        r = client.patch(
            "/api/v1/board-packs/pk-1",
            json={"label": "Updated Q1 Pack"},
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert r.json()["updated"] is True
    mock_audit.assert_called_once()
    audit_kwargs = mock_audit.call_args
    assert audit_kwargs[0][2] == "board_pack.updated"
    assert "label" in audit_kwargs[1]["event_data"]["changed_fields"]


def test_patch_not_found_returns_404() -> None:
    def _conn_update_0(_tid: str):
        conn = MagicMock()
        conn.execute = AsyncMock(return_value="UPDATE 0")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.board_packs.tenant_conn", side_effect=_conn_update_0):
        r = client.patch(
            "/api/v1/board-packs/pk-999",
            json={"label": "Nope"},
            headers=HEADERS,
        )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Branding validation
# ---------------------------------------------------------------------------

def test_patch_branding_valid_keys() -> None:
    with (
        patch("apps.api.app.routers.board_packs.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.board_packs.create_audit_event", new_callable=AsyncMock),
    ):
        r = client.patch(
            "/api/v1/board-packs/pk-1",
            json={"branding_json": {"logo_url": "https://example.com/logo.png", "primary_color": "#1a1a2e"}},
            headers=HEADERS,
        )
    assert r.status_code == 200


def test_patch_branding_unknown_keys_rejected() -> None:
    with patch("apps.api.app.routers.board_packs.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.patch(
            "/api/v1/board-packs/pk-1",
            json={"branding_json": {"logo_url": "https://example.com/logo.png", "bad_key": "nope"}},
            headers=HEADERS,
        )
    assert r.status_code == 422
    assert "bad_key" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Section order validation
# ---------------------------------------------------------------------------

def test_patch_section_order_valid() -> None:
    with (
        patch("apps.api.app.routers.board_packs.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.board_packs.create_audit_event", new_callable=AsyncMock),
    ):
        r = client.patch(
            "/api/v1/board-packs/pk-1",
            json={"section_order": ["executive_summary", "income_statement"]},
            headers=HEADERS,
        )
    assert r.status_code == 200


def test_patch_section_order_empty_string_rejected() -> None:
    with patch("apps.api.app.routers.board_packs.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.patch(
            "/api/v1/board-packs/pk-1",
            json={"section_order": ["executive_summary", ""]},
            headers=HEADERS,
        )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Narrative section updates
# ---------------------------------------------------------------------------

def test_patch_narrative_sections() -> None:
    def _conn_with_narrative(_tid: str):
        conn = MagicMock()
        conn.execute = AsyncMock(return_value="UPDATE 1")
        conn.fetchrow = AsyncMock(return_value={
            "narrative_json": json.dumps({"executive_summary": "Old text.", "strategic_commentary": "Old strat."}),
        })
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with (
        patch("apps.api.app.routers.board_packs.tenant_conn", side_effect=_conn_with_narrative),
        patch("apps.api.app.routers.board_packs.create_audit_event", new_callable=AsyncMock) as mock_audit,
    ):
        r = client.patch(
            "/api/v1/board-packs/pk-1",
            json={"sections": [
                {"section_key": "executive_summary", "content": "Updated exec summary."},
            ]},
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert r.json()["updated"] is True

    # Verify the narrative was updated with merged content
    mock_audit.assert_called_once()
    assert "narrative_sections" in mock_audit.call_args[1]["event_data"]["changed_fields"]


def test_patch_narrative_sections_pack_not_found() -> None:
    def _conn_no_pack(_tid: str):
        conn = MagicMock()
        conn.execute = AsyncMock(return_value="UPDATE 1")
        conn.fetchrow = AsyncMock(return_value=None)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.board_packs.tenant_conn", side_effect=_conn_no_pack):
        r = client.patch(
            "/api/v1/board-packs/pk-999",
            json={"sections": [
                {"section_key": "executive_summary", "content": "New text."},
            ]},
            headers=HEADERS,
        )
    assert r.status_code == 404


def test_patch_narrative_with_null_narrative_json() -> None:
    """When narrative_json is null, sections update should create a new dict."""
    def _conn_null_narrative(_tid: str):
        conn = MagicMock()
        conn.execute = AsyncMock(return_value="UPDATE 1")
        conn.fetchrow = AsyncMock(return_value={"narrative_json": None})
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with (
        patch("apps.api.app.routers.board_packs.tenant_conn", side_effect=_conn_null_narrative),
        patch("apps.api.app.routers.board_packs.create_audit_event", new_callable=AsyncMock),
    ):
        r = client.patch(
            "/api/v1/board-packs/pk-1",
            json={"sections": [
                {"section_key": "executive_summary", "content": "Brand new content."},
            ]},
            headers=HEADERS,
        )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Combined updates
# ---------------------------------------------------------------------------

def test_patch_label_and_sections_together() -> None:
    with (
        patch("apps.api.app.routers.board_packs.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.board_packs.create_audit_event", new_callable=AsyncMock) as mock_audit,
    ):
        r = client.patch(
            "/api/v1/board-packs/pk-1",
            json={
                "label": "New Label",
                "sections": [{"section_key": "strategic_commentary", "content": "Updated."}],
            },
            headers=HEADERS,
        )
    assert r.status_code == 200
    event_data = mock_audit.call_args[1]["event_data"]
    assert "label" in event_data["changed_fields"]
    assert "narrative_sections" in event_data["changed_fields"]


def test_patch_requires_tenant() -> None:
    r = client.patch("/api/v1/board-packs/pk-1", json={"label": "Test"})
    assert r.status_code == 400
