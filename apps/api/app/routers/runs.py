"""Run CRUD and execute: create run, get status/results, statements, KPIs, MC, progress."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field as PydField

from apps.api.app.db import ensure_tenant, tenant_conn
from apps.api.app.db.audit import EVENT_RUN_ACCESSED, EVENT_RUN_CREATED, create_audit_event
from apps.api.app.db.covenants import check_covenants, list_covenant_definitions
from apps.api.app.db.notifications import create_notification
from apps.api.app.deps import get_artifact_store, require_role, ROLES_ANY, ROLES_CAN_WRITE
from apps.worker.tasks import run_mc_execute
from apps.worker.celery_app import REDIS_URL
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
from shared.fm_shared.analysis.valuation import dcf_valuation, multiples_valuation

from apps.api.app.services.excel_export import build_run_excel

router = APIRouter(prefix="/runs", tags=["runs"])


class CreateRunBody(BaseModel):
    baseline_id: str
    mode: str = "deterministic"
    num_simulations: int = PydField(default=1000, ge=1, le=100_000)
    seed: int = PydField(default=42, ge=0)
    scenario_id: str | None = None
    scenario_overrides: list[dict[str, Any]] | None = None
    dcf_config: dict[str, Any] | None = None
    multiples_config: dict[str, Any] | None = None
    valuation_config: dict[str, Any] | None = None


MC_PROGRESS_KEY = "run:mc_progress"

_redis_pool: Any = None


def _get_redis():
    global _redis_pool
    if _redis_pool is None:
        import redis
        _redis_pool = redis.ConnectionPool.from_url(REDIS_URL)
    import redis
    return redis.Redis(connection_pool=_redis_pool)


def _get_mc_progress(tenant_id: str, run_id: str) -> dict[str, Any] | None:
    try:
        r = _get_redis()
        key = f"{MC_PROGRESS_KEY}:{tenant_id}:{run_id}"
        raw = r.get(key)
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


@router.post("", status_code=201)
async def create_run(
    body: CreateRunBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    baseline_id = body.baseline_id
    mc_enabled = body.mode != "deterministic"
    num_simulations = body.num_simulations
    seed = body.seed
    scenario_id = body.scenario_id

    async with tenant_conn(x_tenant_id) as conn:
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
            run_id = f"run_{uuid.uuid4().hex[:12]}"
            status = "queued" if mc_enabled else "running"
            await conn.execute(
                """INSERT INTO runs (tenant_id, run_id, baseline_id, baseline_version, scenario_id, status,
                   mc_enabled, num_simulations, seed)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                x_tenant_id,
                run_id,
                baseline_id,
                baseline_version,
                scenario_id,
                status,
                mc_enabled,
                num_simulations if mc_enabled else None,
                seed if mc_enabled else None,
            )

        if mc_enabled:
            result = run_mc_execute.apply_async(
                kwargs={
                    "tenant_id": x_tenant_id,
                    "run_id": run_id,
                    "baseline_id": baseline_id,
                    "baseline_version": baseline_version,
                    "scenario_id": scenario_id,
                    "num_simulations": num_simulations,
                    "seed": seed,
                }
            )
            async with conn.transaction():
                await conn.execute(
                    "UPDATE runs SET task_id = $3 WHERE tenant_id = $1 AND run_id = $2",
                    x_tenant_id,
                    run_id,
                    result.id,
                )
                await create_audit_event(
                    conn,
                    x_tenant_id,
                    EVENT_RUN_CREATED,
                    "run",
                    "run",
                    run_id,
                    user_id=x_user_id or None,
                    event_data={"baseline_id": baseline_id, "status": "queued", "task_id": result.id},
                )
            return {
                "run_id": run_id,
                "baseline_id": baseline_id,
                "baseline_version": baseline_version,
                "scenario_id": scenario_id,
                "status": "queued",
                "task_id": result.id,
                "mc_enabled": True,
                "num_simulations": num_simulations,
                "seed": seed,
            }

        # Synchronous deterministic run
        artifact_id = f"{baseline_id}_{baseline_version}"
        try:
            config_dict = store.load(x_tenant_id, "model_config_v1", artifact_id)
        except StorageError as e:
            if e.code == "ERR_STOR_NOT_FOUND":
                raise HTTPException(404, "Baseline artifact not found") from e
            raise
        config = ModelConfig.model_validate(config_dict)

        scenario_overrides_list: list[ScenarioOverride] | None = None
        if scenario_id and config.scenarios:
            for sc in config.scenarios:
                if sc.scenario_id == scenario_id:
                    scenario_overrides_list = list(sc.overrides)
                    break

        try:
            time_series = run_engine(config, scenario_overrides_list)
            statements = generate_statements(config, time_series)
            kpis = calculate_kpis(statements)
        except (EngineError, StatementImbalanceError) as e:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE runs SET status = 'failed' WHERE tenant_id = $1 AND run_id = $2",
                    x_tenant_id,
                    run_id,
                )
            raise HTTPException(422, str(e)) from e

        run_artifact_id = f"{run_id}_statements"
        run_results_payload = {
            "statements": {
                "income_statement": statements.income_statement,
                "balance_sheet": statements.balance_sheet,
                "cash_flow": statements.cash_flow,
                "periods": statements.periods,
                "revenue_by_segment": statements.revenue_by_segment,
            },
            "kpis": kpis,
            "time_series": time_series,
        }

        valuation_payload: dict[str, Any] | None = None
        valuation_config = body.valuation_config
        if valuation_config and isinstance(valuation_config, dict):
            fcf_series = [k.get("fcf", 0) for k in kpis]
            dcf_cfg = valuation_config.get("dcf") or {}
            wacc = float(dcf_cfg.get("wacc", 0.10))
            g = dcf_cfg.get("terminal_growth_rate")
            g = float(g) if g is not None else None
            mult = dcf_cfg.get("terminal_multiple")
            mult = float(mult) if mult is not None else None
            proj_years = int(dcf_cfg.get("projection_years", 5))
            dcf_result = dcf_valuation(fcf_series, wacc, terminal_growth_rate=g, terminal_multiple=mult, projection_years=proj_years)
            last_is = statements.income_statement[-1] if statements.income_statement else {}
            metrics = {
                "revenue": last_is.get("revenue", 0),
                "ebitda": last_is.get("ebitda", 0),
                "net_income": last_is.get("net_income", 0),
            }
            comp = (valuation_config.get("multiples") or {}).get("comparables") or []
            mult_result = multiples_valuation(metrics, comp)
            valuation_payload = {
                "dcf": {
                    "enterprise_value": dcf_result.enterprise_value,
                    "pv_explicit": dcf_result.pv_explicit,
                    "pv_terminal": dcf_result.pv_terminal,
                    "terminal_value": dcf_result.terminal_value,
                    "wacc": dcf_result.wacc,
                    "terminal_growth_rate": dcf_result.terminal_growth_rate,
                    "projection_periods": dcf_result.projection_periods,
                },
                "multiples": {
                    "implied_ev_range": list(mult_result.implied_ev_range),
                    "metrics_applied": mult_result.metrics_applied,
                },
            }

        async with conn.transaction():
            storage_path = store.save(
                x_tenant_id,
                "run_results",
                run_artifact_id,
                run_results_payload,
            )
            definitions = await list_covenant_definitions(conn, x_tenant_id)
            breached = check_covenants(kpis, definitions)
            covenant_breached = len(breached) > 0
            await conn.execute(
                "UPDATE runs SET status = 'succeeded', covenant_breached = $3 WHERE tenant_id = $1 AND run_id = $2",
                x_tenant_id,
                run_id,
                covenant_breached,
            )
            if covenant_breached:
                breach_summary = "; ".join(
                    f"{b['label']}: {b['metric_ref']} {b['operator']} {b['threshold_value']} (actual: {b['actual_value']})"
                    for b in breached
                )
                await create_notification(
                    conn,
                    x_tenant_id,
                    "covenant_breach",
                    "Covenant breach",
                    body=f"Run {run_id}: {breach_summary}",
                    entity_type="run",
                    entity_id=run_id,
                    user_id=x_user_id or None,
                )
            if valuation_payload:
                val_path = store.save(x_tenant_id, "run_results", f"{run_id}_valuation", valuation_payload)
                await conn.execute(
                    """INSERT INTO run_artifacts (tenant_id, run_id, artifact_type, storage_path)
                       VALUES ($1, $2, 'valuation', $3)""",
                    x_tenant_id,
                    run_id,
                    val_path,
                )
            await create_notification(
                conn,
                x_tenant_id,
                "run_complete",
                "Run completed",
                body=f"Run {run_id} completed successfully.",
                entity_type="run",
                entity_id=run_id,
                user_id=x_user_id or None,
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

    return {
        "run_id": run_id,
        "baseline_id": baseline_id,
        "baseline_version": baseline_version,
        "scenario_id": scenario_id,
        "status": "succeeded",
        "covenant_breached": covenant_breached,
    }


@router.get("")
async def list_runs(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: None = require_role(*ROLES_ANY),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        total = await conn.fetchval(
            "SELECT count(*) FROM runs WHERE tenant_id = $1",
            x_tenant_id,
        )
        rows = await conn.fetch(
            """SELECT run_id, baseline_id, baseline_version, scenario_id, status, created_at, covenant_breached
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
                "covenant_breached": r.get("covenant_breached", False),
            }
            for r in rows
        ]
        return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{run_id}")
async def get_run(
    run_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    _: None = require_role(*ROLES_ANY),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT run_id, baseline_id, baseline_version, scenario_id, status, created_at,
                      task_id, mc_enabled, num_simulations, seed, covenant_breached
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
        out: dict[str, Any] = {
            "run_id": row["run_id"],
            "baseline_id": row["baseline_id"],
            "baseline_version": row["baseline_version"],
            "scenario_id": row["scenario_id"],
            "status": row["status"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "covenant_breached": row.get("covenant_breached", False),
        }
        if row.get("task_id"):
            out["task_id"] = row["task_id"]
        if row.get("mc_enabled"):
            out["mc_enabled"] = True
            out["num_simulations"] = row.get("num_simulations")
            out["seed"] = row.get("seed")
        if row["status"] in ("queued", "running"):
            progress = _get_mc_progress(x_tenant_id, run_id)
            if progress:
                out["mc_progress"] = progress
        return out


@router.get("/{run_id}/statements")
async def get_run_statements(
    run_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    _: None = require_role(*ROLES_ANY),
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
    _: None = require_role(*ROLES_ANY),
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


@router.get("/{run_id}/mc")
async def get_run_mc(
    run_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    _: None = require_role(*ROLES_ANY),
) -> dict[str, Any]:
    """Return Monte Carlo percentile results when mc_enabled run has completed."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    try:
        data = store.load(x_tenant_id, "run_results", f"{run_id}_mc")
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "MC results not found") from e
        raise
    return data


@router.get("/{run_id}/sensitivity")
async def get_run_sensitivity(
    run_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    pct: float = Query(0.10, ge=0.01, le=0.50, description="Vary drivers by ±pct (e.g. 0.10 = ±10%)"),
    _: None = require_role(*ROLES_ANY),
) -> dict[str, Any]:
    """One-at-a-time sensitivity: vary each driver by ±pct, return impact on terminal FCF (tornado data)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    try:
        data = store.load(x_tenant_id, "run_results", f"{run_id}_statements")
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Run results not found") from e
        raise
    # We need config to run engine with overrides; get baseline from run
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT baseline_id, baseline_version FROM runs WHERE tenant_id = $1 AND run_id = $2",
            x_tenant_id,
            run_id,
        )
        if not row:
            raise HTTPException(404, "Run not found")
    baseline_id, baseline_version = row["baseline_id"], row["baseline_version"]
    try:
        config_dict = store.load(x_tenant_id, "model_config_v1", f"{baseline_id}_{baseline_version}")
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Baseline not found") from e
        raise
    config = ModelConfig.model_validate(config_dict)
    kpis = data.get("kpis", [])
    base_fcf = kpis[-1].get("fcf", 0) if kpis else 0.0
    # Drivers to vary: from config.distributions or blueprint driver refs
    refs = [d.ref for d in config.distributions] if config.distributions else []
    if not refs:
        return {"base_fcf": base_fcf, "pct": pct, "drivers": [], "target_metric": "terminal_fcf"}
    MAX_SENSITIVITY_DRIVERS = 30
    if len(refs) > MAX_SENSITIVITY_DRIVERS:
        raise HTTPException(400, f"Too many drivers for sensitivity ({len(refs)}); max {MAX_SENSITIVITY_DRIVERS}")
    drivers_data: list[dict[str, Any]] = []
    for ref in refs:
        overrides_low = [ScenarioOverride(ref=ref, field="multiplier", value=1.0 - pct)]
        overrides_high = [ScenarioOverride(ref=ref, field="multiplier", value=1.0 + pct)]
        ts_low = run_engine(config, overrides_low)
        st_low = generate_statements(config, ts_low)
        kpis_low = calculate_kpis(st_low)
        ts_high = run_engine(config, overrides_high)
        st_high = generate_statements(config, ts_high)
        kpis_high = calculate_kpis(st_high)
        fcf_low = kpis_low[-1].get("fcf", 0) if kpis_low else 0
        fcf_high = kpis_high[-1].get("fcf", 0) if kpis_high else 0
        drivers_data.append({
            "ref": ref,
            "base": 1.0,
            "low": 1.0 - pct,
            "high": 1.0 + pct,
            "impact_low": round(base_fcf - fcf_low, 2),
            "impact_high": round(fcf_high - base_fcf, 2),
            "terminal_fcf_low": round(fcf_low, 2),
            "terminal_fcf_high": round(fcf_high, 2),
        })
    return {
        "base_fcf": round(base_fcf, 2),
        "pct": pct,
        "target_metric": "terminal_fcf",
        "drivers": drivers_data,
    }


@router.get("/{run_id}/valuation")
async def get_run_valuation(
    run_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    _: None = require_role(*ROLES_ANY),
) -> dict[str, Any]:
    """Return DCF + multiples valuation when run had valuation_config."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    try:
        data = store.load(x_tenant_id, "run_results", f"{run_id}_valuation")
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Valuation results not found") from e
        raise
    return data


@router.get("/{run_id}/export/excel")
async def export_run_excel(
    run_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    _: None = require_role(*ROLES_ANY),
) -> Response:
    """Export run statements and KPIs to Excel (IS, BS, CF, KPIs sheets). VA-P5-01."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    try:
        data = store.load(x_tenant_id, "run_results", f"{run_id}_statements")
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Run results not found") from e
        raise
    statements = data.get("statements", {})
    kpis = data.get("kpis", [])
    body = build_run_excel(statements, kpis=kpis)
    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="run_{run_id}.xlsx"'},
    )
