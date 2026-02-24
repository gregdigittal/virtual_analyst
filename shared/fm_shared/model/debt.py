"""
Debt schedule: balances, interest, draws, repayments, current/non-current split.
Used by the three-statement generator; cash-plug facilities are excluded (Phase 2).
"""

from __future__ import annotations

from dataclasses import dataclass

from shared.fm_shared.model.schemas import DebtFacility, DrawRepayPoint


@dataclass
class DebtScheduleResult:
    balance_per_period: dict[str, list[float]]  # facility_id -> [balance_t0..tn]
    interest_per_period: list[float]  # total interest per period
    draws_per_period: list[float]  # total draws per period
    repayments_per_period: list[float]  # total repayments per period
    current_debt_per_period: list[float]  # maturing within 12 months
    non_current_debt_per_period: list[float]  # long-term portion


def empty_debt_result(horizon: int) -> DebtScheduleResult:
    """Return a zero-filled result when no debt facilities exist."""
    return DebtScheduleResult(
        balance_per_period={},
        interest_per_period=[0.0] * horizon,
        draws_per_period=[0.0] * horizon,
        repayments_per_period=[0.0] * horizon,
        current_debt_per_period=[0.0] * horizon,
        non_current_debt_per_period=[0.0] * horizon,
    )


def _draws_at_month(schedule: list[DrawRepayPoint] | None, month: int) -> float:
    if not schedule:
        return 0.0
    return sum(p.amount for p in schedule if p.month == month)


def _repays_at_month(schedule: list[DrawRepayPoint] | None, month: int) -> float:
    if not schedule:
        return 0.0
    return sum(p.amount for p in schedule if p.month == month)


def _repayments_due_next_12_months(
    schedule: list[DrawRepayPoint] | None, from_month: int, horizon: int
) -> float:
    """Sum of repayments scheduled in months [from_month+1, from_month+12] (1-based window)."""
    if not schedule:
        return 0.0
    end = min(from_month + 12, horizon)
    return sum(p.amount for p in schedule if from_month + 1 <= p.month <= end)


def calculate_debt_schedule(
    facilities: list[DebtFacility],
    horizon: int,
) -> DebtScheduleResult:
    """
    Calculate debt balances, interest, draws, and repayments for each period.

    For each facility per period t:
    - draws[t] = sum of draw_schedule amounts at month t
    - repays[t] = sum of repayment_schedule amounts at month t
    - balance[t] = balance[t-1] + draws[t] - repays[t], clamped to [0, limit]
    - interest[t] = balance[t] * interest_rate / 12

    Current vs non-current split:
    - Sum of repayments due within the next 12 months = current portion
    - Remainder = non-current portion
    """
    result = empty_debt_result(horizon)
    for fac in facilities:
        if fac.is_cash_plug:
            continue
        balance = 0.0
        balances: list[float] = []
        for t in range(horizon):
            draw_t = _draws_at_month(fac.draw_schedule, t)
            repay_t = _repays_at_month(fac.repayment_schedule, t)
            balance = balance + draw_t - repay_t
            balance = max(0.0, min(fac.limit, balance))
            balances.append(balance)
            result.interest_per_period[t] += balance * fac.interest_rate / 12
            result.draws_per_period[t] += draw_t
            result.repayments_per_period[t] += repay_t
        result.balance_per_period[fac.facility_id] = balances

    for t in range(horizon):
        current_total = 0.0
        non_current_total = 0.0
        for fac in facilities:
            if fac.is_cash_plug:
                continue
            bal = result.balance_per_period[fac.facility_id][t]
            repay_next_12 = _repayments_due_next_12_months(
                fac.repayment_schedule, t, horizon
            )
            current_fac = min(bal, repay_next_12)
            non_current_total += bal - current_fac
            current_total += current_fac
        result.current_debt_per_period[t] = current_total
        result.non_current_debt_per_period[t] = non_current_total

    return result
