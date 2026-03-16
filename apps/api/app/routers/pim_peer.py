"""PIM-7.1: Peer comparison percentile ranking endpoints.

Endpoints:
  POST   /pim/peer/benchmarks                          — upload / upsert benchmark cohort data
  GET    /pim/peer/benchmarks                          — list available cohorts for tenant
  DELETE /pim/peer/benchmarks/{benchmark_id}           — remove a cohort record
  GET    /pim/peer/assessments/{assessment_id}/rank    — rank a PE assessment against its cohort

All endpoints require PIM access gate (require_pim_access).

Percentile rank formula:
  For a metric m in a cohort with known quartile boundaries (p25, p50, p75):
    - Interpolate linearly between {0, p25, p50, p75, 100th} quantile anchors.
    - Returns {metric, value, p25, p50, p75, percentile_rank, quartile_label}.

CFA Level III — Benchmarking PE funds: use pooled IRR or horizon IRR vs public market
equivalent (PME), reporting quartile rank within a vintage-year cohort (Cambridge Associates).
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.deps import require_pim_access

logger = structlog.get_logger()

router = APIRouter(prefix="/pim", tags=["pim"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

_VALID_STRATEGIES = frozenset(
    {"buyout", "venture", "growth", "real_assets", "credit"}
)
_VALID_GEOGRAPHIES = frozenset(
    {"north_america", "europe", "asia_pacific", "global"}
)

QUARTILE_LABELS = {1: "Top Quartile", 2: "Second Quartile", 3: "Third Quartile", 4: "Bottom Quartile"}


class CreatePeerBenchmarkBody(BaseModel):
    vintage_year: int = Field(..., ge=1980, le=2100)
    strategy: str = Field("buyout")
    geography: str = Field("global")

    dpi_p25: float | None = None
    dpi_p50: float | None = None
    dpi_p75: float | None = None

    tvpi_p25: float | None = None
    tvpi_p50: float | None = None
    tvpi_p75: float | None = None

    irr_p25: float | None = None
    irr_p50: float | None = None
    irr_p75: float | None = None

    fund_count: int | None = None
    data_source: str | None = None
    as_of_date: str | None = None  # ISO date

    def model_post_init(self, __context: Any) -> None:
        if self.strategy not in _VALID_STRATEGIES:
            raise ValueError(f"strategy must be one of {sorted(_VALID_STRATEGIES)}")
        if self.geography not in _VALID_GEOGRAPHIES:
            raise ValueError(f"geography must be one of {sorted(_VALID_GEOGRAPHIES)}")


class PeerBenchmark(BaseModel):
    benchmark_id: str
    tenant_id: str
    vintage_year: int
    strategy: str
    geography: str
    dpi_p25: float | None
    dpi_p50: float | None
    dpi_p75: float | None
    tvpi_p25: float | None
    tvpi_p50: float | None
    tvpi_p75: float | None
    irr_p25: float | None
    irr_p50: float | None
    irr_p75: float | None
    fund_count: int | None
    data_source: str | None
    as_of_date: str | None
    created_at: str | None
    updated_at: str | None


class PeerBenchmarksResponse(BaseModel):
    items: list[PeerBenchmark]
    total: int
    limit: int
    offset: int


class MetricRank(BaseModel):
    metric: str           # "dpi" | "tvpi" | "irr"
    value: float | None   # the fund's computed value for this metric
    p25: float | None
    p50: float | None
    p75: float | None
    percentile_rank: float | None   # 0–100; None if insufficient benchmark data
    quartile: int | None            # 1 (top) through 4 (bottom); None if rank unavailable
    quartile_label: str | None


class PeerRankResponse(BaseModel):
    assessment_id: str
    vintage_year: int
    strategy: str
    geography: str
    benchmark_id: str | None          # None if no matching cohort found
    fund_count: int | None
    data_source: str | None
    rankings: list[MetricRank]
    warning: str | None               # populated if benchmark data is missing / stale


# ---------------------------------------------------------------------------
# Pure computation helpers
# ---------------------------------------------------------------------------

def _percentile_rank(value: float, p25: float, p50: float, p75: float) -> float:
    """Linear interpolation percentile rank (0–100) from quartile anchors.

    Anchors: 0 → 0th percentile (assumed 0 or half of p25),
             p25 → 25th, p50 → 50th, p75 → 75th, +∞ → 99th.

    # CFA Level III — Percentile rank: (number of values below x + 0.5) / n × 100
    # Here we approximate from three quartile boundaries.
    """
    if value <= p25:
        # Below p25 → 0–25th percentile, anchor at 0 assumes minimum ≈ 0
        lo_val, lo_pct = 0.0, 0.0
        hi_val, hi_pct = p25, 25.0
    elif value <= p50:
        lo_val, lo_pct = p25, 25.0
        hi_val, hi_pct = p50, 50.0
    elif value <= p75:
        lo_val, lo_pct = p50, 50.0
        hi_val, hi_pct = p75, 75.0
    else:
        # Above p75 → 75–99th; cap at 99 to avoid claiming 100th
        lo_val, lo_pct = p75, 75.0
        hi_val, hi_pct = p75 * 2.0 if p75 > 0 else 1.0, 99.0

    span_val = hi_val - lo_val
    if span_val == 0:
        return lo_pct
    frac = (value - lo_val) / span_val
    rank = lo_pct + frac * (hi_pct - lo_pct)
    return round(min(max(rank, 0.0), 99.0), 1)


def _quartile(rank: float) -> int:
    """Convert percentile rank to quartile (1 = top, 4 = bottom).

    PE convention: higher DPI/TVPI/IRR is better, so top quartile = rank ≥ 75.
    """
    if rank >= 75:
        return 1
    if rank >= 50:
        return 2
    if rank >= 25:
        return 3
    return 4


def _rank_metric(
    metric_name: str,
    fund_value: float | None,
    p25: float | None,
    p50: float | None,
    p75: float | None,
) -> MetricRank:
    """Build a MetricRank for a single metric."""
    pct_rank: float | None = None
    quartile: int | None = None
    quartile_label: str | None = None

    if fund_value is not None and p25 is not None and p50 is not None and p75 is not None:
        pct_rank = _percentile_rank(fund_value, p25, p50, p75)
        quartile = _quartile(pct_rank)
        quartile_label = QUARTILE_LABELS.get(quartile)

    return MetricRank(
        metric=metric_name,
        value=fund_value,
        p25=p25,
        p50=p50,
        p75=p75,
        percentile_rank=pct_rank,
        quartile=quartile,
        quartile_label=quartile_label,
    )


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------

def _row_to_benchmark(row: Any) -> PeerBenchmark:
    return PeerBenchmark(
        benchmark_id=str(row["benchmark_id"]),
        tenant_id=str(row["tenant_id"]),
        vintage_year=row["vintage_year"],
        strategy=row["strategy"],
        geography=row["geography"],
        dpi_p25=float(row["dpi_p25"]) if row["dpi_p25"] is not None else None,
        dpi_p50=float(row["dpi_p50"]) if row["dpi_p50"] is not None else None,
        dpi_p75=float(row["dpi_p75"]) if row["dpi_p75"] is not None else None,
        tvpi_p25=float(row["tvpi_p25"]) if row["tvpi_p25"] is not None else None,
        tvpi_p50=float(row["tvpi_p50"]) if row["tvpi_p50"] is not None else None,
        tvpi_p75=float(row["tvpi_p75"]) if row["tvpi_p75"] is not None else None,
        irr_p25=float(row["irr_p25"]) if row["irr_p25"] is not None else None,
        irr_p50=float(row["irr_p50"]) if row["irr_p50"] is not None else None,
        irr_p75=float(row["irr_p75"]) if row["irr_p75"] is not None else None,
        fund_count=row["fund_count"],
        data_source=row["data_source"],
        as_of_date=str(row["as_of_date"]) if row["as_of_date"] else None,
        created_at=str(row["created_at"]) if row["created_at"] else None,
        updated_at=str(row["updated_at"]) if row["updated_at"] else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/peer/benchmarks", response_model=PeerBenchmark, status_code=201)
async def create_peer_benchmark(
    body: CreatePeerBenchmarkBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
) -> PeerBenchmark:
    """Upload a peer benchmark cohort (quartile data for a vintage/strategy/geography).

    Use this to load Cambridge Associates or Preqin benchmark tables for percentile ranking.
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO pim_peer_benchmarks (
                tenant_id, vintage_year, strategy, geography,
                dpi_p25, dpi_p50, dpi_p75,
                tvpi_p25, tvpi_p50, tvpi_p75,
                irr_p25, irr_p50, irr_p75,
                fund_count, data_source, as_of_date
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16::date)
            RETURNING *
            """,
            x_tenant_id,
            body.vintage_year,
            body.strategy,
            body.geography,
            body.dpi_p25, body.dpi_p50, body.dpi_p75,
            body.tvpi_p25, body.tvpi_p50, body.tvpi_p75,
            body.irr_p25, body.irr_p50, body.irr_p75,
            body.fund_count,
            body.data_source,
            body.as_of_date,
        )

    if row is None:
        raise HTTPException(status_code=500, detail="Failed to create benchmark")
    return _row_to_benchmark(row)


@router.get("/peer/benchmarks", response_model=PeerBenchmarksResponse)
async def list_peer_benchmarks(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    vintage_year: int | None = Query(None),
    strategy: str | None = Query(None),
) -> PeerBenchmarksResponse:
    """List peer benchmark cohorts available for the tenant."""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        if vintage_year is not None and strategy is not None:
            count_row = await conn.fetchrow(
                "SELECT count(*) AS n FROM pim_peer_benchmarks WHERE tenant_id=$1 AND vintage_year=$2 AND strategy=$3",
                x_tenant_id, vintage_year, strategy,
            )
            rows = await conn.fetch(
                "SELECT * FROM pim_peer_benchmarks WHERE tenant_id=$1 AND vintage_year=$2 AND strategy=$3 ORDER BY vintage_year DESC LIMIT $4 OFFSET $5",
                x_tenant_id, vintage_year, strategy, limit, offset,
            )
        elif vintage_year is not None:
            count_row = await conn.fetchrow(
                "SELECT count(*) AS n FROM pim_peer_benchmarks WHERE tenant_id=$1 AND vintage_year=$2",
                x_tenant_id, vintage_year,
            )
            rows = await conn.fetch(
                "SELECT * FROM pim_peer_benchmarks WHERE tenant_id=$1 AND vintage_year=$2 ORDER BY vintage_year DESC LIMIT $3 OFFSET $4",
                x_tenant_id, vintage_year, limit, offset,
            )
        else:
            count_row = await conn.fetchrow(
                "SELECT count(*) AS n FROM pim_peer_benchmarks WHERE tenant_id=$1",
                x_tenant_id,
            )
            rows = await conn.fetch(
                "SELECT * FROM pim_peer_benchmarks WHERE tenant_id=$1 ORDER BY vintage_year DESC, strategy LIMIT $2 OFFSET $3",
                x_tenant_id, limit, offset,
            )

    total = int(count_row["n"]) if count_row else 0
    return PeerBenchmarksResponse(
        items=[_row_to_benchmark(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/peer/benchmarks/{benchmark_id}", response_model=dict)
async def delete_peer_benchmark(
    benchmark_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
) -> dict[str, bool]:
    """Delete a peer benchmark cohort record."""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            "DELETE FROM pim_peer_benchmarks WHERE tenant_id=$1 AND benchmark_id=$2",
            x_tenant_id, benchmark_id,
        )

    if result != "DELETE 1":
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return {"deleted": True}


@router.get("/peer/assessments/{assessment_id}/rank", response_model=PeerRankResponse)
async def rank_pe_assessment(
    assessment_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
    strategy: str = Query("buyout"),
    geography: str = Query("global"),
) -> PeerRankResponse:
    """Rank a PE assessment's DPI/TVPI/IRR against the closest peer cohort.

    Finds the benchmark cohort matching vintage_year + strategy + geography.
    Falls back to any geography if no exact match for the requested geography.
    Returns quartile labels and percentile ranks for each available metric.

    # CFA Level III — PE benchmarking: vintage-year cohort comparison,
    # quartile rank as primary reporting metric (Cambridge Associates convention).
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        # Fetch the assessment
        assessment = await conn.fetchrow(
            """
            SELECT assessment_id, vintage_year, dpi, tvpi, irr
            FROM pim_pe_assessments
            WHERE tenant_id = $1 AND assessment_id = $2
            """,
            x_tenant_id, assessment_id,
        )
        if assessment is None:
            raise HTTPException(status_code=404, detail="PE assessment not found")

        vintage_year = assessment["vintage_year"]

        # Find exact match (vintage + strategy + geography)
        benchmark = await conn.fetchrow(
            """
            SELECT * FROM pim_peer_benchmarks
            WHERE tenant_id=$1 AND vintage_year=$2 AND strategy=$3 AND geography=$4
            ORDER BY as_of_date DESC NULLS LAST
            LIMIT 1
            """,
            x_tenant_id, vintage_year, strategy, geography,
        )

        # Fall back to any geography for this vintage + strategy
        if benchmark is None:
            benchmark = await conn.fetchrow(
                """
                SELECT * FROM pim_peer_benchmarks
                WHERE tenant_id=$1 AND vintage_year=$2 AND strategy=$3
                ORDER BY as_of_date DESC NULLS LAST
                LIMIT 1
                """,
                x_tenant_id, vintage_year, strategy,
            )

    fund_dpi = float(assessment["dpi"]) if assessment["dpi"] is not None else None
    fund_tvpi = float(assessment["tvpi"]) if assessment["tvpi"] is not None else None
    fund_irr = float(assessment["irr"]) if assessment["irr"] is not None else None

    warning: str | None = None
    benchmark_id: str | None = None
    fund_count: int | None = None
    data_source: str | None = None

    rankings: list[MetricRank]

    if benchmark is None:
        warning = f"No benchmark cohort found for vintage {vintage_year} / {strategy} / {geography}. Upload benchmark data via POST /pim/peer/benchmarks."
        rankings = [
            _rank_metric("dpi", fund_dpi, None, None, None),
            _rank_metric("tvpi", fund_tvpi, None, None, None),
            _rank_metric("irr", fund_irr, None, None, None),
        ]
    else:
        benchmark_id = str(benchmark["benchmark_id"])
        fund_count = benchmark["fund_count"]
        data_source = benchmark["data_source"]

        rankings = [
            _rank_metric(
                "dpi", fund_dpi,
                float(benchmark["dpi_p25"]) if benchmark["dpi_p25"] is not None else None,
                float(benchmark["dpi_p50"]) if benchmark["dpi_p50"] is not None else None,
                float(benchmark["dpi_p75"]) if benchmark["dpi_p75"] is not None else None,
            ),
            _rank_metric(
                "tvpi", fund_tvpi,
                float(benchmark["tvpi_p25"]) if benchmark["tvpi_p25"] is not None else None,
                float(benchmark["tvpi_p50"]) if benchmark["tvpi_p50"] is not None else None,
                float(benchmark["tvpi_p75"]) if benchmark["tvpi_p75"] is not None else None,
            ),
            _rank_metric(
                "irr", fund_irr,
                float(benchmark["irr_p25"]) if benchmark["irr_p25"] is not None else None,
                float(benchmark["irr_p50"]) if benchmark["irr_p50"] is not None else None,
                float(benchmark["irr_p75"]) if benchmark["irr_p75"] is not None else None,
            ),
        ]

    logger.info(
        "pe_peer_rank",
        tenant_id=x_tenant_id,
        assessment_id=assessment_id,
        vintage_year=vintage_year,
        strategy=strategy,
        benchmark_found=benchmark is not None,
    )

    return PeerRankResponse(
        assessment_id=assessment_id,
        vintage_year=vintage_year,
        strategy=strategy,
        geography=geography,
        benchmark_id=benchmark_id,
        fund_count=fund_count,
        data_source=data_source,
        rankings=rankings,
        warning=warning,
    )
