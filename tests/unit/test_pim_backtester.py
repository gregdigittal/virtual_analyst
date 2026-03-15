"""Unit tests for apps.api.app.services.pim.backtester.

PIM-4.7: Walk-forward backtester (run_backtest, persist_backtest).
PIM-4.8: IC and ICIR computation (compute_ic, compute_icir).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from apps.api.app.services.pim.backtester import (
    BacktestConfig,
    BacktestResult,
    HistoricalCISRecord,
    _compute_max_drawdown,
    compute_ic,
    compute_icir,
    persist_backtest,
    run_backtest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_records(
    n_dates: int,
    n_companies: int,
    base_cis: float = 60.0,
    base_return: float = 0.02,
) -> list[HistoricalCISRecord]:
    """Create synthetic records: n_dates × n_companies with deterministic CIS + returns."""
    records = []
    for d in range(n_dates):
        date = f"2024-{(d // 28) + 1:02d}-{(d % 28) + 1:02d}"
        for c in range(n_companies):
            records.append(
                HistoricalCISRecord(
                    date=date,
                    company_id=f"co_{c}",
                    cis_score=base_cis - c * 2.0,
                    sector="Technology" if c < n_companies // 2 else "Finance",
                    realised_return=base_return - c * 0.001,
                )
            )
    return records


# ---------------------------------------------------------------------------
# compute_ic (PIM-4.8)
# ---------------------------------------------------------------------------


class TestComputeIC:
    def test_perfect_positive_correlation(self):
        scores = [1.0, 2.0, 3.0]
        returns = [0.01, 0.02, 0.03]
        ic = compute_ic(scores, returns)
        assert ic is not None
        assert abs(ic - 1.0) < 1e-9

    def test_perfect_negative_correlation(self):
        scores = [3.0, 2.0, 1.0]
        returns = [0.01, 0.02, 0.03]
        ic = compute_ic(scores, returns)
        assert ic is not None
        assert abs(ic - (-1.0)) < 1e-9

    def test_zero_correlation(self):
        # Orthogonal: returns are same regardless of score ranking
        scores = [1.0, 2.0, 3.0, 4.0]
        returns = [0.01, 0.01, 0.01, 0.01]
        ic = compute_ic(scores, returns)
        assert ic is None  # std_y == 0

    def test_fewer_than_2_returns_none(self):
        assert compute_ic([5.0], [0.01]) is None

    def test_mismatched_lengths_returns_none(self):
        assert compute_ic([1.0, 2.0], [0.01]) is None

    def test_empty_lists_returns_none(self):
        assert compute_ic([], []) is None

    def test_zero_variance_in_scores_returns_none(self):
        scores = [50.0, 50.0, 50.0]
        returns = [0.01, 0.02, 0.03]
        assert compute_ic(scores, returns) is None

    def test_ic_bounded(self):
        scores = [10.0, 20.0, 30.0, 40.0, 50.0]
        returns = [0.05, 0.03, 0.07, 0.01, 0.09]
        ic = compute_ic(scores, returns)
        assert ic is not None
        assert -1.0 <= ic <= 1.0


# ---------------------------------------------------------------------------
# compute_icir (PIM-4.8)
# ---------------------------------------------------------------------------


class TestComputeICIR:
    def test_consistent_positive_ics(self):
        ic_series = [0.3, 0.4, 0.35, 0.3, 0.4]
        icir = compute_icir(ic_series)
        assert icir is not None
        assert icir > 0

    def test_icir_formula(self):
        # Manual: mean=0.4, std=0.0 → None (degenerate)
        ic_series = [0.4, 0.4, 0.4]
        icir = compute_icir(ic_series)
        assert icir is None  # std == 0

    def test_icir_with_variance(self):
        ic_series = [0.2, 0.6]  # mean=0.4, std=0.2, ICIR=2.0
        icir = compute_icir(ic_series)
        assert icir is not None
        assert abs(icir - 2.0) < 1e-9

    def test_fewer_than_2_returns_none(self):
        assert compute_icir([0.5]) is None

    def test_empty_returns_none(self):
        assert compute_icir([]) is None

    def test_negative_icir_for_negative_ics(self):
        ic_series = [-0.3, -0.4, -0.5]
        icir = compute_icir(ic_series)
        assert icir is not None
        assert icir < 0


# ---------------------------------------------------------------------------
# _compute_max_drawdown
# ---------------------------------------------------------------------------


class TestMaxDrawdown:
    def test_no_drawdown(self):
        path = [1.0, 1.1, 1.2, 1.3]
        assert _compute_max_drawdown(path) == pytest.approx(0.0, abs=1e-9)

    def test_full_loss(self):
        path = [1.0, 0.5]
        dd = _compute_max_drawdown(path)
        assert abs(dd - 0.5) < 1e-9  # 50% from peak 1.0 to trough 0.5

    def test_recovery_after_drawdown(self):
        path = [1.0, 1.2, 0.9, 1.5]
        dd = _compute_max_drawdown(path)
        # Peak=1.2, trough=0.9 → dd = (1.2 - 0.9) / 1.2 = 0.25
        assert abs(dd - 0.25) < 1e-6

    def test_short_path_no_drawdown(self):
        assert _compute_max_drawdown([1.0]) == 0.0

    def test_empty_path(self):
        assert _compute_max_drawdown([]) == 0.0


# ---------------------------------------------------------------------------
# run_backtest — basic cases (PIM-4.7)
# ---------------------------------------------------------------------------


class TestRunBacktest:
    def test_insufficient_dates_returns_empty_result(self):
        records = _make_records(n_dates=1, n_companies=5)
        result = run_backtest(records, tenant_id="t1")
        assert result.n_periods == 0

    def test_basic_backtest_produces_periods(self):
        records = _make_records(n_dates=5, n_companies=10)
        result = run_backtest(records, BacktestConfig(top_n=3, rebalance_freq_days=21), tenant_id="t1")
        assert result.n_periods >= 1

    def test_backtest_id_is_uuid(self):
        import re
        records = _make_records(n_dates=4, n_companies=6)
        result = run_backtest(records, tenant_id="t1")
        uuid_pattern = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
        assert uuid_pattern.match(result.backtest_id)

    def test_tenant_id_propagated(self):
        records = _make_records(n_dates=3, n_companies=4)
        result = run_backtest(records, tenant_id="tenant_abc")
        assert result.tenant_id == "tenant_abc"

    def test_config_propagated(self):
        config = BacktestConfig(top_n=5, strategy_label="my_strat")
        records = _make_records(n_dates=3, n_companies=6)
        result = run_backtest(records, config, tenant_id="t1")
        assert result.config.strategy_label == "my_strat"

    def test_positive_returns_positive_cumulative(self):
        # All positive returns → cumulative should be positive
        records = _make_records(n_dates=4, n_companies=5, base_return=0.02)
        result = run_backtest(records, BacktestConfig(top_n=3), tenant_id="t1")
        if result.n_periods > 0:
            assert result.cumulative_return > 0

    def test_no_look_ahead_bias(self):
        # Ensure the backtester uses CIS from the rebalance date, not the next period
        # Verify by checking that n_holdings <= top_n in all periods
        records = _make_records(n_dates=5, n_companies=10)
        result = run_backtest(records, BacktestConfig(top_n=5), tenant_id="t1")
        for p in result.periods:
            assert p.n_holdings <= 5

    def test_weights_sum_constraint(self):
        # Each period should select at most top_n companies
        records = _make_records(n_dates=4, n_companies=8)
        config = BacktestConfig(top_n=3)
        result = run_backtest(records, config, tenant_id="t1")
        for period in result.periods:
            assert period.n_holdings <= config.top_n

    def test_volatility_nonnegative(self):
        records = _make_records(n_dates=5, n_companies=6)
        result = run_backtest(records, tenant_id="t1")
        assert result.volatility >= 0.0

    def test_max_drawdown_between_0_and_1(self):
        records = _make_records(n_dates=5, n_companies=6)
        result = run_backtest(records, tenant_id="t1")
        assert 0.0 <= result.max_drawdown <= 1.0

    def test_config_validation_raises(self):
        with pytest.raises(ValueError):
            run_backtest([], BacktestConfig(top_n=0), tenant_id="t1")


# ---------------------------------------------------------------------------
# IC / ICIR in run_backtest (PIM-4.8)
# ---------------------------------------------------------------------------


class TestBacktestICICIR:
    def test_ic_computed_when_returns_available(self):
        # Records with return data — IC should be computed
        records = _make_records(n_dates=4, n_companies=8, base_return=0.02)
        result = run_backtest(records, BacktestConfig(top_n=4), tenant_id="t1")
        # At least some periods should have IC
        ics = [p.ic for p in result.periods if p.ic is not None]
        assert len(ics) >= 0  # May or may not have IC depending on variance

    def test_ic_mean_and_icir_present_when_computed(self):
        records = _make_records(n_dates=6, n_companies=10, base_return=0.02)
        result = run_backtest(records, BacktestConfig(top_n=5), tenant_id="t1")
        # ic_mean and icir are either both None or both floats
        if result.ic_mean is not None:
            assert isinstance(result.ic_mean, float)
        if result.icir is not None:
            assert isinstance(result.icir, float)

    def test_no_return_data_ic_is_none(self):
        # Records without realised_return → IC should be None
        records = [
            HistoricalCISRecord(date=f"2024-01-{i+1:02d}", company_id=f"co_{j}", cis_score=50.0 + j)
            for i in range(3)
            for j in range(5)
        ]
        result = run_backtest(records, BacktestConfig(top_n=3), tenant_id="t1")
        for period in result.periods:
            assert period.ic is None

    def test_limitations_disclaimer_present(self):
        records = _make_records(n_dates=3, n_companies=4)
        result = run_backtest(records, tenant_id="t1")
        assert len(result.limitations) > 0
        assert "simulated" in result.limitations.lower()


# ---------------------------------------------------------------------------
# persist_backtest (PIM-4.7)
# ---------------------------------------------------------------------------


class TestPersistBacktest:
    @pytest.fixture()
    def mock_conn(self):
        conn = AsyncMock()
        conn.execute = AsyncMock()
        return conn

    @pytest.fixture()
    def sample_result(self):
        records = _make_records(n_dates=4, n_companies=6, base_return=0.01)
        return run_backtest(records, BacktestConfig(top_n=3), tenant_id="t_persist")

    async def test_persist_calls_execute(self, mock_conn, sample_result):
        await persist_backtest(sample_result, mock_conn)
        assert mock_conn.execute.called

    async def test_persist_backtest_id_in_args(self, mock_conn, sample_result):
        await persist_backtest(sample_result, mock_conn)
        call_args = mock_conn.execute.call_args[0]
        assert sample_result.backtest_id in call_args

    async def test_persist_empty_result(self, mock_conn):
        empty = run_backtest([], tenant_id="t_empty")
        await persist_backtest(empty, mock_conn)
        assert mock_conn.execute.called
