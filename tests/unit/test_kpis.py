"""Unit tests for KPI calculator."""

from shared.fm_shared.model import generate_statements, run_engine
from shared.fm_shared.model.kpis import calculate_kpis
from tests.conftest import minimal_model_config


def test_calculate_kpis_returns_list() -> None:
    """calculate_kpis returns one dict per period."""
    config = minimal_model_config(
        horizon_months=3, tax_rate=0.25, initial_cash=50_000.0, initial_equity=100_000.0
    )
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    kpis = calculate_kpis(statements)
    assert len(kpis) == 3


def test_calculate_kpis_keys() -> None:
    """KPI dicts include gross_margin_pct, ebitda_margin_pct, net_margin_pct, revenue_growth_pct, current_ratio, roe, fcf, cash_conversion_cycle."""
    config = minimal_model_config(
        horizon_months=2, tax_rate=0.25, initial_cash=50_000.0, initial_equity=100_000.0
    )
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    kpis = calculate_kpis(statements)
    row = kpis[0]
    assert "gross_margin_pct" in row
    assert "ebitda_margin_pct" in row
    assert "net_margin_pct" in row
    assert "revenue_growth_pct" in row
    assert "current_ratio" in row
    assert "roe" in row
    assert "fcf" in row
    assert "cash_conversion_cycle" in row


def test_calculate_kpis_cash_conversion_cycle() -> None:
    """CCC is computed (DSO + DIO - DPO) and present in output."""
    config = minimal_model_config(
        horizon_months=1, tax_rate=0.25, initial_cash=50_000.0, initial_equity=100_000.0
    )
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    kpis = calculate_kpis(statements)
    assert "cash_conversion_cycle" in kpis[0]
    # With 30 days AR/AP/Inv, CCC = 30 + 30 - 30 = 30
    assert kpis[0]["cash_conversion_cycle"] == 30.0


def test_calculate_kpis_margins_with_revenue() -> None:
    """With revenue 1000 and no COGS, gross_margin_pct is 100."""
    config = minimal_model_config(
        horizon_months=1, tax_rate=0.25, initial_cash=50_000.0, initial_equity=100_000.0
    )
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    kpis = calculate_kpis(statements)
    assert kpis[0]["gross_margin_pct"] == 100.0
