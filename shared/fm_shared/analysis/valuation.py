"""
Valuation: DCF and multiples. Used in run results when valuation_config provided.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DCFResult:
    """DCF valuation result."""

    enterprise_value: float = 0.0
    pv_explicit: float = 0.0
    pv_terminal: float = 0.0
    terminal_value: float = 0.0
    wacc: float = 0.0
    terminal_growth_rate: float | None = None
    terminal_multiple: float | None = None
    projection_periods: int = 0
    breakdown: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MultiplesResult:
    """Multiples-based implied valuation."""

    metrics_applied: dict[str, float] = field(default_factory=dict)
    implied_ev_range: tuple[float, float] = (0.0, 0.0)
    comparables: list[dict[str, Any]] = field(default_factory=list)


def dcf_valuation(
    fcf_series: list[float],
    wacc: float,
    terminal_growth_rate: float | None = None,
    terminal_multiple: float | None = None,
    projection_years: int = 5,
) -> DCFResult:
    """
    DCF: PV of explicit FCFs + PV of terminal value.
    Terminal value: perpetuity growth (FCF_last * (1+g)/(wacc-g)) or exit multiple (not used here without EBITDA).
    """
    if not fcf_series or wacc <= -1.0:
        return DCFResult(wacc=wacc)
    n = min(len(fcf_series), projection_years * 12) if projection_years else len(fcf_series)
    fcf = fcf_series[:n]
    pv_explicit = 0.0
    breakdown: list[dict[str, Any]] = []
    for t, cf in enumerate(fcf):
        pv = cf / ((1.0 + wacc) ** ((t + 1) / 12.0))
        pv_explicit += pv
        breakdown.append({"period": t, "fcf": round(cf, 2), "pv": round(pv, 2)})
    # Annualize: sum the last 12 months (or all periods if fewer than 12)
    trailing = fcf[-12:] if len(fcf) >= 12 else fcf
    fcf_annual = sum(trailing) * (12 / len(trailing)) if trailing else 0.0
    terminal_value = 0.0
    if terminal_growth_rate is not None and wacc > terminal_growth_rate:
        g = terminal_growth_rate
        terminal_value = fcf_annual * (1.0 + g) / (wacc - g)
    elif terminal_multiple is not None and terminal_multiple > 0:
        terminal_value = fcf_annual * terminal_multiple
    pv_terminal = terminal_value / ((1.0 + wacc) ** (n / 12.0)) if terminal_value else 0.0
    enterprise_value = pv_explicit + pv_terminal
    return DCFResult(
        enterprise_value=round(enterprise_value, 2),
        pv_explicit=round(pv_explicit, 2),
        pv_terminal=round(pv_terminal, 2),
        terminal_value=round(terminal_value, 2),
        wacc=wacc,
        terminal_growth_rate=terminal_growth_rate,
        terminal_multiple=terminal_multiple,
        projection_periods=n,
        breakdown=breakdown,
    )


def multiples_valuation(
    metrics: dict[str, float],
    comparables: list[dict[str, Any]],
) -> MultiplesResult:
    """
    Implied EV from median/mean of comparable multiples applied to entity metrics.
    comparables: list of { "name": str, "ev_ebitda": float?, "ev_revenue": float?, "p_e": float? }
    """
    if not comparables:
        return MultiplesResult(metrics_applied=metrics)
    ev_ebitda_vals: list[float] = []
    ev_revenue_vals: list[float] = []
    p_e_vals: list[float] = []
    for c in comparables:
        if c.get("ev_ebitda") is not None and metrics.get("ebitda"):
            ev_ebitda_vals.append(metrics["ebitda"] * c["ev_ebitda"])
        if c.get("ev_revenue") is not None and metrics.get("revenue"):
            ev_revenue_vals.append(metrics["revenue"] * c["ev_revenue"])
        if c.get("p_e") is not None and metrics.get("net_income") and metrics["net_income"] > 0:
            p_e_vals.append(metrics["net_income"] * c["p_e"])
    all_ev: list[float] = ev_ebitda_vals + ev_revenue_vals + p_e_vals
    ev_min = min(all_ev) if all_ev else 0.0
    ev_max = max(all_ev) if all_ev else 0.0
    return MultiplesResult(
        metrics_applied=metrics,
        implied_ev_range=(round(ev_min, 2), round(ev_max, 2)),
        comparables=comparables,
    )
