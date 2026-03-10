"""Tests for REM-09: Per-period FX rate support in consolidation engine."""

from __future__ import annotations

import pytest

from shared.fm_shared.analysis.consolidation import (
    ConsolidatedResult,
    EntityResult,
    _apply_rate_to_series,
    _get_rate,
    _resolve_rate_for_period,
    consolidate,
    translate_statements,
)


# ---------------------------------------------------------------------------
# Helper: minimal entity statements
# ---------------------------------------------------------------------------
def _make_statements(horizon: int, revenue: list[float], equity: list[float]) -> dict:
    return {
        "income_statement": {"revenue": revenue, "net_income": [r * 0.1 for r in revenue]},
        "balance_sheet": {"total_equity": equity, "total_assets": [e * 2 for e in equity]},
        "cash_flow": {"operating": [r * 0.05 for r in revenue]},
    }


# ---------------------------------------------------------------------------
# _get_rate: scalar backward compatibility
# ---------------------------------------------------------------------------
def test_get_rate_scalar() -> None:
    rates = {("ZAR", "USD"): 0.055}
    assert _get_rate(rates, "ZAR", "USD") == 0.055


def test_get_rate_scalar_inverse() -> None:
    rates = {("ZAR", "USD"): 0.05}
    result = _get_rate(rates, "USD", "ZAR")
    assert abs(result - 20.0) < 1e-9


def test_get_rate_same_currency() -> None:
    assert _get_rate({}, "USD", "USD") == 1.0


# ---------------------------------------------------------------------------
# _get_rate: per-period list
# ---------------------------------------------------------------------------
def test_get_rate_per_period_list() -> None:
    rates = {("ZAR", "USD"): [0.055, 0.054, 0.056]}
    result = _get_rate(rates, "ZAR", "USD")
    assert result == [0.055, 0.054, 0.056]


def test_get_rate_per_period_inverse() -> None:
    rates = {("ZAR", "USD"): [0.05, 0.04]}
    result = _get_rate(rates, "USD", "ZAR")
    assert isinstance(result, list)
    assert abs(result[0] - 20.0) < 1e-9
    assert abs(result[1] - 25.0) < 1e-9


def test_get_rate_missing_with_integrity() -> None:
    integrity: dict = {"warnings": []}
    result = _get_rate({}, "ZAR", "USD", integrity)
    assert result == 1.0
    assert len(integrity["warnings"]) == 1


# ---------------------------------------------------------------------------
# _resolve_rate_for_period
# ---------------------------------------------------------------------------
def test_resolve_scalar() -> None:
    assert _resolve_rate_for_period(1.5, 0) == 1.5
    assert _resolve_rate_for_period(1.5, 99) == 1.5


def test_resolve_list_in_range() -> None:
    assert _resolve_rate_for_period([1.0, 2.0, 3.0], 1) == 2.0


def test_resolve_list_out_of_range() -> None:
    """Out-of-range index returns last element."""
    assert _resolve_rate_for_period([1.0, 2.0], 5) == 2.0


# ---------------------------------------------------------------------------
# _apply_rate_to_series
# ---------------------------------------------------------------------------
def test_apply_scalar_rate() -> None:
    result = _apply_rate_to_series([100.0, 200.0], 0.5)
    assert result == [50.0, 100.0]


def test_apply_per_period_rate() -> None:
    result = _apply_rate_to_series([100.0, 200.0, 300.0], [0.5, 0.6, 0.7])
    assert abs(result[0] - 50.0) < 1e-9
    assert abs(result[1] - 120.0) < 1e-9
    assert abs(result[2] - 210.0) < 1e-9


# ---------------------------------------------------------------------------
# translate_statements: scalar (backward compat)
# ---------------------------------------------------------------------------
def test_translate_scalar_rate() -> None:
    stmts = _make_statements(3, [1000, 2000, 3000], [500, 600, 700])
    avg_rates = {("ZAR", "USD"): 0.05}
    closing_rates = {("ZAR", "USD"): 0.048}
    result = translate_statements(stmts, "ZAR", "USD", avg_rates, closing_rates, 3)
    # Revenue should be translated at avg rate
    is_data = {r["label"]: [r[f"period_{t}"] for t in range(3)] for r in result["income_statement"]}
    assert abs(is_data["revenue"][0] - 50.0) < 1e-9  # 1000 * 0.05
    # BS should be translated at closing rate
    bs_data = {r["label"]: [r[f"period_{t}"] for t in range(3)] for r in result["balance_sheet"]}
    assert abs(bs_data["total_equity"][0] - 24.0) < 1e-9  # 500 * 0.048


# ---------------------------------------------------------------------------
# translate_statements: per-period rates (IAS 21)
# ---------------------------------------------------------------------------
def test_translate_per_period_rates() -> None:
    stmts = _make_statements(3, [1000, 2000, 3000], [500, 600, 700])
    avg_rates = {("ZAR", "USD"): [0.05, 0.06, 0.07]}
    closing_rates = {("ZAR", "USD"): [0.048, 0.058, 0.068]}
    result = translate_statements(stmts, "ZAR", "USD", avg_rates, closing_rates, 3)
    is_data = {r["label"]: [r[f"period_{t}"] for t in range(3)] for r in result["income_statement"]}
    # Revenue: 1000*0.05, 2000*0.06, 3000*0.07
    assert abs(is_data["revenue"][0] - 50.0) < 1e-9
    assert abs(is_data["revenue"][1] - 120.0) < 1e-9
    assert abs(is_data["revenue"][2] - 210.0) < 1e-9
    # BS equity: 500*0.048, 600*0.058, 700*0.068
    bs_data = {r["label"]: [r[f"period_{t}"] for t in range(3)] for r in result["balance_sheet"]}
    assert abs(bs_data["total_equity"][0] - 24.0) < 1e-9
    assert abs(bs_data["total_equity"][1] - 34.8) < 1e-9
    assert abs(bs_data["total_equity"][2] - 47.6) < 1e-9


def test_translate_same_currency_noop() -> None:
    stmts = _make_statements(2, [100, 200], [50, 60])
    result = translate_statements(stmts, "USD", "USD", {}, None, 2)
    assert "translation_reserve" in result


# ---------------------------------------------------------------------------
# consolidate: per-period rates end-to-end
# ---------------------------------------------------------------------------
def test_consolidate_per_period_fx() -> None:
    horizon = 3
    entity = EntityResult(
        entity_id="sub_za",
        currency="ZAR",
        statements=_make_statements(horizon, [1000, 2000, 3000], [500, 600, 700]),
        kpis={},
        ownership_pct=100.0,
        consolidation_method="full",
    )
    avg_rates = {("ZAR", "USD"): [0.05, 0.06, 0.07]}
    closing_rates = {("ZAR", "USD"): [0.048, 0.058, 0.068]}
    result = consolidate(
        entity_results=[entity],
        eliminations=[],
        reporting_currency="USD",
        fx_avg_rates=avg_rates,
        minority_interest_treatment="full",
        horizon=horizon,
        fx_closing_rates=closing_rates,
    )
    assert isinstance(result, ConsolidatedResult)
    # IS revenue should reflect per-period avg rates
    is_rows = result.consolidated_is["income_statement"]
    rev_row = next(r for r in is_rows if r["label"] == "revenue")
    assert abs(rev_row["period_0"] - 50.0) < 1e-9
    assert abs(rev_row["period_1"] - 120.0) < 1e-9


def test_consolidate_scalar_backward_compat() -> None:
    """Scalar rates still work (backward compatibility)."""
    horizon = 2
    entity = EntityResult(
        entity_id="sub_ng",
        currency="NGN",
        statements=_make_statements(horizon, [1000, 2000], [500, 600]),
        kpis={},
        ownership_pct=100.0,
        consolidation_method="full",
    )
    result = consolidate(
        entity_results=[entity],
        eliminations=[],
        reporting_currency="USD",
        fx_avg_rates={("NGN", "USD"): 0.001},
        minority_interest_treatment="full",
        horizon=horizon,
    )
    is_rows = result.consolidated_is["income_statement"]
    rev_row = next(r for r in is_rows if r["label"] == "revenue")
    assert abs(rev_row["period_0"] - 1.0) < 1e-9  # 1000 * 0.001
    assert abs(rev_row["period_1"] - 2.0) < 1e-9  # 2000 * 0.001
