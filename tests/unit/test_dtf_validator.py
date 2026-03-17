"""Unit tests for DTF-B weekly_validator.py — pure logic functions only.

No database connection required.  asyncpg calls are mocked.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.dtf.weekly_validator import (
    IC_THRESHOLD,
    MIN_OBSERVATIONS,
    build_report,
    compute_spearman_ic,
)

# ---------------------------------------------------------------------------
# compute_spearman_ic tests
# ---------------------------------------------------------------------------


def test_ic_computation_known_inputs() -> None:
    """IC with perfectly correlated ranks = 1.0."""
    # Both predicted and actual are perfectly ordered the same way
    pairs = [(5.0, 50.0), (4.0, 40.0), (3.0, 30.0), (2.0, 20.0), (1.0, 10.0)]
    ic = compute_spearman_ic(pairs)
    assert abs(ic - 1.0) < 1e-9, f"Expected IC=1.0, got {ic}"


def test_ic_perfectly_anti_correlated() -> None:
    """IC with perfectly anti-correlated ranks = -1.0."""
    pairs = [(1.0, 50.0), (2.0, 40.0), (3.0, 30.0), (4.0, 20.0), (5.0, 10.0)]
    ic = compute_spearman_ic(pairs)
    assert abs(ic - (-1.0)) < 1e-9, f"Expected IC=-1.0, got {ic}"


def test_ic_uncorrelated_returns_near_zero() -> None:
    """IC for uncorrelated data should be near 0, not 1 or -1."""
    # Alternating pattern
    pairs = [(1.0, 10.0), (5.0, 10.0), (2.0, 10.0), (4.0, 10.0), (3.0, 10.0)]
    ic = compute_spearman_ic(pairs)
    # All actual scores are equal → zero variance → IC = 0
    assert ic == 0.0


def test_ic_single_pair_returns_zero() -> None:
    """IC with only 1 pair returns 0.0 (not enough data for correlation)."""
    ic = compute_spearman_ic([(5.0, 50.0)])
    assert ic == 0.0


def test_ic_empty_returns_zero() -> None:
    """IC with empty list returns 0.0."""
    ic = compute_spearman_ic([])
    assert ic == 0.0


def test_ic_with_ties() -> None:
    """IC handles tied values using average rank."""
    # Two pairs with same predicted score — should not crash
    pairs = [(3.0, 30.0), (3.0, 20.0), (1.0, 10.0)]
    ic = compute_spearman_ic(pairs)
    assert -1.0 <= ic <= 1.0


# ---------------------------------------------------------------------------
# build_report tests
# ---------------------------------------------------------------------------


def test_report_json_structure_sufficient_data() -> None:
    """Report JSON has all required keys when data is sufficient."""
    today = date(2026, 3, 16)
    pairs = [("AAPL", 75.0, 2.5), ("MSFT", 80.0, 3.0), ("GOOG", 60.0, 1.0)]
    ic = 0.65

    report = build_report(today, weeks_evaluated=4, pairs=pairs, ic_score=ic)

    required_keys = {"date", "weeks_evaluated", "ic_score", "ic_threshold", "pass", "n_observations"}
    assert required_keys.issubset(set(report.keys())), f"Missing keys: {required_keys - set(report.keys())}"
    assert report["date"] == "2026-03-16"
    assert report["weeks_evaluated"] == 4
    assert report["n_observations"] == 3
    assert report["ic_threshold"] == IC_THRESHOLD


def test_report_pass_true_when_ic_above_threshold() -> None:
    """pass=True when IC >= 0.4."""
    today = date(2026, 3, 16)
    pairs = [("A", 70.0, 1.0), ("B", 60.0, 0.5)]
    report = build_report(today, weeks_evaluated=4, pairs=pairs, ic_score=0.5)
    assert report["pass"] is True


def test_report_pass_false_when_ic_below_threshold() -> None:
    """pass=False when IC < 0.4."""
    today = date(2026, 3, 16)
    pairs = [("A", 70.0, 1.0), ("B", 60.0, 0.5)]
    report = build_report(today, weeks_evaluated=4, pairs=pairs, ic_score=0.3)
    assert report["pass"] is False


def test_insufficient_data_returns_null_pass() -> None:
    """n < 10 observations → pass: null, reason: 'insufficient_data'."""
    today = date(2026, 3, 16)
    # Fewer than MIN_OBSERVATIONS pairs
    pairs = [("A", 70.0, 1.0), ("B", 60.0, 0.5)]  # only 2 pairs
    assert len(pairs) < MIN_OBSERVATIONS

    report = build_report(today, weeks_evaluated=4, pairs=pairs, ic_score=None, reason="insufficient_data")

    assert report["pass"] is None
    assert report["reason"] == "insufficient_data"
    assert report["ic_score"] is None
    assert report["n_observations"] == 2


def test_report_details_contains_company_ids() -> None:
    """Report details list has an entry per company with required keys."""
    today = date(2026, 3, 16)
    pairs = [("AAPL", 75.0, 2.5), ("MSFT", 80.0, 3.0)]
    report = build_report(today, weeks_evaluated=4, pairs=pairs, ic_score=0.6)

    assert len(report["details"]) == 2
    for detail in report["details"]:
        assert "company_id" in detail
        assert "predicted_score" in detail
        assert "actual_score_change" in detail


def test_report_ic_score_rounded() -> None:
    """IC score is rounded to 6 decimal places in the report."""
    today = date(2026, 3, 16)
    pairs = [("X", 50.0, 1.0)]
    ic = 0.123456789
    report = build_report(today, weeks_evaluated=4, pairs=pairs, ic_score=ic)
    # Should be rounded to 6 decimal places
    assert report["ic_score"] == round(ic, 6)
