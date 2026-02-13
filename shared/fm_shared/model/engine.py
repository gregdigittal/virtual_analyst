"""
Deterministic time-series engine.
Given model_config + optional scenario overrides, produces time-series for all nodes.
"""

from __future__ import annotations

import copy

import structlog

from shared.fm_shared.errors import EngineError
from shared.fm_shared.model.evaluator import EvalError, evaluate
from shared.fm_shared.model.graph import CalcGraph
from shared.fm_shared.model.schemas import (
    Assumptions,
    DriverValue,
    ModelConfig,
    ScenarioOverride,
)

logger = structlog.get_logger()


def _ref_to_var(s: str) -> str:
    if s.startswith("drv:"):
        return s[4:]
    if s.startswith("n_"):
        return s[2:]
    return s


def _resolve_driver(driver: DriverValue, t: int) -> float:
    if driver.value_type == "constant":
        return float(driver.value or 0)
    if driver.value_type == "ramp" and driver.schedule:
        return _interpolate_schedule(driver.schedule, t, driver.interpolation == "linear")
    if driver.value_type == "step" and driver.schedule:
        return _step_schedule(driver.schedule, t)
    if (
        driver.value_type == "seasonal"
        and driver.seasonal_factors
        and len(driver.seasonal_factors) >= 12
    ):
        base = float(driver.value or 0)
        idx = t % 12
        return base * driver.seasonal_factors[idx]
    return float(driver.value or 0)


def _interpolate_schedule(schedule: list, t: int, linear: bool) -> float:
    points = sorted([(p.month, p.value) for p in schedule], key=lambda x: x[0])
    if not points:
        return 0.0
    if t <= points[0][0]:
        return float(points[0][1])
    if t >= points[-1][0]:
        return float(points[-1][1])
    for i in range(len(points) - 1):
        m0, v0 = points[i]
        m1, v1 = points[i + 1]
        if m0 <= t <= m1:
            if linear:
                frac = (t - m0) / (m1 - m0) if m1 != m0 else 0
                return v0 + frac * (v1 - v0)
            return float(v0)
    return float(points[-1][1])


def _step_schedule(schedule: list, t: int) -> float:
    points = sorted([(p.month, p.value) for p in schedule], key=lambda x: x[0])
    if not points:
        return 0.0
    out = points[0][1]
    for m, v in points:
        if t >= m:
            out = v
    return float(out)


def _collect_driver_values_by_ref(assumptions: Assumptions) -> dict[str, DriverValue]:
    by_ref: dict[str, DriverValue] = {}
    for rs in assumptions.revenue_streams:
        for d in rs.drivers.volume + rs.drivers.pricing + rs.drivers.direct_costs:
            by_ref[d.ref] = d
    for item in assumptions.cost_structure.variable_costs + assumptions.cost_structure.fixed_costs:
        by_ref[item.driver.ref] = item.driver
    by_ref[assumptions.working_capital.ar_days.ref] = assumptions.working_capital.ar_days
    by_ref[assumptions.working_capital.ap_days.ref] = assumptions.working_capital.ap_days
    by_ref[assumptions.working_capital.inv_days.ref] = assumptions.working_capital.inv_days
    return by_ref


def run_engine(
    config: ModelConfig,
    scenario_overrides: list[ScenarioOverride] | None = None,
) -> dict[str, list[float]]:
    """
    Run deterministic time-series engine.
    Returns time_series: { node_id or ref: [v0, v1, ...] } for horizon_months.
    """
    assumptions = copy.deepcopy(config.assumptions)
    if scenario_overrides:
        drivers_by_ref = _collect_driver_values_by_ref(assumptions)
        for ov in scenario_overrides:
            if ov.ref not in drivers_by_ref:
                continue
            d = drivers_by_ref[ov.ref]
            if ov.field == "value":
                d.value = ov.value
                d.value_type = "constant"
                d.schedule = None
            elif ov.field == "multiplier" and d.value_type == "constant" and d.value is not None:
                d.value = d.value * ov.value

    horizon = config.metadata.horizon_months
    graph = CalcGraph.from_blueprint(config.driver_blueprint)
    order = graph.topo_sort()
    drivers_by_ref = _collect_driver_values_by_ref(assumptions)
    ref_to_node: dict[str, str] = {
        node.ref: node.node_id for node in graph.nodes.values() if getattr(node, "ref", None)
    }

    time_series: dict[str, list[float]] = {nid: [0.0] * horizon for nid in graph.nodes}

    def input_to_var_and_key(inp: str) -> tuple[str, str]:
        if inp in graph.nodes:
            node = graph.nodes[inp]
            var_name = (
                (node.ref or inp)[4:]
                if (node.ref and node.ref.startswith("drv:"))
                else (_ref_to_var(inp))
            )
            key = inp
        elif inp in ref_to_node:
            key = ref_to_node[inp]
            var_name = inp[4:] if inp.startswith("drv:") else inp
        else:
            key = inp
            var_name = _ref_to_var(inp)
        return var_name, key

    for t in range(horizon):
        for nid in order:
            node = graph.nodes[nid]
            if node.type == "driver":
                ref = node.ref
                if ref and ref in drivers_by_ref:
                    val = _resolve_driver(drivers_by_ref[ref], t)
                else:
                    val = 0.0
                time_series[nid][t] = val
            else:
                formula = graph.formulas_by_output.get(nid)
                if not formula:
                    time_series[nid][t] = 0.0
                    continue
                variables: dict[str, float] = {}
                try:
                    for inp in formula.inputs:
                        var_name, key = input_to_var_and_key(inp)
                        variables[var_name] = time_series[key][t]
                except KeyError as e:
                    raise EngineError(
                        f"Formula input '{e.args[0] if e.args else '?'}' not found in time_series for node '{nid}' at period {t}"
                    ) from e
                try:
                    time_series[nid][t] = evaluate(formula.expression, variables)
                except EvalError as e:
                    logger.warning(
                        "formula_eval_fallback",
                        node_id=nid,
                        period=t,
                        expression=formula.expression,
                        error=str(e),
                    )
                    time_series[nid][t] = 0.0

    return time_series
