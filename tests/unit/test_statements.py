"""Unit tests for three-statement generator."""

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.statements import Statements


def _minimal_config(horizon_months: int = 12) -> ModelConfig:
    """Minimal ModelConfig for statement generation (revenue only, no COGS)."""
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


def test_generate_statements_returns_three_lists() -> None:
    """generate_statements returns Statements with IS, BS, CF and periods."""
    config = _minimal_config(horizon_months=3)
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    assert isinstance(st, Statements)
    assert len(st.income_statement) == 3
    assert len(st.balance_sheet) == 3
    assert len(st.cash_flow) == 3
    assert len(st.periods) == 3


def test_generate_statements_income_statement_keys() -> None:
    """Income statement rows have expected keys (revenue, cogs, gross_profit, ebitda, net_income, etc.)."""
    config = _minimal_config(horizon_months=2)
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    row = st.income_statement[0]
    assert "revenue" in row
    assert "cogs" in row
    assert "gross_profit" in row
    assert "ebitda" in row
    assert "net_income" in row
    assert row["revenue"] == 1000.0
    assert row["cogs"] == 0.0
    assert row["gross_profit"] == 1000.0


def test_generate_statements_balance_sheet_keys() -> None:
    """Balance sheet rows have total_current_assets, total_equity, cash, etc."""
    config = _minimal_config(horizon_months=2)
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    row = st.balance_sheet[0]
    assert "total_current_assets" in row
    assert "total_liabilities" in row
    assert "total_equity" in row
    assert "cash" in row
    assert "accounts_receivable" in row
    assert "inventory" in row
    assert "accounts_payable" in row


def test_generate_statements_cash_flow_keys() -> None:
    """Cash flow rows have operating, investing, financing, net_cf, closing_cash."""
    config = _minimal_config(horizon_months=2)
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    row = st.cash_flow[0]
    assert "operating" in row
    assert "investing" in row
    assert "financing" in row
    assert "net_cf" in row
    assert "closing_cash" in row


def test_generate_statements_periods() -> None:
    """periods list has one string per horizon (e.g. period labels)."""
    config = _minimal_config(horizon_months=4)
    time_series = run_engine(config)
    st = generate_statements(config, time_series)
    assert len(st.periods) == 4
