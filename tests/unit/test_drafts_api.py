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


@patch("apps.api.app.routers.drafts.get_conn")
def test_get_draft_returns_404_when_not_found(mock_get_conn: MagicMock) -> None:
    """GET draft returns 404 when draft_sessions has no row."""
    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.close = AsyncMock()
    mock_conn.transaction = MagicMock()
    mock_conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    mock_conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_get_conn.return_value = AsyncMock(return_value=mock_conn)

    r = client.get(
        "/api/v1/drafts/ds_nonexistent",
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 404
