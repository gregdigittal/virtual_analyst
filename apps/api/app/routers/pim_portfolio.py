"""PIM portfolio construction endpoints.

PIM-4.2: POST /pim/portfolio/build     — greedy top-N by CIS, apply constraints
PIM-4.3: Constraints enforced in build (max_weight_pct, max_sector_pct, min_liquidity)
PIM-4.4: POST /pim/portfolio/build     — result persisted as versioned run_id snapshot
PIM-4.5: GET  /pim/portfolio/{run_id}/narrative — LLM narrative for a run
          POST /pim/portfolio/build    — optionally generates narrative in one call

GET  /pim/portfolio/runs              — list recent portfolio runs
GET  /pim/portfolio/{run_id}          — fetch a specific run with holdings
DELETE /pim/portfolio/{run_id}        — remove a run (owner/admin only)

All endpoints require PIM access gate (check_pim_access).
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_llm_router, require_pim_access, require_role
from apps.api.app.services.llm.router import LLMRouter
from apps.api.app.services.pim.portfolio import (
    _LIMITATIONS,
    PortfolioCandidate,
    PositionConstraints,
    build_portfolio,
    generate_narrative,
    persist_run,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/pim/portfolio", tags=["pim"])

_ANALYST_ROLES = ("owner", "admin", "analyst")
_WRITE_ROLES = ("owner", "admin")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ConstraintsInput(BaseModel):
    top_n: int = Field(default=10, ge=1, le=200)
    max_weight_pct: float = Field(default=0.15, gt=0.0, le=1.0)
    max_sector_pct: float = Field(default=0.35, gt=0.0, le=1.0)
    min_cis_score: float = Field(default=0.0, ge=0.0, le=100.0)
    min_liquidity_usd: float | None = Field(default=None, ge=0.0)


class CandidateInput(BaseModel):
    company_id: str
    cis_score: float = Field(..., ge=0.0, le=100.0)
    ticker: str | None = None
    name: str | None = None
    sector: str | None = None
    market_cap_usd: float | None = Field(default=None, ge=0.0)
    fundamental_quality: float | None = Field(default=None, ge=0.0, le=100.0)
    fundamental_momentum: float | None = Field(default=None, ge=0.0, le=100.0)
    idiosyncratic_sentiment: float | None = Field(default=None, ge=0.0, le=100.0)
    sentiment_momentum: float | None = Field(default=None, ge=0.0, le=100.0)
    sector_positioning: float | None = Field(default=None, ge=0.0, le=100.0)


class BuildPortfolioBody(BaseModel):
    candidates: list[CandidateInput] = Field(..., min_length=1, max_length=500)
    constraints: ConstraintsInput = Field(default_factory=ConstraintsInput)
    current_regime: str | None = Field(
        default=None, pattern="^(expansion|contraction|transition)$"
    )
    generate_narrative: bool = Field(
        default=True,
        description="Generate LLM portfolio narrative (pim_portfolio_narrative) synchronously.",
    )


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def _holding_to_dict(h: Any) -> dict[str, Any]:
    return {
        "rank": h.rank,
        "company_id": h.company_id,
        "ticker": h.ticker,
        "name": h.name,
        "cis_score": h.cis_score,
        "weight": h.weight,
        "weight_pct": round(h.weight * 100, 2),
        "sector": h.sector,
        "factor_scores": {
            "fundamental_quality": h.fundamental_quality,
            "fundamental_momentum": h.fundamental_momentum,
            "idiosyncratic_sentiment": h.idiosyncratic_sentiment,
            "sentiment_momentum": h.sentiment_momentum,
            "sector_positioning": h.sector_positioning,
        },
    }


def _run_to_dict(run: Any, include_holdings: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "run_id": run.run_id,
        "tenant_id": run.tenant_id,
        "n_candidates": run.n_candidates,
        "n_holdings": run.n_holdings,
        "avg_cis_score": round(run.avg_cis_score, 2),
        "total_cis_score": round(run.total_cis_score, 2),
        "regime_at_run": run.regime_at_run,
        "constraints": {
            "top_n": run.constraints.top_n,
            "max_weight_pct": run.constraints.max_weight_pct,
            "max_sector_pct": run.constraints.max_sector_pct,
            "min_cis_score": run.constraints.min_cis_score,
            "min_liquidity_usd": run.constraints.min_liquidity_usd,
        },
        "narrative": run.narrative,
        "narrative_top_picks": run.narrative_top_picks,
        "narrative_risk_note": run.narrative_risk_note,
        "narrative_regime_context": run.narrative_regime_context,
        "limitations": run.limitations,
    }
    if include_holdings:
        result["holdings"] = [_holding_to_dict(h) for h in run.holdings]
    return result


def _row_to_run_summary(row: Any) -> dict[str, Any]:
    """Convert a DB run row to a summary dict (no holdings)."""
    import json as _json
    constraints_raw = row["constraints_json"]
    if isinstance(constraints_raw, str):
        constraints = _json.loads(constraints_raw)
    elif isinstance(constraints_raw, dict):
        constraints = constraints_raw
    else:
        constraints = {}

    return {
        "run_id": row["run_id"],
        "run_at": row["run_at"].isoformat() if row["run_at"] else None,
        "n_candidates": row["n_candidates"],
        "n_holdings": row["n_holdings"],
        "avg_cis_score": float(row["avg_cis_score"]),
        "regime_at_run": row["regime_at_run"],
        "constraints": constraints,
        "has_narrative": bool(row["narrative"]),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/build", status_code=201)
async def build_portfolio_endpoint(
    body: BuildPortfolioBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    llm: LLMRouter = Depends(get_llm_router),  # noqa: B008
    _: None = require_role(*_ANALYST_ROLES),  # noqa: B008
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """Construct a portfolio from CIS-ranked candidates, persist and optionally narrate.

    PIM-4.2 + PIM-4.3 + PIM-4.4 + PIM-4.5.

    1. Applies constraints (CIS filter, liquidity filter, sector cap, max_weight).
    2. Selects top-N by CIS (greedy).
    3. Assigns equal-weights (capped at max_weight_pct).
    4. Persists the run to pim_portfolio_runs/holdings (versioned snapshot).
    5. Optionally generates LLM portfolio narrative (pim_portfolio_narrative).
    """
    # Build constraints object
    try:
        constraints = PositionConstraints(
            top_n=body.constraints.top_n,
            max_weight_pct=body.constraints.max_weight_pct,
            max_sector_pct=body.constraints.max_sector_pct,
            min_cis_score=body.constraints.min_cis_score,
            min_liquidity_usd=body.constraints.min_liquidity_usd,
        )
    except ValueError as e:
        raise HTTPException(400, f"Invalid constraints: {e}") from e

    # Build candidate objects
    candidates = [
        PortfolioCandidate(
            company_id=c.company_id,
            cis_score=c.cis_score,
            ticker=c.ticker,
            name=c.name,
            sector=c.sector,
            market_cap_usd=c.market_cap_usd,
            fundamental_quality=c.fundamental_quality,
            fundamental_momentum=c.fundamental_momentum,
            idiosyncratic_sentiment=c.idiosyncratic_sentiment,
            sentiment_momentum=c.sentiment_momentum,
            sector_positioning=c.sector_positioning,
        )
        for c in body.candidates
    ]

    # Construct portfolio (PIM-4.2 + PIM-4.3)
    run = build_portfolio(
        candidates=candidates,
        constraints=constraints,
        current_regime=body.current_regime,
        tenant_id=x_tenant_id,
    )

    # Generate LLM narrative if requested (PIM-4.5)
    if body.generate_narrative:
        run = await generate_narrative(run, llm)

    # Persist run snapshot (PIM-4.4)
    async with tenant_conn(x_tenant_id) as conn:
        await persist_run(run, conn)

    logger.info(
        "portfolio_built",
        tenant_id=x_tenant_id,
        run_id=run.run_id,
        n_holdings=run.n_holdings,
        regime=body.current_regime,
    )
    return _run_to_dict(run)


@router.get("/runs")
async def list_portfolio_runs(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: None = require_role(*_ANALYST_ROLES),  # noqa: B008
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """List recent portfolio construction runs for this tenant."""
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT run_id, run_at, n_candidates, n_holdings, avg_cis_score,
                      regime_at_run, constraints_json, narrative
               FROM pim_portfolio_runs
               WHERE tenant_id = $1
               ORDER BY run_at DESC
               LIMIT $2 OFFSET $3""",
            x_tenant_id,
            limit,
            offset,
        )
        total = await conn.fetchval(
            "SELECT count(*) FROM pim_portfolio_runs WHERE tenant_id = $1",
            x_tenant_id,
        )
    return {
        "items": [_row_to_run_summary(r) for r in rows],
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{run_id}")
async def get_portfolio_run(
    run_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = require_role(*_ANALYST_ROLES),  # noqa: B008
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """Fetch a specific portfolio run with all holdings."""
    async with tenant_conn(x_tenant_id) as conn:
        run_row = await conn.fetchrow(
            """SELECT run_id, run_at, n_candidates, n_holdings, avg_cis_score,
                      total_cis_score, regime_at_run, constraints_json,
                      narrative, narrative_top_picks, narrative_risk_note, narrative_regime_context
               FROM pim_portfolio_runs
               WHERE tenant_id = $1 AND run_id = $2""",
            x_tenant_id,
            run_id,
        )
        if not run_row:
            raise HTTPException(404, f"Portfolio run '{run_id}' not found")
        holding_rows = await conn.fetch(
            """SELECT rank, company_id, ticker, name, cis_score, weight, sector,
                      fundamental_quality, fundamental_momentum, idiosyncratic_sentiment,
                      sentiment_momentum, sector_positioning
               FROM pim_portfolio_holdings
               WHERE tenant_id = $1 AND run_id = $2
               ORDER BY rank ASC""",
            x_tenant_id,
            run_id,
        )

    import json as _json
    constraints_raw = run_row["constraints_json"]
    if isinstance(constraints_raw, str):
        constraints_dict = _json.loads(constraints_raw)
    elif isinstance(constraints_raw, dict):
        constraints_dict = constraints_raw
    else:
        constraints_dict = {}

    holdings = [
        {
            "rank": r["rank"],
            "company_id": r["company_id"],
            "ticker": r["ticker"],
            "name": r["name"],
            "cis_score": float(r["cis_score"]),
            "weight": float(r["weight"]),
            "weight_pct": round(float(r["weight"]) * 100, 2),
            "sector": r["sector"],
            "factor_scores": {
                "fundamental_quality": r["fundamental_quality"],
                "fundamental_momentum": r["fundamental_momentum"],
                "idiosyncratic_sentiment": r["idiosyncratic_sentiment"],
                "sentiment_momentum": r["sentiment_momentum"],
                "sector_positioning": r["sector_positioning"],
            },
        }
        for r in holding_rows
    ]

    return {
        "run_id": run_row["run_id"],
        "run_at": run_row["run_at"].isoformat() if run_row["run_at"] else None,
        "n_candidates": run_row["n_candidates"],
        "n_holdings": run_row["n_holdings"],
        "avg_cis_score": float(run_row["avg_cis_score"]),
        "total_cis_score": float(run_row["total_cis_score"]),
        "regime_at_run": run_row["regime_at_run"],
        "constraints": constraints_dict,
        "narrative": run_row["narrative"],
        "narrative_top_picks": run_row["narrative_top_picks"],
        "narrative_risk_note": run_row["narrative_risk_note"],
        "narrative_regime_context": run_row["narrative_regime_context"],
        "limitations": _LIMITATIONS,
        "holdings": holdings,
    }


@router.delete("/{run_id}", status_code=204)
async def delete_portfolio_run(
    run_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = require_role(*_WRITE_ROLES),  # noqa: B008
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> None:
    """Delete a portfolio run and all its holdings (cascade)."""
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            "DELETE FROM pim_portfolio_runs WHERE tenant_id = $1 AND run_id = $2",
            x_tenant_id,
            run_id,
        )
    if result == "DELETE 0":
        raise HTTPException(404, f"Portfolio run '{run_id}' not found")
