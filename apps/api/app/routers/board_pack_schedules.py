"""Board pack scheduling & distribution (VA-P7-09): CRUD schedules, run-now, history, distribute stub."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_artifact_store, get_llm_router, require_role, ROLES_CAN_WRITE
from apps.api.app.routers.board_packs import (
    DEFAULT_SECTION_ORDER,
    create_board_pack_impl,
    generate_board_pack_impl,
)
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.errors import LLMError, StorageError
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/board-packs/schedules", tags=["board-packs"], dependencies=[require_role(*ROLES_CAN_WRITE)])


class CreateScheduleBody(BaseModel):
    label: str = Field(..., description="Schedule label")
    run_id: str = Field(..., description="Run ID for generated packs")
    budget_id: str | None = Field(default=None, description="Optional budget ID")
    section_order: list[str] | None = Field(default=None, description="Section order")
    cron_expr: str = Field(..., description="Cron expression (e.g. 0 9 5 * * for 5th at 9am monthly)")
    distribution_emails: list[str] = Field(default_factory=list, description="Emails to receive pack")


class PatchScheduleBody(BaseModel):
    label: str | None = None
    run_id: str | None = None
    budget_id: str | None = None
    cron_expr: str | None = None
    distribution_emails: list[str] | None = None
    enabled: bool | None = None


class DistributeBody(BaseModel):
    emails: list[str] = Field(default_factory=list, description="Override distribution list for this run")


@router.post("", status_code=201)
async def create_schedule(
    body: CreateScheduleBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a recurring board pack schedule (VA-P7-09)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    schedule_id = f"sch_{uuid.uuid4().hex[:12]}"
    section_order = body.section_order or DEFAULT_SECTION_ORDER
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO pack_schedules (tenant_id, schedule_id, label, run_id, budget_id, section_order, cron_expr, distribution_emails, created_by)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)""",
            x_tenant_id,
            schedule_id,
            body.label,
            body.run_id,
            body.budget_id,
            json.dumps(section_order),
            body.cron_expr,
            body.distribution_emails,
            x_user_id or None,
        )
    return {
        "schedule_id": schedule_id,
        "label": body.label,
        "run_id": body.run_id,
        "cron_expr": body.cron_expr,
        "distribution_emails": body.distribution_emails,
    }


@router.get("")
async def list_schedules(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List pack schedules for the tenant."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT schedule_id, label, run_id, budget_id, section_order, cron_expr, next_run_at, distribution_emails, enabled, created_at
               FROM pack_schedules WHERE tenant_id = $1 ORDER BY created_at DESC""",
            x_tenant_id,
        )
    items = []
    for r in rows:
        so = r["section_order"]
        if so is not None and not isinstance(so, list):
            so = json.loads(so) if isinstance(so, str) else list(so)
        items.append({
            "schedule_id": r["schedule_id"],
            "label": r["label"],
            "run_id": r["run_id"],
            "budget_id": r["budget_id"],
            "section_order": so or DEFAULT_SECTION_ORDER,
            "cron_expr": r["cron_expr"],
            "next_run_at": r["next_run_at"].isoformat() if r["next_run_at"] else None,
            "distribution_emails": list(r["distribution_emails"] or []),
            "enabled": r["enabled"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        })
    return {"items": items}


@router.get("/history")
async def list_pack_history(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    schedule_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List pack generation history (VA-P7-09)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        if schedule_id:
            rows = await conn.fetch(
                """SELECT history_id, schedule_id, pack_id, label, run_id, generated_at, distributed_at, status, error_message
                   FROM pack_generation_history WHERE tenant_id = $1 AND schedule_id = $2 ORDER BY generated_at DESC LIMIT $3""",
                x_tenant_id,
                schedule_id,
                limit,
            )
        else:
            rows = await conn.fetch(
                """SELECT history_id, schedule_id, pack_id, label, run_id, generated_at, distributed_at, status, error_message
                   FROM pack_generation_history WHERE tenant_id = $1 ORDER BY generated_at DESC LIMIT $2""",
                x_tenant_id,
                limit,
            )
    items = []
    for r in rows:
        items.append({
            "history_id": r["history_id"],
            "schedule_id": r["schedule_id"],
            "pack_id": r["pack_id"],
            "label": r["label"],
            "run_id": r["run_id"],
            "generated_at": r["generated_at"].isoformat() if r["generated_at"] else None,
            "distributed_at": r["distributed_at"].isoformat() if r["distributed_at"] else None,
            "status": r["status"],
            "error_message": r["error_message"],
        })
    return {"items": items}


@router.post("/{schedule_id}/run-now", status_code=201)
async def run_schedule_now(
    schedule_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Generate a board pack now from schedule config (VA-P7-09). Creates pack, runs generate, records history."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT schedule_id, label, run_id, budget_id, section_order FROM pack_schedules WHERE tenant_id = $1 AND schedule_id = $2""",
            x_tenant_id,
            schedule_id,
        )
    if not row:
        raise HTTPException(404, "Schedule not found")
    so = row["section_order"]
    if so is not None and not isinstance(so, list):
        so = json.loads(so) if isinstance(so, str) else list(so)
    so = so or DEFAULT_SECTION_ORDER
    create_resp = await create_board_pack_impl(
        x_tenant_id,
        x_user_id or None,
        row["label"],
        row["run_id"],
        row["budget_id"],
        so,
        None,
    )
    pack_id = create_resp["pack_id"]
    try:
        await generate_board_pack_impl(x_tenant_id, pack_id, store, llm)
    except HTTPException:
        history_id = f"hist_{uuid.uuid4().hex[:12]}"
        async with tenant_conn(x_tenant_id) as conn:
            await conn.execute(
                """INSERT INTO pack_generation_history (tenant_id, history_id, schedule_id, pack_id, label, run_id, status, error_message)
                   VALUES ($1, $2, $3, $4, $5, $6, 'failed', $7)""",
                x_tenant_id,
                history_id,
                schedule_id,
                pack_id,
                row["label"],
                row["run_id"],
                "Generate failed",
            )
        raise
    history_id = f"hist_{uuid.uuid4().hex[:12]}"
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO pack_generation_history (tenant_id, history_id, schedule_id, pack_id, label, run_id, status)
               VALUES ($1, $2, $3, $4, $5, $6, 'ready')""",
            x_tenant_id,
            history_id,
            schedule_id,
            pack_id,
            row["label"],
            row["run_id"],
        )
    return {"pack_id": pack_id, "history_id": history_id, "status": "ready"}


@router.post("/history/{history_id}/distribute")
async def distribute_pack(
    history_id: str,
    body: DistributeBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Mark pack as distributed and stub email (VA-P7-09). In production wire to SendGrid/SES."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    emails = body.emails
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT history_id, pack_id FROM pack_generation_history WHERE tenant_id = $1 AND history_id = $2""",
            x_tenant_id,
            history_id,
        )
        if not row:
            raise HTTPException(404, "History not found")
        await conn.execute(
            """UPDATE pack_generation_history SET distributed_at = now(), status = 'distributed' WHERE tenant_id = $1 AND history_id = $2""",
            x_tenant_id,
            history_id,
        )
    return {"history_id": history_id, "distributed": True, "emails_sent_to": emails}


@router.patch("/{schedule_id}")
async def patch_schedule(
    schedule_id: str,
    body: PatchScheduleBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Update schedule."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    updates = []
    args: list[Any] = []
    pos = 1
    if body.label is not None:
        updates.append(f"label = ${pos}")
        args.append(body.label)
        pos += 1
    if body.run_id is not None:
        updates.append(f"run_id = ${pos}")
        args.append(body.run_id)
        pos += 1
    if body.budget_id is not None:
        updates.append(f"budget_id = ${pos}")
        args.append(body.budget_id)
        pos += 1
    if body.cron_expr is not None:
        updates.append(f"cron_expr = ${pos}")
        args.append(body.cron_expr)
        pos += 1
    if body.distribution_emails is not None:
        updates.append(f"distribution_emails = ${pos}")
        args.append(body.distribution_emails)
        pos += 1
    if body.enabled is not None:
        updates.append(f"enabled = ${pos}")
        args.append(body.enabled)
        pos += 1
    if not updates:
        raise HTTPException(400, "No fields to update")
    args.extend([x_tenant_id, schedule_id])
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            f"UPDATE pack_schedules SET {', '.join(updates)} WHERE tenant_id = ${pos} AND schedule_id = ${pos + 1}",
            *args,
        )
    if result == "UPDATE 0":
        raise HTTPException(404, "Schedule not found")
    return {"schedule_id": schedule_id, "updated": True}


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Delete a schedule."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            "DELETE FROM pack_schedules WHERE tenant_id = $1 AND schedule_id = $2",
            x_tenant_id,
            schedule_id,
        )
    if result == "DELETE 0":
        raise HTTPException(404, "Schedule not found")
    return {"schedule_id": schedule_id, "deleted": True}
