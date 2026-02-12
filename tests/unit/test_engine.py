"""Unit tests for time-series engine."""

import pytest

from shared.fm_shared.model import run_engine
from shared.fm_shared.model.graph import GraphCycleError
from tests.conftest import minimal_model_config


def test_run_engine_returns_time_series() -> None:
    """run_engine returns dict of node_id -> list[float] with length horizon."""
    config = minimal_model_config(horizon_months=6)
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
    config = minimal_model_config(horizon_months=3)
    r1 = run_engine(config)
    r2 = run_engine(config)
    assert r1 == r2


def test_run_engine_scenario_override() -> None:
    """Scenario overrides change driver values."""
    config = minimal_model_config(horizon_months=2)
    from shared.fm_shared.model.schemas import ScenarioOverride

    overrides = [ScenarioOverride(ref="drv:price", field="value", value=20.0)]
    result = run_engine(config, scenario_overrides=overrides)
    assert result["n_price"] == [20.0, 20.0]
    assert result["n_revenue"] == [2000.0, 2000.0]


def test_run_engine_cycle_raises() -> None:
    """Blueprint with cycle raises GraphCycleError (via topo_sort)."""
    config = minimal_model_config(horizon_months=1)
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
