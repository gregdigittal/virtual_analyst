"""Draft session CRUD: create, list, get, patch (status/workspace), delete (abandon)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from apps.api.app.db import ensure_tenant, get_conn
from apps.api.app.db.audit import (
    EVENT_DRAFT_ABANDONED,
    EVENT_DRAFT_ACCESSED,
    EVENT_DRAFT_CREATED,
    create_audit_event,
)
from apps.api.app.deps import get_artifact_store
from shared.fm_shared.errors import StorageError
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/drafts", tags=["drafts"])

DRAFT_WORKSPACE_TYPE = "draft_workspace"
STATUS_ACTIVE = "active"
STATUS_READY_TO_COMMIT = "ready_to_commit"
STATUS_COMMITTED = "committed"
STATUS_ABANDONED = "abandoned"

VALID_TRANSITIONS: dict[str, set[str]] = {
    STATUS_ACTIVE: {STATUS_READY_TO_COMMIT, STATUS_ABANDONED},
    STATUS_READY_TO_COMMIT: {STATUS_ACTIVE, STATUS_COMMITTED, STATUS_ABANDONED},
    STATUS_COMMITTED: set(),
    STATUS_ABANDONED: set(),
}


class CreateDraftBody(BaseModel):
    """Optional template and parent baseline for new draft."""

    template_id: str | None = None
    parent_baseline_id: str | None = None
    parent_baseline_version: str | None = None


def _empty_workspace(draft_session_id: str, template_id: str | None, parent_baseline_id: str | None, parent_baseline_version: str | None) -> dict[str, Any]:
    return {
        "draft_session_id": draft_session_id,
        "template_id": template_id,
        "parent_baseline_id": parent_baseline_id,
        "parent_baseline_version": parent_baseline_version,
        "assumptions": {
            "revenue_streams": [],
            "cost_structure": {"variable_costs": [], "fixed_costs": []},
            "working_capital": {},
            "capex": {},
            "funding": {},
        },
        "driver_blueprint": {"nodes": [], "edges": [], "formulas": []},
        "distributions": [],
        "scenarios": [],
        "evidence": [],
        "chat_history": [],
        "pending_proposals": [],
    }


@router.post("", status_code=201)
async def create_draft(
    body: CreateDraftBody | None = None,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Create a new draft session. Optionally from existing baseline (future: load workspace from baseline)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    b = body or CreateDraftBody()
    draft_session_id = f"ds_{uuid.uuid4().hex[:12]}"
    storage_path = f"{x_tenant_id}/{DRAFT_WORKSPACE_TYPE}/{draft_session_id}.json"
    workspace = _empty_workspace(
        draft_session_id, b.template_id, b.parent_baseline_id, b.parent_baseline_version
    )
    store.save(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id, workspace)
    conn = await get_conn()
    try:
        async with conn.transaction():
            await ensure_tenant(conn, x_tenant_id)
            await conn.execute(
                """INSERT INTO draft_sessions (tenant_id, draft_session_id, parent_baseline_id, parent_baseline_version, status, storage_path, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                x_tenant_id,
                draft_session_id,
                b.parent_baseline_id,
                b.parent_baseline_version,
                STATUS_ACTIVE,
                storage_path,
                x_user_id or None,
            )
            await create_audit_event(
                conn,
                x_tenant_id,
                EVENT_DRAFT_CREATED,
                "draft",
                "draft_session",
                draft_session_id,
                user_id=x_user_id or None,
                event_data={"storage_path": storage_path},
            )
        return {
            "draft_session_id": draft_session_id,
            "status": STATUS_ACTIVE,
            "storage_path": storage_path,
        }
    finally:
        await conn.close()


@router.get("")
async def list_drafts(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    status: Literal["active", "ready_to_commit", "committed", "abandoned"] | None = None,
) -> dict[str, Any]:
    """List draft sessions for tenant, optionally filtered by status."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    conn = await get_conn()
    try:
        if status:
            rows = await conn.fetch(
                """SELECT draft_session_id, parent_baseline_id, parent_baseline_version, status, created_at
                   FROM draft_sessions WHERE tenant_id = $1 AND status = $2 ORDER BY created_at DESC""",
                x_tenant_id,
                status,
            )
        else:
            rows = await conn.fetch(
                """SELECT draft_session_id, parent_baseline_id, parent_baseline_version, status, created_at
                   FROM draft_sessions WHERE tenant_id = $1 ORDER BY created_at DESC""",
                x_tenant_id,
            )
        items = [
            {
                "draft_session_id": r["draft_session_id"],
                "parent_baseline_id": r["parent_baseline_id"],
                "parent_baseline_version": r["parent_baseline_version"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return {"items": items}
    finally:
        await conn.close()


@router.get("/{draft_session_id}")
async def get_draft(
    draft_session_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Return draft workspace and meta. Rejects abandoned/committed unless we allow read."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            """SELECT draft_session_id, parent_baseline_id, parent_baseline_version, status, storage_path, created_at
               FROM draft_sessions WHERE tenant_id = $1 AND draft_session_id = $2""",
            x_tenant_id,
            draft_session_id,
        )
        if not row:
            raise HTTPException(404, "Draft not found")
        if row["status"] == STATUS_ABANDONED:
            raise HTTPException(410, "Draft abandoned")
        workspace = store.load(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id)
        await create_audit_event(
            conn,
            x_tenant_id,
            EVENT_DRAFT_ACCESSED,
            "draft",
            "draft_session",
            draft_session_id,
            user_id=x_user_id or None,
            event_data={"status": row["status"]},
        )
        return {
            "draft_session_id": row["draft_session_id"],
            "parent_baseline_id": row["parent_baseline_id"],
            "parent_baseline_version": row["parent_baseline_version"],
            "status": row["status"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "workspace": workspace,
        }
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Draft workspace not found") from e
        raise
    finally:
        await conn.close()


@router.patch("/{draft_session_id}")
async def patch_draft(
    draft_session_id: str,
    body: dict[str, Any],
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Update status (state machine) and/or workspace (autosave). Invalid transitions return 409."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    new_status: str | None = body.get("status")
    workspace_update: dict[str, Any] | None = body.get("workspace")
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            """SELECT draft_session_id, status, storage_path FROM draft_sessions
               WHERE tenant_id = $1 AND draft_session_id = $2""",
            x_tenant_id,
            draft_session_id,
        )
        if not row:
            raise HTTPException(404, "Draft not found")
        if row["status"] in (STATUS_ABANDONED, STATUS_COMMITTED):
            raise HTTPException(410, f"Draft is {row['status']}")

        if new_status is not None:
            allowed = VALID_TRANSITIONS.get(row["status"], set())
            if new_status not in allowed:
                raise HTTPException(
                    409,
                    f"Invalid transition from {row['status']} to {new_status}",
                )
            await conn.execute(
                "UPDATE draft_sessions SET status = $1 WHERE tenant_id = $2 AND draft_session_id = $3",
                new_status,
                x_tenant_id,
                draft_session_id,
            )

        if workspace_update is not None:
            current = store.load(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id)
            merged = {**current, **workspace_update}
            store.save(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id, merged)

        row2 = await conn.fetchrow(
            """SELECT draft_session_id, status FROM draft_sessions
               WHERE tenant_id = $1 AND draft_session_id = $2""",
            x_tenant_id,
            draft_session_id,
        )
        return {
            "draft_session_id": draft_session_id,
            "status": row2["status"] if row2 else new_status or row["status"],
        }
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Draft workspace not found") from e
        raise
    finally:
        await conn.close()


@router.delete("/{draft_session_id}", status_code=200)
async def delete_draft(
    draft_session_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Abandon draft (soft delete: set status=abandoned)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    conn = await get_conn()
    try:
        async with conn.transaction():
            res = await conn.execute(
                """UPDATE draft_sessions SET status = $1
                   WHERE tenant_id = $2 AND draft_session_id = $3 AND status NOT IN ($4, $5)
                   RETURNING draft_session_id""",
                STATUS_ABANDONED,
                x_tenant_id,
                draft_session_id,
                STATUS_ABANDONED,
                STATUS_COMMITTED,
            )
            if res == "UPDATE 0":
                row = await conn.fetchrow(
                    "SELECT status FROM draft_sessions WHERE tenant_id = $1 AND draft_session_id = $2",
                    x_tenant_id,
                    draft_session_id,
                )
                if not row:
                    raise HTTPException(404, "Draft not found")
                raise HTTPException(410, f"Draft is already {row['status']}")
            await create_audit_event(
                conn,
                x_tenant_id,
                EVENT_DRAFT_ABANDONED,
                "draft",
                "draft_session",
                draft_session_id,
                user_id=x_user_id or None,
            )
        return {"draft_session_id": draft_session_id, "status": STATUS_ABANDONED}
    finally:
        await conn.close()
