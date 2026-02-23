"""H-01: Metrics summary API tests — latency summary (no DB)."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-h01"


def test_metrics_summary_requires_tenant() -> None:
    r = client.get("/api/v1/metrics/summary")
    assert r.status_code in (400, 403)


def test_metrics_summary_success() -> None:
    mock_summary = {"p50_ms": 12.5, "p95_ms": 45.0, "total_requests": 100}
    with patch("apps.api.app.routers.metrics_summary.get_latency_summary", return_value=mock_summary):
        r = client.get("/api/v1/metrics/summary", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    assert r.json()["p50_ms"] == 12.5
