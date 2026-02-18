from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from apps.api.app.core.settings import Settings
from apps.api.app.main import app
from tests.conftest import minimal_model_config_dict
from tests.integration.conftest import integration_marker

client = TestClient(app)

SECRET = "test-secret"


def _settings() -> Settings:
    return Settings(supabase_jwt_secret=SECRET, environment="test")


def _make_token(
    tenant_id: str,
    *,
    user_id: str = "u_test",
    aud: str = "authenticated",
    exp_delta: timedelta = timedelta(hours=1),
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "aud": aud,
        "exp": int((now + exp_delta).timestamp()),
        "app_metadata": {"tenant_id": tenant_id},
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def test_missing_auth_header_returns_401() -> None:
    with patch("apps.api.app.middleware.auth.get_settings", return_value=_settings()):
        r = client.get("/api/v1/drafts", headers={"X-Tenant-ID": "t1"})
    assert r.status_code == 401


def test_expired_token_returns_401() -> None:
    token = _make_token("t1", exp_delta=timedelta(seconds=-10))
    with patch("apps.api.app.middleware.auth.get_settings", return_value=_settings()):
        r = client.get(
            "/api/v1/drafts",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "t1"},
        )
    assert r.status_code == 401


def test_wrong_audience_returns_401() -> None:
    token = _make_token("t1", aud="wrong-audience")
    with patch("apps.api.app.middleware.auth.get_settings", return_value=_settings()):
        r = client.get(
            "/api/v1/drafts",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "t1"},
        )
    assert r.status_code == 401


def test_spoofed_tenant_header_ignored() -> None:
    token = _make_token("t_real")
    captured: dict[str, str] = {}

    def _mock_tenant_conn(tenant_id: str):
        captured["tenant_id"] = tenant_id
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchval = AsyncMock(return_value=0)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    role_conn = MagicMock()
    role_conn.fetchrow = AsyncMock(return_value={"role": "owner"})
    role_cm = MagicMock()
    role_cm.__aenter__ = AsyncMock(return_value=role_conn)
    role_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("apps.api.app.middleware.auth.get_settings", return_value=_settings()):
        with patch("apps.api.app.middleware.auth.tenant_conn", return_value=role_cm):
            with patch("apps.api.app.routers.drafts.tenant_conn", side_effect=_mock_tenant_conn):
                r = client.get(
                    "/api/v1/drafts",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-Tenant-ID": "t_spoofed",
                    },
                )
    assert r.status_code == 200
    assert captured["tenant_id"] == "t_real"


@integration_marker
async def test_rls_cross_tenant_isolation(client) -> None:
    headers_a = {"X-Tenant-ID": "t_sec_a", "X-User-ID": "u_a"}
    create = await client.post(
        "/api/v1/baselines",
        json={"model_config": minimal_model_config_dict(tenant_id="t_sec_a", horizon_months=6)},
        headers=headers_a,
    )
    assert create.status_code == 201
    baseline_id_a = create.json()["baseline_id"]

    headers_b = {"X-Tenant-ID": "t_sec_b", "X-User-ID": "u_b"}
    list_b = await client.get("/api/v1/baselines", headers=headers_b)
    assert list_b.status_code == 200
    items_b = list_b.json()["items"]
    assert not any(b["baseline_id"] == baseline_id_a for b in items_b)
