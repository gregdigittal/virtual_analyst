"""PIM-1.7: Sentiment query endpoints.

FR-1.7: Dashboard shows latest scores, trend sparklines, source breakdown.
Read-only endpoints that query pim_sentiment_signals and pim_sentiment_aggregates.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query

from apps.api.app.db import tenant_conn
from apps.api.app.deps import require_pim_access

logger = structlog.get_logger()

router = APIRouter(prefix="/pim/sentiment", tags=["pim"])


# --- Helpers ---


def _signal_to_dict(r: Any) -> dict[str, Any]:
    return {
        "signal_id": r["signal_id"],
        "company_id": r["company_id"],
        "source_type": r["source_type"],
        "source_ref": r["source_ref"],
        "headline": r["headline"],
        "published_at": r["published_at"].isoformat() if r["published_at"] else None,
        "sentiment_score": float(r["sentiment_score"]),
        "confidence": float(r["confidence"]),
        "llm_model": r["llm_model"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    }


def _aggregate_to_dict(r: Any) -> dict[str, Any]:
    return {
        "company_id": r["company_id"],
        "period_type": r["period_type"],
        "period_start": r["period_start"].isoformat() if r["period_start"] else None,
        "period_end": r["period_end"].isoformat() if r["period_end"] else None,
        "avg_sentiment": float(r["avg_sentiment"]),
        "median_sentiment": float(r["median_sentiment"]) if r["median_sentiment"] is not None else None,
        "min_sentiment": float(r["min_sentiment"]) if r["min_sentiment"] is not None else None,
        "max_sentiment": float(r["max_sentiment"]) if r["max_sentiment"] is not None else None,
        "std_sentiment": float(r["std_sentiment"]) if r["std_sentiment"] is not None else None,
        "signal_count": r["signal_count"],
        "avg_confidence": float(r["avg_confidence"]) if r["avg_confidence"] is not None else None,
        "source_breakdown": r["source_breakdown"] if r["source_breakdown"] else {},
        "trend_direction": r["trend_direction"],
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
    }


# --- Endpoints ---


@router.get("/scores")
async def list_latest_scores(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    company_id: str | None = Query(None, description="Filter by company"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """List latest sentiment signals, optionally filtered by company.

    Returns most recent signals ordered by published_at descending.
    """
    async with tenant_conn(x_tenant_id) as conn:
        where = "WHERE tenant_id = $1"
        params: list[Any] = [x_tenant_id]
        if company_id:
            where += " AND company_id = $2"
            params.append(company_id)

        count_row = await conn.fetchrow(
            f"SELECT count(*) AS cnt FROM pim_sentiment_signals {where}",
            *params,
        )
        total = count_row["cnt"] if count_row else 0

        rows = await conn.fetch(
            f"""SELECT signal_id, company_id, source_type, source_ref, headline,
                       published_at, sentiment_score, confidence, llm_model, created_at
                FROM pim_sentiment_signals
                {where}
                ORDER BY published_at DESC
                LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}""",
            *params,
            limit,
            offset,
        )

    return {
        "items": [_signal_to_dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/aggregates")
async def list_aggregates(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    company_id: str | None = Query(None, description="Filter by company"),
    period_type: str = Query("weekly", description="'weekly' or 'monthly'"),
    months_back: int = Query(6, ge=1, le=24, description="How many months of history"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """List sentiment aggregates (weekly or monthly time-series).

    Used for trend sparklines on the dashboard.
    """
    if period_type not in ("weekly", "monthly"):
        raise HTTPException(400, "period_type must be 'weekly' or 'monthly'")

    cutoff = date.today() - timedelta(days=months_back * 30)

    async with tenant_conn(x_tenant_id) as conn:
        where = "WHERE tenant_id = $1 AND period_type = $2 AND period_start >= $3"
        params: list[Any] = [x_tenant_id, period_type, cutoff]
        if company_id:
            where += f" AND company_id = ${len(params) + 1}"
            params.append(company_id)

        count_row = await conn.fetchrow(
            f"SELECT count(*) AS cnt FROM pim_sentiment_aggregates {where}",
            *params,
        )
        total = count_row["cnt"] if count_row else 0

        rows = await conn.fetch(
            f"""SELECT company_id, period_type, period_start, period_end,
                       avg_sentiment, median_sentiment, min_sentiment, max_sentiment,
                       std_sentiment, signal_count, avg_confidence, source_breakdown,
                       trend_direction, updated_at
                FROM pim_sentiment_aggregates
                {where}
                ORDER BY period_start DESC
                LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}""",
            *params,
            limit,
            offset,
        )

    return {
        "items": [_aggregate_to_dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/dashboard")
async def sentiment_dashboard(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """Aggregated dashboard view: latest score per company + source breakdown.

    Returns one entry per active company with their latest weekly aggregate,
    overall source breakdown, and trend direction.
    """
    async with tenant_conn(x_tenant_id) as conn:
        # Get all active companies from universe
        companies = await conn.fetch(
            """SELECT company_id, ticker, company_name, sector
               FROM pim_universes
               WHERE tenant_id = $1 AND is_active = true
               ORDER BY company_name""",
            x_tenant_id,
        )

        if not companies:
            return {"items": [], "total": 0}

        company_ids = [co["company_id"] for co in companies]

        # Batch query 1: latest weekly aggregate per company (DISTINCT ON eliminates N+1)
        agg_rows = await conn.fetch(
            """SELECT DISTINCT ON (company_id)
                      company_id, avg_sentiment, signal_count, avg_confidence,
                      source_breakdown, trend_direction, period_start, period_end
               FROM pim_sentiment_aggregates
               WHERE tenant_id = $1 AND period_type = 'weekly' AND company_id = ANY($2::text[])
               ORDER BY company_id, period_start DESC""",
            x_tenant_id,
            company_ids,
        )
        agg_by_company = {r["company_id"]: r for r in agg_rows}

        # Batch query 2: latest signal per company (DISTINCT ON eliminates N+1)
        sig_rows = await conn.fetch(
            """SELECT DISTINCT ON (company_id)
                      company_id, sentiment_score, confidence, headline, published_at, source_type
               FROM pim_sentiment_signals
               WHERE tenant_id = $1 AND company_id = ANY($2::text[])
               ORDER BY company_id, published_at DESC NULLS LAST""",
            x_tenant_id,
            company_ids,
        )
        sig_by_company = {r["company_id"]: r for r in sig_rows}

        # Batch query 3: total signal count per company
        count_rows = await conn.fetch(
            """SELECT company_id, count(*) AS cnt
               FROM pim_sentiment_signals
               WHERE tenant_id = $1 AND company_id = ANY($2::text[])
               GROUP BY company_id""",
            x_tenant_id,
            company_ids,
        )
        count_by_company = {r["company_id"]: r["cnt"] for r in count_rows}

        items: list[dict[str, Any]] = []
        for co in companies:
            cid = co["company_id"]
            agg_row = agg_by_company.get(cid)
            sig_row = sig_by_company.get(cid)

            entry: dict[str, Any] = {
                "company_id": cid,
                "ticker": co["ticker"],
                "company_name": co["company_name"],
                "sector": co["sector"],
                "total_signals": count_by_company.get(cid, 0),
            }

            if agg_row:
                entry["latest_avg_sentiment"] = float(agg_row["avg_sentiment"])
                entry["latest_signal_count"] = agg_row["signal_count"]
                entry["latest_avg_confidence"] = float(agg_row["avg_confidence"]) if agg_row["avg_confidence"] else None
                entry["source_breakdown"] = agg_row["source_breakdown"] if agg_row["source_breakdown"] else {}
                entry["trend_direction"] = agg_row["trend_direction"]
                entry["latest_period_start"] = agg_row["period_start"].isoformat() if agg_row["period_start"] else None
                entry["latest_period_end"] = agg_row["period_end"].isoformat() if agg_row["period_end"] else None
            else:
                entry["latest_avg_sentiment"] = None
                entry["latest_signal_count"] = 0
                entry["latest_avg_confidence"] = None
                entry["source_breakdown"] = {}
                entry["trend_direction"] = None
                entry["latest_period_start"] = None
                entry["latest_period_end"] = None

            if sig_row:
                entry["latest_signal"] = {
                    "sentiment_score": float(sig_row["sentiment_score"]),
                    "confidence": float(sig_row["confidence"]),
                    "headline": sig_row["headline"],
                    "published_at": sig_row["published_at"].isoformat() if sig_row["published_at"] else None,
                    "source_type": sig_row["source_type"],
                }
            else:
                entry["latest_signal"] = None

            items.append(entry)

    return {"items": items, "total": len(items)}


@router.get("/company/{company_id}")
async def company_sentiment_detail(
    company_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    period_type: str = Query("weekly", description="'weekly' or 'monthly'"),
    months_back: int = Query(6, ge=1, le=24),
    signals_limit: int = Query(20, ge=1, le=100),
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """Detailed sentiment view for a single company.

    Returns recent signals + aggregate time-series for charting.
    """
    if period_type not in ("weekly", "monthly"):
        raise HTTPException(400, "period_type must be 'weekly' or 'monthly'")

    cutoff = date.today() - timedelta(days=months_back * 30)

    async with tenant_conn(x_tenant_id) as conn:
        # Company info
        co = await conn.fetchrow(
            """SELECT company_id, ticker, company_name, sector, sub_sector
               FROM pim_universes
               WHERE tenant_id = $1 AND company_id = $2""",
            x_tenant_id,
            company_id,
        )
        if not co:
            raise HTTPException(404, "Company not found in universe")

        # Aggregates time-series
        agg_rows = await conn.fetch(
            """SELECT company_id, period_type, period_start, period_end,
                      avg_sentiment, median_sentiment, min_sentiment, max_sentiment,
                      std_sentiment, signal_count, avg_confidence, source_breakdown,
                      trend_direction, updated_at
               FROM pim_sentiment_aggregates
               WHERE tenant_id = $1 AND company_id = $2 AND period_type = $3 AND period_start >= $4
               ORDER BY period_start ASC""",
            x_tenant_id,
            company_id,
            period_type,
            cutoff,
        )

        # Recent signals
        sig_rows = await conn.fetch(
            """SELECT signal_id, company_id, source_type, source_ref, headline,
                      published_at, sentiment_score, confidence, llm_model, created_at
               FROM pim_sentiment_signals
               WHERE tenant_id = $1 AND company_id = $2
               ORDER BY published_at DESC
               LIMIT $3""",
            x_tenant_id,
            company_id,
            signals_limit,
        )

    return {
        "company": {
            "company_id": co["company_id"],
            "ticker": co["ticker"],
            "company_name": co["company_name"],
            "sector": co["sector"],
            "sub_sector": co["sub_sector"],
        },
        "aggregates": [_aggregate_to_dict(r) for r in agg_rows],
        "recent_signals": [_signal_to_dict(r) for r in sig_rows],
    }
