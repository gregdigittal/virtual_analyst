"""Unit tests for KPI calculator."""

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.kpis import calculate_kpis


def _minimal_config(horizon_months: int = 12) -> ModelConfig:
    """Minimal ModelConfig for KPI tests."""
    data = {
        "artifact_type": "model_config_v1",
        "artifact_version": "1.0.0",
        "tenant_id": "t_test",
        "baseline_id": "bl_test",
        "baseline_version": "v1",
        "created_at": "2026-01-01T00:00:00Z",
        "metadata": {
            "entity_name": "Test",
            "currency": "USD",
            "start_date": "2026-01-01",
            "horizon_months": horizon_months,
            "tax_rate": 0.25,
            "initial_cash": 50_000.0,
            "initial_equity": 100_000.0,
        },
        "assumptions": {
            "revenue_streams": [
                {
                    "stream_id": "rs1",
                    "label": "Revenue",
                    "stream_type": "unit_sale",
                    "drivers": {
                        "volume": [
                            {"ref": "drv:units", "value_type": "constant", "value": 100.0},
                            {"ref": "drv:price", "value_type": "constant", "value": 10.0},
                        ],
                        "pricing": [],
                        "direct_costs": [],
                    },
                }
            ],
            "cost_structure": {"variable_costs": [], "fixed_costs": []},
            "working_capital": {
                "ar_days": {"ref": "drv:ar_days", "value_type": "constant", "value": 30.0},
                "ap_days": {"ref": "drv:ap_days", "value_type": "constant", "value": 30.0},
                "inv_days": {"ref": "drv:inv_days", "value_type": "constant", "value": 30.0},
            },
        },
        "driver_blueprint": {
            "nodes": [
                {"node_id": "n_units", "type": "driver", "label": "Units", "ref": "drv:units"},
                {"node_id": "n_price", "type": "driver", "label": "Price", "ref": "drv:price"},
                {"node_id": "n_revenue", "type": "output", "label": "Revenue"},
            ],
            "edges": [
                {"from": "n_units", "to": "n_revenue"},
                {"from": "n_price", "to": "n_revenue"},
            ],
            "formulas": [
                {
                    "formula_id": "f_rev",
                    "output_node_id": "n_revenue",
                    "expression": "units * price",
                    "inputs": ["drv:units", "drv:price"],
                }
            ],
        },
        "scenarios": [],
        "integrity": {"status": "passed", "checks": []},
    }
    return ModelConfig.model_validate(data)


def test_calculate_kpis_returns_list() -> None:
    """calculate_kpis returns one dict per period."""
    config = _minimal_config(horizon_months=3)
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    kpis = calculate_kpis(statements)
    assert len(kpis) == 3


def test_calculate_kpis_keys() -> None:
    """KPI dicts include gross_margin_pct, ebitda_margin_pct, net_margin_pct, revenue_growth_pct, current_ratio, roe, fcf, cash_conversion_cycle."""
    config = _minimal_config(horizon_months=2)
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
    config = _minimal_config(horizon_months=1)
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    kpis = calculate_kpis(statements)
    assert "cash_conversion_cycle" in kpis[0]
    # With 30 days AR/AP/Inv, CCC = 30 + 30 - 30 = 30
    assert kpis[0]["cash_conversion_cycle"] == 30.0


def test_calculate_kpis_margins_with_revenue() -> None:
    """With revenue 1000 and no COGS, gross_margin_pct is 100."""
    config = _minimal_config(horizon_months=1)
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    kpis = calculate_kpis(statements)
    assert kpis[0]["gross_margin_pct"] == 100.0
