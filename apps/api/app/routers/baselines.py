"""Baseline CRUD: create, list, get, patch (archive/restore)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from apps.api.app.db import ensure_tenant, tenant_conn
from apps.api.app.db.audit import (
    EVENT_BASELINE_ACCESSED,
    EVENT_BASELINE_CREATED,
    create_audit_event,
)
from apps.api.app.deps import get_artifact_store, require_role, ROLES_ANY, ROLES_CAN_WRITE
from shared.fm_shared.errors import StorageError
from shared.fm_shared.model.schemas import ModelConfig
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/baselines", tags=["baselines"])


class CreateBaselineBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    model_config_payload: dict[str, Any] = Field(..., alias="model_config")


@router.post("", status_code=201)
async def create_baseline(
    body: CreateBaselineBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    try:
        ModelConfig.model_validate(body.model_config_payload)
    except Exception as e:
        raise HTTPException(400, str(e)) from e
    baseline_id = f"bl_{uuid.uuid4().hex[:12]}"
    baseline_version = "v1"
    storage_path = f"{x_tenant_id}/model_config_v1/{baseline_id}_{baseline_version}.json"
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            await ensure_tenant(conn, x_tenant_id)
            await conn.execute(
                "UPDATE model_baselines SET is_active = false WHERE tenant_id = $1",
                x_tenant_id,
            )
            await conn.execute(
                """INSERT INTO model_baselines (tenant_id, baseline_id, baseline_version, status, storage_path, is_active)
                   VALUES ($1, $2, $3, 'active', $4, true)""",
                x_tenant_id,
                baseline_id,
                baseline_version,
                storage_path,
            )
            store.save(
                x_tenant_id,
                "model_config_v1",
                f"{baseline_id}_{baseline_version}",
                body.model_config_payload,
            )
            await create_audit_event(
                conn,
                x_tenant_id,
                EVENT_BASELINE_CREATED,
                "baseline",
                "baseline",
                baseline_id,
                user_id=x_user_id or None,
                event_data={"baseline_version": baseline_version, "storage_path": storage_path},
            )
    return {
        "tenant_id": x_tenant_id,
        "baseline_id": baseline_id,
        "baseline_version": baseline_version,
        "status": "active",
        "storage_path": storage_path,
    }


@router.get("")
async def list_baselines(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=100, description="Max 100 to avoid N+1 and large responses"),
    offset: int = Query(0, ge=0),
    _: None = require_role(*ROLES_ANY),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT baseline_id, baseline_version, status, storage_path, is_active, created_at
               FROM model_baselines WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
            x_tenant_id,
            limit,
            offset,
        )
        items = [
            {
                "baseline_id": r["baseline_id"],
                "baseline_version": r["baseline_version"],
                "status": r["status"],
                "is_active": r["is_active"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return {"items": items, "limit": limit, "offset": offset}


@router.get("/{baseline_id}")
async def get_baseline(
    baseline_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    _: None = require_role(*ROLES_ANY),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        try:
            row = await conn.fetchrow(
                """SELECT baseline_id, baseline_version, status, storage_path, is_active, created_at
                   FROM model_baselines WHERE tenant_id = $1 AND baseline_id = $2 AND is_active = true""",
                x_tenant_id,
                baseline_id,
            )
            if not row:
                raise HTTPException(404, "Baseline not found")
            artifact_id = f"{row['baseline_id']}_{row['baseline_version']}"
            config = store.load(x_tenant_id, "model_config_v1", artifact_id)
            await create_audit_event(
                conn,
                x_tenant_id,
                EVENT_BASELINE_ACCESSED,
                "baseline",
                "baseline",
                baseline_id,
                user_id=x_user_id or None,
                event_data={"baseline_version": row["baseline_version"]},
            )
            return {
                "baseline_id": row["baseline_id"],
                "baseline_version": row["baseline_version"],
                "status": row["status"],
                "is_active": row["is_active"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "model_config": config,
            }
        except StorageError as e:
            if e.code == "ERR_STOR_NOT_FOUND":
                raise HTTPException(404, "Baseline artifact not found") from e
            raise


class PatchBaselineBody(BaseModel):
    status: Literal["active", "archived"]


@router.patch("/{baseline_id}")
async def patch_baseline(
    baseline_id: str,
    body: PatchBaselineBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            if body.status == "active":
                await conn.execute(
                    "UPDATE model_baselines SET is_active = false WHERE tenant_id = $1", x_tenant_id
                )
            await conn.execute(
                "UPDATE model_baselines SET status = $1, is_active = $2 WHERE tenant_id = $3 AND baseline_id = $4",
                body.status,
                body.status == "active",
                x_tenant_id,
                baseline_id,
            )
        return {"baseline_id": baseline_id, "status": body.status}
