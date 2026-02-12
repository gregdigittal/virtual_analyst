"""Metrics summary for performance dashboard (latency, request count)."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from shared.fm_shared.metrics import get_latency_summary

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary")
async def metrics_summary(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict:
    """Return in-memory latency summary (p50, p95, by endpoint) for dashboard."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    return get_latency_summary()
