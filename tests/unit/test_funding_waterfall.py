"""Unit tests for funding waterfall (cash-plug facilities)."""

from __future__ import annotations

import pytest

from shared.fm_shared.model.funding_waterfall import (
    apply_funding_waterfall,
    empty_waterfall_result,
)
from shared.fm_shared.model.schemas import DebtFacility


def _revolver(facility_id: str = "rev", limit: float = 300_000.0, rate: float = 0.06) -> DebtFacility:
    return DebtFacility(
        facility_id=facility_id,
        label="Revolver",
        type="revolver",
        limit=limit,
        interest_rate=rate,
        draw_schedule=None,
        repayment_schedule=None,
        is_cash_plug=True,
    )


def _overdraft(
    facility_id: str = "od", limit: float = 200_000.0, rate: float = 0.12
) -> DebtFacility:
    return DebtFacility(
        facility_id=facility_id,
        label="Overdraft",
        type="overdraft",
        limit=limit,
        interest_rate=rate,
        draw_schedule=None,
        repayment_schedule=None,
        is_cash_plug=True,
    )


def test_no_shortfall() -> None:
    """Cash always above minimum -> no injections."""
    closing = [100_000.0] * 12
    facilities = [_revolver(limit=300_000.0)]
    result = apply_funding_waterfall(closing, facilities, minimum_cash=50_000.0, horizon=12)
    assert result.cash_after_funding == closing
    assert result.additional_draws["rev"] == [0.0] * 12
    assert result.overdraft_interest == [0.0] * 12
    assert result.waterfall_debt_per_period == [0.0] * 12


def test_single_revolver_injection() -> None:
    """Cash goes negative in month 6; revolver draws to cover minimum."""
    closing = [80_000.0] * 5 + [-20_000.0] + [80_000.0] * 6  # shortfall in month 5
    facilities = [_revolver(limit=100_000.0)]
    result = apply_funding_waterfall(closing, facilities, minimum_cash=10_000.0, horizon=12)
    # Month 5: -20k below min 10k -> shortfall 30k, draw 30k
    assert result.additional_draws["rev"][5] == 30_000.0
    assert result.cash_after_funding[5] == -20_000.0 + 30_000.0  # 10k
    assert result.waterfall_debt_per_period[5] == 30_000.0


def test_revolver_capped_at_limit() -> None:
    """Shortfall exceeds revolver limit -> partial cover only."""
    closing = [-400_000.0] + [0.0] * 11  # need 410k to reach min 10k
    facilities = [_revolver(limit=300_000.0)]
    result = apply_funding_waterfall(closing, facilities, minimum_cash=10_000.0, horizon=12)
    assert result.additional_draws["rev"][0] == 300_000.0
    assert result.cash_after_funding[0] == -400_000.0 + 300_000.0  # -100k still
    assert result.waterfall_debt_per_period[0] == 300_000.0


def test_overdraft_fallback() -> None:
    """Revolver full; overdraft covers remainder."""
    closing = [-400_000.0] + [0.0] * 11
    facilities = [_revolver(limit=300_000.0), _overdraft(limit=150_000.0)]
    result = apply_funding_waterfall(closing, facilities, minimum_cash=10_000.0, horizon=12)
    # Shortfall 410k: revolver 300k, overdraft 110k (capped at 150k)
    assert result.additional_draws["rev"][0] == 300_000.0
    assert result.additional_draws["od"][0] == 110_000.0
    assert result.cash_after_funding[0] == -400_000.0 + 300_000.0 + 110_000.0  # 10k
    assert result.waterfall_debt_per_period[0] == 410_000.0


def test_overdraft_interest() -> None:
    """overdraft_interest = balance * rate / 12 (balance-based, not draw-based)."""
    closing = [-50_000.0] + [0.0] * 11  # shortfall 60k to reach min 10k
    facilities = [_overdraft(limit=100_000.0, rate=0.12)]
    result = apply_funding_waterfall(closing, facilities, minimum_cash=10_000.0, horizon=12)
    assert result.additional_draws["od"][0] == 60_000.0
    # Interest on closing balance of 60K
    assert result.overdraft_interest[0] == pytest.approx(60_000.0 * 0.12 / 12, abs=0.01)
    # waterfall_interest includes all facility interest (overdraft-only here)
    assert result.waterfall_interest[0] == pytest.approx(60_000.0 * 0.12 / 12, abs=0.01)


def test_surplus_repayment() -> None:
    """Cash exceeds minimum; repay outstanding draws."""
    closing = [-30_000.0, 200_000.0] + [0.0] * 10  # draw 40k in 0, repay in 1
    facilities = [_revolver(limit=100_000.0)]
    result = apply_funding_waterfall(closing, facilities, minimum_cash=10_000.0, horizon=12)
    assert result.additional_draws["rev"][0] == 40_000.0
    assert result.cash_after_funding[0] == 10_000.0
    assert result.cash_after_funding[1] == 200_000.0 - 40_000.0  # excess 190k, repay 40k
    assert result.waterfall_debt_per_period[0] == 40_000.0
    assert result.waterfall_debt_per_period[1] == 0.0


def test_multiple_facilities_ordering() -> None:
    """Revolver used before overdraft."""
    closing = [-200_000.0] + [0.0] * 11
    facilities = [_overdraft(limit=300_000.0), _revolver(limit=300_000.0)]
    result = apply_funding_waterfall(closing, facilities, minimum_cash=10_000.0, horizon=12)
    # Draw order: revolver first, then overdraft. So revolver gets 210k draw.
    assert result.additional_draws["rev"][0] == 210_000.0
    assert result.additional_draws["od"][0] == 0.0


def test_empty_facilities() -> None:
    """No plug facilities -> empty result, cash unchanged."""
    closing = [50_000.0] * 12
    result = apply_funding_waterfall(closing, [], minimum_cash=10_000.0, horizon=12)
    assert result.cash_after_funding == closing
    assert result.additional_draws == {}
    assert result.overdraft_interest == [0.0] * 12
    assert result.waterfall_debt_per_period == [0.0] * 12


def test_revolver_interest_in_waterfall() -> None:
    """waterfall_interest includes revolver interest on outstanding balance."""
    closing = [-30_000.0, 0.0] + [0.0] * 10  # draw 40k in month 0
    facilities = [_revolver(limit=100_000.0, rate=0.06)]
    result = apply_funding_waterfall(closing, facilities, minimum_cash=10_000.0, horizon=12)
    assert result.additional_draws["rev"][0] == 40_000.0
    # Revolver interest: 40K * 6% / 12 = 200
    assert result.waterfall_interest[0] == pytest.approx(200.0, abs=0.01)
    # Overdraft interest is 0 (no overdraft)
    assert result.overdraft_interest[0] == 0.0
    # Month 1: balance still 40K (no surplus to repay since cash == 0 < min 10K)
    # Actually month 1 closing is 0, shortfall = 10K, draw another 10K
    assert result.waterfall_interest[1] == pytest.approx(50_000.0 * 0.06 / 12, abs=0.01)


def test_empty_waterfall_result_shape() -> None:
    """empty_waterfall_result has correct horizon."""
    r = empty_waterfall_result(24)
    assert len(r.cash_after_funding) == 24
    assert len(r.overdraft_interest) == 24
    assert len(r.waterfall_interest) == 24
    assert len(r.waterfall_debt_per_period) == 24
