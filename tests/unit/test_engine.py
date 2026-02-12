"""Unit tests for time-series engine."""

import pytest

from shared.fm_shared.model import ModelConfig, run_engine
from shared.fm_shared.model.graph import GraphCycleError


def _minimal_config(horizon_months: int = 12) -> ModelConfig:
    """Minimal ModelConfig: two drivers -> one formula -> one output (revenue)."""
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
            "tax_rate": 0.0,
            "initial_cash": 0.0,
            "initial_equity": 1000.0,
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


def test_run_engine_returns_time_series() -> None:
    """run_engine returns dict of node_id -> list[float] with length horizon."""
    config = _minimal_config(horizon_months=6)
    result = run_engine(config)
    assert "n_units" in result
    assert "n_price" in result
    assert "n_revenue" in result
    assert len(result["n_revenue"]) == 6
    assert result["n_units"] == [100.0] * 6
    assert result["n_price"] == [10.0] * 6
    assert result["n_revenue"] == [1000.0] * 6


def test_run_engine_deterministic() -> None:
    """Same config produces same time_series."""
    config = _minimal_config(horizon_months=3)
    r1 = run_engine(config)
    r2 = run_engine(config)
    assert r1 == r2


def test_run_engine_scenario_override() -> None:
    """Scenario overrides change driver values."""
    config = _minimal_config(horizon_months=2)
    from shared.fm_shared.model.schemas import ScenarioOverride

    overrides = [ScenarioOverride(ref="drv:price", field="value", value=20.0)]
    result = run_engine(config, scenario_overrides=overrides)
    assert result["n_price"] == [20.0, 20.0]
    assert result["n_revenue"] == [2000.0, 2000.0]


def test_run_engine_cycle_raises() -> None:
    """Blueprint with cycle raises GraphCycleError (via topo_sort)."""
    config = _minimal_config(horizon_months=1)
    # Build new blueprint with cycle: n_revenue -> n_units (n_units -> n_revenue already exists)
    cyclic_blueprint = {
        "nodes": config.driver_blueprint.model_dump()["nodes"],
        "edges": [
            {"from": "n_units", "to": "n_revenue"},
            {"from": "n_price", "to": "n_revenue"},
            {"from": "n_revenue", "to": "n_units"},
        ],
        "formulas": config.driver_blueprint.model_dump()["formulas"],
    }
    from shared.fm_shared.model.schemas import DriverBlueprint

    config_cyclic = config.model_copy(
        update={"driver_blueprint": DriverBlueprint.model_validate(cyclic_blueprint)}
    )
    with pytest.raises(GraphCycleError):
        run_engine(config_cyclic)
