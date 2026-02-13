"""Excel live links API (VA-P5-01): connections CRUD, pull, push."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.db.excel import (
    create_connection as db_create_connection,
    delete_connection as db_delete_connection,
    get_connection as db_get_connection,
    insert_sync_event,
    list_connections as db_list_connections,
    update_connection as db_update_connection,
)
from apps.api.app.deps import get_artifact_store
from shared.fm_shared.errors import StorageError
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/excel", tags=["excel"])


class CreateExcelConnectionBody(BaseModel):
    target_json: dict[str, Any] = Field(
        ..., description="Target: { baseline_id, baseline_version, run_id }"
    )
    bindings_json: list[dict[str, Any]] = Field(
        default_factory=list, description="Cell bindings"
    )
    mode: str = Field(default="readonly", description="readonly or readwrite")
    label: str | None = Field(default=None, description="Human-readable label")
    workbook_json: dict[str, Any] | None = Field(default=None)
    sync_json: dict[str, Any] | None = Field(default=None)
    permissions_json: dict[str, Any] | None = Field(default=None)


def _get_by_path(data: dict | list, path: str) -> Any:
    """Get value at dot-separated path, e.g. income_statement.0.revenue."""
    parts = path.split(".")
    obj: Any = data
    for p in parts:
        if isinstance(obj, list):
            obj = obj[int(p)]
        else:
            obj = obj.get(p)
        if obj is None:
            return None
    return obj


@router.post("/connections", status_code=201)
async def create_excel_connection(
    body: CreateExcelConnectionBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create an Excel connection (target baseline/run, bindings)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.mode not in ("readonly", "readwrite"):
        raise HTTPException(400, "mode must be readonly or readwrite")
    async with tenant_conn(x_tenant_id) as conn:
        excel_connection_id = await db_create_connection(
            conn,
            x_tenant_id,
            body.label,
            body.mode,
            body.target_json,
            body.bindings_json,
            body.workbook_json,
            body.sync_json,
            body.permissions_json,
            x_user_id or None,
        )
    return {
        "excel_connection_id": excel_connection_id,
        "label": body.label,
        "mode": body.mode,
        "target_json": body.target_json,
        "bindings_json": body.bindings_json,
    }


@router.get("/connections")
async def list_excel_connections(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List Excel connections for the tenant."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        items = await db_list_connections(conn, x_tenant_id, limit=limit, offset=offset)
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/connections/{excel_connection_id}")
async def get_excel_connection(
    excel_connection_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get one Excel connection by id."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await db_get_connection(conn, x_tenant_id, excel_connection_id)
    if not row:
        raise HTTPException(404, "Excel connection not found")
    return row


@router.patch("/connections/{excel_connection_id}")
async def update_excel_connection(
    excel_connection_id: str,
    body: dict[str, Any],
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Update connection (label, mode, bindings_json, sync_json, status)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            row = await db_get_connection(conn, x_tenant_id, excel_connection_id)
            if not row:
                raise HTTPException(404, "Excel connection not found")
            await db_update_connection(
                conn,
                x_tenant_id,
                excel_connection_id,
                label=body.get("label"),
                mode=body.get("mode"),
                bindings_json=body.get("bindings_json") or body.get("bindings"),
                sync_json=body.get("sync_json"),
                status=body.get("status"),
            )
    return {"excel_connection_id": excel_connection_id, "updated": True}


@router.delete("/connections/{excel_connection_id}")
async def delete_excel_connection(
    excel_connection_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Delete an Excel connection."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        ok = await db_delete_connection(conn, x_tenant_id, excel_connection_id)
    if not ok:
        raise HTTPException(404, "Excel connection not found")
    return {"excel_connection_id": excel_connection_id, "deleted": True}


@router.post("/connections/{excel_connection_id}/pull")
async def excel_pull(
    excel_connection_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Gather current values for all bindings from run/baseline. Returns list of { binding_id, value, path }."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await db_get_connection(conn, x_tenant_id, excel_connection_id)
        if not row:
            raise HTTPException(404, "Excel connection not found")
        target = row["target_json"]
        run_id = target.get("run_id")
        bindings = row["bindings_json"]
        if not run_id:
            raise HTTPException(400, "Pull requires target_json.run_id")
        try:
            data = store.load(x_tenant_id, "run_results", f"{run_id}_statements")
        except StorageError as e:
            if e.code == "ERR_STOR_NOT_FOUND":
                raise HTTPException(404, "Run results not found") from e
            raise
        statements = data.get("statements", {})
        kpis = data.get("kpis", [])
        values = _resolve_pull_values(statements, kpis, bindings)
        await insert_sync_event(
            conn,
            x_tenant_id,
            excel_connection_id,
            direction="pull",
            status="succeeded",
            diff_json={"bindings": len(values)},
            initiated_by=x_user_id or None,
            bindings_synced=len(values),
            target_json=target,
        )
    return {"values": values}


def _resolve_pull_values(statements: dict[str, Any], kpis: list[dict], bindings: list[dict]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for b in bindings:
        bid = b.get("binding_id") or b.get("id")
        path = b.get("path")
        if not path:
            continue
        try:
            if path.startswith("kpis."):
                val = _get_by_path(kpis, path[5:].strip("."))
            else:
                val = _get_by_path(statements, path)
        except (KeyError, IndexError, TypeError):
            val = None
        out.append({"binding_id": bid, "path": path, "value": val})
    return out


@router.post("/connections/{excel_connection_id}/push")
async def excel_push(
    excel_connection_id: str,
    body: dict[str, Any],
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Receive changed values from Excel. Logs sync event; push_behavior can be draft_override or changeset (future)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    changes = body.get("changes") or []
    if not isinstance(changes, list):
        raise HTTPException(400, "changes must be an array of { binding_id, new_value }")
    if len(changes) > 500:
        raise HTTPException(400, "Maximum 500 changes per push")
    for c in changes:
        if not isinstance(c, dict) or "binding_id" not in c:
            raise HTTPException(400, "Each change must have a binding_id")
    async with tenant_conn(x_tenant_id) as conn:
        row = await db_get_connection(conn, x_tenant_id, excel_connection_id)
        if not row:
            raise HTTPException(404, "Excel connection not found")
        if row["mode"] != "readwrite":
            raise HTTPException(403, "Connection is readonly; push requires mode=readwrite")
        await insert_sync_event(
            conn,
            x_tenant_id,
            excel_connection_id,
            direction="push",
            status="succeeded",
            diff_json={"changed": changes, "errors": []},
            initiated_by=x_user_id or None,
            bindings_synced=len(changes),
            target_json=row["target_json"],
        )
    return {"received": len(changes), "status": "logged"}
