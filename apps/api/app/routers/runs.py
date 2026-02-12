"""Run CRUD and execute: create run, get status/results, statements, KPIs."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from apps.api.app.db import ensure_tenant, get_conn
from apps.api.app.db.audit import EVENT_RUN_ACCESSED, EVENT_RUN_CREATED, create_audit_event
from apps.api.app.deps import get_artifact_store
from shared.fm_shared.errors import EngineError, StorageError
from shared.fm_shared.model import (
    ModelConfig,
    StatementImbalanceError,
    calculate_kpis,
    generate_statements,
    run_engine,
)
from shared.fm_shared.model.schemas import ScenarioOverride
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", status_code=201)
async def create_run(
    body: dict[str, Any],
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    baseline_id = body.get("baseline_id")
    if not baseline_id:
        raise HTTPException(400, "baseline_id required")
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    conn = await get_conn()
    try:
        async with conn.transaction():
            await ensure_tenant(conn, x_tenant_id)
            row = await conn.fetchrow(
                """SELECT baseline_id, baseline_version, storage_path FROM model_baselines
                   WHERE tenant_id = $1 AND baseline_id = $2 AND is_active = true""",
                x_tenant_id,
                baseline_id,
            )
            if not row:
                raise HTTPException(404, "Baseline not found")
            baseline_version = row["baseline_version"]
    finally:
        await conn.close()

    artifact_id = f"{baseline_id}_{baseline_version}"
    try:
        config_dict = store.load(x_tenant_id, "model_config_v1", artifact_id)
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Baseline artifact not found") from e
        raise
    config = ModelConfig.model_validate(config_dict)

    scenario_overrides: list[ScenarioOverride] | None = None
    scenario_id = body.get("scenario_id")
    if scenario_id and config.scenarios:
        for sc in config.scenarios:
            if sc.scenario_id == scenario_id:
                scenario_overrides = sc.overrides
                break

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    status = "running"
    conn = await get_conn()
    try:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO runs (tenant_id, run_id, baseline_id, baseline_version, scenario_id, status)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                x_tenant_id,
                run_id,
                baseline_id,
                baseline_version,
                scenario_id,
                status,
            )
    finally:
        await conn.close()

    try:
        time_series = run_engine(config, scenario_overrides)
        statements = generate_statements(config, time_series)
        kpis = calculate_kpis(statements)
    except (EngineError, StatementImbalanceError) as e:
        conn = await get_conn()
        try:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE runs SET status = 'failed' WHERE tenant_id = $1 AND run_id = $2",
                    x_tenant_id,
                    run_id,
                )
        finally:
            await conn.close()
        raise HTTPException(422, str(e)) from e

    run_artifact_id = f"{run_id}_statements"
    storage_path = store.save(
        x_tenant_id,
        "run_results",
        run_artifact_id,
        {
            "statements": {
                "income_statement": statements.income_statement,
                "balance_sheet": statements.balance_sheet,
                "cash_flow": statements.cash_flow,
                "periods": statements.periods,
            },
            "kpis": kpis,
            "time_series": time_series,
        },
    )

    conn = await get_conn()
    try:
        async with conn.transaction():
            await conn.execute(
                "UPDATE runs SET status = 'succeeded' WHERE tenant_id = $1 AND run_id = $2",
                x_tenant_id,
                run_id,
            )
            await conn.execute(
                """INSERT INTO run_artifacts (tenant_id, run_id, artifact_type, storage_path)
                   VALUES ($1, $2, 'run_results', $3)""",
                x_tenant_id,
                run_id,
                storage_path,
            )
            await create_audit_event(
                conn,
                x_tenant_id,
                EVENT_RUN_CREATED,
                "run",
                "run",
                run_id,
                user_id=x_user_id or None,
                event_data={"baseline_id": baseline_id, "status": "succeeded"},
            )
    finally:
        await conn.close()

    return {
        "run_id": run_id,
        "baseline_id": baseline_id,
        "baseline_version": baseline_version,
        "scenario_id": scenario_id,
        "status": "succeeded",
    }


@router.get("")
async def list_runs(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=100, description="Max 100 to avoid N+1 and large responses"),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    conn = await get_conn()
    try:
        rows = await conn.fetch(
            """SELECT run_id, baseline_id, baseline_version, scenario_id, status, created_at
               FROM runs WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
            x_tenant_id,
            limit,
            offset,
        )
        items = [
            {
                "run_id": r["run_id"],
                "baseline_id": r["baseline_id"],
                "baseline_version": r["baseline_version"],
                "scenario_id": r["scenario_id"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return {"items": items, "limit": limit, "offset": offset}
    finally:
        await conn.close()


@router.get("/{run_id}")
async def get_run(
    run_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            """SELECT run_id, baseline_id, baseline_version, scenario_id, status, created_at
               FROM runs WHERE tenant_id = $1 AND run_id = $2""",
            x_tenant_id,
            run_id,
        )
        if not row:
            raise HTTPException(404, "Run not found")
        await create_audit_event(
            conn,
            x_tenant_id,
            EVENT_RUN_ACCESSED,
            "run",
            "run",
            run_id,
            user_id=x_user_id or None,
            event_data={"baseline_id": row["baseline_id"]},
        )
        return {
            "run_id": row["run_id"],
            "baseline_id": row["baseline_id"],
            "baseline_version": row["baseline_version"],
            "scenario_id": row["scenario_id"],
            "status": row["status"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }
    finally:
        await conn.close()


@router.get("/{run_id}/statements")
async def get_run_statements(
    run_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    try:
        data = store.load(x_tenant_id, "run_results", f"{run_id}_statements")
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Run results not found") from e
        raise
    return data.get("statements", {})


@router.get("/{run_id}/kpis")
async def get_run_kpis(
    run_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> list[dict[str, Any]]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    try:
        data = store.load(x_tenant_id, "run_results", f"{run_id}_statements")
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Run results not found") from e
        raise
    return data.get("kpis", [])
