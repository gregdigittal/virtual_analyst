"""PIM Markov chain endpoints — PIM-5.4.

Endpoints:
  GET  /pim/markov/states           — all 81 state labels (shared reference data)
  GET  /pim/markov/steady-state     — steady-state distribution from latest matrix
  GET  /pim/markov/top-transitions  — top transitions between the highest-probability states

All endpoints require PIM access gate (require_pim_access).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from apps.api.app.db import tenant_conn
from apps.api.app.deps import require_pim_access
from apps.api.app.services.pim.markov import N_STATES, compute_steady_state

logger = structlog.get_logger()

router = APIRouter(prefix="/pim", tags=["pim"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class MarkovStateLabel(BaseModel):
    state_index: int
    gdp_state: int
    sentiment_state: int
    quality_state: int
    momentum_state: int
    label: str


class MarkovStateLabelsResponse(BaseModel):
    items: list[MarkovStateLabel]
    total: int


class MarkovTopState(BaseModel):
    state_index: int
    label: str
    probability: float


class MarkovSteadyStateResponse(BaseModel):
    top_states: list[MarkovTopState]
    is_ergodic: bool
    quantecon_available: bool
    n_observations: int
    matrix_id: str
    limitations: str


class MarkovTransitionEdge(BaseModel):
    from_state: int
    from_label: str
    to_state: int
    to_label: str
    probability: float


class MarkovTopTransitionsResponse(BaseModel):
    edges: list[MarkovTransitionEdge]
    top_state_indices: list[int]
    limitations: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LIMITATIONS = (
    "Markov model requires ≥30 observations for reliable estimates. "
    "Steady-state assumes stationarity — regime shifts may invalidate forward projections. "
    "SR-4: Laplace smoothing (α=1.0) applied to all transition counts."
)


async def _latest_matrix(conn: Any, tenant_id: str) -> dict[str, Any] | None:
    """Return the latest matrix row for a tenant, or None if none exist."""
    row = await conn.fetchrow(
        """
        SELECT matrix_id, n_observations, is_ergodic
        FROM pim_markov_matrices
        WHERE tenant_id = $1
        ORDER BY estimated_at DESC
        LIMIT 1
        """,
        tenant_id,
    )
    return dict(row) if row else None


async def _build_matrix(conn: Any, tenant_id: str, matrix_id: str) -> np.ndarray:
    """Reconstruct the 81×81 numpy transition matrix from DB rows."""
    rows = await conn.fetch(
        """
        SELECT from_state, to_state, probability
        FROM pim_markov_transitions
        WHERE tenant_id = $1 AND matrix_id = $2
        """,
        tenant_id,
        matrix_id,
    )
    matrix = np.zeros((N_STATES, N_STATES), dtype=np.float64)
    for r in rows:
        matrix[r["from_state"]][r["to_state"]] = r["probability"]
    # Normalise rows (guard against DB rounding drift)
    row_sums = matrix.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums == 0, 1.0, row_sums)
    return matrix / row_sums


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/markov/states", response_model=MarkovStateLabelsResponse)
async def list_markov_states(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
) -> MarkovStateLabelsResponse:
    """Return all 81 Markov state labels (shared reference data, no tenant filter)."""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """
            SELECT state_index, gdp_state, sentiment_state, quality_state, momentum_state, label
            FROM pim_markov_state_labels
            ORDER BY state_index
            """
        )

    items = [
        MarkovStateLabel(
            state_index=r["state_index"],
            gdp_state=r["gdp_state"],
            sentiment_state=r["sentiment_state"],
            quality_state=r["quality_state"],
            momentum_state=r["momentum_state"],
            label=r["label"],
        )
        for r in rows
    ]
    return MarkovStateLabelsResponse(items=items, total=len(items))


@router.get("/markov/steady-state", response_model=MarkovSteadyStateResponse)
async def get_steady_state(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
) -> MarkovSteadyStateResponse:
    """Compute steady-state distribution from the tenant's latest Markov matrix."""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        meta = await _latest_matrix(conn, x_tenant_id)
        if meta is None:
            raise HTTPException(
                status_code=404,
                detail="No Markov matrix found. Run a CIS computation to build the transition matrix.",
            )

        matrix = await _build_matrix(conn, x_tenant_id, meta["matrix_id"])

    try:
        result = compute_steady_state(matrix)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return MarkovSteadyStateResponse(
        top_states=[
            MarkovTopState(
                state_index=s["state_index"],
                label=s["label"],
                probability=s["probability"],
            )
            for s in result.top_states
        ],
        is_ergodic=result.is_ergodic,
        quantecon_available=result.quantecon_available,
        n_observations=meta["n_observations"],
        matrix_id=meta["matrix_id"],
        limitations=_LIMITATIONS,
    )


@router.get("/markov/top-transitions", response_model=MarkovTopTransitionsResponse)
async def get_top_transitions(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_pim_access),
    top_n: int = 8,
) -> MarkovTopTransitionsResponse:
    """Return transitions between the top-N steady-state states for diagram rendering.

    Only includes edges with probability > 0.05 between the top-N states.
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")
    top_n = min(max(top_n, 3), 15)

    async with tenant_conn(x_tenant_id) as conn:
        meta = await _latest_matrix(conn, x_tenant_id)
        if meta is None:
            raise HTTPException(
                status_code=404,
                detail="No Markov matrix found.",
            )

        matrix = await _build_matrix(conn, x_tenant_id, meta["matrix_id"])

        # Fetch state labels for lookup
        label_rows = await conn.fetch(
            "SELECT state_index, label FROM pim_markov_state_labels ORDER BY state_index"
        )

    labels: dict[int, str] = {r["state_index"]: r["label"] for r in label_rows}

    result = compute_steady_state(matrix)
    top_indices = [s["state_index"] for s in result.top_states[:top_n]]
    top_set = set(top_indices)

    edges: list[MarkovTransitionEdge] = []
    for i in top_indices:
        for j in top_indices:
            p = float(matrix[i][j])
            if i != j and p > 0.05 and j in top_set:
                edges.append(
                    MarkovTransitionEdge(
                        from_state=i,
                        from_label=labels.get(i, str(i)),
                        to_state=j,
                        to_label=labels.get(j, str(j)),
                        probability=round(p, 4),
                    )
                )

    # Sort edges by probability descending
    edges.sort(key=lambda e: e.probability, reverse=True)

    return MarkovTopTransitionsResponse(
        edges=edges,
        top_state_indices=top_indices,
        limitations=_LIMITATIONS,
    )
