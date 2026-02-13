"""Excel connections and sync events (VA-P5-01)."""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg


async def create_connection(
    conn: asyncpg.Connection,
    tenant_id: str,
    label: str | None,
    mode: str,
    target_json: dict[str, Any],
    bindings_json: list[dict[str, Any]],
    workbook_json: dict[str, Any] | None = None,
    sync_json: dict[str, Any] | None = None,
    permissions_json: dict[str, Any] | None = None,
    created_by: str | None = None,
) -> str:
    """Insert excel_connection; returns excel_connection_id."""
    import json as _json
    excel_connection_id = f"ex_{uuid.uuid4().hex[:12]}"
    await conn.execute(
        """INSERT INTO excel_connections
           (tenant_id, excel_connection_id, label, mode, target_json, workbook_json, bindings_json, sync_json, permissions_json, created_by)
           VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb, $8::jsonb, $9::jsonb, $10)""",
        tenant_id,
        excel_connection_id,
        label or "",
        mode,
        _json.dumps(target_json),
        _json.dumps(workbook_json) if workbook_json else None,
        _json.dumps(bindings_json),
        _json.dumps(sync_json) if sync_json else None,
        _json.dumps(permissions_json) if permissions_json else None,
        created_by,
    )
    return excel_connection_id


async def list_connections(
    conn: asyncpg.Connection,
    tenant_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List excel connections for tenant."""
    import json as _json
    rows = await conn.fetch(
        """SELECT excel_connection_id, label, mode, target_json, workbook_json, bindings_json, sync_json, status, created_at
           FROM excel_connections WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
        tenant_id,
        limit,
        offset,
    )
    return [
        {
            "excel_connection_id": r["excel_connection_id"],
            "label": r["label"],
            "mode": r["mode"],
            "target_json": r["target_json"] if isinstance(r["target_json"], dict) else _json.loads(r["target_json"] or "{}"),
            "workbook_json": r["workbook_json"] if isinstance(r["workbook_json"], dict) else (_json.loads(r["workbook_json"]) if r["workbook_json"] else None),
            "bindings_json": r["bindings_json"] if isinstance(r["bindings_json"], list) else _json.loads(r["bindings_json"] or "[]"),
            "sync_json": r["sync_json"] if isinstance(r["sync_json"], dict) else (_json.loads(r["sync_json"]) if r["sync_json"] else None),
            "status": r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def get_connection(
    conn: asyncpg.Connection,
    tenant_id: str,
    excel_connection_id: str,
) -> dict[str, Any] | None:
    """Get one connection by id."""
    import json as _json
    row = await conn.fetchrow(
        """SELECT excel_connection_id, label, mode, target_json, workbook_json, bindings_json, sync_json, permissions_json, status, created_at, created_by
           FROM excel_connections WHERE tenant_id = $1 AND excel_connection_id = $2""",
        tenant_id,
        excel_connection_id,
    )
    if not row:
        return None
    return {
        "excel_connection_id": row["excel_connection_id"],
        "label": row["label"],
        "mode": row["mode"],
        "target_json": row["target_json"] if isinstance(row["target_json"], dict) else _json.loads(row["target_json"] or "{}"),
        "workbook_json": row["workbook_json"] if isinstance(row["workbook_json"], dict) else (_json.loads(row["workbook_json"]) if row["workbook_json"] else None),
        "bindings_json": row["bindings_json"] if isinstance(row["bindings_json"], list) else _json.loads(row["bindings_json"] or "[]"),
        "sync_json": row["sync_json"] if isinstance(row["sync_json"], dict) else (_json.loads(row["sync_json"]) if row["sync_json"] else None),
        "permissions_json": row["permissions_json"] if isinstance(row["permissions_json"], dict) else (_json.loads(row["permissions_json"]) if row["permissions_json"] else None),
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "created_by": row["created_by"],
    }


async def update_connection(
    conn: asyncpg.Connection,
    tenant_id: str,
    excel_connection_id: str,
    label: str | None = None,
    mode: str | None = None,
    bindings_json: list[dict[str, Any]] | None = None,
    sync_json: dict[str, Any] | None = None,
    status: str | None = None,
) -> bool:
    """Update connection; returns True if row was updated."""
    import json as _json
    updates: list[str] = ["updated_at = now()"]
    params: list[Any] = []
    idx = 1
    if label is not None:
        updates.append(f"label = ${idx}")
        params.append(label)
        idx += 1
    if mode is not None:
        updates.append(f"mode = ${idx}")
        params.append(mode)
        idx += 1
    if bindings_json is not None:
        updates.append(f"bindings_json = ${idx}::jsonb")
        params.append(_json.dumps(bindings_json))
        idx += 1
    if sync_json is not None:
        updates.append(f"sync_json = ${idx}::jsonb")
        params.append(_json.dumps(sync_json))
        idx += 1
    if status is not None:
        updates.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if len(params) == 0:
        return True
    params.extend([tenant_id, excel_connection_id])
    result = await conn.execute(
        f"UPDATE excel_connections SET {', '.join(updates)} WHERE tenant_id = ${idx} AND excel_connection_id = ${idx + 1}",
        *params,
    )
    return result != "UPDATE 0"


async def delete_connection(
    conn: asyncpg.Connection,
    tenant_id: str,
    excel_connection_id: str,
) -> bool:
    """Delete connection; returns True if deleted."""
    result = await conn.execute(
        "DELETE FROM excel_connections WHERE tenant_id = $1 AND excel_connection_id = $2",
        tenant_id,
        excel_connection_id,
    )
    return result != "DELETE 0"


async def insert_sync_event(
    conn: asyncpg.Connection,
    tenant_id: str,
    excel_connection_id: str,
    direction: str,
    status: str,
    diff_json: dict[str, Any],
    initiated_by: str | None = None,
    bindings_synced: int = 0,
    target_json: dict[str, Any] | None = None,
) -> str:
    """Insert excel_sync_events row; returns event_id."""
    import json as _json
    event_id = f"ev_{uuid.uuid4().hex[:12]}"
    await conn.execute(
        """INSERT INTO excel_sync_events
           (tenant_id, event_id, excel_connection_id, direction, status, diff_json, initiated_by, bindings_synced, target_json)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9::jsonb)""",
        tenant_id,
        event_id,
        excel_connection_id,
        direction,
        status,
        _json.dumps(diff_json),
        initiated_by,
        bindings_synced,
        _json.dumps(target_json) if target_json else None,
    )
    return event_id
