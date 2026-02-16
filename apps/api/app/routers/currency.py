"""VA-P8-01: Multi-currency and FX overlays — tenant currency settings and FX rates API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.deps import require_role, ROLES_CAN_WRITE

router = APIRouter(prefix="/currency", tags=["currency"], dependencies=[require_role(*ROLES_CAN_WRITE)])


# --- Request/response models ---


class CurrencySettingsBody(BaseModel):
    base_currency: str = Field(..., min_length=1, max_length=6)
    reporting_currency: str = Field(..., min_length=1, max_length=6)
    fx_source: str = Field(..., pattern="^(manual|feed)$")


class FxRateBody(BaseModel):
    from_currency: str = Field(..., min_length=1, max_length=6)
    to_currency: str = Field(..., min_length=1, max_length=6)
    effective_date: str = Field(..., description="YYYY-MM-DD")
    rate: float = Field(..., gt=0)


# --- Tenant currency settings ---


@router.get("/settings")
async def get_currency_settings(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get tenant currency settings (base, reporting, fx_source). Defaults to USD/USD/manual if not set."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT base_currency, reporting_currency, fx_source, updated_at
               FROM tenant_currency_settings WHERE tenant_id = $1""",
            x_tenant_id,
        )
    if not row:
        return {
            "base_currency": "USD",
            "reporting_currency": "USD",
            "fx_source": "manual",
            "updated_at": None,
        }
    return {
        "base_currency": row["base_currency"],
        "reporting_currency": row["reporting_currency"],
        "fx_source": row["fx_source"],
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


@router.put("/settings")
async def put_currency_settings(
    body: CurrencySettingsBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Create or update tenant currency settings."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO tenant_currency_settings (tenant_id, base_currency, reporting_currency, fx_source, updated_at)
               VALUES ($1, $2, $3, $4, now())
               ON CONFLICT (tenant_id) DO UPDATE SET
                 base_currency = EXCLUDED.base_currency,
                 reporting_currency = EXCLUDED.reporting_currency,
                 fx_source = EXCLUDED.fx_source,
                 updated_at = now()""",
            x_tenant_id,
            body.base_currency,
            body.reporting_currency,
            body.fx_source,
        )
    return {"ok": True, "base_currency": body.base_currency, "reporting_currency": body.reporting_currency}


# --- FX rates (auditable) ---


@router.get("/rates")
async def list_fx_rates(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    from_currency: str | None = Query(None),
    to_currency: str | None = Query(None),
    effective_from: str | None = Query(None, description="YYYY-MM-DD"),
    effective_to: str | None = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List FX rates for the tenant with optional filters."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    conditions = ["tenant_id = $1"]
    params: list[Any] = [x_tenant_id]
    n = 1
    if from_currency:
        n += 1
        params.append(from_currency)
        conditions.append(f"from_currency = ${n}")
    if to_currency:
        n += 1
        params.append(to_currency)
        conditions.append(f"to_currency = ${n}")
    if effective_from:
        n += 1
        params.append(effective_from)
        conditions.append(f"effective_date >= ${n}")
    if effective_to:
        n += 1
        params.append(effective_to)
        conditions.append(f"effective_date <= ${n}")
    where = " AND ".join(conditions)
    count_params = list(params)
    params.extend([limit, offset])
    n_limit = len(params) - 1
    n_offset = len(params)
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            f"""SELECT from_currency, to_currency, effective_date, rate, created_at, created_by
                FROM fx_rates WHERE {where}
                ORDER BY effective_date DESC, from_currency, to_currency
                LIMIT ${n_limit} OFFSET ${n_offset}""",
            *params,
        )
        total = await conn.fetchval(
            f"SELECT count(*) FROM fx_rates WHERE {where}",
            *count_params,
        )
    rates = [
        {
            "from_currency": r["from_currency"],
            "to_currency": r["to_currency"],
            "effective_date": r["effective_date"].isoformat() if hasattr(r["effective_date"], "isoformat") else str(r["effective_date"]),
            "rate": float(r["rate"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "created_by": r["created_by"],
        }
        for r in rows
    ]
    return {"rates": rates, "total": total, "limit": limit, "offset": offset}


@router.post("/rates", status_code=201)
async def add_fx_rate(
    body: FxRateBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Add or replace an FX rate for a given date (auditable)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    try:
        effective_date = date.fromisoformat(body.effective_date)
    except ValueError:
        raise HTTPException(400, "effective_date must be YYYY-MM-DD")
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO fx_rates (tenant_id, from_currency, to_currency, effective_date, rate, created_by)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (tenant_id, from_currency, to_currency, effective_date) DO UPDATE SET
                 rate = EXCLUDED.rate,
                 created_by = EXCLUDED.created_by""",
            x_tenant_id,
            body.from_currency,
            body.to_currency,
            effective_date,
            Decimal(str(body.rate)),
            x_user_id or None,
        )
    return {
        "from_currency": body.from_currency,
        "to_currency": body.to_currency,
        "effective_date": body.effective_date,
        "rate": body.rate,
    }


@router.delete("/rates/{from_currency}/{to_currency}/{effective_date}")
async def delete_fx_rate(
    from_currency: str,
    to_currency: str,
    effective_date: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Delete a single FX rate."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    try:
        eff = date.fromisoformat(effective_date)
    except ValueError:
        raise HTTPException(400, "effective_date must be YYYY-MM-DD")
    async with tenant_conn(x_tenant_id) as conn:
        n = await conn.execute(
            """DELETE FROM fx_rates
               WHERE tenant_id = $1 AND from_currency = $2 AND to_currency = $3 AND effective_date = $4""",
            x_tenant_id,
            from_currency,
            to_currency,
            eff,
        )
    if n == "DELETE 0":
        raise HTTPException(404, "FX rate not found")
    return {"ok": True}


# --- Conversion helper (for run output / board pack) ---


@router.get("/convert")
async def get_conversion_rate(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    from_currency: str = Query(...),
    to_currency: str = Query(...),
    as_of: str | None = Query(None, description="YYYY-MM-DD; default today"),
) -> dict[str, Any]:
    """Get the FX rate to convert from_currency to to_currency (for display/export). Returns rate and as_of date."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if from_currency == to_currency:
        return {"rate": 1.0, "from_currency": from_currency, "to_currency": to_currency, "as_of": as_of or date.today().isoformat()}
    as_of_date = date.fromisoformat(as_of) if as_of else date.today()
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT rate, effective_date FROM fx_rates
               WHERE tenant_id = $1 AND from_currency = $2 AND to_currency = $3 AND effective_date <= $4
               ORDER BY effective_date DESC LIMIT 1""",
            x_tenant_id,
            from_currency,
            to_currency,
            as_of_date,
        )
    if not row:
        raise HTTPException(404, f"No FX rate for {from_currency} -> {to_currency} on or before {as_of_date}")
    return {
        "rate": float(row["rate"]),
        "from_currency": from_currency,
        "to_currency": to_currency,
        "as_of": row["effective_date"].isoformat() if hasattr(row["effective_date"], "isoformat") else str(row["effective_date"]),
    }
