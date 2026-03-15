"""PIM backtest endpoints.

PIM-4.7: POST /pim/backtest/run    — walk-forward backtest from historical CIS records
PIM-4.8: IC/ICIR included in every result

GET  /pim/backtest/results         — list recent backtest runs
GET  /pim/backtest/{backtest_id}   — fetch a specific backtest with periods

All endpoints require PIM access gate (check_pim_access).
"""

from __future__ import annotations

import json as _json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_llm_router, require_pim_access, require_role
from apps.api.app.services.llm.router import LLMRouter
from apps.api.app.services.pim.backtester import (
    BacktestConfig,
    HistoricalCISRecord,
    generate_backtest_commentary,
    persist_backtest,
    run_backtest,
)
from apps.api.app.services.pim.transaction_costs import VALID_COST_TYPES, row_to_cost
from shared.fm_shared.errors import LLMError

logger = structlog.get_logger()

router = APIRouter(prefix="/pim/backtest", tags=["pim"])

_ANALYST_ROLES = ("owner", "admin", "analyst")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class BacktestConfigInput(BaseModel):
    lookback_days: int = Field(default=252, ge=1, le=3650)
    rebalance_freq_days: int = Field(default=21, ge=1, le=365)
    top_n: int = Field(default=10, ge=1, le=200)
    max_weight_pct: float = Field(default=0.15, gt=0.0, le=1.0)
    max_sector_pct: float = Field(default=0.35, gt=0.0, le=1.0)
    benchmark_label: str = Field(default="equal_weight", max_length=64)
    strategy_label: str = Field(default="top_n_cis", max_length=64)


class CISRecordInput(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="ISO date: YYYY-MM-DD")
    company_id: str
    cis_score: float = Field(..., ge=0.0, le=100.0)
    sector: str | None = None
    realised_return: float | None = Field(
        default=None,
        description="Fractional period return realised after this date (e.g. 0.02 = 2%). "
                    "None if not yet available.",
    )


class RunBacktestBody(BaseModel):
    records: list[CISRecordInput] = Field(
        ...,
        min_length=2,
        max_length=10000,
        description="Historical CIS observations. Must span at least 2 distinct dates.",
    )
    config: BacktestConfigInput = Field(default_factory=BacktestConfigInput)


class TransactionCostInput(BaseModel):
    cost_type: str = Field(
        ...,
        description="Cost category: 'commission', 'spread', or 'slippage'.",
    )
    estimated_bps: float = Field(
        ..., ge=0.0, le=500.0,
        description="Estimated per-rebalance cost in basis points (max 500 bps = 5%).",
    )
    n_rebalances: int = Field(
        ..., ge=0,
        description="Number of rebalance events this cost applies to.",
    )
    actual_bps: float | None = Field(
        default=None, ge=0.0, le=500.0,
        description="Actual per-rebalance cost in basis points, if known. "
                    "Overrides estimated_bps in net-return calculations.",
    )
    description: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/run", status_code=201)
async def run_backtest_endpoint(
    body: RunBacktestBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = require_role(*_ANALYST_ROLES),  # noqa: B008
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """Run a walk-forward backtest and persist the results.

    PIM-4.7: Walk-forward loop with configurable lookback and rebalance frequency.
    PIM-4.8: IC and ICIR computed per period; aggregate IC metrics in response.

    Each record's realised_return is the period return earned between that date
    and the next rebalance date. No look-ahead bias — selection uses only CIS
    scores available at the rebalance date.
    """
    try:
        config = BacktestConfig(
            lookback_days=body.config.lookback_days,
            rebalance_freq_days=body.config.rebalance_freq_days,
            top_n=body.config.top_n,
            max_weight_pct=body.config.max_weight_pct,
            max_sector_pct=body.config.max_sector_pct,
            benchmark_label=body.config.benchmark_label,
            strategy_label=body.config.strategy_label,
        )
    except ValueError as e:
        raise HTTPException(400, f"Invalid backtest config: {e}") from e

    records = [
        HistoricalCISRecord(
            date=r.date,
            company_id=r.company_id,
            cis_score=r.cis_score,
            sector=r.sector,
            realised_return=r.realised_return,
        )
        for r in body.records
    ]

    result = run_backtest(records, config, tenant_id=x_tenant_id)

    async with tenant_conn(x_tenant_id) as conn:
        await persist_backtest(result, conn)

    logger.info(
        "backtest_run_complete",
        tenant_id=x_tenant_id,
        backtest_id=result.backtest_id,
        n_periods=result.n_periods,
        strategy=config.strategy_label,
    )

    return _result_to_dict(result)


@router.get("/summary")
async def get_backtest_summary(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = require_role(*_ANALYST_ROLES),  # noqa: B008
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """Return aggregated backtest performance per strategy from the materialised view.

    PIM-5.3, P-06: Reads from pim_backtest_summary_mv (refreshed every 30 min
    by the refresh_pim_backtest_summary_mv Celery task).
    Data may be up to 30 minutes stale — this is documented in the response.
    """
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT strategy_label, run_count, latest_run_at,
                      avg_cumulative_return, avg_annualised_return, avg_sharpe_ratio,
                      avg_max_drawdown, avg_ic_mean, avg_ic_std, avg_icir,
                      best_cumulative_return, worst_cumulative_return
               FROM pim_backtest_summary_mv
               WHERE tenant_id = $1
               ORDER BY avg_icir DESC NULLS LAST""",
            x_tenant_id,
        )
    items = [
        {
            "strategy_label": r["strategy_label"],
            "run_count": r["run_count"],
            "latest_run_at": r["latest_run_at"].isoformat() if r["latest_run_at"] else None,
            "avg_cumulative_return": _f(r["avg_cumulative_return"]),
            "avg_annualised_return": _f(r["avg_annualised_return"]),
            "avg_sharpe_ratio": _f(r["avg_sharpe_ratio"]),
            "avg_max_drawdown": _f(r["avg_max_drawdown"]),
            "avg_ic_mean": _f(r["avg_ic_mean"]),
            "avg_ic_std": _f(r["avg_ic_std"]),
            "avg_icir": _f(r["avg_icir"]),
            "best_cumulative_return": _f(r["best_cumulative_return"]),
            "worst_cumulative_return": _f(r["worst_cumulative_return"]),
        }
        for r in rows
    ]
    return {
        "items": items,
        "total": len(items),
        "note": "Data from pim_backtest_summary_mv — refreshed every 30 minutes.",
    }


@router.get("/results")
async def list_backtest_results(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    strategy_label: str | None = Query(default=None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: None = require_role(*_ANALYST_ROLES),  # noqa: B008
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """List recent backtest results for this tenant, optionally filtered by strategy."""
    async with tenant_conn(x_tenant_id) as conn:
        if strategy_label:
            rows = await conn.fetch(
                """SELECT backtest_id, run_at, strategy_label, n_periods,
                          cumulative_return, annualised_return, sharpe_ratio,
                          max_drawdown, ic_mean, icir, benchmark_label,
                          benchmark_cumulative_return
                   FROM pim_backtest_results
                   WHERE tenant_id = $1 AND strategy_label = $2
                   ORDER BY run_at DESC
                   LIMIT $3 OFFSET $4""",
                x_tenant_id,
                strategy_label,
                limit,
                offset,
            )
            total = await conn.fetchval(
                "SELECT count(*) FROM pim_backtest_results WHERE tenant_id = $1 AND strategy_label = $2",
                x_tenant_id,
                strategy_label,
            )
        else:
            rows = await conn.fetch(
                """SELECT backtest_id, run_at, strategy_label, n_periods,
                          cumulative_return, annualised_return, sharpe_ratio,
                          max_drawdown, ic_mean, icir, benchmark_label,
                          benchmark_cumulative_return
                   FROM pim_backtest_results
                   WHERE tenant_id = $1
                   ORDER BY run_at DESC
                   LIMIT $2 OFFSET $3""",
                x_tenant_id,
                limit,
                offset,
            )
            total = await conn.fetchval(
                "SELECT count(*) FROM pim_backtest_results WHERE tenant_id = $1",
                x_tenant_id,
            )

    return {
        "items": [_row_to_summary(r) for r in rows],
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{backtest_id}")
async def get_backtest_result(
    backtest_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = require_role(*_ANALYST_ROLES),  # noqa: B008
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """Fetch a specific backtest result including per-period breakdown."""
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT backtest_id, run_at, strategy_label, config_json,
                      start_date, end_date, n_periods,
                      cumulative_return, annualised_return, volatility,
                      sharpe_ratio, max_drawdown,
                      ic_mean, ic_std, icir,
                      benchmark_label, benchmark_cumulative_return, benchmark_annualised_return,
                      periods_json
               FROM pim_backtest_results
               WHERE tenant_id = $1 AND backtest_id = $2""",
            x_tenant_id,
            backtest_id,
        )
    if not row:
        raise HTTPException(404, f"Backtest '{backtest_id}' not found")

    config_raw = row["config_json"]
    config_dict = _parse_jsonb(config_raw)
    periods_raw = row["periods_json"]
    periods_list = _parse_jsonb(periods_raw) if periods_raw else []

    return {
        "backtest_id": row["backtest_id"],
        "run_at": row["run_at"].isoformat() if row["run_at"] else None,
        "strategy_label": row["strategy_label"],
        "config": config_dict,
        "start_date": row["start_date"].isoformat() if row["start_date"] else None,
        "end_date": row["end_date"].isoformat() if row["end_date"] else None,
        "n_periods": row["n_periods"],
        "performance": {
            "cumulative_return": _f(row["cumulative_return"]),
            "annualised_return": _f(row["annualised_return"]),
            "volatility": _f(row["volatility"]),
            "sharpe_ratio": _f(row["sharpe_ratio"]),
            "max_drawdown": _f(row["max_drawdown"]),
        },
        "signal_quality": {
            "ic_mean": _f(row["ic_mean"]),
            "ic_std": _f(row["ic_std"]),
            "icir": _f(row["icir"]),
        },
        "benchmark": {
            "label": row["benchmark_label"],
            "cumulative_return": _f(row["benchmark_cumulative_return"]),
            "annualised_return": _f(row["benchmark_annualised_return"]),
        },
        "periods": periods_list,
        "limitations": (
            "Backtest results are simulated. Past model performance does not predict future returns."
        ),
    }


@router.get("/{backtest_id}/commentary")
async def get_backtest_commentary(
    backtest_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    llm: LLMRouter = Depends(get_llm_router),  # noqa: B008
    _: None = require_role(*_ANALYST_ROLES),  # noqa: B008
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """Return LLM commentary for a completed backtest run.

    PIM-5.2: If commentary has already been generated and stored, return it
    from the DB (cache hit). Otherwise generate via LLM, persist, then return.

    LLM failure is non-fatal: raises HTTP 503 with a clear message rather
    than crashing — the backtest data itself is unaffected.
    """
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT backtest_id, strategy_label, n_periods,
                      cumulative_return, annualised_return, sharpe_ratio,
                      max_drawdown, ic_mean, ic_std, icir,
                      benchmark_label, benchmark_cumulative_return,
                      commentary, commentary_risks
               FROM pim_backtest_results
               WHERE tenant_id = $1 AND backtest_id = $2""",
            x_tenant_id,
            backtest_id,
        )
        if not row:
            raise HTTPException(404, f"Backtest '{backtest_id}' not found")

        commentary = row["commentary"]
        commentary_risks = row["commentary_risks"]

        if not commentary:
            # Generate and persist
            try:
                commentary, commentary_risks = await generate_backtest_commentary(
                    backtest_id=backtest_id,
                    tenant_id=x_tenant_id,
                    n_periods=row["n_periods"],
                    cumulative_return=_f(row["cumulative_return"]),
                    annualised_return=_f(row["annualised_return"]),
                    sharpe_ratio=_f(row["sharpe_ratio"]),
                    max_drawdown=_f(row["max_drawdown"]),
                    ic_mean=_f(row["ic_mean"]),
                    icir=_f(row["icir"]),
                    strategy_label=row["strategy_label"],
                    benchmark_label=row["benchmark_label"],
                    benchmark_cumulative_return=_f(row["benchmark_cumulative_return"]),
                    llm_router=llm,
                )
            except LLMError as exc:
                raise HTTPException(
                    503,
                    f"Commentary generation failed: {exc.message}",
                ) from exc

            await conn.execute(
                """UPDATE pim_backtest_results
                   SET commentary = $1, commentary_risks = $2
                   WHERE tenant_id = $3 AND backtest_id = $4""",
                commentary,
                commentary_risks,
                x_tenant_id,
                backtest_id,
            )
            logger.info(
                "backtest_commentary_generated",
                tenant_id=x_tenant_id,
                backtest_id=backtest_id,
            )

    return {
        "backtest_id": backtest_id,
        "commentary": commentary,
        "commentary_risks": commentary_risks,
        "limitations": (
            "Backtest results are simulated. Past model performance does not predict future returns. "
            "LLM commentary is generated from quantitative metrics and does not constitute investment advice."
        ),
    }


@router.post("/{backtest_id}/costs", status_code=201)
async def add_transaction_cost(
    backtest_id: str,
    body: TransactionCostInput,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = require_role(*_ANALYST_ROLES),  # noqa: B008
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """Record a transaction cost assumption for a backtest run.

    PIM-5.5, SR-7: Supports commission, spread, and slippage cost types.
    Multiple cost records can be attached to one backtest_id.
    """
    if body.cost_type not in VALID_COST_TYPES:
        raise HTTPException(
            422,
            f"Invalid cost_type '{body.cost_type}'. "
            f"Must be one of: {', '.join(VALID_COST_TYPES)}.",
        )

    async with tenant_conn(x_tenant_id) as conn:
        exists = await conn.fetchrow(
            "SELECT backtest_id FROM pim_backtest_results WHERE tenant_id = $1 AND backtest_id = $2",
            x_tenant_id,
            backtest_id,
        )
        if not exists:
            raise HTTPException(404, f"Backtest '{backtest_id}' not found")

        row = await conn.fetchrow(
            """INSERT INTO pim_transaction_costs
                   (tenant_id, backtest_id, cost_type, estimated_bps, actual_bps, n_rebalances, description)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               RETURNING cost_id, backtest_id, cost_type, estimated_bps, actual_bps,
                         n_rebalances, description, created_at""",
            x_tenant_id,
            backtest_id,
            body.cost_type,
            body.estimated_bps,
            body.actual_bps,
            body.n_rebalances,
            body.description,
        )

    logger.info(
        "transaction_cost_added",
        tenant_id=x_tenant_id,
        backtest_id=backtest_id,
        cost_type=body.cost_type,
    )
    return row_to_cost(row)


@router.get("/{backtest_id}/costs")
async def list_transaction_costs(
    backtest_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = require_role(*_ANALYST_ROLES),  # noqa: B008
    _pim: None = Depends(require_pim_access),  # noqa: B008
) -> dict[str, Any]:
    """List all transaction cost records for a backtest run.

    PIM-5.5, SR-7: Returns costs ordered by created_at so callers can
    compute aggregate net-of-cost returns.
    """
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT cost_id, backtest_id, cost_type, estimated_bps, actual_bps,
                      n_rebalances, description, created_at
               FROM pim_transaction_costs
               WHERE tenant_id = $1 AND backtest_id = $2
               ORDER BY created_at ASC""",
            x_tenant_id,
            backtest_id,
        )
    return {
        "backtest_id": backtest_id,
        "items": [row_to_cost(r) for r in rows],
        "total": len(rows),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _f(val: Any) -> float | None:
    return float(val) if val is not None else None


def _parse_jsonb(val: Any) -> Any:
    if isinstance(val, str):
        return _json.loads(val)
    return val


def _row_to_summary(row: Any) -> dict[str, Any]:
    return {
        "backtest_id": row["backtest_id"],
        "run_at": row["run_at"].isoformat() if row["run_at"] else None,
        "strategy_label": row["strategy_label"],
        "n_periods": row["n_periods"],
        "cumulative_return": _f(row["cumulative_return"]),
        "annualised_return": _f(row["annualised_return"]),
        "sharpe_ratio": _f(row["sharpe_ratio"]),
        "max_drawdown": _f(row["max_drawdown"]),
        "ic_mean": _f(row["ic_mean"]),
        "icir": _f(row["icir"]),
        "benchmark_label": row["benchmark_label"],
        "benchmark_cumulative_return": _f(row["benchmark_cumulative_return"]),
    }


def _result_to_dict(result: Any) -> dict[str, Any]:
    return {
        "backtest_id": result.backtest_id,
        "strategy_label": result.config.strategy_label,
        "n_periods": result.n_periods,
        "performance": {
            "cumulative_return": result.cumulative_return,
            "annualised_return": result.annualised_return,
            "volatility": result.volatility,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
        },
        "signal_quality": {
            "ic_mean": result.ic_mean,
            "ic_std": result.ic_std,
            "icir": result.icir,
        },
        "benchmark": {
            "label": result.config.benchmark_label,
            "cumulative_return": result.benchmark_cumulative_return,
            "annualised_return": result.benchmark_annualised_return,
        },
        "periods": [
            {
                "period_index": p.period_index,
                "rebalance_date": p.rebalance_date,
                "n_candidates": p.n_candidates,
                "n_holdings": p.n_holdings,
                "strategy_return": p.strategy_return,
                "benchmark_return": p.benchmark_return,
                "ic": p.ic,
            }
            for p in result.periods
        ],
        "limitations": result.limitations,
    }
