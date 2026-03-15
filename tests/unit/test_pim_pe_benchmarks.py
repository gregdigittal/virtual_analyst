"""PIM-6.3: DPI/TVPI/IRR computation engine unit tests."""
from __future__ import annotations

import math
from datetime import date

import pytest

from apps.api.app.services.pim.pe_benchmarks import (
    CashFlow,
    PeMetrics,
    compute_irr,
    compute_j_curve,
    compute_multiples,
    compute_pe_metrics,
    parse_cash_flows,
)


# ---------------------------------------------------------------------------
# CashFlow dataclass
# ---------------------------------------------------------------------------

class TestCashFlow:
    def test_valid_drawdown(self) -> None:
        cf = CashFlow(date(2020, 1, 1), 100_000.0, "drawdown")
        assert cf.amount_usd == 100_000.0

    def test_invalid_amount_zero(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            CashFlow(date(2020, 1, 1), 0.0, "drawdown")

    def test_invalid_cf_type(self) -> None:
        with pytest.raises(ValueError, match="cf_type"):
            CashFlow(date(2020, 1, 1), 100.0, "dividend")

    def test_valid_distribution(self) -> None:
        cf = CashFlow(date(2021, 6, 30), 50_000.0, "distribution")
        assert cf.cf_type == "distribution"

    def test_valid_recallable_distribution(self) -> None:
        cf = CashFlow(date(2021, 6, 30), 50_000.0, "recallable_distribution")
        assert cf.cf_type == "recallable_distribution"


# ---------------------------------------------------------------------------
# parse_cash_flows
# ---------------------------------------------------------------------------

class TestParseCashFlows:
    def test_empty(self) -> None:
        assert parse_cash_flows([]) == []

    def test_sorted_by_date(self) -> None:
        raw = [
            {"date": "2022-06-30", "amount_usd": 200_000, "cf_type": "distribution"},
            {"date": "2020-01-01", "amount_usd": 500_000, "cf_type": "drawdown"},
        ]
        cfs = parse_cash_flows(raw)
        assert cfs[0].cf_date == date(2020, 1, 1)
        assert cfs[1].cf_date == date(2022, 6, 30)

    def test_date_object_accepted(self) -> None:
        raw = [{"date": date(2020, 1, 1), "amount_usd": 100_000, "cf_type": "drawdown"}]
        cfs = parse_cash_flows(raw)
        assert cfs[0].cf_date == date(2020, 1, 1)


# ---------------------------------------------------------------------------
# compute_multiples — DPI / TVPI / MOIC
# ---------------------------------------------------------------------------

class TestComputeMultiples:
    def _cfs(self) -> list[CashFlow]:
        return [
            CashFlow(date(2020, 1, 1), 1_000_000.0, "drawdown"),
            CashFlow(date(2021, 6, 30), 600_000.0, "distribution"),
        ]

    def test_paid_in_capital(self) -> None:
        paid_in, *_ = compute_multiples(self._cfs(), nav_usd=None)
        assert paid_in == pytest.approx(1_000_000.0)

    def test_distributed(self) -> None:
        _, distributed, *_ = compute_multiples(self._cfs(), nav_usd=None)
        assert distributed == pytest.approx(600_000.0)

    def test_dpi_no_nav(self) -> None:
        paid_in, distributed, dpi, tvpi, moic = compute_multiples(self._cfs(), nav_usd=None)
        assert dpi == pytest.approx(0.6)
        assert tvpi == pytest.approx(0.6)   # no NAV → tvpi = dpi

    def test_tvpi_with_nav(self) -> None:
        _, _, dpi, tvpi, moic = compute_multiples(self._cfs(), nav_usd=800_000.0)
        # tvpi = (600k + 800k) / 1000k = 1.4
        assert tvpi == pytest.approx(1.4)
        assert moic == pytest.approx(1.4)

    def test_zero_paid_in_returns_nones(self) -> None:
        cfs = [CashFlow(date(2020, 1, 1), 100_000.0, "distribution")]
        paid_in, distributed, dpi, tvpi, moic = compute_multiples(cfs, nav_usd=None)
        assert paid_in == pytest.approx(0.0)
        assert dpi is None
        assert tvpi is None

    def test_recallable_distribution_counted(self) -> None:
        cfs = [
            CashFlow(date(2020, 1, 1), 1_000_000.0, "drawdown"),
            CashFlow(date(2021, 1, 1), 300_000.0, "recallable_distribution"),
        ]
        _, distributed, dpi, _, _ = compute_multiples(cfs, nav_usd=None)
        assert distributed == pytest.approx(300_000.0)
        assert dpi == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# compute_irr
# ---------------------------------------------------------------------------

class TestComputeIrr:
    def test_no_cash_flows_returns_none(self) -> None:
        irr, converged = compute_irr([], nav_usd=None)
        assert irr is None
        assert not converged

    def test_no_return_no_nav_returns_none(self) -> None:
        cfs = [CashFlow(date(2020, 1, 1), 1_000_000.0, "drawdown")]
        irr, converged = compute_irr(cfs, nav_usd=None)
        assert irr is None
        assert not converged

    def test_simple_irr_one_year(self) -> None:
        """Invest 1000 on Jan 1; receive 1100 one year later → IRR ≈ 10%."""
        cfs = [
            CashFlow(date(2020, 1, 1), 1_000.0, "drawdown"),
            CashFlow(date(2021, 1, 1), 1_100.0, "distribution"),
        ]
        irr, converged = compute_irr(cfs, nav_usd=None, start_date=date(2020, 1, 1))
        assert converged
        assert irr is not None
        assert abs(irr - 0.10) < 0.01   # within 1% of 10%

    def test_irr_with_nav_as_terminal(self) -> None:
        """1000 invested, 500 returned, 600 remaining NAV → total return = 1.1x."""
        cfs = [
            CashFlow(date(2020, 1, 1), 1_000.0, "drawdown"),
            CashFlow(date(2021, 6, 1), 500.0, "distribution"),
        ]
        irr, converged = compute_irr(cfs, nav_usd=600.0, start_date=date(2020, 1, 1))
        assert converged
        assert irr is not None
        assert irr > 0  # net positive return

    def test_negative_irr_scenario(self) -> None:
        """1000 invested; only 500 returned (loss) → IRR should be negative."""
        cfs = [
            CashFlow(date(2020, 1, 1), 1_000.0, "drawdown"),
            CashFlow(date(2022, 1, 1), 500.0, "distribution"),
        ]
        irr, converged = compute_irr(cfs, nav_usd=None, start_date=date(2020, 1, 1))
        assert converged
        assert irr is not None
        assert irr < 0  # loss scenario


# ---------------------------------------------------------------------------
# compute_j_curve
# ---------------------------------------------------------------------------

class TestComputeJCurve:
    def test_empty_cash_flows(self) -> None:
        assert compute_j_curve([], commitment_usd=1_000_000) == []

    def test_zero_commitment_returns_empty(self) -> None:
        cfs = [CashFlow(date(2020, 1, 1), 100_000.0, "drawdown")]
        assert compute_j_curve(cfs, commitment_usd=0) == []

    def test_j_shape_starts_negative(self) -> None:
        """First drawdown should produce a negative cumulative return."""
        cfs = [
            CashFlow(date(2020, 1, 1), 500_000.0, "drawdown"),
            CashFlow(date(2021, 1, 1), 600_000.0, "distribution"),
        ]
        points = compute_j_curve(cfs, commitment_usd=1_000_000.0)
        assert len(points) == 2
        # After drawdown: cumulative_net = -500k → return = -0.5
        assert points[0]["cumulative_return"] == pytest.approx(-0.5)
        # After distribution: cumulative_net = -500k + 600k = +100k → return = +0.1
        assert points[1]["cumulative_return"] == pytest.approx(0.1)

    def test_period_months_positive(self) -> None:
        cfs = [
            CashFlow(date(2020, 1, 1), 100.0, "drawdown"),
            CashFlow(date(2020, 7, 1), 50.0, "distribution"),
        ]
        points = compute_j_curve(cfs, commitment_usd=100.0)
        assert points[0]["period_months"] == pytest.approx(0.0, abs=0.1)
        assert points[1]["period_months"] > 5.0  # approximately 6 months


# ---------------------------------------------------------------------------
# compute_pe_metrics — integration
# ---------------------------------------------------------------------------

class TestComputePeMetrics:
    def _raw_flows(self) -> list[dict]:
        return [
            {"date": "2020-01-01", "amount_usd": 1_000_000, "cf_type": "drawdown"},
            {"date": "2021-06-30", "amount_usd": 800_000, "cf_type": "distribution"},
        ]

    def test_returns_pe_metrics_instance(self) -> None:
        result = compute_pe_metrics(self._raw_flows(), commitment_usd=1_000_000, nav_usd=None)
        assert isinstance(result, PeMetrics)

    def test_dpi_computed(self) -> None:
        result = compute_pe_metrics(self._raw_flows(), commitment_usd=1_000_000, nav_usd=None)
        assert result.dpi == pytest.approx(0.8)

    def test_tvpi_with_nav(self) -> None:
        result = compute_pe_metrics(self._raw_flows(), commitment_usd=1_000_000, nav_usd=400_000)
        # tvpi = (800k + 400k) / 1000k = 1.2
        assert result.tvpi == pytest.approx(1.2)

    def test_j_curve_populated(self) -> None:
        result = compute_pe_metrics(self._raw_flows(), commitment_usd=1_000_000, nav_usd=None)
        assert len(result.j_curve) == 2

    def test_limitations_non_empty(self) -> None:
        result = compute_pe_metrics(self._raw_flows(), commitment_usd=1_000_000, nav_usd=None)
        assert len(result.limitations) > 0

    def test_empty_flows(self) -> None:
        result = compute_pe_metrics([], commitment_usd=1_000_000, nav_usd=None)
        assert result.paid_in_capital == pytest.approx(0.0)
        assert result.dpi is None
        assert result.irr is None
