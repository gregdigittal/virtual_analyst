"""PIM-1.1: Company universe CRUD endpoints."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.deps import ROLES_CAN_WRITE, require_role
from apps.api.app.services.pim.access import check_pim_access

logger = structlog.get_logger()

router = APIRouter(prefix="/pim/universe", tags=["pim"], dependencies=[require_role(*ROLES_CAN_WRITE)])


def _company_id() -> str:
    return f"pco_{uuid.uuid4().hex[:14]}"


# --- Request/response models ---


class AddCompanyBody(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    company_name: str = Field(..., min_length=1, max_length=255)
    sector: str | None = Field(default=None, max_length=128)
    sub_sector: str | None = Field(default=None, max_length=128)
    country_iso: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    market_cap_usd: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    exchange: str | None = Field(default=None, max_length=20)
    tags: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)


class UpdateCompanyBody(BaseModel):
    ticker: str | None = Field(default=None, min_length=1, max_length=20)
    company_name: str | None = Field(default=None, min_length=1, max_length=255)
    sector: str | None = Field(default=None, max_length=128)
    sub_sector: str | None = Field(default=None, max_length=128)
    country_iso: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    market_cap_usd: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    exchange: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None
    tags: list[str] | None = None
    notes: str | None = Field(default=None, max_length=2000)


class BulkAddBody(BaseModel):
    companies: list[AddCompanyBody] = Field(..., min_length=1, max_length=500)


# --- Helpers ---


def _row_to_dict(r: Any) -> dict[str, Any]:
    return {
        "company_id": r["company_id"],
        "ticker": r["ticker"],
        "company_name": r["company_name"],
        "sector": r["sector"],
        "sub_sector": r["sub_sector"],
        "country_iso": r["country_iso"],
        "market_cap_usd": float(r["market_cap_usd"]) if r["market_cap_usd"] is not None else None,
        "currency": r["currency"],
        "exchange": r["exchange"],
        "is_active": r["is_active"],
        "tags": r["tags"] if r["tags"] else [],
        "notes": r["notes"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
    }


# --- Endpoints ---


@router.post("", status_code=201)
async def add_company(
    body: AddCompanyBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Add a company to the tenant's investable universe."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    company_id = _company_id()
    import json
    async with tenant_conn(x_tenant_id) as conn:
        await check_pim_access(x_tenant_id, conn)
        await conn.execute(
            """INSERT INTO pim_universes
               (tenant_id, company_id, ticker, company_name, sector, sub_sector,
                country_iso, market_cap_usd, currency, exchange, tags, notes, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12, $13)""",
            x_tenant_id,
            company_id,
            body.ticker,
            body.company_name,
            body.sector,
            body.sub_sector,
            body.country_iso,
            body.market_cap_usd,
            body.currency,
            body.exchange,
            json.dumps(body.tags),
            body.notes,
            x_user_id or None,
        )
        row = await conn.fetchrow(
            "SELECT * FROM pim_universes WHERE tenant_id = $1 AND company_id = $2",
            x_tenant_id,
            company_id,
        )
    return _row_to_dict(row)


@router.post("/bulk", status_code=201)
async def bulk_add_companies(
    body: BulkAddBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Bulk add companies to the universe (up to 500)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    import json
    added: list[dict[str, Any]] = []
    async with tenant_conn(x_tenant_id) as conn:
        await check_pim_access(x_tenant_id, conn)
        async with conn.transaction():
            for c in body.companies:
                cid = _company_id()
                await conn.execute(
                    """INSERT INTO pim_universes
                       (tenant_id, company_id, ticker, company_name, sector, sub_sector,
                        country_iso, market_cap_usd, currency, exchange, tags, notes, created_by)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb, $12, $13)
                       ON CONFLICT (tenant_id, company_id) DO NOTHING""",
                    x_tenant_id,
                    cid,
                    c.ticker,
                    c.company_name,
                    c.sector,
                    c.sub_sector,
                    c.country_iso,
                    c.market_cap_usd,
                    c.currency,
                    c.exchange,
                    json.dumps(c.tags),
                    c.notes,
                    x_user_id or None,
                )
                added.append({"company_id": cid, "ticker": c.ticker, "company_name": c.company_name})
    return {"added": len(added), "companies": added}


@router.get("")
async def list_companies(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    sector: str | None = Query(default=None, description="Filter by sector"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    search: str | None = Query(default=None, description="Search ticker or company name"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List companies in the tenant's universe with optional filters."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    conditions = ["tenant_id = $1"]
    args: list[Any] = [x_tenant_id]
    idx = 1
    if sector is not None:
        idx += 1
        conditions.append(f"sector = ${idx}")
        args.append(sector)
    if is_active is not None:
        idx += 1
        conditions.append(f"is_active = ${idx}")
        args.append(is_active)
    if search:
        idx += 1
        conditions.append(f"(ticker ILIKE ${idx} OR company_name ILIKE ${idx})")
        args.append(f"%{search}%")
    idx += 1
    limit_ph = idx
    idx += 1
    offset_ph = idx
    args.extend([limit, offset])
    async with tenant_conn(x_tenant_id) as conn:
        await check_pim_access(x_tenant_id, conn)
        rows = await conn.fetch(
            f"""SELECT * FROM pim_universes
                WHERE {" AND ".join(conditions)}
                ORDER BY ticker ASC
                LIMIT ${limit_ph} OFFSET ${offset_ph}""",
            *args,
        )
        count_args = args[:-2]  # exclude limit/offset
        total = await conn.fetchval(
            f"SELECT count(*) FROM pim_universes WHERE {' AND '.join(conditions)}",
            *count_args,
        )
    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{company_id}")
async def get_company(
    company_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get a single company by ID."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        await check_pim_access(x_tenant_id, conn)
        row = await conn.fetchrow(
            "SELECT * FROM pim_universes WHERE tenant_id = $1 AND company_id = $2",
            x_tenant_id,
            company_id,
        )
    if not row:
        raise HTTPException(404, "Company not found")
    return _row_to_dict(row)


@router.patch("/{company_id}")
async def update_company(
    company_id: str,
    body: UpdateCompanyBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Update a company in the universe."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    import json
    async with tenant_conn(x_tenant_id) as conn:
        await check_pim_access(x_tenant_id, conn)
        row = await conn.fetchrow(
            "SELECT company_id FROM pim_universes WHERE tenant_id = $1 AND company_id = $2",
            x_tenant_id,
            company_id,
        )
        if not row:
            raise HTTPException(404, "Company not found")
        updates: list[str] = []
        args: list[Any] = []
        n = 0
        for field_name, value in body.model_dump(exclude_unset=True).items():
            if field_name == "tags" and value is not None:
                n += 1
                updates.append(f"tags = ${n}::jsonb")
                args.append(json.dumps(value))
            else:
                n += 1
                updates.append(f"{field_name} = ${n}")
                args.append(value)
        if not updates:
            row = await conn.fetchrow(
                "SELECT * FROM pim_universes WHERE tenant_id = $1 AND company_id = $2",
                x_tenant_id,
                company_id,
            )
            return _row_to_dict(row)
        n += 1
        args.append(x_tenant_id)
        n += 1
        args.append(company_id)
        await conn.execute(
            f"UPDATE pim_universes SET {', '.join(updates)} WHERE tenant_id = ${n - 1} AND company_id = ${n}",
            *args,
        )
        row = await conn.fetchrow(
            "SELECT * FROM pim_universes WHERE tenant_id = $1 AND company_id = $2",
            x_tenant_id,
            company_id,
        )
    return _row_to_dict(row)


@router.delete("/{company_id}", status_code=204)
async def remove_company(
    company_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> None:
    """Remove a company from the universe."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        await check_pim_access(x_tenant_id, conn)
        res = await conn.execute(
            "DELETE FROM pim_universes WHERE tenant_id = $1 AND company_id = $2",
            x_tenant_id,
            company_id,
        )
    if res == "DELETE 0":
        raise HTTPException(404, "Company not found")


@router.get("/sectors/list")
async def list_sectors(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List distinct sectors in the universe with counts."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        await check_pim_access(x_tenant_id, conn)
        rows = await conn.fetch(
            """SELECT sector, count(*) AS count
               FROM pim_universes
               WHERE tenant_id = $1 AND is_active = true AND sector IS NOT NULL
               GROUP BY sector ORDER BY count DESC""",
            x_tenant_id,
        )
    return {"sectors": [{"sector": r["sector"], "count": r["count"]} for r in rows]}
