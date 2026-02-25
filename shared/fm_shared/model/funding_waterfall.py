"""
Funding waterfall: cover cash shortfalls with cash-plug facilities (revolver, overdraft).
Draw order: revolver first, overdraft last. Repay in reverse order when surplus.
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.fm_shared.model.schemas import DebtFacility

# Draw order: revolver first, trade_finance, then term_loan, then overdraft last
_TYPE_ORDER = {"revolver": 0, "trade_finance": 1, "term_loan": 2, "overdraft": 3}


def _sort_draw_order(facilities: list[DebtFacility]) -> list[DebtFacility]:
    return sorted(facilities, key=lambda f: _TYPE_ORDER.get(f.type, 1))


def _sort_repay_order(facilities: list[DebtFacility]) -> list[DebtFacility]:
    return sorted(facilities, key=lambda f: -_TYPE_ORDER.get(f.type, 1))


@dataclass
class WaterfallResult:
    cash_after_funding: list[float]
    additional_draws: dict[str, list[float]]  # facility_id -> extra draws per period
    overdraft_interest: list[float]
    waterfall_interest: list[float]  # total interest on all plug-facility balances
    waterfall_debt_per_period: list[float]  # total plug-facility balance each period


def empty_waterfall_result(horizon: int) -> WaterfallResult:
    return WaterfallResult(
        cash_after_funding=[0.0] * horizon,
        additional_draws={},
        overdraft_interest=[0.0] * horizon,
        waterfall_interest=[0.0] * horizon,
        waterfall_debt_per_period=[0.0] * horizon,
    )


def apply_funding_waterfall(
    closing_cash: list[float],
    facilities: list[DebtFacility],
    minimum_cash: float,
    horizon: int,
    asset_values: dict[str, list[float]] | None = None,
) -> WaterfallResult:
    """
    Cover shortfalls by drawing from facilities (revolver first, overdraft last).
    When cash exceeds minimum, repay facilities in reverse order.
    """
    result = empty_waterfall_result(horizon)
    if not facilities:
        result.cash_after_funding = list(closing_cash)
        return result

    draw_order = _sort_draw_order(facilities)
    repay_order = _sort_repay_order(facilities)
    for f in facilities:
        result.additional_draws[f.facility_id] = [0.0] * horizon

    balance: dict[str, float] = {f.facility_id: 0.0 for f in facilities}

    for t in range(horizon):
        cash_t = closing_cash[t]
        total_draws_t = 0.0
        total_repays_t = 0.0

        if cash_t < minimum_cash:
            shortfall = minimum_cash - cash_t
            for fac in draw_order:
                effective_limit = fac.limit
                if fac.asset_linked and asset_values:
                    asset_bal = asset_values.get(fac.asset_linked, [0.0] * horizon)
                    effective_limit = min(fac.limit, asset_bal[t] * fac.advance_rate)
                available = effective_limit - balance[fac.facility_id]
                draw = min(shortfall, max(0.0, available))
                if draw > 0:
                    result.additional_draws[fac.facility_id][t] = draw
                    balance[fac.facility_id] += draw
                    total_draws_t += draw
                    shortfall -= draw
                if shortfall <= 0:
                    break
        elif cash_t > minimum_cash:
            excess = cash_t - minimum_cash
            for fac in repay_order:
                repay = min(excess, balance[fac.facility_id])
                if repay > 0:
                    balance[fac.facility_id] -= repay
                    total_repays_t += repay
                    excess -= repay
                if excess <= 0:
                    break

        # Interest on outstanding balances (after draws/repays applied)
        overdraft_interest_t = 0.0
        waterfall_interest_t = 0.0
        for fac in facilities:
            bal = balance[fac.facility_id]
            if bal > 0:
                fac_interest = bal * fac.interest_rate / 12
                waterfall_interest_t += fac_interest
                if fac.type == "overdraft":
                    overdraft_interest_t += fac_interest

        result.cash_after_funding[t] = cash_t + total_draws_t - total_repays_t
        result.overdraft_interest[t] = overdraft_interest_t
        result.waterfall_interest[t] = waterfall_interest_t
        result.waterfall_debt_per_period[t] = sum(balance.values())

    return result
