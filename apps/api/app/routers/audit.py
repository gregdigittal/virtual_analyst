"""Audit log: list and export (VA-P4-03). Immutable append-only log."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from apps.api.app.db import tenant_conn
from apps.api.app.db.audit import (
    AUDIT_EVENT_CATALOG,
    list_audit_events,
)
from apps.api.app.deps import require_role, ROLES_OWNER_OR_ADMIN

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[require_role(*ROLES_OWNER_OR_ADMIN)])


@router.get("/events/catalog")
async def get_audit_event_catalog() -> dict[str, Any]:
    """Return full event type catalog for filtering and documentation."""
    return {"events": AUDIT_EVENT_CATALOG}


@router.get("/events")
async def list_events(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    user_id: str | None = Query(None),
    event_type: str | None = Query(None),
    resource_type: str | None = Query(None),
    start_date: str | None = Query(None, description="ISO date or datetime"),
    end_date: str | None = Query(None, description="ISO date or datetime"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List audit events for the tenant. Log is immutable (append-only)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        events = await list_audit_events(
            conn,
            x_tenant_id,
            user_id=user_id,
            event_type=event_type,
            resource_type=resource_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
    return {"events": events, "limit": limit, "offset": offset}


@router.get("/events/export")
async def export_events(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    export_format: str = Query("json", alias="format", description="json or csv"),
    user_id: str | None = Query(None),
    event_type: str | None = Query(None),
    resource_type: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(10_000, ge=1, le=50_000),
) -> StreamingResponse:
    """Export audit events as JSON or CSV. Same filters as list."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        events = await list_audit_events(
            conn,
            x_tenant_id,
            user_id=user_id,
            event_type=event_type,
            resource_type=resource_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=0,
        )

    if export_format == "csv":
        def csv_generator():
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["audit_event_id", "tenant_id", "user_id", "event_type", "event_category", "resource_type", "resource_id", "timestamp", "event_data"])
            yield output.getvalue()
            output.truncate(0)
            output.seek(0)
            for row in events:
                writer.writerow([
                    row.get("audit_event_id"),
                    row.get("tenant_id"),
                    row.get("user_id"),
                    row.get("event_type"),
                    row.get("event_category"),
                    row.get("resource_type"),
                    row.get("resource_id"),
                    str(row.get("timestamp") or ""),
                    json.dumps(dict(row.get("event_data") or {})),
                ])
                yield output.getvalue()
                output.truncate(0)
                output.seek(0)

        return StreamingResponse(
            csv_generator(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="audit_export.csv"'},
        )

    body = json.dumps({"events": events}).encode("utf-8")
    return StreamingResponse(
        iter([body]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=audit_events.json"},
    )
