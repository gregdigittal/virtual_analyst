"""PIM transaction cost reporting (PIM-5.5, SR-7).

SR-7: Backtest results must report transaction cost assumptions (estimated and
actual where available) to prevent overstated returns.

Transaction costs are stored per-backtest and per-cost-type. The net return
computation subtracts total cost (n_rebalances × bps / 10_000) from the gross
backtest cumulative return.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------


VALID_COST_TYPES = ("commission", "spread", "slippage")
"""Supported cost type labels.

commission — round-trip broker commission per rebalance
spread     — bid-ask spread cost per rebalance
slippage   — market impact / execution slippage per rebalance
"""


@dataclass
class TransactionCostRecord:
    """A single transaction cost assumption for a backtest run.

    SR-7: estimated_bps represents the assumption used in cost-adjusted
    return computation. actual_bps (when provided) takes precedence.
    """

    cost_id: str
    backtest_id: str
    cost_type: str
    estimated_bps: float
    n_rebalances: int
    actual_bps: float | None = None
    description: str | None = None


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------


def compute_net_return(
    gross_return: float,
    estimated_bps: float,
    n_rebalances: int,
    actual_bps: float | None = None,
) -> float:
    """Compute net-of-cost cumulative return for a single cost type.

    SR-7: Subtracts total transaction cost from the gross backtest return.
    Actual bps (when provided) takes precedence over estimated bps.

    The cost is applied as:
        total_cost = n_rebalances × effective_bps / 10_000
        net_return = gross_return - total_cost

    Args:
        gross_return: Gross cumulative return (fractional, e.g. 0.15 = 15%).
        estimated_bps: Estimated cost per rebalance in basis points.
        n_rebalances: Number of rebalance events in the backtest.
        actual_bps: Actual cost per rebalance, if available. Overrides estimated.

    Returns:
        Net cumulative return after deducting total transaction costs.
    """
    if n_rebalances <= 0:
        return gross_return
    effective_bps = actual_bps if actual_bps is not None else estimated_bps
    total_cost = n_rebalances * effective_bps / 10_000.0
    return gross_return - total_cost


def aggregate_net_return(
    gross_return: float,
    costs: list[TransactionCostRecord],
) -> float:
    """Compute net return after deducting all cost types combined.

    SR-7: Aggregate net return = gross_return − Σ(all cost deductions).
    """
    net = gross_return
    for cost in costs:
        net = compute_net_return(
            gross_return=net,
            estimated_bps=cost.estimated_bps,
            n_rebalances=cost.n_rebalances,
            actual_bps=cost.actual_bps,
        )
    return net


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def row_to_cost(row: Any) -> dict[str, Any]:
    """Convert a DB row to a transaction cost response dict."""
    return {
        "cost_id": row["cost_id"],
        "backtest_id": row["backtest_id"],
        "cost_type": row["cost_type"],
        "estimated_bps": float(row["estimated_bps"]),
        "actual_bps": float(row["actual_bps"]) if row["actual_bps"] is not None else None,
        "n_rebalances": row["n_rebalances"],
        "description": row["description"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }
