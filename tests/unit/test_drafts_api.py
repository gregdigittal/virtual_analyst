"""Unit tests for drafts API (VA-P2-02): CRUD and state machine."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app
from apps.api.app.routers.drafts import VALID_TRANSITIONS

client = TestClient(app)
TENANT = "tenant-1"


def test_draft_state_machine_transitions() -> None:
    """Valid transitions: active->ready_to_commit|abandoned; ready_to_commit->active|committed|abandoned."""
    assert "ready_to_commit" in VALID_TRANSITIONS["active"]
    assert "abandoned" in VALID_TRANSITIONS["active"]
    assert "active" in VALID_TRANSITIONS["ready_to_commit"]
    assert "committed" in VALID_TRANSITIONS["ready_to_commit"]
    assert "abandoned" in VALID_TRANSITIONS["ready_to_commit"]
    assert len(VALID_TRANSITIONS["committed"]) == 0
    assert len(VALID_TRANSITIONS["abandoned"]) == 0


def test_list_drafts_requires_x_tenant_id() -> None:
    """List drafts returns 400 without X-Tenant-ID."""
    r = client.get("/api/v1/drafts")
    assert r.status_code == 400


def test_create_draft_requires_x_tenant_id() -> None:
    """Create draft returns 400 without X-Tenant-ID."""
    r = client.post("/api/v1/drafts", json={})
    assert r.status_code == 400


@patch("apps.api.app.routers.drafts.tenant_conn")
def test_get_draft_returns_404_when_not_found(mock_tenant_conn: MagicMock) -> None:
    """GET draft returns 404 when draft_sessions has no row."""
    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_tenant_conn.return_value = mock_cm

    r = client.get(
        "/api/v1/drafts/ds_nonexistent",
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 404


def test_draft_chat_requires_x_tenant_id() -> None:
    r = client.post("/api/v1/drafts/ds_123/chat", json={"message": "hello"})
    assert r.status_code == 400


def test_accept_proposal_requires_x_tenant_id() -> None:
    r = client.post("/api/v1/drafts/ds_123/proposals/prop_abc/accept")
    assert r.status_code == 400


def test_reject_proposal_requires_x_tenant_id() -> None:
    r = client.post("/api/v1/drafts/ds_123/proposals/prop_abc/reject")
    assert r.status_code == 400


def test_commit_draft_requires_x_tenant_id() -> None:
    r = client.post("/api/v1/drafts/ds_123/commit", json={})
    assert r.status_code == 400


def test_validate_proposal_content_rejects_unsafe() -> None:
    from apps.api.app.routers.drafts import _validate_proposal_content

    assert _validate_proposal_content({"evidence": "See https://evil.com", "value": 100}) is not None
    assert _validate_proposal_content({"evidence": "User stated 10%", "value": 100}) is None
    assert _validate_proposal_content({"evidence": "Clean", "value": 1e16}) is not None
    assert _validate_proposal_content({"evidence": "Clean", "value": 500}) is None
