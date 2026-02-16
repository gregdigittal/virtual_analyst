"""Integrations API: OAuth connections and sync (Xero, etc.)."""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from apps.api.app.db import ensure_tenant, tenant_conn
from apps.api.app.db.integrations import (
    complete_sync_run,
    delete_connection,
    get_connection,
    insert_snapshot,
    insert_sync_run,
    list_connections,
    list_snapshots,
    update_connection_status,
    upsert_connection,
)
from apps.api.app.deps import get_artifact_store, require_role, ROLES_OWNER_OR_ADMIN
from apps.api.app.core.settings import get_settings
from apps.api.app.services.integrations import get_adapter
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/integrations", tags=["integrations"], dependencies=[require_role(*ROLES_OWNER_OR_ADMIN)])

CANONICAL_ARTIFACT_TYPE = "canonical_sync_snapshot_v1"


def _sign_oauth_state(tenant_id: str, provider: str, secret: str) -> str:
    """Create signed state: timestamp.tenant_id.provider.signature"""
    ts = str(int(time.time()))
    payload = f"{ts}.{tenant_id}.{provider}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload}.{sig}"


def _verify_oauth_state(state: str, secret: str, max_age_seconds: int = 600) -> tuple[str, str] | None:
    """Verify signed state; return (tenant_id, provider) or None if invalid/expired."""
    parts = state.rsplit(".", 1)
    if len(parts) != 2:
        return None
    payload, sig = parts
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected):
        return None
    payload_parts = payload.split(".", 2)
    if len(payload_parts) != 3:
        return None
    ts_str, tenant_id, provider = payload_parts
    try:
        if int(time.time()) - int(ts_str) > max_age_seconds:
            return None
    except ValueError:
        return None
    return (tenant_id, provider)


class InitiateConnectionBody(BaseModel):
    provider: str = Field(..., description="Provider id, e.g. xero")


class SyncConnectionBody(BaseModel):
    period_start: date | None = None
    period_end: date | None = None


@router.post("/connections", status_code=201)
async def initiate_connection(
    body: InitiateConnectionBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Return OAuth authorize URL for the given provider. Client redirects user there."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    adapter = get_adapter(body.provider)
    if not adapter:
        raise HTTPException(400, f"Unknown provider: {body.provider}")
    settings = get_settings()
    redirect_uri = settings.integration_oauth_redirect_uri
    state = _sign_oauth_state(x_tenant_id, body.provider, settings.oauth_state_secret)
    url = await adapter.get_authorize_url(state, redirect_uri)
    return {"authorize_url": url, "state": state}


@router.get("/connections/callback")
async def oauth_callback(
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="State (tenant_id)"),
) -> Any:
    """Exchange code for tokens, store connection, redirect to app. No auth header (browser redirect)."""
    settings = get_settings()
    parsed = _verify_oauth_state(state, settings.oauth_state_secret)
    if not parsed:
        raise HTTPException(400, "Invalid or expired OAuth state")
    x_tenant_id, provider = parsed
    adapter = get_adapter(provider)
    if not adapter:
        raise HTTPException(502, f"{provider} adapter not configured")
    redirect_uri = settings.integration_oauth_redirect_uri
    try:
        result = await adapter.exchange_code(code, redirect_uri)
    except Exception as e:
        raise HTTPException(400, f"OAuth exchange failed: {e}") from e
    connection_id = f"conn_{uuid.uuid4().hex[:16]}"
    oauth_data = {
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "expires_at": result.expires_at,
    }
    if result.provider_tenant_id:
        if provider == "xero":
            oauth_data["xero_tenant_id"] = result.provider_tenant_id
        else:
            oauth_data["realm_id"] = result.provider_tenant_id
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            await ensure_tenant(conn, x_tenant_id)
            await upsert_connection(
                conn,
                x_tenant_id,
                connection_id,
                provider,
                "connected",
                org_name=result.org_name,
                oauth_data=oauth_data,
                created_by=None,
            )
    app_url = settings.integration_callback_base_url.rstrip("/")
    return RedirectResponse(url=f"{app_url}?connection_id={connection_id}&provider={provider}", status_code=302)


@router.get("/connections")
async def list_connections_route(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        await ensure_tenant(conn, x_tenant_id)
        items = await list_connections(conn, x_tenant_id)
    return {"connections": items}


@router.get("/connections/{connection_id}")
async def get_connection_route(
    connection_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await get_connection(conn, x_tenant_id, connection_id)
    if not row:
        raise HTTPException(404, "Connection not found")
    out = dict(row)
    out.pop("oauth", None)
    return out


@router.post("/connections/{connection_id}/sync", status_code=202)
async def trigger_sync(
    connection_id: str,
    body: SyncConnectionBody | None = None,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Start a sync run; returns sync_run_id. Snapshot is written to artifact store and DB."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    body = body or SyncConnectionBody()
    async with tenant_conn(x_tenant_id) as conn:
        row = await get_connection(conn, x_tenant_id, connection_id)
    if not row:
        raise HTTPException(404, "Connection not found")
    if row["status"] != "connected":
        raise HTTPException(400, "Connection not active")
    adapter = get_adapter(row["provider"])
    if not adapter:
        raise HTTPException(502, f"Adapter not configured: {row['provider']}")
    oauth = row.get("oauth") or {}
    access = oauth.get("access_token")
    if not access:
        raise HTTPException(400, "Connection missing tokens")
    sync_run_id = f"sync_{uuid.uuid4().hex[:16]}"
    period_start = body.period_start
    period_end = body.period_end or date.today()

    async with tenant_conn(x_tenant_id) as conn:
        await insert_sync_run(conn, x_tenant_id, sync_run_id, connection_id, "running")

    try:
        result = await adapter.sync(
            access_token=access,
            period_start=period_start,
            period_end=period_end,
            tenant_id=oauth.get("xero_tenant_id") or oauth.get("realm_id"),
        )
    except Exception as e:
        async with tenant_conn(x_tenant_id) as conn:
            await complete_sync_run(conn, x_tenant_id, sync_run_id, "failed", error_details=str(e))
        raise HTTPException(502, f"Sync failed: {e}") from e

    snapshot_id = f"snap_{uuid.uuid4().hex[:16]}"
    storage_path = store.save(
        x_tenant_id,
        CANONICAL_ARTIFACT_TYPE,
        snapshot_id,
        result.canonical_snapshot,
    )
    as_of = result.canonical_snapshot.get("as_of") or datetime.now(UTC).isoformat()
    period_start_str = result.canonical_snapshot.get("period_start")
    period_end_str = result.canonical_snapshot.get("period_end")

    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            await insert_snapshot(
                conn,
                x_tenant_id,
                snapshot_id,
                connection_id,
                as_of,
                period_start_str,
                period_end_str,
                storage_path,
            )
            await complete_sync_run(
                conn,
                x_tenant_id,
                sync_run_id,
                "succeeded",
                records_synced=result.records_synced,
                snapshot_id=snapshot_id,
            )
            await update_connection_status(
                conn,
                x_tenant_id,
                connection_id,
                "connected",
                last_sync_at=datetime.now(UTC),
            )

    return {
        "sync_run_id": sync_run_id,
        "status": "succeeded",
        "snapshot_id": snapshot_id,
        "records_synced": result.records_synced,
    }


@router.get("/connections/{connection_id}/snapshots")
async def list_snapshots_route(
    connection_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await get_connection(conn, x_tenant_id, connection_id)
        if not row:
            raise HTTPException(404, "Connection not found")
        items = await list_snapshots(conn, x_tenant_id, connection_id, limit=limit, offset=offset)
    return {"snapshots": items}


@router.delete("/connections/{connection_id}")
async def disconnect_connection(
    connection_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        deleted = await delete_connection(conn, x_tenant_id, connection_id)
    if not deleted:
        raise HTTPException(404, "Connection not found")
    return {"status": "disconnected"}
