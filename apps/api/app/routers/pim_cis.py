"""PIM economic context + CIS endpoints — PIM-2.5 data API + PIM-2.8.

Endpoints:
  GET  /pim/economic/snapshots          — recent economic snapshots (regime + indicators)
  GET  /pim/economic/current            — latest snapshot only
  POST /pim/cis/compute                 — compute CIS for one or more companies
  POST /pim/cis/factor-attribution      — LLM narrative for factor attribution (pim_factor_attribution)

All endpoints require PIM access gate (check_pim_access).
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_llm_router, require_pim_access
from apps.api.app.services.llm.router import LLMRouter
from apps.api.app.services.pim.cis import (
    CISResult,
    CISWeights,
    compute_cis,
    compute_factor_scores,
)
from shared.fm_shared.errors import LLMError

logger = structlog.get_logger()

router = APIRouter(prefix="/pim", tags=["pim"])

_ANALYST_ROLES = ("owner", "admin", "analyst")

_FACTOR_ATTRIBUTION_SCHEMA = {
    "type": "object",
    "required": ["narrative", "top_driver", "risk_note"],
    "additionalProperties": False,
    "properties": {
        "narrative": {
            "type": "string",
            "description": "2-4 sentence explanation of CIS score composition citing specific factor values",
        },
        "top_driver": {
            "type": "string",
            "description": "Name of the factor contributing most to the score",
        },
        "risk_note": {
            "type": "string",
            "description": "Brief note on the weakest factor or key uncertainty",
        },
    },
}

_FACTOR_ATTRIBUTION_SYSTEM = (
    "You are a quantitative analyst explaining a Composite Investment Score (CIS). "
    "Describe what drives the score using only the factor data provided. "
    "Do not extrapolate, speculate, or recommend buying or selling. "
    "Include a limitations disclaimer referencing model uncertainty."
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CISFactorInput(BaseModel):
    company_id: str
    sector: str | None = None
    # Fundamental quality inputs
    dcf_upside_pct: float | None = Field(default=None, description="DCF upside % vs market price")
    roe: float | None = Field(default=None, description="Return on equity %")
    debt_to_equity: float | None = Field(default=None, ge=0.0, description="D/E ratio")
    # Fundamental momentum inputs
    revenue_growth_qoq: float | None = Field(default=None, description="QoQ revenue growth %")
    ebitda_margin_change: float | None = Field(default=None, description="QoQ EBITDA margin change pp")
    # Sentiment inputs (from pim_sentiment_aggregates)
    avg_sentiment_score: float | None = Field(default=None, ge=-1.0, le=1.0)
    trend_direction: str | None = Field(default=None, pattern="^(improving|stable|declining)$")


class ComputeCISBody(BaseModel):
    companies: list[CISFactorInput] = Field(..., min_length=1, max_length=100)
    weights: dict[str, float] | None = Field(
        default=None,
        description="Custom factor weights (must sum to 1.0). Keys: fundamental_quality, fundamental_momentum, idiosyncratic_sentiment, sentiment_momentum, sector_positioning",
    )


class FactorAttributionBody(BaseModel):
    company_id: str
    cis_score: float = Field(..., ge=0.0, le=100.0)
    fundamental_quality: float | None = Field(default=None, ge=0.0, le=100.0)
    fundamental_momentum: float | None = Field(default=None, ge=0.0, le=100.0)
    idiosyncratic_sentiment: float | None = Field(default=None, ge=0.0, le=100.0)
    sentiment_momentum: float | None = Field(default=None, ge=0.0, le=100.0)
    sector_positioning: float | None = Field(default=None, ge=0.0, le=100.0)
    current_regime: str | None = Field(default=None, pattern="^(expansion|contraction|transition)$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _snapshot_to_dict(row: Any) -> dict[str, Any]:
    return {
        "snapshot_id": row["snapshot_id"],
        "fetched_at": row["fetched_at"].isoformat() if row["fetched_at"] else None,
        "gdp_growth_pct": row["gdp_growth_pct"],
        "cpi_yoy_pct": row["cpi_yoy_pct"],
        "unemployment_rate": row["unemployment_rate"],
        "yield_spread_10y2y": row["yield_spread_10y2y"],
        "ism_pmi": row["ism_pmi"],
        "regime": row["regime"],
        "regime_confidence": float(row["regime_confidence"]),
        "indicators_agreeing": row["indicators_agreeing"],
        "indicators_total": row["indicators_total"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def _cis_result_to_dict(result: CISResult) -> dict[str, Any]:
    fs = result.factor_scores
    w = result.weights_used
    return {
        "company_id": result.company_id,
        "cis_score": result.cis_score,
        "factors_available": result.factors_available,
        "factors_total": result.factors_total,
        "factor_scores": {
            "fundamental_quality": fs.fundamental_quality,
            "fundamental_momentum": fs.fundamental_momentum,
            "idiosyncratic_sentiment": fs.idiosyncratic_sentiment,
            "sentiment_momentum": fs.sentiment_momentum,
            "sector_positioning": fs.sector_positioning,
        },
        "weights_used": {
            "fundamental_quality": w.fundamental_quality,
            "fundamental_momentum": w.fundamental_momentum,
            "idiosyncratic_sentiment": w.idiosyncratic_sentiment,
            "sentiment_momentum": w.sentiment_momentum,
            "sector_positioning": w.sector_positioning,
        },
        "limitations": result.limitations,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/economic/snapshots")
async def list_economic_snapshots(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(12, ge=1, le=60, description="Max snapshots to return (default 12 = 1 year monthly)"),
    offset: int = Query(0, ge=0),
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """List recent economic context snapshots (regime timeline). PIM-2.5."""
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT snapshot_id, fetched_at, gdp_growth_pct, cpi_yoy_pct, unemployment_rate,
                      yield_spread_10y2y, ism_pmi, regime, regime_confidence,
                      indicators_agreeing, indicators_total, created_at
               FROM pim_economic_snapshots
               WHERE tenant_id = $1
               ORDER BY fetched_at DESC
               LIMIT $2 OFFSET $3""",
            x_tenant_id,
            limit,
            offset,
        )
    return {
        "snapshots": [_snapshot_to_dict(r) for r in rows],
        "limit": limit,
        "offset": offset,
    }


@router.get("/economic/current")
async def get_current_economic_snapshot(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """Get the most recent economic context snapshot. PIM-2.5."""
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT snapshot_id, fetched_at, gdp_growth_pct, cpi_yoy_pct, unemployment_rate,
                      yield_spread_10y2y, ism_pmi, regime, regime_confidence,
                      indicators_agreeing, indicators_total, created_at
               FROM pim_economic_snapshots
               WHERE tenant_id = $1
               ORDER BY fetched_at DESC
               LIMIT 1""",
            x_tenant_id,
        )
    if not row:
        raise HTTPException(404, "No economic snapshot available; run FRED refresh first")
    return _snapshot_to_dict(row)


@router.post("/cis/compute", status_code=200)
async def compute_cis_scores(
    body: ComputeCISBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """Compute CIS scores for one or more companies. PIM-2.6/2.7.

    Accepts raw financial + sentiment signals; returns CIS [0, 100] per company.
    """
    # Resolve current regime for sector positioning
    current_regime: str | None = None
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT regime FROM pim_economic_snapshots WHERE tenant_id = $1 ORDER BY fetched_at DESC LIMIT 1",
            x_tenant_id,
        )
        if row:
            current_regime = row["regime"]

    # Build CIS weights from request (or use defaults)
    weights: CISWeights | None = None
    if body.weights:
        try:
            weights = CISWeights(**body.weights)
            weights.validate()
        except (TypeError, ValueError) as e:
            raise HTTPException(400, f"Invalid CIS weights: {e}") from e

    results = []
    for company_input in body.companies:
        factor_scores = compute_factor_scores(
            company_input.company_id,
            dcf_upside_pct=company_input.dcf_upside_pct,
            roe=company_input.roe,
            debt_to_equity=company_input.debt_to_equity,
            revenue_growth_qoq=company_input.revenue_growth_qoq,
            ebitda_margin_change=company_input.ebitda_margin_change,
            avg_sentiment_score=company_input.avg_sentiment_score,
            trend_direction=company_input.trend_direction,
            sector=company_input.sector,
            current_regime=current_regime,
        )
        cis_result = compute_cis(factor_scores, weights)
        results.append(_cis_result_to_dict(cis_result))

    # Sort descending by CIS score
    results.sort(key=lambda r: r["cis_score"], reverse=True)

    return {
        "companies": results,
        "current_regime": current_regime,
        "count": len(results),
    }


@router.post("/cis/factor-attribution", status_code=200)
async def get_factor_attribution(
    body: FactorAttributionBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    llm: LLMRouter = Depends(get_llm_router),  # noqa: B008
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """Generate LLM narrative explaining CIS factor attribution. PIM-2.8.

    Uses pim_factor_attribution task label at temperature=0.2 (FR-3.6).
    """
    factor_summary = (
        f"Company: {body.company_id}\n"
        f"CIS Score: {body.cis_score:.1f}/100\n"
        f"Current Economic Regime: {body.current_regime or 'unknown'}\n\n"
        f"Factor Scores (0=worst, 100=best):\n"
        f"  Fundamental Quality (35% weight):     {body.fundamental_quality if body.fundamental_quality is not None else 'N/A'}\n"
        f"  Fundamental Momentum (20% weight):    {body.fundamental_momentum if body.fundamental_momentum is not None else 'N/A'}\n"
        f"  Idiosyncratic Sentiment (25% weight): {body.idiosyncratic_sentiment if body.idiosyncratic_sentiment is not None else 'N/A'}\n"
        f"  Sentiment Momentum (10% weight):      {body.sentiment_momentum if body.sentiment_momentum is not None else 'N/A'}\n"
        f"  Sector Positioning (10% weight):      {body.sector_positioning if body.sector_positioning is not None else 'N/A'}\n"
    )

    try:
        response = await llm.complete_with_routing(
            x_tenant_id,
            [
                {"role": "system", "content": _FACTOR_ATTRIBUTION_SYSTEM},
                {"role": "user", "content": factor_summary},
            ],
            _FACTOR_ATTRIBUTION_SCHEMA,
            "pim_factor_attribution",
            max_tokens=512,
            temperature=0.2,
        )
    except LLMError as e:
        raise HTTPException(
            503 if e.code == "ERR_LLM_ALL_PROVIDERS_FAILED" else 429,
            detail=f"{e.message}: {e.details}" if e.details else e.message,
        ) from e

    content = response.content or {}
    if not isinstance(content, dict):
        logger.warning("pim_factor_attribution_not_dict", content_type=type(content).__name__)
        content = {}

    return {
        "company_id": body.company_id,
        "cis_score": body.cis_score,
        "narrative": content.get("narrative", ""),
        "top_driver": content.get("top_driver", ""),
        "risk_note": content.get("risk_note", ""),
        "limitations": (
            "CIS is a model-based estimate. Scores do not constitute investment advice. "
            "Past performance does not predict future results."
        ),
    }
