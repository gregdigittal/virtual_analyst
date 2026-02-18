from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)


def _async_cm(conn: MagicMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def test_get_currency_settings_requires_x_tenant_id() -> None:
    r = client.get("/api/v1/currency/settings")
    assert r.status_code == 400


def test_get_currency_settings_defaults_when_missing() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=None)
    with patch("apps.api.app.routers.currency.tenant_conn", return_value=_async_cm(conn)):
        r = client.get("/api/v1/currency/settings", headers={"X-Tenant-ID": "t1"})
    assert r.status_code == 200
    data = r.json()
    assert data["base_currency"] == "USD"
    assert data["reporting_currency"] == "USD"
    assert data["fx_source"] == "manual"


def test_put_currency_settings_requires_x_tenant_id() -> None:
    r = client.put("/api/v1/currency/settings", json={"base_currency": "USD", "reporting_currency": "USD", "fx_source": "manual"})
    assert r.status_code == 400


def test_add_fx_rate_invalid_date_returns_400() -> None:
    r = client.post(
        "/api/v1/currency/rates",
        json={"from_currency": "USD", "to_currency": "EUR", "effective_date": "2026-99-99", "rate": 1.2},
        headers={"X-Tenant-ID": "t1"},
    )
    assert r.status_code == 400


def test_list_fx_rates_returns_items() -> None:
    conn = MagicMock()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "from_currency": "USD",
                "to_currency": "EUR",
                "effective_date": date(2026, 2, 1),
                "rate": Decimal("1.23"),
                "created_at": datetime(2026, 2, 1, tzinfo=timezone.utc),
                "created_by": "u1",
            }
        ]
    )
    conn.fetchval = AsyncMock(return_value=1)
    with patch("apps.api.app.routers.currency.tenant_conn", return_value=_async_cm(conn)):
        r = client.get("/api/v1/currency/rates", headers={"X-Tenant-ID": "t1"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["rates"][0]["from_currency"] == "USD"
    assert data["rates"][0]["rate"] == 1.23


def test_convert_same_currency_returns_1() -> None:
    r = client.get(
        "/api/v1/currency/convert",
        params={"from_currency": "USD", "to_currency": "USD"},
        headers={"X-Tenant-ID": "t1"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["rate"] == 1.0
