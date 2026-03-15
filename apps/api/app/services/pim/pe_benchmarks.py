"""PE fund performance computation engine — PIM-6.3.

Computes DPI, TVPI, MOIC, and IRR from cash-flow schedules.

FR-7.1: PE assessment CRUD: fund name, vintage year, commitment, drawdowns, distributions.
FR-7.2: Compute DPI, TVPI, IRR per fund and per vintage year.
FR-7.3: J-curve analysis — cumulative net cash flow over time.

Cash-flow sign convention:
  - drawdown:               positive amount_usd (capital CALLED from LP)
  - distribution:           positive amount_usd (capital RETURNED to LP)
  - recallable_distribution: positive amount_usd (treated as distribution for metrics)

IRR uses Newton-Raphson NPV root-finding (CFA Level III — Modified Dietz / XIRR standard).
Monetary values use explicit rounding to 6 decimal places to avoid float drift — these are
ratio metrics (unitless), so Decimal is not required (CFA convention: ratios to 4 d.p.).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CashFlow:
    """Single PE fund cash flow event."""
    cf_date: date
    amount_usd: float    # always positive — cf_type discriminates direction
    cf_type: str         # "drawdown" | "distribution" | "recallable_distribution"

    def __post_init__(self) -> None:
        if self.amount_usd <= 0:
            raise ValueError(f"amount_usd must be positive; got {self.amount_usd}")
        if self.cf_type not in {"drawdown", "distribution", "recallable_distribution"}:
            raise ValueError(f"Invalid cf_type: {self.cf_type!r}")


@dataclass
class PeMetrics:
    """Computed PE fund performance metrics.  (PIM-6.3 / FR-7.2)"""

    paid_in_capital: float       # sum of drawdown amounts
    distributed: float           # sum of distribution amounts (incl. recallable)
    dpi: float | None            # Distributed to Paid-In = distributed / paid_in  # CFA: TVPI components
    tvpi: float | None           # Total Value to Paid-In = (distributed + nav) / paid_in
    moic: float | None           # Multiple on Invested Capital (≡ TVPI at fund level)
    irr: float | None            # Annualised IRR (Newton-Raphson, requires NAV as terminal CF)
    irr_converged: bool          # False if Newton-Raphson did not converge
    j_curve: list[dict[str, Any]] = field(default_factory=list)
    # [{period_months, cumulative_net_cf, cumulative_return}]
    limitations: str = ""


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_date(d: str | date) -> date:
    """Parse an ISO date string or return a date directly."""
    if isinstance(d, date):
        return d
    return date.fromisoformat(d)


def parse_cash_flows(raw: list[dict[str, Any]]) -> list[CashFlow]:
    """Convert raw dicts (from DB JSONB) into CashFlow objects, sorted by date."""
    cfs = [
        CashFlow(
            cf_date=_parse_date(r["date"]),
            amount_usd=float(r["amount_usd"]),
            cf_type=r["cf_type"],
        )
        for r in raw
    ]
    cfs.sort(key=lambda c: c.cf_date)
    return cfs


# ---------------------------------------------------------------------------
# DPI / TVPI / MOIC
# ---------------------------------------------------------------------------

def compute_multiples(
    cash_flows: list[CashFlow],
    nav_usd: float | None,
) -> tuple[float, float, float | None, float | None, float | None]:
    """Compute paid_in_capital, distributed, DPI, TVPI/MOIC.

    Returns (paid_in, distributed, dpi, tvpi, moic).
    Returns None for ratio metrics if paid_in == 0.

    # CFA Level III — PE performance: DPI = distributions / paid-in capital
    # CFA Level III — TVPI = (distributions + NAV) / paid-in capital
    """
    paid_in = round(sum(cf.amount_usd for cf in cash_flows if cf.cf_type == "drawdown"), 6)
    distributed = round(
        sum(
            cf.amount_usd
            for cf in cash_flows
            if cf.cf_type in ("distribution", "recallable_distribution")
        ),
        6,
    )

    if paid_in == 0:
        return paid_in, distributed, None, None, None

    dpi = round(distributed / paid_in, 6)

    nav = nav_usd if nav_usd is not None and nav_usd >= 0 else 0.0
    tvpi = round((distributed + nav) / paid_in, 6)
    moic = tvpi  # identical at fund level

    return paid_in, distributed, dpi, tvpi, moic


# ---------------------------------------------------------------------------
# IRR — Newton-Raphson XIRR
# ---------------------------------------------------------------------------

def _npv(rate: float, net_flows: list[tuple[float, float]]) -> float:
    """NPV at a given rate for [(years_from_start, net_cashflow), ...]."""
    total = 0.0
    for t, cf in net_flows:
        # Avoid overflow for extreme rates
        denom = (1.0 + rate) ** t
        if denom == 0.0:
            return float("nan")
        total += cf / denom
    return total


def _dnpv(rate: float, net_flows: list[tuple[float, float]]) -> float:
    """Derivative of NPV with respect to rate."""
    total = 0.0
    for t, cf in net_flows:
        denom = (1.0 + rate) ** (t + 1)
        if denom == 0.0:
            return float("nan")
        total -= t * cf / denom
    return total


def compute_irr(
    cash_flows: list[CashFlow],
    nav_usd: float | None,
    start_date: date | None = None,
    max_iter: int = 200,
    tol: float = 1e-9,
) -> tuple[float | None, bool]:
    """Compute IRR using Newton-Raphson.

    The sign convention for NPV roots:
      - Drawdowns are OUTFLOWS (negative) from the LP perspective
      - Distributions are INFLOWS (positive) from the LP perspective
      - NAV on the last date is treated as a terminal inflow

    Returns (irr_annualised, converged).
    Returns (None, False) when there are no flows, insufficient data, or non-convergence.

    # CFA Level III — XIRR: extends IRR to irregular cash-flow dates
    # SR-3: IRR carries inherent uncertainty — report with caution on few data points
    """
    if not cash_flows:
        return None, False

    # Need at least one drawdown and one distribution (or NAV) to compute meaningful IRR
    has_drawdown = any(cf.cf_type == "drawdown" for cf in cash_flows)
    has_return = any(cf.cf_type in ("distribution", "recallable_distribution") for cf in cash_flows)
    has_nav = nav_usd is not None and nav_usd > 0

    if not has_drawdown or (not has_return and not has_nav):
        return None, False

    origin = start_date or cash_flows[0].cf_date

    # Build signed net cash flows in years from origin
    net_flows: list[tuple[float, float]] = []
    for cf in cash_flows:
        days = (cf.cf_date - origin).days
        t = days / 365.25
        if cf.cf_type == "drawdown":
            net_flows.append((t, -cf.amount_usd))  # outflow
        else:
            net_flows.append((t, cf.amount_usd))   # inflow

    # Append NAV as terminal inflow on a synthetic future date (one year after last CF)
    if has_nav and nav_usd is not None:
        last_date = max(cf.cf_date for cf in cash_flows)
        nav_days = (last_date - origin).days + 365
        net_flows.append((nav_days / 365.25, nav_usd))

    # Newton-Raphson — start from 0.1 (10%)
    rate = 0.1
    for _ in range(max_iter):
        npv = _npv(rate, net_flows)
        if not math.isfinite(npv):
            return None, False
        d = _dnpv(rate, net_flows)
        if d == 0.0 or not math.isfinite(d):
            break
        rate_new = rate - npv / d
        if abs(rate_new - rate) < tol:
            return round(rate_new, 8), True
        rate = rate_new
        # Guard against divergence
        if abs(rate) > 100.0:
            break

    return None, False


# ---------------------------------------------------------------------------
# J-curve
# ---------------------------------------------------------------------------

def compute_j_curve(
    cash_flows: list[CashFlow],
    commitment_usd: float,
) -> list[dict[str, Any]]:
    """Build J-curve data: cumulative net return vs months from first drawdown.

    The J-curve plots the LP's net position over time. Early periods are negative
    (capital called, nothing returned yet) forming the characteristic J shape.

    # FR-7.3: J-curve analysis with graphical representation

    Returns list of {period_months, cumulative_net_cf, cumulative_return} dicts.
    cumulative_return = cumulative_net_cf / commitment_usd (can be negative).
    """
    if not cash_flows or commitment_usd <= 0:
        return []

    origin = cash_flows[0].cf_date
    points: list[dict[str, Any]] = []
    cumulative_net = 0.0

    for cf in cash_flows:
        months = round((cf.cf_date - origin).days / 30.4375, 1)
        if cf.cf_type == "drawdown":
            cumulative_net -= cf.amount_usd    # capital called is LP cost
        else:
            cumulative_net += cf.amount_usd    # distributions returned to LP

        cumulative_return = round(cumulative_net / commitment_usd, 6)
        points.append({
            "period_months": months,
            "cumulative_net_cf": round(cumulative_net, 2),
            "cumulative_return": cumulative_return,
        })

    return points


# ---------------------------------------------------------------------------
# Top-level compute function
# ---------------------------------------------------------------------------

def compute_pe_metrics(
    cash_flows_raw: list[dict[str, Any]],
    commitment_usd: float,
    nav_usd: float | None,
    start_date: date | None = None,
) -> PeMetrics:
    """Compute all PE metrics from raw cash-flow dicts.

    This is the single entry point called by the router after fetching from DB.
    Returns PeMetrics with computed DPI, TVPI, MOIC, IRR, and J-curve.

    # CFA Level III — PE performance measurement
    # SR-3: IRR is a point estimate; report with limitations
    """
    cfs = parse_cash_flows(cash_flows_raw)

    paid_in, distributed, dpi, tvpi, moic = compute_multiples(cfs, nav_usd)

    irr, irr_converged = compute_irr(cfs, nav_usd, start_date=start_date)

    j_curve = compute_j_curve(cfs, commitment_usd)

    limitations = (
        "IRR is sensitive to timing and magnitude of cash flows. "
        "TVPI includes unrealised NAV which is subject to valuation uncertainty (SR-3). "
        "Metrics require at least one drawdown and one return event for meaningful results."
    )

    return PeMetrics(
        paid_in_capital=paid_in,
        distributed=distributed,
        dpi=dpi,
        tvpi=tvpi,
        moic=moic,
        irr=irr,
        irr_converged=irr_converged,
        j_curve=j_curve,
        limitations=limitations,
    )
