"""Organization hierarchy & consolidation: org structures, entities, ownership, intercompany, consolidated runs."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import ensure_tenant, tenant_conn
from apps.api.app.deps import get_artifact_store, require_role, ROLES_OWNER_OR_ADMIN
from shared.fm_shared.analysis.consolidation import (
    EntityResult,
    IntercompanyElimination,
    compute_intercompany_amounts,
    consolidate,
)
from shared.fm_shared.errors import EngineError
from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.storage import ArtifactStore

logger = structlog.get_logger()

router = APIRouter(
    prefix="/org-structures",
    tags=["org-structures"],
    dependencies=[require_role(*ROLES_OWNER_OR_ADMIN)],
)


# ---------- Pydantic request bodies ----------

OrgStatus = Literal["draft", "active", "archived"]
ConsolidationMethod = Literal["full", "proportional", "equity_method"]
MinorityInterest = Literal["proportional", "full_goodwill"]
EntityType = Literal["holding", "operating", "spv", "jv", "associate", "branch"]
EntityStatus = Literal["active", "dormant", "disposed"]
LinkType = Literal["management_fee", "royalty", "loan", "trade", "dividend"]
Frequency = Literal["monthly", "quarterly", "annual", "one_time"]


class CreateOrgStructureBody(BaseModel):
    group_name: str = Field("New Group", min_length=1)
    reporting_currency: str = Field("USD", pattern=r"^[A-Z]{3}$")
    consolidation_method: ConsolidationMethod = "full"
    eliminate_intercompany: bool = True
    minority_interest_treatment: MinorityInterest = "proportional"


class UpdateOrgStructureBody(BaseModel):
    group_name: str | None = None
    reporting_currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    status: OrgStatus | None = None
    consolidation_method: ConsolidationMethod | None = None
    eliminate_intercompany: bool | None = None
    minority_interest_treatment: MinorityInterest | None = None


class CreateEntityBody(BaseModel):
    name: str = Field("Entity", min_length=1)
    entity_type: EntityType = "operating"
    currency: str = Field("USD", pattern=r"^[A-Z]{3}$")
    country_iso: str = Field("US", pattern=r"^[A-Z]{2}$")
    tax_jurisdiction: str | None = None
    tax_rate: float | None = Field(None, ge=0, le=1)
    withholding_tax_rate: float = Field(0, ge=0, le=1)
    is_root: bool = False
    baseline_id: str | None = None


class UpdateEntityBody(BaseModel):
    name: str | None = None
    entity_type: EntityType | None = None
    currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    country_iso: str | None = Field(None, pattern=r"^[A-Z]{2}$")
    tax_jurisdiction: str | None = None
    tax_rate: float | None = Field(None, ge=0, le=1)
    withholding_tax_rate: float | None = Field(None, ge=0, le=1)
    is_root: bool | None = None
    baseline_id: str | None = None
    status: EntityStatus | None = None


class CreateOwnershipBody(BaseModel):
    parent_entity_id: str = Field(..., min_length=1)
    child_entity_id: str = Field(..., min_length=1)
    ownership_pct: float = Field(100, gt=0, le=100)
    voting_pct: float | None = Field(None, ge=0, le=100)
    consolidation_method: Literal["full", "proportional", "equity_method", "not_consolidated"] = "full"
    effective_date: str | None = None  # YYYY-MM-DD


class CreateIntercompanyBody(BaseModel):
    from_entity_id: str = Field(..., min_length=1)
    to_entity_id: str = Field(..., min_length=1)
    link_type: LinkType = "management_fee"
    description: str | None = None
    driver_ref: str | None = None
    amount_or_rate: float | None = None
    frequency: Frequency = "monthly"
    withholding_tax_applicable: bool = False


class UpdateIntercompanyBody(BaseModel):
    description: str | None = None
    driver_ref: str | None = None
    amount_or_rate: float | None = None
    frequency: Frequency | None = None
    withholding_tax_applicable: bool | None = None


class TriggerConsolidatedRunBody(BaseModel):
    """Optional request body for consolidated run trigger."""

    fx_avg_rates: dict[str, float] = Field(
        default_factory=dict,
        description="Average FX rates as {\"USD/GBP\": 1.27, ...}. Keys are FROM/TO currency pairs.",
    )
    fx_closing_rates: dict[str, float] | None = Field(
        None,
        description="Closing FX rates (BS translation). Same format as fx_avg_rates. If omitted, uses fx_avg_rates.",
    )
    horizon_granularity: Literal["monthly", "quarterly", "annual"] = "annual"


def _parse_fx_dict(raw: dict[str, float]) -> dict[tuple[str, str], float]:
    """Convert {\"USD/GBP\": 1.27} -> {(\"USD\", \"GBP\"): 1.27}."""
    out: dict[tuple[str, str], float] = {}
    for key, rate in raw.items():
        parts = key.split("/")
        if len(parts) == 2:
            out[(parts[0].strip().upper(), parts[1].strip().upper())] = float(rate)
    return out


# Allowlisted column names for dynamic UPDATE (M-13: avoid injection from model_dump)
_ORG_STRUCTURES_UPDATE_COLUMNS = frozenset(
    {"group_name", "reporting_currency", "status", "consolidation_method", "eliminate_intercompany", "minority_interest_treatment"}
)
_ORG_ENTITIES_UPDATE_COLUMNS = frozenset(
    {"name", "entity_type", "currency", "country_iso", "tax_jurisdiction", "tax_rate", "withholding_tax_rate", "is_root", "baseline_id", "status"}
)
_ORG_INTERCOMPANY_UPDATE_COLUMNS = frozenset(
    {"description", "driver_ref", "amount_or_rate", "frequency", "withholding_tax_applicable"}
)


# ---------- Org structure CRUD ----------


@router.post("", status_code=201)
async def create_org_structure(
    body: CreateOrgStructureBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    org_id = f"og_{uuid.uuid4().hex[:12]}"
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            await ensure_tenant(conn, x_tenant_id)
            await conn.execute(
                """INSERT INTO org_structures (tenant_id, org_id, group_name, reporting_currency,
                   consolidation_method, eliminate_intercompany, minority_interest_treatment, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                x_tenant_id,
                org_id,
                body.group_name,
                body.reporting_currency,
                body.consolidation_method,
                body.eliminate_intercompany,
                body.minority_interest_treatment,
                x_user_id,
            )
    return {
        "org_id": org_id,
        "group_name": body.group_name,
        "reporting_currency": body.reporting_currency,
        "status": "draft",
    }


@router.get("")
async def list_org_structures(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        where = "WHERE tenant_id = $1"
        params: list[Any] = [x_tenant_id]
        if status:
            where += " AND status = $2"
            params.append(status)
        params.extend([limit, offset])
        rows = await conn.fetch(
            f"""SELECT o.org_id, o.group_name, o.reporting_currency, o.status, o.created_at,
                (SELECT count(*) FROM org_entities e WHERE e.tenant_id = o.tenant_id AND e.org_id = o.org_id) AS entity_count
                FROM org_structures o {where}
                ORDER BY o.created_at DESC LIMIT ${len(params)-1} OFFSET ${len(params)}""",
            *params,
        )
    return {
        "items": [
            {
                "org_id": r["org_id"],
                "group_name": r["group_name"],
                "reporting_currency": r["reporting_currency"],
                "status": r["status"],
                "entity_count": r["entity_count"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/{org_id}")
async def get_org_structure(
    org_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT org_id, group_name, reporting_currency, status, consolidation_method,
               eliminate_intercompany, minority_interest_treatment, created_at
               FROM org_structures WHERE tenant_id = $1 AND org_id = $2""",
            x_tenant_id,
            org_id,
        )
        if not row:
            raise HTTPException(404, "Org structure not found")
        entities = await conn.fetch(
            """SELECT entity_id, name, entity_type, currency, country_iso, tax_jurisdiction, tax_rate,
               withholding_tax_rate, is_root, baseline_id, status
               FROM org_entities WHERE tenant_id = $1 AND org_id = $2""",
            x_tenant_id,
            org_id,
        )
        ownership = await conn.fetch(
            """SELECT parent_entity_id, child_entity_id, ownership_pct, voting_pct, consolidation_method, effective_date
               FROM org_ownership_links WHERE tenant_id = $1 AND org_id = $2""",
            x_tenant_id,
            org_id,
        )
        intercompany = await conn.fetch(
            """SELECT link_id, from_entity_id, to_entity_id, link_type, description, driver_ref, amount_or_rate, frequency, withholding_tax_applicable
               FROM org_intercompany_links WHERE tenant_id = $1 AND org_id = $2""",
            x_tenant_id,
            org_id,
        )
    return {
        "org_id": row["org_id"],
        "group_name": row["group_name"],
        "reporting_currency": row["reporting_currency"],
        "status": row["status"],
        "consolidation_method": row["consolidation_method"],
        "eliminate_intercompany": row["eliminate_intercompany"],
        "minority_interest_treatment": row["minority_interest_treatment"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "entities": [
            {
                "entity_id": e["entity_id"],
                "name": e["name"],
                "entity_type": e["entity_type"],
                "currency": e["currency"],
                "country_iso": e["country_iso"],
                "tax_jurisdiction": e["tax_jurisdiction"],
                "tax_rate": float(e["tax_rate"]) if e["tax_rate"] is not None else None,
                "withholding_tax_rate": float(e["withholding_tax_rate"]) if e["withholding_tax_rate"] is not None else 0,
                "is_root": e["is_root"],
                "baseline_id": e["baseline_id"],
                "status": e["status"],
            }
            for e in entities
        ],
        "ownership": [
            {
                "parent_entity_id": o["parent_entity_id"],
                "child_entity_id": o["child_entity_id"],
                "ownership_pct": float(o["ownership_pct"]),
                "voting_pct": float(o["voting_pct"]) if o["voting_pct"] is not None else None,
                "consolidation_method": o["consolidation_method"],
                "effective_date": o["effective_date"].isoformat() if o["effective_date"] else None,
            }
            for o in ownership
        ],
        "intercompany": [
            {
                "link_id": i["link_id"],
                "from_entity_id": i["from_entity_id"],
                "to_entity_id": i["to_entity_id"],
                "link_type": i["link_type"],
                "description": i["description"],
                "driver_ref": i["driver_ref"],
                "amount_or_rate": float(i["amount_or_rate"]) if i["amount_or_rate"] is not None else None,
                "frequency": i["frequency"],
                "withholding_tax_applicable": i["withholding_tax_applicable"],
            }
            for i in intercompany
        ],
    }


@router.patch("/{org_id}")
async def update_org_structure(
    org_id: str,
    body: UpdateOrgStructureBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    raw = body.model_dump(exclude_unset=True)
    updates = {k: v for k, v in raw.items() if k in _ORG_STRUCTURES_UPDATE_COLUMNS}
    if not updates:
        return {"org_id": org_id}
    set_clause = ", ".join(f"{k} = ${i+3}" for i, k in enumerate(updates))
    params = [x_tenant_id, org_id] + list(updates.values())
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            f"UPDATE org_structures SET updated_at = now(), {set_clause} WHERE tenant_id = $1 AND org_id = $2",
            *params,
        )
    return {"org_id": org_id, "updated": list(updates.keys())}


@router.delete("/{org_id}", status_code=204)
async def delete_org_structure(
    org_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> None:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        r = await conn.execute("DELETE FROM org_structures WHERE tenant_id = $1 AND org_id = $2", x_tenant_id, org_id)
    if r == "DELETE 0":
        raise HTTPException(404, "Org structure not found")


# ---------- Entity CRUD ----------


@router.post("/{org_id}/entities", status_code=201)
async def create_entity(
    org_id: str,
    body: CreateEntityBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    entity_id = f"en_{uuid.uuid4().hex[:12]}"
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow("SELECT 1 FROM org_structures WHERE tenant_id = $1 AND org_id = $2", x_tenant_id, org_id)
        if not row:
            raise HTTPException(404, "Org structure not found")
        await conn.execute(
            """INSERT INTO org_entities (tenant_id, org_id, entity_id, name, entity_type, currency, country_iso,
               tax_jurisdiction, tax_rate, withholding_tax_rate, is_root, baseline_id)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)""",
            x_tenant_id,
            org_id,
            entity_id,
            body.name,
            body.entity_type,
            body.currency,
            body.country_iso,
            body.tax_jurisdiction,
            body.tax_rate,
            body.withholding_tax_rate,
            body.is_root,
            body.baseline_id,
        )
    return {"entity_id": entity_id, "name": body.name, "entity_type": body.entity_type, "currency": body.currency}


@router.get("/{org_id}/entities")
async def list_entities(
    org_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT entity_id, name, entity_type, currency, country_iso, tax_jurisdiction, tax_rate,
               withholding_tax_rate, is_root, baseline_id, status
               FROM org_entities WHERE tenant_id = $1 AND org_id = $2 ORDER BY name""",
            x_tenant_id,
            org_id,
        )
    return {
        "items": [
            {
                "entity_id": r["entity_id"],
                "name": r["name"],
                "entity_type": r["entity_type"],
                "currency": r["currency"],
                "country_iso": r["country_iso"],
                "tax_rate": float(r["tax_rate"]) if r["tax_rate"] is not None else None,
                "withholding_tax_rate": float(r["withholding_tax_rate"]) if r["withholding_tax_rate"] is not None else 0,
                "is_root": r["is_root"],
                "baseline_id": r["baseline_id"],
                "status": r["status"],
            }
            for r in rows
        ],
    }


@router.patch("/{org_id}/entities/{entity_id}")
async def update_entity(
    org_id: str,
    entity_id: str,
    body: UpdateEntityBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    raw = body.model_dump(exclude_unset=True)
    updates = {k: v for k, v in raw.items() if k in _ORG_ENTITIES_UPDATE_COLUMNS}
    if not updates:
        return {"entity_id": entity_id}
    set_clause = ", ".join(f"{k} = ${i+4}" for i, k in enumerate(updates))
    params = [x_tenant_id, org_id, entity_id] + list(updates.values())
    async with tenant_conn(x_tenant_id) as conn:
        r = await conn.execute(
            f"UPDATE org_entities SET {set_clause} WHERE tenant_id = $1 AND org_id = $2 AND entity_id = $3",
            *params,
        )
    if r == "UPDATE 0":
        raise HTTPException(404, "Entity not found")
    return {"entity_id": entity_id, "updated": list(updates.keys())}


@router.delete("/{org_id}/entities/{entity_id}", status_code=204)
async def delete_entity(
    org_id: str,
    entity_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> None:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        r = await conn.execute(
            "DELETE FROM org_entities WHERE tenant_id = $1 AND org_id = $2 AND entity_id = $3",
            x_tenant_id,
            org_id,
            entity_id,
        )
    if r == "DELETE 0":
        raise HTTPException(404, "Entity not found")


# ---------- Ownership ----------


@router.post("/{org_id}/ownership", status_code=201)
async def create_ownership(
    org_id: str,
    body: CreateOwnershipBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.parent_entity_id == body.child_entity_id:
        raise HTTPException(400, "Parent and child must differ")
    effective_date = body.effective_date  # pass as string; DB accepts date
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            existing = await conn.fetch(
                """SELECT ownership_pct FROM org_ownership_links
                   WHERE tenant_id = $1 AND org_id = $2 AND child_entity_id = $3
                     AND parent_entity_id != $4""",
                x_tenant_id,
                org_id,
                body.child_entity_id,
                body.parent_entity_id,
            )
            total = sum(float(r["ownership_pct"]) for r in existing) + body.ownership_pct
            if total > 100:
                raise HTTPException(400, f"Total ownership for child would exceed 100% (current + new = {total})")
            await conn.execute(
                """INSERT INTO org_ownership_links (tenant_id, org_id, parent_entity_id, child_entity_id, ownership_pct, voting_pct, consolidation_method, effective_date)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   ON CONFLICT (tenant_id, org_id, parent_entity_id, child_entity_id) DO UPDATE SET ownership_pct = $5, voting_pct = $6, consolidation_method = $7, effective_date = $8""",
                x_tenant_id,
                org_id,
                body.parent_entity_id,
                body.child_entity_id,
                body.ownership_pct,
                body.voting_pct,
                body.consolidation_method,
                effective_date,
            )
    return {"parent_entity_id": body.parent_entity_id, "child_entity_id": body.child_entity_id, "ownership_pct": body.ownership_pct}


@router.get("/{org_id}/ownership")
async def list_ownership(
    org_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT parent_entity_id, child_entity_id, ownership_pct, voting_pct, consolidation_method, effective_date
               FROM org_ownership_links WHERE tenant_id = $1 AND org_id = $2""",
            x_tenant_id,
            org_id,
        )
    return {
        "items": [
            {
                "parent_entity_id": r["parent_entity_id"],
                "child_entity_id": r["child_entity_id"],
                "ownership_pct": float(r["ownership_pct"]),
                "voting_pct": float(r["voting_pct"]) if r["voting_pct"] is not None else None,
                "consolidation_method": r["consolidation_method"],
                "effective_date": r["effective_date"].isoformat() if r["effective_date"] else None,
            }
            for r in rows
        ],
    }


@router.delete("/{org_id}/ownership/{parent_id}/{child_id}", status_code=204)
async def delete_ownership(
    org_id: str,
    parent_id: str,
    child_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> None:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        r = await conn.execute(
            "DELETE FROM org_ownership_links WHERE tenant_id = $1 AND org_id = $2 AND parent_entity_id = $3 AND child_entity_id = $4",
            x_tenant_id,
            org_id,
            parent_id,
            child_id,
        )
    if r == "DELETE 0":
        raise HTTPException(404, "Ownership link not found")


# ---------- Intercompany ----------


@router.post("/{org_id}/intercompany", status_code=201)
async def create_intercompany(
    org_id: str,
    body: CreateIntercompanyBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.from_entity_id == body.to_entity_id:
        raise HTTPException(400, "From and to entity must differ")
    link_id = f"ic_{uuid.uuid4().hex[:12]}"
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO org_intercompany_links (tenant_id, org_id, link_id, from_entity_id, to_entity_id, link_type,
               description, driver_ref, amount_or_rate, frequency, withholding_tax_applicable)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
            x_tenant_id,
            org_id,
            link_id,
            body.from_entity_id,
            body.to_entity_id,
            body.link_type,
            body.description,
            body.driver_ref,
            body.amount_or_rate,
            body.frequency,
            body.withholding_tax_applicable,
        )
    return {"link_id": link_id, "from_entity_id": body.from_entity_id, "to_entity_id": body.to_entity_id, "link_type": body.link_type}


@router.get("/{org_id}/intercompany")
async def list_intercompany(
    org_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT link_id, from_entity_id, to_entity_id, link_type, description, driver_ref, amount_or_rate, frequency, withholding_tax_applicable
               FROM org_intercompany_links WHERE tenant_id = $1 AND org_id = $2""",
            x_tenant_id,
            org_id,
        )
    return {
        "items": [
            {
                "link_id": r["link_id"],
                "from_entity_id": r["from_entity_id"],
                "to_entity_id": r["to_entity_id"],
                "link_type": r["link_type"],
                "description": r["description"],
                "driver_ref": r["driver_ref"],
                "amount_or_rate": float(r["amount_or_rate"]) if r["amount_or_rate"] is not None else None,
                "frequency": r["frequency"],
                "withholding_tax_applicable": r["withholding_tax_applicable"],
            }
            for r in rows
        ],
    }


@router.patch("/{org_id}/intercompany/{link_id}")
async def update_intercompany(
    org_id: str,
    link_id: str,
    body: UpdateIntercompanyBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    raw = body.model_dump(exclude_unset=True)
    updates = {k: v for k, v in raw.items() if k in _ORG_INTERCOMPANY_UPDATE_COLUMNS}
    if not updates:
        return {"link_id": link_id}
    set_clause = ", ".join(f"{k} = ${i+4}" for i, k in enumerate(updates))
    params = [x_tenant_id, org_id, link_id] + list(updates.values())
    async with tenant_conn(x_tenant_id) as conn:
        r = await conn.execute(
            f"UPDATE org_intercompany_links SET {set_clause} WHERE tenant_id = $1 AND org_id = $2 AND link_id = $3",
            *params,
        )
    if r == "UPDATE 0":
        raise HTTPException(404, "Intercompany link not found")
    return {"link_id": link_id, "updated": list(updates.keys())}


@router.delete("/{org_id}/intercompany/{link_id}", status_code=204)
async def delete_intercompany(
    org_id: str,
    link_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> None:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        r = await conn.execute(
            "DELETE FROM org_intercompany_links WHERE tenant_id = $1 AND org_id = $2 AND link_id = $3",
            x_tenant_id,
            org_id,
            link_id,
        )
    if r == "DELETE 0":
        raise HTTPException(404, "Intercompany link not found")


# ---------- Hierarchy (nested tree) ----------


@router.get("/{org_id}/hierarchy")
async def get_hierarchy(
    org_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        entities = await conn.fetch(
            "SELECT entity_id, name, entity_type, is_root FROM org_entities WHERE tenant_id = $1 AND org_id = $2",
            x_tenant_id,
            org_id,
        )
        ownership = await conn.fetch(
            "SELECT parent_entity_id, child_entity_id, ownership_pct FROM org_ownership_links WHERE tenant_id = $1 AND org_id = $2",
            x_tenant_id,
            org_id,
        )
    by_id = {e["entity_id"]: {"entity_id": e["entity_id"], "name": e["name"], "entity_type": e["entity_type"], "ownership_pct": None, "children": []} for e in entities}
    ownership_map: dict[str, list[tuple[str, float]]] = {}
    for o in ownership:
        parent = o["parent_entity_id"]
        child = o["child_entity_id"]
        pct = float(o["ownership_pct"])
        ownership_map.setdefault(parent, []).append((child, pct))

    def _build_tree_node(entity_id: str, visited: set[str] | None = None) -> dict[str, Any] | None:
        if visited is None:
            visited = set()
        if entity_id in visited:
            return None
        visited.add(entity_id)
        if entity_id not in by_id:
            return None
        node = {"entity_id": by_id[entity_id]["entity_id"], "name": by_id[entity_id]["name"], "entity_type": by_id[entity_id]["entity_type"], "ownership_pct": None, "children": []}
        for child_id, pct in ownership_map.get(entity_id, []):
            child_node = _build_tree_node(child_id, visited.copy())
            if child_node is not None:
                child_node["ownership_pct"] = pct
                node["children"].append(child_node)
        return node

    roots = []
    for n in by_id.values():
        if entities and any(e["entity_id"] == n["entity_id"] and e["is_root"] for e in entities):
            root_node = _build_tree_node(n["entity_id"])
            if root_node is not None:
                roots.append(root_node)
    if not roots and by_id:
        all_children = {c for children in ownership_map.values() for c, _ in children}
        root_ids = [eid for eid in by_id if eid not in all_children]
        for eid in root_ids:
            root_node = _build_tree_node(eid)
            if root_node is not None:
                roots.append(root_node)
    if not roots and by_id:
        single = _build_tree_node(list(by_id.keys())[0])
        if single is not None:
            roots.append(single)
    return {"org_id": org_id, "roots": roots}


# ---------- Validate ----------


@router.post("/{org_id}/validate")
async def validate_org_structure(
    org_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    checks: list[dict[str, Any]] = []
    status = "passed"
    async with tenant_conn(x_tenant_id) as conn:
        entities = await conn.fetch(
            "SELECT entity_id, name, is_root, baseline_id FROM org_entities WHERE tenant_id = $1 AND org_id = $2",
            x_tenant_id,
            org_id,
        )
        ownership = await conn.fetch(
            "SELECT parent_entity_id, child_entity_id, ownership_pct FROM org_ownership_links WHERE tenant_id = $1 AND org_id = $2",
            x_tenant_id,
            org_id,
        )
        intercompany = await conn.fetch(
            "SELECT link_id, from_entity_id, to_entity_id FROM org_intercompany_links WHERE tenant_id = $1 AND org_id = $2",
            x_tenant_id,
            org_id,
        )
    entity_ids = {e["entity_id"] for e in entities}
    roots = sum(1 for e in entities if e["is_root"])
    if roots == 0:
        checks.append({"check": "root", "status": "failed", "message": "No root entity (exactly one required)"})
        status = "failed"
    elif roots > 1:
        checks.append({"check": "root", "status": "failed", "message": "Multiple root entities"})
        status = "failed"
    else:
        checks.append({"check": "root", "status": "passed", "message": "Exactly one root"})
    child_totals: dict[str, float] = {}
    for o in ownership:
        child_id = o["child_entity_id"]
        child_totals[child_id] = child_totals.get(child_id, 0) + float(o["ownership_pct"])
    for cid, total in child_totals.items():
        if total > 100:
            checks.append({"check": "ownership", "status": "failed", "message": f"Child {cid} has total ownership {total}%"})
            status = "failed"
    if not any(c.get("status") == "failed" for c in checks):
        checks.append({"check": "ownership", "status": "passed", "message": "No child over 100%"})
    for i in intercompany:
        if i["from_entity_id"] not in entity_ids or i["to_entity_id"] not in entity_ids:
            checks.append({"check": "intercompany", "status": "warning", "message": f"Link {i['link_id']} references missing entity"})
            if status == "passed":
                status = "warning"
    return {"status": status, "checks": checks}


# ---------- Consolidated runs ----------


@router.post("/{org_id}/run", status_code=200)
async def trigger_consolidated_run(
    org_id: str,
    body: TriggerConsolidatedRunBody | None = None,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body is None:
        body = TriggerConsolidatedRunBody()

    consolidated_run_id = f"cr_{uuid.uuid4().hex[:12]}"

    async with tenant_conn(x_tenant_id) as conn:
        org_row = await conn.fetchrow(
            """SELECT reporting_currency, eliminate_intercompany, minority_interest_treatment,
                      consolidation_method
               FROM org_structures WHERE tenant_id = $1 AND org_id = $2""",
            x_tenant_id,
            org_id,
        )
        if not org_row:
            raise HTTPException(404, "Org structure not found")

        entities = await conn.fetch(
            """SELECT entity_id, name, currency, baseline_id, is_root, status,
                      withholding_tax_rate
               FROM org_entities WHERE tenant_id = $1 AND org_id = $2 AND status = 'active'""",
            x_tenant_id,
            org_id,
        )
        if not entities:
            raise HTTPException(400, "No active entities in org structure")

        ownership_rows = await conn.fetch(
            """SELECT parent_entity_id, child_entity_id, ownership_pct,
                      consolidation_method
               FROM org_ownership_links WHERE tenant_id = $1 AND org_id = $2""",
            x_tenant_id,
            org_id,
        )

        ic_rows = await conn.fetch(
            """SELECT from_entity_id, to_entity_id, link_type, amount_or_rate,
                      frequency, withholding_tax_applicable
               FROM org_intercompany_links WHERE tenant_id = $1 AND org_id = $2""",
            x_tenant_id,
            org_id,
        )

        await conn.execute(
            """INSERT INTO consolidated_runs
               (tenant_id, consolidated_run_id, org_id, status, created_by)
               VALUES ($1, $2, $3, 'running', $4)""",
            x_tenant_id,
            consolidated_run_id,
            org_id,
            x_user_id,
        )

    ownership_map: dict[str, dict[str, Any]] = {}
    for o in ownership_rows:
        child_id = o["child_entity_id"]
        if child_id not in ownership_map or float(o["ownership_pct"]) > ownership_map[child_id]["ownership_pct"]:
            ownership_map[child_id] = {
                "ownership_pct": float(o["ownership_pct"]),
                "consolidation_method": o["consolidation_method"],
            }

    entity_results: list[EntityResult] = []
    entity_run_ids: dict[str, str | None] = {}
    horizon: int | None = None

    fx_avg_rates = _parse_fx_dict(body.fx_avg_rates)
    fx_closing_rates = _parse_fx_dict(body.fx_closing_rates) if body.fx_closing_rates else None

    try:
        for ent in entities:
            entity_id = ent["entity_id"]
            baseline_id = ent["baseline_id"]
            currency = ent["currency"]
            wt_rate = float(ent["withholding_tax_rate"] or 0)

            own_info = ownership_map.get(
                entity_id,
                {
                    "ownership_pct": 100.0,
                    "consolidation_method": org_row["consolidation_method"] or "full",
                },
            )

            if not baseline_id:
                logger.warning("entity_no_baseline", entity_id=entity_id, org_id=org_id)
                entity_run_ids[entity_id] = None
                continue

            config_dict = None
            for suffix in ["", "_v1"]:
                try:
                    config_dict = store.load(x_tenant_id, "model_config_v1", f"{baseline_id}{suffix}")
                    break
                except Exception:
                    continue
            if config_dict is None:
                logger.error("baseline_not_found", entity_id=entity_id, baseline_id=baseline_id)
                entity_run_ids[entity_id] = None
                continue

            config = ModelConfig.model_validate(config_dict)
            time_series = run_engine(config, None)
            statements = generate_statements(config, time_series)

            periods = statements.periods or []
            if horizon is None:
                horizon = len(periods)

            entity_results.append(
                EntityResult(
                    entity_id=entity_id,
                    currency=currency,
                    statements={
                        "income_statement": statements.income_statement,
                        "balance_sheet": statements.balance_sheet,
                        "cash_flow": statements.cash_flow,
                    },
                    kpis={},
                    ownership_pct=own_info["ownership_pct"],
                    consolidation_method=own_info["consolidation_method"],
                    withholding_tax_rate=wt_rate,
                )
            )
            entity_run_ids[entity_id] = baseline_id

        if not entity_results or horizon is None or horizon == 0:
            raise ValueError("No entities with valid baselines/runs found")

        ic_links = [
            {
                "from_entity_id": r["from_entity_id"],
                "to_entity_id": r["to_entity_id"],
                "link_type": r["link_type"],
                "amount_or_rate": float(r["amount_or_rate"]) if r["amount_or_rate"] is not None else None,
                "frequency": r["frequency"],
                "withholding_tax_applicable": r["withholding_tax_applicable"],
            }
            for r in ic_rows
        ]
        eliminations = compute_intercompany_amounts(
            ic_links,
            entity_results,
            horizon,
            horizon_granularity=body.horizon_granularity,
        )

        result = consolidate(
            entity_results=entity_results,
            eliminations=eliminations,
            reporting_currency=org_row["reporting_currency"],
            fx_avg_rates=fx_avg_rates,
            minority_interest_treatment=org_row["minority_interest_treatment"] or "proportional",
            horizon=horizon,
            eliminate_intercompany=org_row["eliminate_intercompany"],
            org_id=org_id,
            fx_closing_rates=fx_closing_rates,
        )

        result_payload = {
            "consolidated_is": result.consolidated_is,
            "consolidated_bs": result.consolidated_bs,
            "consolidated_cf": result.consolidated_cf,
            "consolidated_kpis": result.consolidated_kpis,
            "minority_interest": result.minority_interest,
            "fx_rates_used": {f"{k[0]}/{k[1]}": v for k, v in result.fx_rates_used.items()},
            "integrity": result.integrity,
        }
        store.save(x_tenant_id, "consolidated_result", consolidated_run_id, result_payload)

        async with tenant_conn(x_tenant_id) as conn:
            await conn.execute(
                """UPDATE consolidated_runs
                   SET status = 'succeeded', entity_run_ids = $3::jsonb,
                       fx_rates_used_json = $4::jsonb, completed_at = now()
                   WHERE tenant_id = $1 AND consolidated_run_id = $2""",
                x_tenant_id,
                consolidated_run_id,
                json.dumps(entity_run_ids),
                json.dumps({f"{k[0]}/{k[1]}": v for k, v in fx_avg_rates.items()}),
            )

    except (EngineError, ValueError, Exception) as e:
        logger.error("consolidated_run_failed", run_id=consolidated_run_id, error=str(e))
        async with tenant_conn(x_tenant_id) as conn:
            await conn.execute(
                """UPDATE consolidated_runs
                   SET status = 'failed', error_message = $3, completed_at = now()
                   WHERE tenant_id = $1 AND consolidated_run_id = $2""",
                x_tenant_id,
                consolidated_run_id,
                str(e)[:1000],
            )
        raise HTTPException(500, "Consolidated run failed") from e

    return {"consolidated_run_id": consolidated_run_id, "status": "succeeded"}


@router.get("/{org_id}/runs")
async def list_consolidated_runs(
    org_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT consolidated_run_id, status, created_at, completed_at, error_message
               FROM consolidated_runs WHERE tenant_id = $1 AND org_id = $2 ORDER BY created_at DESC LIMIT $3 OFFSET $4""",
            x_tenant_id,
            org_id,
            limit,
            offset,
        )
    return {
        "items": [
            {
                "consolidated_run_id": r["consolidated_run_id"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
                "error_message": r["error_message"],
            }
            for r in rows
        ],
    }


@router.get("/{org_id}/runs/{run_id}")
async def get_consolidated_run(
    org_id: str,
    run_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT consolidated_run_id, status, entity_run_ids, consolidation_adjustments_json, fx_rates_used_json, error_message, created_at, completed_at
               FROM consolidated_runs WHERE tenant_id = $1 AND org_id = $2 AND consolidated_run_id = $3""",
            x_tenant_id,
            org_id,
            run_id,
        )
        if not row:
            raise HTTPException(404, "Consolidated run not found")
    artifact = store.load(x_tenant_id, "consolidated_result", run_id) if row["status"] == "succeeded" else None
    return {
        "consolidated_run_id": row["consolidated_run_id"],
        "status": row["status"],
        "entity_run_ids": row["entity_run_ids"],
        "consolidation_adjustments": row["consolidation_adjustments_json"] or {},
        "fx_rates_used": row["fx_rates_used_json"] or {},
        "error_message": row["error_message"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
        "result": artifact,
    }


@router.get("/{org_id}/runs/{run_id}/statements")
async def get_consolidated_statements(
    org_id: str,
    run_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT status FROM consolidated_runs WHERE tenant_id = $1 AND org_id = $2 AND consolidated_run_id = $3",
            x_tenant_id,
            org_id,
            run_id,
        )
        if not row:
            raise HTTPException(404, "Consolidated run not found")
        if row["status"] != "succeeded":
            raise HTTPException(400, f"Run not ready: {row['status']}")
    artifact = store.load(x_tenant_id, "consolidated_result", run_id)
    if not artifact:
        return {"income_statement": [], "balance_sheet": [], "cash_flow": []}
    return {
        "income_statement": artifact.get("consolidated_is", {}).get("income_statement", []),
        "balance_sheet": artifact.get("consolidated_bs", {}).get("balance_sheet", []),
        "cash_flow": artifact.get("consolidated_cf", {}).get("cash_flow", []),
    }
