"""Sensitivity analysis — single-variable sweeps and two-variable heat maps."""

from __future__ import annotations

from dataclasses import dataclass

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.kpis import calculate_kpis


@dataclass
class SensitivityResult:
    parameter: str
    base_value: float
    values: list[float]
    metric_values: list[float]


@dataclass
class HeatMapResult:
    param_a: str
    param_b: str
    values_a: list[float]
    values_b: list[float]
    matrix: list[list[float]]  # matrix[i][j] = metric at (values_a[i], values_b[j])


def _get_nested(obj: object, path: str) -> float:
    """Resolve a dot-path like 'metadata.tax_rate' on a Pydantic model."""
    parts = path.split(".")
    cur: object = obj
    for p in parts:
        if isinstance(cur, dict):
            cur = cur[p]
        else:
            cur = getattr(cur, p)
    return float(cur)  # type: ignore[arg-type]


def _set_nested(obj: object, path: str, value: float) -> None:
    """Set a value at a dot-path on a Pydantic model (mutates in place)."""
    parts = path.split(".")
    cur: object = obj
    for p in parts[:-1]:
        if isinstance(cur, dict):
            cur = cur[p]
        else:
            cur = getattr(cur, p)
    if isinstance(cur, dict):
        cur[parts[-1]] = value
    else:
        setattr(cur, parts[-1], value)


_TERMINAL_METRICS = {
    "revenue": lambda is_list, _kpis: sum(p["revenue"] for p in is_list),
    "ebitda": lambda is_list, _kpis: sum(p["ebitda"] for p in is_list),
    "net_income": lambda is_list, _kpis: sum(p["net_income"] for p in is_list),
    "fcf": lambda _is_list, kpis: sum(p["fcf"] for p in kpis),
}


def _extract_metric(config: ModelConfig, metric: str) -> float:
    """Run engine + statements + kpis and extract the summed metric."""
    ts = run_engine(config)
    stmts = generate_statements(config, ts)
    kpis = calculate_kpis(stmts)
    return _TERMINAL_METRICS[metric](stmts.income_statement, kpis)


def run_sensitivity(
    config: ModelConfig,
    parameter_path: str,
    low: float,
    high: float,
    steps: int,
    metric: str,
) -> SensitivityResult:
    """Sweep one parameter from low to high and record metric output at each step."""
    if metric not in _TERMINAL_METRICS:
        raise ValueError(f"Unknown metric '{metric}'. Valid: {list(_TERMINAL_METRICS)}")
    if steps < 2:
        raise ValueError("steps must be >= 2")

    base_value = _get_nested(config, parameter_path)
    step_size = (high - low) / (steps - 1)
    values: list[float] = [low + i * step_size for i in range(steps)]
    metric_values: list[float] = []

    for v in values:
        cfg = config.model_copy(deep=True)
        _set_nested(cfg, parameter_path, v)
        metric_values.append(_extract_metric(cfg, metric))

    return SensitivityResult(
        parameter=parameter_path,
        base_value=base_value,
        values=[round(v, 10) for v in values],
        metric_values=[round(m, 2) for m in metric_values],
    )


def run_heatmap(
    config: ModelConfig,
    param_a_path: str,
    param_a_range: tuple[float, float, int],
    param_b_path: str,
    param_b_range: tuple[float, float, int],
    metric: str,
) -> HeatMapResult:
    """Sweep two parameters and build a metric matrix."""
    if metric not in _TERMINAL_METRICS:
        raise ValueError(f"Unknown metric '{metric}'. Valid: {list(_TERMINAL_METRICS)}")

    a_low, a_high, a_steps = param_a_range
    b_low, b_high, b_steps = param_b_range
    if a_steps < 2 or b_steps < 2:
        raise ValueError("steps must be >= 2 for both parameters")

    a_step = (a_high - a_low) / (a_steps - 1)
    b_step = (b_high - b_low) / (b_steps - 1)
    values_a = [a_low + i * a_step for i in range(a_steps)]
    values_b = [b_low + j * b_step for j in range(b_steps)]

    matrix: list[list[float]] = []
    for va in values_a:
        row: list[float] = []
        for vb in values_b:
            cfg = config.model_copy(deep=True)
            _set_nested(cfg, param_a_path, va)
            _set_nested(cfg, param_b_path, vb)
            row.append(round(_extract_metric(cfg, metric), 2))
        matrix.append(row)

    return HeatMapResult(
        param_a=param_a_path,
        param_b=param_b_path,
        values_a=[round(v, 10) for v in values_a],
        values_b=[round(v, 10) for v in values_b],
        matrix=matrix,
    )
