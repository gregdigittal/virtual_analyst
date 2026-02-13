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
EVENT_DRAFT_UPDATED = "draft.updated"
