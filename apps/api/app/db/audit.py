"""Append-only audit logging: baseline and run events."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import asyncpg


def _generate_id() -> str:
    return f"ae_{uuid.uuid4().hex[:12]}"


def _checksum(data: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


async def create_audit_event(
    conn: asyncpg.Connection,
    tenant_id: str,
    event_type: str,
    event_category: str,
    resource_type: str,
    resource_id: str,
    user_id: str | None = None,
    event_data: dict[str, Any] | None = None,
) -> str:
    """
    Insert one audit log row. Append-only; no updates/deletes.
    Returns audit_event_id.
    """
    audit_event_id = _generate_id()
    data = event_data or {}
    payload = {
        "audit_event_id": audit_event_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "event_type": event_type,
        "event_category": event_category,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "event_data": data,
    }
    checksum = _checksum(payload)

    await conn.execute(
        """INSERT INTO audit_log (audit_event_id, tenant_id, user_id, event_type, event_category, resource_type, resource_id, event_data, checksum)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9)""",
        audit_event_id,
        tenant_id,
        user_id,
        event_type,
        event_category,
        resource_type,
        resource_id,
        json.dumps(data),
        checksum,
    )
    return audit_event_id


EVENT_BASELINE_CREATED = "baseline.created"
EVENT_BASELINE_ACCESSED = "baseline.accessed"
EVENT_RUN_CREATED = "run.created"
EVENT_RUN_ACCESSED = "run.accessed"
EVENT_DRAFT_CREATED = "draft.created"
EVENT_DRAFT_ACCESSED = "draft.accessed"
EVENT_DRAFT_ABANDONED = "draft.abandoned"
EVENT_DRAFT_COMMITTED = "draft.committed"
EVENT_DRAFT_UPDATED = "draft.updated"
EVENT_SCENARIO_CREATED = "scenario.created"
EVENT_SCENARIO_DELETED = "scenario.deleted"
EVENT_INTEGRATION_CONNECTED = "integration.connected"
EVENT_INTEGRATION_SYNCED = "integration.synced"
EVENT_COVENANT_CREATED = "covenant.created"
EVENT_COVENANT_DELETED = "covenant.deleted"
EVENT_COVENANT_BREACHED = "covenant.breached"
EVENT_CSV_IMPORTED = "csv.imported"
EVENT_GDPR_EXPORT = "gdpr.export"
EVENT_GDPR_ANONYMIZE = "gdpr.anonymize"

# Full event catalog for export and filtering (VA-P4-03)
AUDIT_EVENT_CATALOG = [
    {"event_type": EVENT_BASELINE_CREATED, "event_category": "baseline", "description": "Baseline created"},
    {"event_type": EVENT_BASELINE_ACCESSED, "event_category": "baseline", "description": "Baseline accessed"},
    {"event_type": EVENT_RUN_CREATED, "event_category": "run", "description": "Run created"},
    {"event_type": EVENT_RUN_ACCESSED, "event_category": "run", "description": "Run accessed"},
    {"event_type": EVENT_DRAFT_CREATED, "event_category": "draft", "description": "Draft created"},
    {"event_type": EVENT_DRAFT_ACCESSED, "event_category": "draft", "description": "Draft accessed"},
    {"event_type": EVENT_DRAFT_ABANDONED, "event_category": "draft", "description": "Draft abandoned"},
    {"event_type": EVENT_DRAFT_COMMITTED, "event_category": "draft", "description": "Draft committed"},
    {"event_type": EVENT_DRAFT_UPDATED, "event_category": "draft", "description": "Draft updated"},
    {"event_type": EVENT_SCENARIO_CREATED, "event_category": "scenario", "description": "Scenario created"},
    {"event_type": EVENT_SCENARIO_DELETED, "event_category": "scenario", "description": "Scenario deleted"},
    {"event_type": EVENT_INTEGRATION_CONNECTED, "event_category": "integration", "description": "Integration connected"},
    {"event_type": EVENT_INTEGRATION_SYNCED, "event_category": "integration", "description": "Integration data synced"},
    {"event_type": EVENT_COVENANT_CREATED, "event_category": "covenant", "description": "Covenant definition created"},
    {"event_type": EVENT_COVENANT_DELETED, "event_category": "covenant", "description": "Covenant definition deleted"},
    {"event_type": EVENT_COVENANT_BREACHED, "event_category": "covenant", "description": "Covenant breached on run completion"},
    {"event_type": EVENT_CSV_IMPORTED, "event_category": "import", "description": "CSV imported as draft + scenario"},
    {"event_type": EVENT_GDPR_EXPORT, "event_category": "compliance", "description": "GDPR data export requested"},
    {"event_type": EVENT_GDPR_ANONYMIZE, "event_category": "compliance", "description": "GDPR user anonymization executed"},
]


async def list_audit_events(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    user_id: str | None = None,
    event_type: str | None = None,
    resource_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List audit events for tenant with optional filters. Immutable table: read-only."""
    conditions = ["tenant_id = $1"]
    params: list[Any] = [tenant_id]
    idx = 2
    if user_id:
        conditions.append(f"user_id = ${idx}")
        params.append(user_id)
        idx += 1
    if event_type:
        conditions.append(f"event_type = ${idx}")
        params.append(event_type)
        idx += 1
    if resource_type:
        conditions.append(f"resource_type = ${idx}")
        params.append(resource_type)
        idx += 1
    if start_date:
        conditions.append(f'"timestamp" >= ${idx}::timestamptz')
        params.append(start_date)
        idx += 1
    if end_date:
        conditions.append(f'"timestamp" <= ${idx}::timestamptz')
        params.append(end_date)
        idx += 1
    params.append(limit)
    params.append(offset)
    where = " AND ".join(conditions)
    rows = await conn.fetch(
        f"""SELECT audit_event_id, tenant_id, user_id, event_type, event_category,
                   "timestamp", resource_type, resource_id, event_data, checksum
            FROM audit_log WHERE {where}
            ORDER BY "timestamp" DESC LIMIT ${idx} OFFSET ${idx + 1}""",
        *params,
    )
    return [
        {
            "audit_event_id": r["audit_event_id"],
            "tenant_id": r["tenant_id"],
            "user_id": r["user_id"],
            "event_type": r["event_type"],
            "event_category": r["event_category"],
            "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None,
            "resource_type": r["resource_type"],
            "resource_id": r["resource_id"],
            "event_data": r["event_data"],
            "checksum": r["checksum"],
        }
        for r in rows
    ]
