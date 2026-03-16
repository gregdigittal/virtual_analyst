"""PIM PE assessment CRUD + compute + memo endpoints — PIM-6.2 / PIM-6.4 / PIM-7.2.

Endpoints:
  POST   /pim/pe/assessments                           — create PE fund assessment
  GET    /pim/pe/assessments                           — list assessments (tenant)
  GET    /pim/pe/assessments/{assessment_id}           — get single assessment
  PUT    /pim/pe/assessments/{assessment_id}           — update assessment
  DELETE /pim/pe/assessments/{assessment_id}           — delete assessment
  POST   /pim/pe/assessments/{assessment_id}/compute   — run DPI/TVPI/IRR engine + store results
  POST   /pim/pe/assessments/{assessment_id}/memo      — generate LLM investment memo (PIM-7.2)

All endpoints require PIM access gate (require_pim_access).
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_llm_router, require_pim_access
from apps.api.app.services.llm.router import LLMRouter
from apps.api.app.services.pim.pe_benchmarks import compute_pe_metrics

logger = structlog.get_logger()

router = APIRouter(prefix="/pim", tags=["pim"])

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

_VALID_CF_TYPES = frozenset({"drawdown", "distribution", "recallable_distribution"})


class CashFlowItem(BaseModel):
    date: str          # ISO date string e.g. "2023-06-30"
    amount_usd: float = Field(..., gt=0, description="Positive dollar amount")
    cf_type: str       # "drawdown" | "distribution" | "recallable_distribution"

    def model_post_init(self, __context: Any) -> None:
        if self.cf_type not in _VALID_CF_TYPES:
            raise ValueError(f"cf_type must be one of {sorted(_VALID_CF_TYPES)}")


class CreatePeAssessmentBody(BaseModel):
    fund_name: str = Field(..., min_length=1, max_length=200)
    vintage_year: int = Field(..., ge=1980, le=2100)
    currency: str = Field("USD", min_length=3, max_length=3)
    commitment_usd: float = Field(..., gt=0)
    cash_flows: list[CashFlowItem] = Field(default_factory=list)
    nav_usd: float | None = Field(None, gt=0)
    nav_date: str | None = None   # ISO date
    notes: str | None = None


class UpdatePeAssessmentBody(BaseModel):
    fund_name: str | None = Field(None, min_length=1, max_length=200)
    vintage_year: int | None = Field(None, ge=1980, le=2100)
    currency: str | None = Field(None, min_length=3, max_length=3)
    commitment_usd: float | None = Field(None, gt=0)
    cash_flows: list[CashFlowItem] | None = None
    nav_usd: float | None = None
    nav_date: str | None = None
    notes: str | None = None


class PeAssessment(BaseModel):
    assessment_id: str
    tenant_id: str
    fund_name: str
    vintage_year: int
    currency: str
    commitment_usd: float
    cash_flows: list[dict[str, Any]]
    nav_usd: float | None
    nav_date: str | None
    paid_in_capital: float | None
    distributed: float | None
    dpi: float | None
    tvpi: float | None
    moic: float | None
    irr: float | None
    irr_computed_at: str | None
    j_curve_json: list[dict[str, Any]] | None
    notes: str | None
    created_at: str | None
    updated_at: str | None


class PeAssessmentsResponse(BaseModel):
    items: list[PeAssessment]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_assessment(row: Any) -> PeAssessment:
    cf = row["cash_flows"]
    cf_list = json.loads(cf) if isinstance(cf, str) else (cf or [])

    jc = row["j_curve_json"]
    jc_list = json.loads(jc) if isinstance(jc, str) else jc

    return PeAssessment(
        assessment_id=row["assessment_id"],
        tenant_id=row["tenant_id"],
        fund_name=row["fund_name"],
        vintage_year=row["vintage_year"],
        currency=row["currency"],
        commitment_usd=row["commitment_usd"],
        cash_flows=cf_list,
        nav_usd=row["nav_usd"],
        nav_date=str(row["nav_date"]) if row["nav_date"] else None,
        paid_in_capital=row["paid_in_capital"],
        distributed=row["distributed"],
        dpi=row["dpi"],
        tvpi=row["tvpi"],
        moic=row["moic"],
        irr=row["irr"],
        irr_computed_at=str(row["irr_computed_at"]) if row["irr_computed_at"] else None,
        j_curve_json=jc_list,
        notes=row["notes"],
        created_at=str(row["created_at"]) if row["created_at"] else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/pe/assessments", response_model=PeAssessment, status_code=201)
async def create_pe_assessment(
    body: CreatePeAssessmentBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
) -> PeAssessment:
    """Create a new PE fund assessment."""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    cf_json = json.dumps([cf.model_dump() for cf in body.cash_flows])

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO pim_pe_assessments
                (tenant_id, fund_name, vintage_year, currency, commitment_usd,
                 cash_flows, nav_usd, nav_date, notes)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8::date, $9)
            RETURNING *
            """,
            x_tenant_id,
            body.fund_name,
            body.vintage_year,
            body.currency.upper(),
            body.commitment_usd,
            cf_json,
            body.nav_usd,
            body.nav_date,
            body.notes,
        )

    if row is None:
        raise HTTPException(status_code=500, detail="Failed to create assessment")
    return _row_to_assessment(row)


@router.get("/pe/assessments", response_model=PeAssessmentsResponse)
async def list_pe_assessments(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    vintage_year: int | None = Query(None),
) -> PeAssessmentsResponse:
    """List PE fund assessments for a tenant, optionally filtered by vintage year."""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        if vintage_year is not None:
            count_row = await conn.fetchrow(
                "SELECT count(*) AS n FROM pim_pe_assessments WHERE tenant_id = $1 AND vintage_year = $2",
                x_tenant_id, vintage_year,
            )
            rows = await conn.fetch(
                """
                SELECT * FROM pim_pe_assessments
                WHERE tenant_id = $1 AND vintage_year = $2
                ORDER BY vintage_year DESC, fund_name
                LIMIT $3 OFFSET $4
                """,
                x_tenant_id, vintage_year, limit, offset,
            )
        else:
            count_row = await conn.fetchrow(
                "SELECT count(*) AS n FROM pim_pe_assessments WHERE tenant_id = $1",
                x_tenant_id,
            )
            rows = await conn.fetch(
                """
                SELECT * FROM pim_pe_assessments
                WHERE tenant_id = $1
                ORDER BY vintage_year DESC, fund_name
                LIMIT $2 OFFSET $3
                """,
                x_tenant_id, limit, offset,
            )

    total = int(count_row["n"]) if count_row else 0
    return PeAssessmentsResponse(
        items=[_row_to_assessment(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/pe/assessments/{assessment_id}", response_model=PeAssessment)
async def get_pe_assessment(
    assessment_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
) -> PeAssessment:
    """Fetch a single PE assessment by ID."""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM pim_pe_assessments WHERE tenant_id = $1 AND assessment_id = $2",
            x_tenant_id, assessment_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="PE assessment not found")
    return _row_to_assessment(row)


@router.put("/pe/assessments/{assessment_id}", response_model=PeAssessment)
async def update_pe_assessment(
    assessment_id: str,
    body: UpdatePeAssessmentBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
) -> PeAssessment:
    """Update a PE assessment. Only provided fields are modified."""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    updates: list[str] = []
    params: list[Any] = [x_tenant_id, assessment_id]
    idx = 3

    if body.fund_name is not None:
        updates.append(f"fund_name = ${idx}")
        params.append(body.fund_name)
        idx += 1
    if body.vintage_year is not None:
        updates.append(f"vintage_year = ${idx}")
        params.append(body.vintage_year)
        idx += 1
    if body.currency is not None:
        updates.append(f"currency = ${idx}")
        params.append(body.currency.upper())
        idx += 1
    if body.commitment_usd is not None:
        updates.append(f"commitment_usd = ${idx}")
        params.append(body.commitment_usd)
        idx += 1
    if body.cash_flows is not None:
        updates.append(f"cash_flows = ${idx}::jsonb")
        params.append(json.dumps([cf.model_dump() for cf in body.cash_flows]))
        # Invalidate IRR when cash flows change
        updates.append("irr_computed_at = NULL")
        idx += 1
    if body.nav_usd is not None:
        updates.append(f"nav_usd = ${idx}")
        params.append(body.nav_usd)
        idx += 1
    if body.nav_date is not None:
        updates.append(f"nav_date = ${idx}::date")
        params.append(body.nav_date)
        idx += 1
    if body.notes is not None:
        updates.append(f"notes = ${idx}")
        params.append(body.notes)
        idx += 1

    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")

    set_clause = ", ".join(updates)
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            f"""
            UPDATE pim_pe_assessments
            SET {set_clause}
            WHERE tenant_id = $1 AND assessment_id = $2
            RETURNING *
            """,  # noqa: S608 — set_clause is built from hardcoded field names, not user input
            *params,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="PE assessment not found")
    return _row_to_assessment(row)


@router.delete("/pe/assessments/{assessment_id}", response_model=dict)
async def delete_pe_assessment(
    assessment_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
) -> dict[str, bool]:
    """Delete a PE assessment."""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            "DELETE FROM pim_pe_assessments WHERE tenant_id = $1 AND assessment_id = $2",
            x_tenant_id, assessment_id,
        )

    deleted = result == "DELETE 1"
    if not deleted:
        raise HTTPException(status_code=404, detail="PE assessment not found")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# PIM-6.4: Compute metrics + store j_curve_json
# ---------------------------------------------------------------------------

class PeComputeResult(BaseModel):
    assessment_id: str
    paid_in_capital: float
    distributed: float
    dpi: float | None
    tvpi: float | None
    moic: float | None
    irr: float | None
    irr_converged: bool
    j_curve: list[dict[str, Any]]
    limitations: str


@router.post("/pe/assessments/{assessment_id}/compute", response_model=PeComputeResult)
async def compute_pe_assessment(
    assessment_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
) -> PeComputeResult:
    """Run DPI/TVPI/IRR computation and persist results to the assessment row.

    Fetches the current cash flows and NAV, runs the pure-Python engine
    (no LLM, no external calls), stores computed metrics + j_curve_json,
    and returns the result.  (PIM-6.3 / PIM-6.4)
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """
            SELECT assessment_id, cash_flows, nav_usd, commitment_usd
            FROM pim_pe_assessments
            WHERE tenant_id = $1 AND assessment_id = $2
            """,
            x_tenant_id, assessment_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="PE assessment not found")

        cf_raw = row["cash_flows"]
        cf_list = json.loads(cf_raw) if isinstance(cf_raw, str) else (cf_raw or [])
        nav_usd = row["nav_usd"]
        commitment_usd = row["commitment_usd"]

        metrics = compute_pe_metrics(cf_list, commitment_usd, nav_usd)

        j_curve_json = json.dumps(metrics.j_curve)

        await conn.execute(
            """
            UPDATE pim_pe_assessments
            SET
                paid_in_capital  = $3,
                distributed      = $4,
                dpi              = $5,
                tvpi             = $6,
                moic             = $7,
                irr              = $8,
                irr_computed_at  = now(),
                j_curve_json     = $9::jsonb
            WHERE tenant_id = $1 AND assessment_id = $2
            """,
            x_tenant_id,
            assessment_id,
            metrics.paid_in_capital,
            metrics.distributed,
            metrics.dpi,
            metrics.tvpi,
            metrics.moic,
            metrics.irr,
            j_curve_json,
        )

    logger.info(
        "pe_metrics_computed",
        tenant_id=x_tenant_id,
        assessment_id=assessment_id,
        dpi=metrics.dpi,
        tvpi=metrics.tvpi,
        irr=metrics.irr,
        irr_converged=metrics.irr_converged,
    )

    return PeComputeResult(
        assessment_id=assessment_id,
        paid_in_capital=metrics.paid_in_capital,
        distributed=metrics.distributed,
        dpi=metrics.dpi,
        tvpi=metrics.tvpi,
        moic=metrics.moic,
        irr=metrics.irr,
        irr_converged=metrics.irr_converged,
        j_curve=metrics.j_curve,
        limitations=metrics.limitations,
    )


# ---------------------------------------------------------------------------
# PIM-7.2: LLM PE investment memo
# ---------------------------------------------------------------------------

_MEMO_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "executive_summary": {"type": "string"},
        "performance_analysis": {"type": "string"},
        "risk_factors": {"type": "string"},
        "recommendation": {"type": "string"},
        "disclaimer": {"type": "string"},
    },
    "required": ["title", "executive_summary", "performance_analysis", "risk_factors", "recommendation", "disclaimer"],
}


class PeMemoResult(BaseModel):
    assessment_id: str
    fund_name: str
    title: str
    executive_summary: str
    performance_analysis: str
    risk_factors: str
    recommendation: str
    disclaimer: str
    model_used: str


@router.post("/pe/assessments/{assessment_id}/memo", response_model=PeMemoResult)
async def generate_pe_memo(
    assessment_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
    llm: LLMRouter = Depends(get_llm_router),  # noqa: B008
) -> PeMemoResult:
    """Generate a natural-language PE investment memo using the LLM.

    Fetches the computed metrics from the assessment and passes them to the
    LLM to produce a structured memo with executive summary, performance
    analysis, risk factors, and recommendation.

    Requires /compute to have been run first (dpi/tvpi/irr must be populated).

    # PIM-7.2: LLM PE memo, task_label=pim_pe_memo, temperature=0.4 for richer prose.
    # LLMs interpret — they do not calculate. The memo narrates pre-computed metrics.
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """
            SELECT assessment_id, fund_name, vintage_year, currency, commitment_usd,
                   paid_in_capital, distributed, dpi, tvpi, moic, irr, irr_computed_at,
                   nav_usd, notes
            FROM pim_pe_assessments
            WHERE tenant_id = $1 AND assessment_id = $2
            """,
            x_tenant_id, assessment_id,
        )

    if row is None:
        raise HTTPException(status_code=404, detail="PE assessment not found")

    if row["dpi"] is None and row["tvpi"] is None:
        raise HTTPException(
            status_code=422,
            detail="Metrics not yet computed. Run POST .../compute first.",
        )

    fund_name = row["fund_name"]
    vintage_year = row["vintage_year"]
    currency = row["currency"]
    commitment = row["commitment_usd"]
    dpi = float(row["dpi"]) if row["dpi"] is not None else None
    tvpi = float(row["tvpi"]) if row["tvpi"] is not None else None
    moic = float(row["moic"]) if row["moic"] is not None else None
    irr = float(row["irr"]) if row["irr"] is not None else None
    nav_usd = float(row["nav_usd"]) if row["nav_usd"] is not None else None
    notes = row["notes"] or ""

    irr_pct = f"{irr * 100:.1f}%" if irr is not None else "N/A"
    nav_str = f"{currency} {nav_usd:,.0f}" if nav_usd else "Not reported"

    prompt = (
        f"You are a CFA-qualified private equity analyst. "
        f"Generate a concise investment memo for the following fund.\n\n"
        f"Fund: {fund_name}\n"
        f"Vintage Year: {vintage_year}\n"
        f"Currency: {currency}\n"
        f"Commitment: {currency} {commitment:,.0f}\n"
        f"DPI (Distributed to Paid-In): {dpi:.2f}x\n"
        f"TVPI (Total Value to Paid-In): {tvpi:.2f}x\n"
        f"MOIC (Multiple on Invested Capital): {moic:.2f}x\n"
        f"IRR (annualised): {irr_pct}\n"
        f"Current NAV: {nav_str}\n"
        f"Manager Notes: {notes or 'None'}\n\n"
        f"Produce a professional investment memo with:\n"
        f"- title: memo title\n"
        f"- executive_summary: 2–3 sentence overview\n"
        f"- performance_analysis: detailed analysis of DPI/TVPI/IRR vs typical benchmarks\n"
        f"- risk_factors: 3–5 key risks for this fund\n"
        f"- recommendation: Hold / Increase / Reduce with justification\n"
        f"- disclaimer: standard PE disclaimer noting limitations\n\n"
        f"Return as structured JSON matching the provided schema."
    )

    try:
        response = await llm.complete_with_routing(
            tenant_id=x_tenant_id,
            messages=[{"role": "user", "content": prompt}],
            response_schema=_MEMO_SCHEMA,
            task_label="pim_pe_memo",
        )
        model_used = response.model or "unknown"
        content = response.content

        if isinstance(content, str):
            import json as _json
            parsed: dict[str, Any] = _json.loads(content)
        else:
            parsed = content  # type: ignore[assignment]

    except Exception as exc:
        logger.error("pe_memo_generation_failed", assessment_id=assessment_id, error=str(exc))
        raise HTTPException(status_code=502, detail=f"Memo generation failed: {exc}") from exc

    logger.info(
        "pe_memo_generated",
        tenant_id=x_tenant_id,
        assessment_id=assessment_id,
        fund_name=fund_name,
    )

    return PeMemoResult(
        assessment_id=assessment_id,
        fund_name=fund_name,
        title=parsed.get("title", f"{fund_name} — Investment Memo"),
        executive_summary=parsed.get("executive_summary", ""),
        performance_analysis=parsed.get("performance_analysis", ""),
        risk_factors=parsed.get("risk_factors", ""),
        recommendation=parsed.get("recommendation", ""),
        disclaimer=parsed.get("disclaimer", ""),
        model_used=model_used,
    )
