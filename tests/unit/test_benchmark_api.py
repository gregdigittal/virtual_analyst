"""H-01: Benchmark API tests — opt-in, summary, aggregates."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-h01"


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


def test_get_opt_in_requires_tenant() -> None:
    r = client.get("/api/v1/benchmark/opt-in")
    assert r.status_code == 400


def test_get_opt_in_not_opted_in() -> None:
    with patch("apps.api.app.routers.benchmark.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get("/api/v1/benchmark/opt-in", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    assert r.json()["opted_in"] is False


def test_set_opt_in_success() -> None:
    with patch("apps.api.app.routers.benchmark.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.put(
            "/api/v1/benchmark/opt-in",
            json={"industry_segment": "tech", "size_segment": "mid"},
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_delete_opt_in_success() -> None:
    with patch("apps.api.app.routers.benchmark.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.delete("/api/v1/benchmark/opt-in", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 204


def test_summary_requires_opt_in() -> None:
    """Summary returns 403 when tenant hasn't opted in (fetchrow returns None)."""
    with patch("apps.api.app.routers.benchmark.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get("/api/v1/benchmark/summary", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 403


def test_summary_success() -> None:
    """Summary returns 200 when tenant has opted in."""
    call_count = 0

    def _conn_with_opt_in(_tid: str):
        nonlocal call_count
        conn = MagicMock()
        if call_count == 0:
            conn.fetchrow = AsyncMock(return_value={"industry_segment": "tech", "size_segment": "mid"})
        else:
            conn.fetch = AsyncMock(return_value=[])
        call_count += 1
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.benchmark.tenant_conn", side_effect=_conn_with_opt_in):
        r = client.get("/api/v1/benchmark/summary", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    assert "metrics" in r.json()


def test_list_aggregates_success() -> None:
    with patch("apps.api.app.routers.benchmark.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get("/api/v1/benchmark/aggregates", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    assert "aggregates" in r.json()
