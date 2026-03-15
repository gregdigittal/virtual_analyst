"""Integration connections: store/load OAuth data and sync runs."""

from __future__ import annotations

import base64
import json
from typing import Any

import asyncpg
import structlog

_logger = structlog.get_logger()


def _encode_oauth(data: dict[str, Any]) -> bytes:
    """Encrypt OAuth payload for storage. Requires OAUTH_ENCRYPTION_KEY."""
    raw = json.dumps(data).encode("utf-8")
    from apps.api.app.core.settings import get_settings
    key = get_settings().oauth_encryption_key
    if not key:
        _logger.critical("oauth_encryption_key_missing", msg="OAuth tokens will be stored as base64 (NOT encrypted). Set OAUTH_ENCRYPTION_KEY in production.")
        return base64.b64encode(raw)
    from cryptography.fernet import Fernet
    return Fernet(key.encode()).encrypt(raw)


def _decode_oauth(raw: bytes | None) -> dict[str, Any]:
    """Decrypt OAuth payload from storage."""
    if not raw:
        return {}
    from apps.api.app.core.settings import get_settings
    key = get_settings().oauth_encryption_key
    if key:
        try:
            from cryptography.fernet import Fernet, InvalidToken
            decrypted = Fernet(key.encode()).decrypt(raw)
            return json.loads(decrypted.decode("utf-8"))
        except (InvalidToken, ValueError, json.JSONDecodeError):
            _logger.error("oauth_decrypt_failed", msg="Fernet decryption failed; falling back to base64. Possible key rotation or data corruption.")
    try:
        return json.loads(base64.b64decode(raw).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        _logger.error("oauth_decode_failed", msg="Both Fernet and base64 decoding failed for OAuth data.")
        return {}


async def get_connection(
    conn: asyncpg.Connection,
    tenant_id: str,
    connection_id: str,
) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """SELECT connection_id, provider, status, org_name, oauth_data_encrypted,
                  last_sync_at, sync_schedule_minutes, created_at
           FROM integration_connections WHERE tenant_id = $1 AND connection_id = $2""",
        tenant_id,
        connection_id,
    )
    if not row:
        return None
    oauth = _decode_oauth(row["oauth_data_encrypted"])
    return {
        "connection_id": row["connection_id"],
        "provider": row["provider"],
        "status": row["status"],
        "org_name": row["org_name"],
        "oauth": oauth,
        "last_sync_at": row["last_sync_at"].isoformat() if row["last_sync_at"] else None,
        "sync_schedule_minutes": row["sync_schedule_minutes"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


async def upsert_connection(
    conn: asyncpg.Connection,
    tenant_id: str,
    connection_id: str,
    provider: str,
    status: str,
    org_name: str | None = None,
    oauth_data: dict[str, Any] | None = None,
    created_by: str | None = None,
) -> None:
    encrypted = _encode_oauth(oauth_data or {}) if oauth_data else None
    await conn.execute(
        """INSERT INTO integration_connections
           (tenant_id, connection_id, provider, status, org_name, oauth_data_encrypted, created_by)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           ON CONFLICT (tenant_id, connection_id) DO UPDATE SET
             status = EXCLUDED.status,
             org_name = EXCLUDED.org_name,
             oauth_data_encrypted = COALESCE(EXCLUDED.oauth_data_encrypted, integration_connections.oauth_data_encrypted)""",
        tenant_id,
        connection_id,
        provider,
        status,
        org_name,
        encrypted,
        created_by,
    )


async def list_connections(
    conn: asyncpg.Connection,
    tenant_id: str,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """SELECT connection_id, provider, status, org_name, last_sync_at, created_at
           FROM integration_connections WHERE tenant_id = $1 ORDER BY created_at DESC""",
        tenant_id,
    )
    return [
        {
            "connection_id": r["connection_id"],
            "provider": r["provider"],
            "status": r["status"],
            "org_name": r["org_name"],
            "last_sync_at": r["last_sync_at"].isoformat() if r["last_sync_at"] else None,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def delete_connection(
    conn: asyncpg.Connection,
    tenant_id: str,
    connection_id: str,
) -> bool:
    """Delete connection; returns True if a row was deleted."""
    r = await conn.execute(
        "DELETE FROM integration_connections WHERE tenant_id = $1 AND connection_id = $2",
        tenant_id,
        connection_id,
    )
    return r == "DELETE 1"


async def update_connection_status(
    conn: asyncpg.Connection,
    tenant_id: str,
    connection_id: str,
    status: str,
    last_sync_at: Any = None,
) -> None:
    await conn.execute(
        """UPDATE integration_connections SET status = $3, last_sync_at = $4
           WHERE tenant_id = $1 AND connection_id = $2""",
        tenant_id,
        connection_id,
        status,
        last_sync_at,
    )


async def insert_sync_run(
    conn: asyncpg.Connection,
    tenant_id: str,
    sync_run_id: str,
    connection_id: str,
    status: str = "running",
) -> None:
    await conn.execute(
        """INSERT INTO integration_sync_runs (tenant_id, sync_run_id, connection_id, status)
           VALUES ($1, $2, $3, $4)""",
        tenant_id,
        sync_run_id,
        connection_id,
        status,
    )


async def complete_sync_run(
    conn: asyncpg.Connection,
    tenant_id: str,
    sync_run_id: str,
    status: str,
    records_synced: int = 0,
    snapshot_id: str | None = None,
    error_details: str | None = None,
) -> None:
    await conn.execute(
        """UPDATE integration_sync_runs SET
             status = $3, records_synced = $4, snapshot_id = $5, error_details = $6, completed_at = now()
           WHERE tenant_id = $1 AND sync_run_id = $2""",
        tenant_id,
        sync_run_id,
        status,
        records_synced,
        snapshot_id,
        error_details,
    )


async def insert_snapshot(
    conn: asyncpg.Connection,
    tenant_id: str,
    snapshot_id: str,
    connection_id: str,
    as_of: str,
    period_start: str | None,
    period_end: str | None,
    storage_path: str,
) -> None:
    await conn.execute(
        """INSERT INTO canonical_sync_snapshots
           (tenant_id, snapshot_id, connection_id, as_of, period_start, period_end, storage_path)
           VALUES ($1, $2, $3, $4::timestamptz, $5::date, $6::date, $7)""",
        tenant_id,
        snapshot_id,
        connection_id,
        as_of,
        period_start,
        period_end,
        storage_path,
    )


async def list_snapshots(
    conn: asyncpg.Connection,
    tenant_id: str,
    connection_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """SELECT snapshot_id, connection_id, as_of, period_start, period_end, storage_path, created_at
           FROM canonical_sync_snapshots
           WHERE tenant_id = $1 AND connection_id = $2 ORDER BY as_of DESC LIMIT $3 OFFSET $4""",
        tenant_id,
        connection_id,
        limit,
        offset,
    )
    return [
        {
            "snapshot_id": r["snapshot_id"],
            "connection_id": r["connection_id"],
            "as_of": r["as_of"].isoformat() if r["as_of"] else None,
            "period_start": str(r["period_start"]) if r["period_start"] else None,
            "period_end": str(r["period_end"]) if r["period_end"] else None,
            "storage_path": r["storage_path"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
