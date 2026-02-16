"""Compliance (VA-P4-04): GDPR data export and deletion (anonymization)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from apps.api.app.db import tenant_conn
from apps.api.app.db.audit import create_audit_event, list_audit_events
from apps.api.app.deps import require_role, ROLES_OWNER_OR_ADMIN

router = APIRouter(prefix="/compliance", tags=["compliance"], dependencies=[require_role(*ROLES_OWNER_OR_ADMIN)])


@router.get("/export")
async def gdpr_data_export(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    user_id: str = Query(..., description="User ID to export data for"),
) -> dict[str, Any]:
    """Export all data associated with the user (GDPR Art. 15). Returns audit events, drafts, runs summary."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if not x_user_id:
        raise HTTPException(400, "X-User-ID required")
    if x_user_id != user_id:
        raise HTTPException(403, "Can only export your own data (admin override not yet implemented)")
    async with tenant_conn(x_tenant_id) as conn:
        audit_events = await list_audit_events(
            conn, x_tenant_id, user_id=user_id, limit=50_000, offset=0
        )
        drafts = await conn.fetch(
            """SELECT draft_session_id, parent_baseline_id, status, created_at
               FROM draft_sessions WHERE tenant_id = $1 AND created_by = $2 ORDER BY created_at DESC""",
            x_tenant_id,
            user_id,
        )
        notifications = await conn.fetch(
            """SELECT id, type, title, body, entity_type, entity_id, created_at
               FROM notifications WHERE tenant_id = $1 AND user_id = $2 ORDER BY created_at DESC""",
            x_tenant_id,
            user_id,
        )
        scenarios = await conn.fetch(
            """SELECT scenario_id, baseline_id, label, created_at
               FROM scenarios WHERE tenant_id = $1 AND created_by = $2 ORDER BY created_at DESC""",
            x_tenant_id,
            user_id,
        )
        connections = await conn.fetch(
            """SELECT connection_id, provider, status, created_at
               FROM integration_connections WHERE tenant_id = $1 AND created_by = $2 ORDER BY created_at DESC""",
            x_tenant_id,
            user_id,
        )
        excel_conns = await conn.fetch(
            """SELECT excel_connection_id, label, mode, status, created_at
               FROM excel_connections WHERE tenant_id = $1 AND created_by = $2 ORDER BY created_at DESC""",
            x_tenant_id,
            user_id,
        )
        excel_syncs = await conn.fetch(
            """SELECT event_id, excel_connection_id, direction, status, "timestamp"
               FROM excel_sync_events WHERE tenant_id = $1 AND initiated_by = $2 ORDER BY "timestamp" DESC""",
            x_tenant_id,
            user_id,
        )
        memos = await conn.fetch(
            """SELECT memo_id, memo_type, title, status, created_at
               FROM memo_packs WHERE tenant_id = $1 AND created_by = $2 ORDER BY created_at DESC""",
            x_tenant_id,
            user_id,
        )
        await create_audit_event(
            conn,
            x_tenant_id,
            "gdpr.export",
            "compliance",
            "user",
            user_id,
            user_id=x_user_id,
            event_data={"target_user_id": user_id},
        )
    return {
        "tenant_id": x_tenant_id,
        "user_id": user_id,
        "audit_events": [
            {
                "audit_event_id": r["audit_event_id"],
                "event_type": r["event_type"],
                "event_category": r["event_category"],
                "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None,
                "resource_type": r["resource_type"],
                "resource_id": r["resource_id"],
            }
            for r in audit_events
        ],
        "drafts": [
            {
                "draft_session_id": r["draft_session_id"],
                "parent_baseline_id": r["parent_baseline_id"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in drafts
        ],
        "notifications": [
            {
                "type": r["type"],
                "title": r["title"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in notifications
        ],
        "scenarios": [
            {
                "scenario_id": r["scenario_id"],
                "baseline_id": r["baseline_id"],
                "label": r["label"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in scenarios
        ],
        "integration_connections": [
            {
                "connection_id": r["connection_id"],
                "provider": r["provider"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in connections
        ],
        "excel_connections": [
            {
                "excel_connection_id": r["excel_connection_id"],
                "label": r["label"],
                "mode": r["mode"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in excel_conns
        ],
        "excel_sync_events": [
            {
                "event_id": r["event_id"],
                "excel_connection_id": r["excel_connection_id"],
                "direction": r["direction"],
                "status": r["status"],
                "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None,
            }
            for r in excel_syncs
        ],
        "memo_packs": [
            {
                "memo_id": r["memo_id"],
                "memo_type": r["memo_type"],
                "title": r["title"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in memos
        ],
    }


@router.post("/anonymize-user")
async def gdpr_anonymize_user(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    user_id: str = Query(..., description="User ID to anonymize"),
) -> dict[str, Any]:
    """Anonymize references to a user for GDPR right to erasure."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if not x_user_id:
        raise HTTPException(400, "X-User-ID required")
    if x_user_id != user_id:
        raise HTTPException(403, "Can only anonymize your own data (admin override not yet implemented)")
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE audit_log SET user_id = NULL WHERE tenant_id = $1 AND user_id = $2",
                x_tenant_id,
                user_id,
            )
            await conn.execute(
                "UPDATE draft_sessions SET created_by = NULL WHERE tenant_id = $1 AND created_by = $2",
                x_tenant_id,
                user_id,
            )
            await conn.execute(
                "UPDATE scenarios SET created_by = NULL WHERE tenant_id = $1 AND created_by = $2",
                x_tenant_id,
                user_id,
            )
            await conn.execute(
                "UPDATE integration_connections SET created_by = NULL WHERE tenant_id = $1 AND created_by = $2",
                x_tenant_id,
                user_id,
            )
            await conn.execute(
                "DELETE FROM notifications WHERE tenant_id = $1 AND user_id = $2",
                x_tenant_id,
                user_id,
            )
            await conn.execute(
                "UPDATE excel_connections SET created_by = NULL WHERE tenant_id = $1 AND created_by = $2",
                x_tenant_id,
                user_id,
            )
            await conn.execute(
                "UPDATE excel_sync_events SET initiated_by = NULL WHERE tenant_id = $1 AND initiated_by = $2",
                x_tenant_id,
                user_id,
            )
            await conn.execute(
                "UPDATE memo_packs SET created_by = NULL WHERE tenant_id = $1 AND created_by = $2",
                x_tenant_id,
                user_id,
            )
            await create_audit_event(
                conn,
                x_tenant_id,
                "gdpr.anonymize",
                "compliance",
                "user",
                user_id,
                user_id=x_user_id,
                event_data={
                    "target_user_id": user_id,
                    "tables_affected": [
                        "audit_log",
                        "draft_sessions",
                        "scenarios",
                        "integration_connections",
                        "notifications",
                        "excel_connections",
                        "excel_sync_events",
                        "memo_packs",
                    ],
                },
            )
    return {
        "status": "anonymized",
        "tenant_id": x_tenant_id,
        "user_id": user_id,
    }
