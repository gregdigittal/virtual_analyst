"""Unit tests for time-series engine."""

import pytest

from shared.fm_shared.model import run_engine
from shared.fm_shared.model.graph import GraphCycleError
from shared.fm_shared.model.schemas import ModelConfig
from tests.conftest import minimal_model_config, minimal_model_config_dict


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


def _make_config_without_launch() -> ModelConfig:
    """Config with no launch_month (backward compat)."""
    d = minimal_model_config_dict(horizon_months=12)
    return ModelConfig.model_validate(d)


def _make_config_with_launch(
    launch_month: int | None,
    ramp_up_months: int | None = None,
    ramp_curve: str = "linear",
) -> ModelConfig:
    """Config with one revenue stream and optional launch/ramp."""
    d = minimal_model_config_dict(horizon_months=12)
    rs = d["assumptions"]["revenue_streams"][0]
    # Move price from volume to pricing so ramp only scales volume
    rs["drivers"]["volume"] = [
        dv for dv in rs["drivers"]["volume"] if "price" not in dv["ref"]
    ]
    rs["drivers"]["pricing"] = [
        {"ref": "drv:price", "value_type": "constant", "value": 10.0}
    ]
    rs["launch_month"] = launch_month
    rs["ramp_up_months"] = ramp_up_months
    rs["ramp_curve"] = ramp_curve
    return ModelConfig.model_validate(d)


def test_launch_month_zeros_pre_launch() -> None:
    """Revenue stream with launch_month=6 produces zero revenue before month 6."""
    config = _make_config_with_launch(launch_month=6, ramp_up_months=None)
    ts = run_engine(config)
    rev = ts["n_revenue"]
    for t in range(6):
        assert rev[t] == 0.0, f"Period {t} should be 0 before launch"
    for t in range(6, 12):
        assert rev[t] > 0.0, f"Period {t} should have revenue after launch"


def test_linear_ramp_up() -> None:
    """Revenue ramps linearly over ramp_up_months after launch_month."""
    config = _make_config_with_launch(launch_month=3, ramp_up_months=6, ramp_curve="linear")
    ts = run_engine(config)
    rev = ts["n_revenue"]
    for t in range(3):
        assert rev[t] == 0.0
    full_rev = rev[9]
    assert full_rev > 0
    for i, t in enumerate(range(3, 9)):
        expected_factor = (i + 1) / 6
        assert abs(rev[t] - full_rev * expected_factor) < 0.01, (
            f"Period {t}: expected factor {expected_factor}, got {rev[t]/full_rev:.3f}"
        )


def test_s_curve_ramp() -> None:
    """S-curve ramp produces values between 0 and 1, monotonically increasing."""
    config = _make_config_with_launch(launch_month=0, ramp_up_months=6, ramp_curve="s_curve")
    ts = run_engine(config)
    rev = ts["n_revenue"]
    for t in range(1, 6):
        assert rev[t] >= rev[t - 1], f"Period {t} should be >= period {t-1}"
    assert rev[0] < rev[5]


def test_step_ramp() -> None:
    """Step ramp: zero during ramp, full at end of ramp."""
    config = _make_config_with_launch(launch_month=2, ramp_up_months=4, ramp_curve="step")
    ts = run_engine(config)
    rev = ts["n_revenue"]
    for t in range(6):
        assert rev[t] == 0.0
    assert rev[6] > 0


def test_no_launch_month_unchanged() -> None:
    """Stream without launch_month behaves normally (backward compat)."""
    config1 = _make_config_without_launch()
    config2 = _make_config_with_launch(launch_month=None, ramp_up_months=None)
    ts1 = run_engine(config1)
    ts2 = run_engine(config2)
    assert ts1["n_revenue"] == ts2["n_revenue"]
