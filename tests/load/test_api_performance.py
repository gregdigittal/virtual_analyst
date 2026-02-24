"""N-06: API-level performance tests — response latency SLAs through the full router pipeline."""

from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app

TENANT = "tenant-perf"
HEADERS = {"X-Tenant-ID": TENANT}
RUNS = 20


def _p95(timings: list[float]) -> float:
    """Return the P95 value from a list of timings in seconds."""
    s = sorted(timings)
    idx = int(math.ceil(len(s) * 0.95)) - 1
    return s[idx]


def _mock_tenant_conn(_tid: str):
    """Return an async context manager yielding a mock connection."""
    conn = MagicMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=0)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.performance
def test_health_live_p95_under_50ms() -> None:
    """GET /api/v1/health/live P95 < 50ms — pure in-process, no DB."""
    client = TestClient(app)
    timings = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        r = client.get("/api/v1/health/live")
        timings.append(time.perf_counter() - t0)
        assert r.status_code == 200
    p95 = _p95(timings)
    assert p95 < 0.05, f"health/live P95 {p95 * 1000:.1f}ms exceeds 50ms"


@pytest.mark.performance
def test_connectors_list_p95_under_100ms() -> None:
    """GET /api/v1/connectors P95 < 100ms — static registry, no DB."""
    client = TestClient(app)
    timings = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        r = client.get("/api/v1/connectors", headers=HEADERS)
        timings.append(time.perf_counter() - t0)
        assert r.status_code == 200
    p95 = _p95(timings)
    assert p95 < 0.1, f"connectors list P95 {p95 * 1000:.1f}ms exceeds 100ms"


@pytest.mark.performance
def test_openapi_schema_p95_under_200ms() -> None:
    """GET /openapi.json P95 < 200ms — schema generation from all routers."""
    client = TestClient(app)
    timings = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        r = client.get("/openapi.json")
        timings.append(time.perf_counter() - t0)
        assert r.status_code == 200
    p95 = _p95(timings)
    assert p95 < 0.2, f"openapi.json P95 {p95 * 1000:.1f}ms exceeds 200ms"


@pytest.mark.performance
def test_concurrent_health_requests_under_1s() -> None:
    """10 parallel requests to /api/v1/health/live — all complete within 1s total."""
    client = TestClient(app)
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [
            pool.submit(client.get, "/api/v1/health/live")
            for _ in range(10)
        ]
        results = [f.result() for f in as_completed(futures)]
    elapsed = time.perf_counter() - t0
    assert all(r.status_code == 200 for r in results)
    assert elapsed < 1.0, f"10 concurrent requests took {elapsed:.2f}s (>1s)"
