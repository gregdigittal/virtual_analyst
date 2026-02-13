"""Changesets: create, get, test (dry-run), merge."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from apps.api.app.db import ensure_tenant, tenant_conn
from apps.api.app.deps import get_artifact_store
from apps.api.app.routers.drafts import _set_by_path
from shared.fm_shared.errors import StorageError
from shared.fm_shared.model import run_engine
from shared.fm_shared.model.schemas import ModelConfig
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/changesets", tags=["changesets"])

CHANGESET_OVERRIDES_TYPE = "changeset_overrides"
STATUS_DRAFT = "draft"
STATUS_TESTED = "tested"
STATUS_MERGED = "merged"
STATUS_ABANDONED = "abandoned"


def _apply_overrides(config_dict: dict[str, Any], overrides: list[dict[str, Any]]) -> dict[str, Any]:
    out = copy.deepcopy(config_dict)
    for o in overrides:
        path = (o.get("path") or "").strip(".")
        value = o.get("value")
        if not path:
            continue
        try:
            _set_by_path(out, path, value)
        except (KeyError, IndexError, TypeError):
            continue
    return out


@router.post("", status_code=201)
async def create_changeset(
    body: dict[str, Any],
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    baseline_id = body.get("baseline_id")
    baseline_version = body.get("base_version") or body.get("baseline_version")
    overrides = body.get("overrides") or []
    if not baseline_id or not baseline_version:
        raise HTTPException(400, "baseline_id and base_version required")
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    changeset_id = f"cs_{uuid.uuid4().hex[:12]}"
    storage_path = f"{x_tenant_id}/{CHANGESET_OVERRIDES_TYPE}/{changeset_id}.json"
    payload = {"overrides": overrides}
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT baseline_id, baseline_version FROM model_baselines
               WHERE tenant_id = $1 AND baseline_id = $2 AND baseline_version = $3""",
            x_tenant_id,
            baseline_id,
            baseline_version,
        )
        if not row:
            raise HTTPException(404, "Baseline not found")
        async with conn.transaction():
            await ensure_tenant(conn, x_tenant_id)
            await conn.execute(
                """INSERT INTO model_changesets (tenant_id, changeset_id, baseline_id, base_version, status, storage_path, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                x_tenant_id,
                changeset_id,
                baseline_id,
                baseline_version,
                STATUS_DRAFT,
                storage_path,
                x_user_id or None,
            )
            store.save(x_tenant_id, CHANGESET_OVERRIDES_TYPE, changeset_id, payload)
    return {
        "changeset_id": changeset_id,
        "baseline_id": baseline_id,
        "base_version": baseline_version,
        "status": STATUS_DRAFT,
        "overrides": overrides,
    }


@router.get("/{changeset_id}")
async def get_changeset(
    changeset_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT changeset_id, baseline_id, base_version, status, storage_path, created_at
               FROM model_changesets WHERE tenant_id = $1 AND changeset_id = $2""",
            x_tenant_id,
            changeset_id,
        )
        if not row:
            raise HTTPException(404, "Changeset not found")
    try:
        data = store.load(x_tenant_id, CHANGESET_OVERRIDES_TYPE, changeset_id)
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Changeset overrides not found") from e
        raise
    overrides = data.get("overrides") or []
    return {
        "changeset_id": row["changeset_id"],
        "baseline_id": row["baseline_id"],
        "base_version": row["base_version"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "overrides": overrides,
    }


@router.post("/{changeset_id}/test")
async def test_changeset(
    changeset_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT changeset_id, baseline_id, base_version FROM model_changesets
               WHERE tenant_id = $1 AND changeset_id = $2""",
            x_tenant_id,
            changeset_id,
        )
        if not row:
            raise HTTPException(404, "Changeset not found")
    try:
        overrides_data = store.load(x_tenant_id, CHANGESET_OVERRIDES_TYPE, changeset_id)
        config_dict = store.load(
            x_tenant_id,
            "model_config_v1",
            f"{row['baseline_id']}_{row['base_version']}",
        )
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Artifact not found") from e
        raise
    overrides = overrides_data.get("overrides") or []
    applied = _apply_overrides(config_dict, overrides)
    config = ModelConfig.model_validate(applied)
    time_series = run_engine(config, None)
    return {"time_series": time_series, "applied_overrides": len(overrides)}


@router.post("/{changeset_id}/merge")
async def merge_changeset(
    changeset_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT changeset_id, baseline_id, base_version, status FROM model_changesets
                   WHERE tenant_id = $1 AND changeset_id = $2 FOR UPDATE""",
                x_tenant_id,
                changeset_id,
            )
            if not row:
                raise HTTPException(404, "Changeset not found")
            if row["status"] == STATUS_MERGED:
                raise HTTPException(409, "Changeset already merged")
            if row["status"] == STATUS_ABANDONED:
                raise HTTPException(409, "Changeset abandoned")
            versions = await conn.fetch(
                """SELECT baseline_version FROM model_baselines
                   WHERE tenant_id = $1 AND baseline_id = $2""",
                x_tenant_id,
                row["baseline_id"],
            )
            max_n = 0
            for v in versions:
                try:
                    n = int(str(v["baseline_version"]).replace("v", ""))
                    max_n = max(max_n, n)
                except ValueError:
                    pass
            next_ver = f"v{max_n + 1}"
            try:
                overrides_data = store.load(x_tenant_id, CHANGESET_OVERRIDES_TYPE, changeset_id)
                config_dict = store.load(
                    x_tenant_id,
                    "model_config_v1",
                    f"{row['baseline_id']}_{row['base_version']}",
                )
            except StorageError as e:
                if e.code == "ERR_STOR_NOT_FOUND":
                    raise HTTPException(404, "Artifact not found") from e
                raise
            overrides = overrides_data.get("overrides") or []
            applied = _apply_overrides(config_dict, overrides)
            applied["baseline_version"] = next_ver
            applied["artifact_version"] = "1.0.0"
            ModelConfig.model_validate(applied)
            storage_path = f"{x_tenant_id}/model_config_v1/{row['baseline_id']}_{next_ver}.json"
            await ensure_tenant(conn, x_tenant_id)
            await conn.execute(
                "UPDATE model_baselines SET is_active = false WHERE tenant_id = $1",
                x_tenant_id,
            )
            await conn.execute(
                """INSERT INTO model_baselines (tenant_id, baseline_id, baseline_version, status, storage_path, is_active)
                   VALUES ($1, $2, $3, 'active', $4, true)""",
                x_tenant_id,
                row["baseline_id"],
                next_ver,
                storage_path,
            )
            store.save(x_tenant_id, "model_config_v1", f"{row['baseline_id']}_{next_ver}", applied)
            await conn.execute(
                """UPDATE model_changesets SET status = $1 WHERE tenant_id = $2 AND changeset_id = $3""",
                STATUS_MERGED,
                x_tenant_id,
                changeset_id,
            )
    return {
        "changeset_id": changeset_id,
        "baseline_id": row["baseline_id"],
        "new_version": next_ver,
        "status": STATUS_MERGED,
    }
