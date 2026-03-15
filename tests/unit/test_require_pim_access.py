"""Tests for the require_pim_access FastAPI dependency (pim-7-5).

Verifies that the dependency:
- Raises HTTP 400 when X-Tenant-ID is absent
- Raises HTTP 403 when check_pim_access denies access
- Returns None (no error) when access is granted
- Propagates the 403 correctly through a real PIM endpoint
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps.api.app.deps import require_pim_access
from apps.api.app.main import app

client = TestClient(app)

TENANT = "tenant-pim-test"


def _make_conn(fetchrow_return=None, fetch_return=None, execute_return=None):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=fetch_return or [])
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock(return_value=execute_return or "DELETE 0")
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


# ---------------------------------------------------------------------------
# Direct unit tests for require_pim_access
# ---------------------------------------------------------------------------


async def test_require_pim_access_missing_tenant_raises_400() -> None:
    """Empty X-Tenant-ID header should raise HTTP 400."""
    with pytest.raises(HTTPException) as exc_info:
        await require_pim_access(x_tenant_id="")
    assert exc_info.value.status_code == 400


async def test_require_pim_access_granted() -> None:
    """Valid tenant with PIM enabled should complete without raising."""
    # patch at the db module level — deps.py uses a deferred import
    with (
        patch("apps.api.app.db.tenant_conn", return_value=_make_conn()),
        patch(
            "apps.api.app.services.pim.access.check_pim_access",
            new_callable=AsyncMock,
        ) as mock_check,
    ):
        result = await require_pim_access(x_tenant_id=TENANT)
    assert result is None
    mock_check.assert_awaited_once()


async def test_require_pim_access_denied_propagates_403() -> None:
    """check_pim_access raising HTTP 403 should propagate from the dependency."""
    with (
        patch("apps.api.app.db.tenant_conn", return_value=_make_conn()),
        patch(
            "apps.api.app.services.pim.access.check_pim_access",
            new_callable=AsyncMock,
            side_effect=HTTPException(403, "PIM is not enabled for this tenant's subscription"),
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await require_pim_access(x_tenant_id=TENANT)
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Integration tests via TestClient — gate fires on real PIM endpoints
# ---------------------------------------------------------------------------


def test_pim_endpoint_returns_400_without_tenant_header() -> None:
    """PIM endpoint without X-Tenant-ID returns 400 via require_pim_access."""
    r = client.get("/api/v1/pim/sentiment/scores")
    assert r.status_code == 400


def test_pim_endpoint_returns_403_when_pim_access_denied() -> None:
    """PIM endpoint returns 403 when require_pim_access gate fires."""
    with (
        patch(
            "apps.api.app.db.tenant_conn",
            return_value=_make_conn(),
        ),
        patch(
            "apps.api.app.services.pim.access.check_pim_access",
            new_callable=AsyncMock,
            side_effect=HTTPException(403, "PIM is not enabled for this tenant's subscription"),
        ),
    ):
        r = client.get(
            "/api/v1/pim/sentiment/scores",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 403


def test_pim_endpoint_succeeds_when_access_granted() -> None:
    """PIM endpoint proceeds normally when require_pim_access passes."""
    with (
        patch(
            "apps.api.app.db.tenant_conn",
            return_value=_make_conn(fetch_return=[]),
        ),
        patch(
            "apps.api.app.services.pim.access.check_pim_access",
            new_callable=AsyncMock,
        ),
        patch(
            "apps.api.app.routers.pim_sentiment.tenant_conn",
            return_value=_make_conn(fetch_return=[]),
        ),
    ):
        r = client.get(
            "/api/v1/pim/sentiment/scores",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
