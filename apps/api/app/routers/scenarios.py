"""Scenario CRUD and compare: overrides per baseline, side-by-side KPI comparison."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from apps.api.app.db import ensure_tenant, tenant_conn
from apps.api.app.db.audit import EVENT_SCENARIO_CREATED, EVENT_SCENARIO_DELETED, create_audit_event
from apps.api.app.deps import get_artifact_store, require_role, ROLES_ANY, ROLES_CAN_WRITE
from shared.fm_shared.errors import StorageError
from shared.fm_shared.model import ModelConfig, calculate_kpis, generate_statements, run_engine
from shared.fm_shared.model.schemas import ScenarioOverride
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


class CreateScenarioBody(BaseModel):
    baseline_id: str
    label: str = ""
    description: str = ""
    overrides: list[dict[str, Any]] = []


class UpdateScenarioBody(BaseModel):
    label: str | None = None
    description: str | None = None
    overrides: list[dict[str, Any]] | None = None


@router.post("", status_code=201)
async def create_scenario(
    body: CreateScenarioBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> dict[str, Any]:
    """Create a scenario for a baseline with overrides (ref, field, value)."""
    baseline_id = body.baseline_id
    label = body.label or "Unnamed"
    overrides = body.overrides
    description = body.description
    if not baseline_id:
        raise HTTPException(400, "baseline_id required")
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            await ensure_tenant(conn, x_tenant_id)
            row = await conn.fetchrow(
                """SELECT baseline_id, baseline_version FROM model_baselines
                   WHERE tenant_id = $1 AND baseline_id = $2 AND is_active = true""",
                x_tenant_id,
                baseline_id,
            )
            if not row:
                raise HTTPException(404, "Baseline not found")
            baseline_version = row["baseline_version"]
            scenario_id = f"sc_{uuid.uuid4().hex[:12]}"
            overrides_json = _overrides_to_json(overrides)
            await conn.execute(
                """INSERT INTO scenarios (tenant_id, scenario_id, baseline_id, baseline_version, label, description, overrides_json)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                x_tenant_id,
                scenario_id,
                baseline_id,
                baseline_version,
                label,
                description,
                overrides_json,
            )
            await create_audit_event(conn, x_tenant_id, EVENT_SCENARIO_CREATED, "scenario", "scenario", scenario_id, user_id=x_user_id or None)
    return {
        "scenario_id": scenario_id,
        "baseline_id": baseline_id,
        "baseline_version": baseline_version,
        "label": label,
        "description": description,
        "overrides": overrides,
    }


def _overrides_to_json(overrides: list[Any]) -> str:
    import json

    out = []
    for o in overrides:
        if isinstance(o, dict):
            ref = o.get("ref", "")
            if not ref:
                continue  # skip overrides without a ref
            out.append(
                {
                    "ref": ref,
                    "field": o.get("field", "value"),
                    "value": float(o.get("value", 0)),
                }
            )
        # Non-dict entries are silently skipped
    return json.dumps(out)


@router.get("")
async def list_scenarios(
    baseline_id: str | None = Query(None, description="Filter by baseline"),
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: None = require_role(*ROLES_ANY),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        if baseline_id:
            total = await conn.fetchval(
                "SELECT count(*) FROM scenarios WHERE tenant_id = $1 AND baseline_id = $2",
                x_tenant_id,
                baseline_id,
            )
            rows = await conn.fetch(
                """SELECT scenario_id, baseline_id, baseline_version, label, description, overrides_json, created_at
                   FROM scenarios WHERE tenant_id = $1 AND baseline_id = $2 ORDER BY created_at DESC LIMIT $3 OFFSET $4""",
                x_tenant_id,
                baseline_id,
                limit,
                offset,
            )
        else:
            total = await conn.fetchval(
                "SELECT count(*) FROM scenarios WHERE tenant_id = $1",
                x_tenant_id,
            )
            rows = await conn.fetch(
                """SELECT scenario_id, baseline_id, baseline_version, label, description, overrides_json, created_at
                   FROM scenarios WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
                x_tenant_id,
                limit,
                offset,
            )
        items = [
            {
                "scenario_id": r["scenario_id"],
                "baseline_id": r["baseline_id"],
                "baseline_version": r["baseline_version"],
                "label": r["label"],
                "description": r["description"],
                "overrides": r["overrides_json"] if isinstance(r["overrides_json"], list) else _parse_overrides_json(r["overrides_json"]),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _parse_overrides_json(val: Any) -> list[dict]:
    if isinstance(val, list):
        return [x if isinstance(x, dict) else {} for x in val]
    if isinstance(val, str):
        import json
        try:
            return json.loads(val)
        except Exception:
            return []
    return []


@router.get("/{scenario_id}")
async def get_scenario(
    scenario_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = require_role(*ROLES_ANY),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT scenario_id, baseline_id, baseline_version, label, description, overrides_json, created_at
               FROM scenarios WHERE tenant_id = $1 AND scenario_id = $2""",
            x_tenant_id,
            scenario_id,
        )
        if not row:
            raise HTTPException(404, "Scenario not found")
        overrides = row["overrides_json"] if isinstance(row["overrides_json"], list) else _parse_overrides_json(row["overrides_json"])
        return {
            "scenario_id": row["scenario_id"],
            "baseline_id": row["baseline_id"],
            "baseline_version": row["baseline_version"],
            "label": row["label"],
            "description": row["description"],
            "overrides": overrides,
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(
    scenario_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> None:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            "DELETE FROM scenarios WHERE tenant_id = $1 AND scenario_id = $2",
            x_tenant_id,
            scenario_id,
        )
        if result == "DELETE 0":
            raise HTTPException(404, "Scenario not found")
        await create_audit_event(conn, x_tenant_id, EVENT_SCENARIO_DELETED, "scenario", "scenario", scenario_id, user_id=x_user_id or None)


@router.post("/compare")
async def compare_scenarios(
    body: dict[str, Any],
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    _: None = require_role(*ROLES_ANY),
) -> dict[str, Any]:
    """Run baseline + each scenario and return side-by-side KPIs (e.g. terminal revenue, FCF)."""
    baseline_id = body.get("baseline_id")
    scenario_ids = body.get("scenario_ids") or []
    if not baseline_id:
        raise HTTPException(400, "baseline_id required")
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    MAX_COMPARE_SCENARIOS = 10
    if len(scenario_ids) > MAX_COMPARE_SCENARIOS:
        raise HTTPException(400, f"Too many scenarios to compare ({len(scenario_ids)}); max {MAX_COMPARE_SCENARIOS}")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT baseline_id, baseline_version FROM model_baselines
               WHERE tenant_id = $1 AND baseline_id = $2 AND is_active = true""",
            x_tenant_id,
            baseline_id,
        )
        if not row:
            raise HTTPException(404, "Baseline not found")
        baseline_version = row["baseline_version"]
    artifact_id = f"{baseline_id}_{baseline_version}"
    try:
        config_dict = store.load(x_tenant_id, "model_config_v1", artifact_id)
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Baseline artifact not found") from e
        raise
    config = ModelConfig.model_validate(config_dict)

    # Base case
    time_series_base = run_engine(config, None)
    statements_base = generate_statements(config, time_series_base)
    kpis_base = calculate_kpis(statements_base)
    base_row = _kpi_summary_row("Base", kpis_base, statements_base)

    # Scenarios
    scenario_rows: list[dict[str, Any]] = [base_row]
    if scenario_ids:
        async with tenant_conn(x_tenant_id) as conn:
            rows = await conn.fetch(
                "SELECT scenario_id, label, overrides_json FROM scenarios WHERE tenant_id = $1 AND scenario_id = ANY($2::text[])",
                x_tenant_id,
                scenario_ids,
            )
            for r in rows:
                ov = r["overrides_json"] if isinstance(r["overrides_json"], list) else _parse_overrides_json(r["overrides_json"])
                overrides_list = [ScenarioOverride(ref=o["ref"], field=o.get("field", "value"), value=float(o.get("value", 0))) for o in ov if o.get("ref")]
                time_series = run_engine(config, overrides_list)
                statements = generate_statements(config, time_series)
                kpis = calculate_kpis(statements)
                scenario_rows.append(_kpi_summary_row(r["label"] or r["scenario_id"], kpis, statements))

    return {
        "baseline_id": baseline_id,
        "baseline_version": baseline_version,
        "scenarios": scenario_rows,
    }


def _kpi_summary_row(label: str, kpis: list[dict], statements: Any) -> dict[str, Any]:
    """One row for compare table: label + key metrics (terminal period)."""
    if not kpis:
        return {"label": label, "revenue": 0, "ebitda": 0, "net_income": 0, "fcf": 0}
    last = kpis[-1]
    is_list = getattr(statements, "income_statement", [])
    rev = is_list[-1]["revenue"] if is_list else 0
    ebitda = is_list[-1]["ebitda"] if is_list else 0
    ni = is_list[-1]["net_income"] if is_list else 0
    return {
        "label": label,
        "revenue": round(rev, 2),
        "ebitda": round(ebitda, 2),
        "net_income": round(ni, 2),
        "fcf": round(last.get("fcf", 0), 2),
        "gross_margin_pct": last.get("gross_margin_pct"),
        "ebitda_margin_pct": last.get("ebitda_margin_pct"),
    }
