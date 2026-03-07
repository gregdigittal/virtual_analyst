"""Board pack scheduling & distribution (VA-P7-09): CRUD schedules, run-now, history, distribute via SendGrid."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from croniter import croniter
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.db.connection import get_pool
from apps.api.app.deps import get_artifact_store, get_llm_router, require_role, ROLES_CAN_WRITE
from apps.api.app.services.email import EmailError, send_board_pack_email
from apps.api.app.routers.board_packs import (
    DEFAULT_SECTION_ORDER,
    create_board_pack_impl,
    generate_board_pack_impl,
)
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/board-packs/schedules", tags=["board-packs"], dependencies=[require_role(*ROLES_CAN_WRITE)])


def compute_next_run(cron_expr: str, base: datetime | None = None) -> datetime | None:
    """Parse cron expression and return the next run time (UTC). Returns None if invalid."""
    try:
        base = base or datetime.now(timezone.utc)
        return croniter(cron_expr, base).get_next(datetime).replace(tzinfo=timezone.utc)
    except (ValueError, KeyError):
        return None


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
    next_run = compute_next_run(body.cron_expr)
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO pack_schedules (tenant_id, schedule_id, label, run_id, budget_id, section_order, cron_expr, next_run_at, distribution_emails, created_by)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10)""",
            x_tenant_id,
            schedule_id,
            body.label,
            body.run_id,
            body.budget_id,
            json.dumps(section_order),
            body.cron_expr,
            next_run,
            body.distribution_emails,
            x_user_id or None,
        )
    return {
        "schedule_id": schedule_id,
        "label": body.label,
        "run_id": body.run_id,
        "cron_expr": body.cron_expr,
        "next_run_at": next_run.isoformat() if next_run else None,
        "distribution_emails": body.distribution_emails,
    }


@router.get("")
async def list_schedules(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List pack schedules for the tenant."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        total = await conn.fetchval(
            "SELECT count(*) FROM pack_schedules WHERE tenant_id = $1",
            x_tenant_id,
        )
        rows = await conn.fetch(
            """SELECT schedule_id, label, run_id, budget_id, section_order, cron_expr, next_run_at, distribution_emails, enabled, created_at
               FROM pack_schedules WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
            x_tenant_id,
            limit,
            offset,
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
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/history")
async def list_pack_history(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    schedule_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List pack generation history (VA-P7-09)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        if schedule_id:
            total = await conn.fetchval(
                "SELECT count(*) FROM pack_generation_history WHERE tenant_id = $1 AND schedule_id = $2",
                x_tenant_id,
                schedule_id,
            )
            rows = await conn.fetch(
                """SELECT history_id, schedule_id, pack_id, label, run_id, generated_at, distributed_at, status, error_message
                   FROM pack_generation_history WHERE tenant_id = $1 AND schedule_id = $2 ORDER BY generated_at DESC LIMIT $3 OFFSET $4""",
                x_tenant_id,
                schedule_id,
                limit,
                offset,
            )
        else:
            total = await conn.fetchval(
                "SELECT count(*) FROM pack_generation_history WHERE tenant_id = $1",
                x_tenant_id,
            )
            rows = await conn.fetch(
                """SELECT history_id, schedule_id, pack_id, label, run_id, generated_at, distributed_at, status, error_message
                   FROM pack_generation_history WHERE tenant_id = $1 ORDER BY generated_at DESC LIMIT $2 OFFSET $3""",
                x_tenant_id,
                limit,
                offset,
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
    return {"items": items, "total": total, "limit": limit, "offset": offset}


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
    """Distribute a board pack via email (VA-P7-09). Sends narrative to recipients via SendGrid."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    emails = body.emails

    # Fetch history + narrative (release connection before HTTP call)
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT h.history_id, h.pack_id, h.label,
                      bp.narrative_json
               FROM pack_generation_history h
               LEFT JOIN board_packs bp ON bp.tenant_id = $1 AND bp.pack_id = h.pack_id
               WHERE h.tenant_id = $1 AND h.history_id = $2""",
            x_tenant_id,
            history_id,
        )
    if not row:
        raise HTTPException(404, "History not found")

    pack_label = row["label"] or "Board Pack"
    narrative_json = row["narrative_json"]
    if narrative_json and isinstance(narrative_json, str):
        narrative_json = json.loads(narrative_json)

    # Send emails via SendGrid (or log in dev mode)
    try:
        email_result = await send_board_pack_email(emails, pack_label, narrative_json)
    except EmailError as e:
        raise HTTPException(502, f"Email delivery failed: {e}") from e

    # Only mark as distributed if emails were actually sent
    distributed = email_result.get("sent", False)
    if distributed:
        async with tenant_conn(x_tenant_id) as conn:
            await conn.execute(
                """UPDATE pack_generation_history SET distributed_at = now(), status = 'distributed' WHERE tenant_id = $1 AND history_id = $2""",
                x_tenant_id,
                history_id,
            )

    return {
        "history_id": history_id,
        "distributed": distributed,
        "emails_sent_to": emails,
        "email_result": email_result,
    }


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
        next_run = compute_next_run(body.cron_expr)
        updates.append(f"next_run_at = ${pos}")
        args.append(next_run)
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


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> None:
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


# --- Cron endpoint (no role auth — secured via X-Cron-Secret) ---

cron_router = APIRouter(prefix="/board-packs/schedules", tags=["board-packs"])


@cron_router.post("/cron/execute", status_code=200)
async def cron_execute_schedules(
    x_cron_secret: str = Header("", alias="X-Cron-Secret"),
    store: ArtifactStore = Depends(get_artifact_store),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Execute due board pack schedules. Called by external cron (every 15-60 min).

    For each tenant, finds enabled schedules where next_run_at <= now(),
    generates the pack, distributes via email, records history, and advances next_run_at.
    Requires X-Cron-Secret when CRON_SECRET env var is set.
    """
    import asyncpg
    import structlog

    from apps.api.app.core.settings import get_settings

    logger = structlog.get_logger()
    settings = get_settings()
    if settings.cron_secret and x_cron_secret != settings.cron_secret:
        raise HTTPException(403, "Invalid cron secret")

    now_ts = datetime.now(timezone.utc)
    executed = 0
    errors = 0

    # Get all tenants
    pool = get_pool()
    if pool:
        async with pool.acquire() as conn:
            tenant_rows = await conn.fetch("SELECT id FROM tenants")
    else:
        conn = await asyncpg.connect(settings.database_url)
        try:
            tenant_rows = await conn.fetch("SELECT id FROM tenants")
        finally:
            await conn.close()

    for trow in tenant_rows:
        tenant_id = trow["id"]
        try:
            async with tenant_conn(tenant_id) as tconn:
                due_schedules = await tconn.fetch(
                    """SELECT schedule_id, label, run_id, budget_id, section_order,
                              cron_expr, distribution_emails, created_by
                       FROM pack_schedules
                       WHERE tenant_id = $1 AND enabled = true AND next_run_at IS NOT NULL AND next_run_at <= $2""",
                    tenant_id,
                    now_ts,
                )
            for sched in due_schedules:
                sched_id = sched["schedule_id"]
                try:
                    so = sched["section_order"]
                    if so is not None and not isinstance(so, list):
                        so = json.loads(so) if isinstance(so, str) else list(so)
                    so = so or DEFAULT_SECTION_ORDER

                    # Generate board pack
                    create_resp = await create_board_pack_impl(
                        tenant_id,
                        sched["created_by"],
                        sched["label"],
                        sched["run_id"],
                        sched["budget_id"],
                        so,
                        None,
                    )
                    pack_id = create_resp["pack_id"]

                    history_id = f"hist_{uuid.uuid4().hex[:12]}"
                    try:
                        await generate_board_pack_impl(tenant_id, pack_id, store, llm)
                    except Exception as gen_err:
                        logger.warning("cron_pack_generate_failed", tenant=tenant_id, schedule=sched_id, error=str(gen_err))
                        async with tenant_conn(tenant_id) as tconn:
                            await tconn.execute(
                                """INSERT INTO pack_generation_history (tenant_id, history_id, schedule_id, pack_id, label, run_id, status, error_message)
                                   VALUES ($1, $2, $3, $4, $5, $6, 'failed', $7)""",
                                tenant_id, history_id, sched_id, pack_id, sched["label"], sched["run_id"], str(gen_err)[:500],
                            )
                        errors += 1
                        continue

                    # Record success history
                    async with tenant_conn(tenant_id) as tconn:
                        await tconn.execute(
                            """INSERT INTO pack_generation_history (tenant_id, history_id, schedule_id, pack_id, label, run_id, status)
                               VALUES ($1, $2, $3, $4, $5, $6, 'ready')""",
                            tenant_id, history_id, sched_id, pack_id, sched["label"], sched["run_id"],
                        )

                    # Distribute via email if recipients configured
                    dist_emails = list(sched["distribution_emails"] or [])
                    if dist_emails:
                        try:
                            # Fetch narrative for email
                            async with tenant_conn(tenant_id) as tconn:
                                bp_row = await tconn.fetchrow(
                                    "SELECT narrative_json FROM board_packs WHERE tenant_id = $1 AND pack_id = $2",
                                    tenant_id, pack_id,
                                )
                            narrative_json = None
                            if bp_row and bp_row["narrative_json"]:
                                nj = bp_row["narrative_json"]
                                narrative_json = json.loads(nj) if isinstance(nj, str) else nj

                            email_result = await send_board_pack_email(dist_emails, sched["label"] or "Board Pack", narrative_json)
                            if email_result.get("sent", False):
                                async with tenant_conn(tenant_id) as tconn:
                                    await tconn.execute(
                                        """UPDATE pack_generation_history SET distributed_at = now(), status = 'distributed'
                                           WHERE tenant_id = $1 AND history_id = $2""",
                                        tenant_id, history_id,
                                    )
                        except EmailError as email_err:
                            logger.warning("cron_pack_email_failed", tenant=tenant_id, schedule=sched_id, error=str(email_err))

                    # Advance next_run_at
                    next_run = compute_next_run(sched["cron_expr"], now_ts)
                    async with tenant_conn(tenant_id) as tconn:
                        await tconn.execute(
                            "UPDATE pack_schedules SET next_run_at = $1 WHERE tenant_id = $2 AND schedule_id = $3",
                            next_run, tenant_id, sched_id,
                        )

                    executed += 1
                    logger.info("cron_pack_executed", tenant=tenant_id, schedule=sched_id, pack_id=pack_id)

                except Exception as e:
                    logger.error("cron_pack_schedule_error", tenant=tenant_id, schedule=sched_id, error=str(e))
                    errors += 1

        except Exception as e:
            logger.error("cron_pack_tenant_error", tenant=tenant_id, error=str(e))

    return {"executed": executed, "errors": errors, "checked_tenants": len(tenant_rows)}
