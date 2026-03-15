"""Sensitivity analysis — single-variable sweeps and two-variable heat maps.

Parallelises independent model runs across CPU cores using ProcessPoolExecutor.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from pydantic import ValidationError

from shared.fm_shared.model import ModelConfig, generate_statements, run_engine
from shared.fm_shared.model.kpis import calculate_kpis

# Minimum number of tasks before switching from sequential to parallel execution.
# Below this threshold, process-spawn overhead outweighs the gains.
_PARALLEL_THRESHOLD = 4


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


_MAX_PATH_DEPTH = 5  # max dot-path segments (real model paths are 2–3 levels deep)
# Non-underscore names that must not be traversed (class introspection, REM-18 / CR-Q9)
_PATH_DENYLIST: frozenset[str] = frozenset({"mro", "bases", "subclasses", "dict", "class"})


def _validate_path(path: str) -> None:
    """Reject paths that could access private/dunder attributes or class internals.

    Guards (REM-18 / CR-Q9):
    - Empty or blank segments rejected
    - Underscore-prefixed segments rejected (blocks __proto__, __class__, _private)
    - Segments in _PATH_DENYLIST rejected (blocks mro, bases, subclasses, dict, class)
    - Non-identifier segments rejected (blocks bracket notation, spaces, injection)
    - Max depth of _MAX_PATH_DEPTH segments enforced
    """
    segments = path.split(".")
    if not segments or not all(segments):
        raise ValueError(f"Invalid parameter path: '{path}'")
    if len(segments) > _MAX_PATH_DEPTH:
        raise ValueError(f"Parameter path too deep (max {_MAX_PATH_DEPTH} segments): '{path}'")
    for segment in segments:
        if segment.startswith("_"):
            raise ValueError(f"Invalid path segment: '{segment}'")
        if segment in _PATH_DENYLIST:
            raise ValueError(f"Denied path segment: '{segment}'")
        if not segment.isidentifier():
            raise ValueError(f"Invalid path segment: '{segment}'")


def _get_nested(obj: object, path: str) -> float:
    """Resolve a dot-path like 'metadata.tax_rate' on a Pydantic model."""
    _validate_path(path)
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
    _validate_path(path)
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
        try:
            setattr(cur, parts[-1], value)
        except (ValidationError, AttributeError, TypeError) as e:
            raise ValueError(
                f"Cannot set '{path}' to {value}: field may be frozen or read-only"
            ) from e


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


# ---------------------------------------------------------------------------
# Process-pool worker functions (must be module-level for pickling)
# ---------------------------------------------------------------------------

def _sweep_worker(args: tuple[dict, str, float, str]) -> float:
    """Compute metric for a single parameter value in a child process."""
    config_dict, parameter_path, value, metric = args
    config = ModelConfig.model_validate(config_dict)
    _set_nested(config, parameter_path, value)
    return _extract_metric(config, metric)


def _heatmap_worker(args: tuple[dict, str, float, str, float, str]) -> float:
    """Compute metric for a single (param_a, param_b) cell in a child process."""
    config_dict, param_a_path, val_a, param_b_path, val_b, metric = args
    config = ModelConfig.model_validate(config_dict)
    _set_nested(config, param_a_path, val_a)
    _set_nested(config, param_b_path, val_b)
    return _extract_metric(config, metric)


def _max_workers(n_tasks: int) -> int:
    """Cap worker count at CPU cores or task count, whichever is smaller."""
    cpus = os.cpu_count() or 4
    return min(n_tasks, cpus)


def _run_sweep_sequential(
    config: ModelConfig, parameter_path: str, values: list[float], metric: str,
) -> list[float]:
    """Run sweep sequentially (used as fallback and for small step counts)."""
    metric_values: list[float] = []
    for v in values:
        cfg = config.model_copy(deep=True)
        _set_nested(cfg, parameter_path, v)
        metric_values.append(_extract_metric(cfg, metric))
    return metric_values


def _run_heatmap_sequential(
    config: ModelConfig,
    param_a_path: str,
    values_a: list[float],
    param_b_path: str,
    values_b: list[float],
    metric: str,
) -> list[list[float]]:
    """Run heatmap sequentially (used as fallback and for small cell counts)."""
    matrix: list[list[float]] = []
    for va in values_a:
        row: list[float] = []
        for vb in values_b:
            cfg = config.model_copy(deep=True)
            _set_nested(cfg, param_a_path, va)
            _set_nested(cfg, param_b_path, vb)
            row.append(round(_extract_metric(cfg, metric), 2))
        matrix.append(row)
    return matrix


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

    if steps >= _PARALLEL_THRESHOLD:
        try:
            config_dict = config.model_dump()
            tasks = [(config_dict, parameter_path, v, metric) for v in values]
            with ProcessPoolExecutor(max_workers=_max_workers(steps)) as pool:
                metric_values = list(pool.map(_sweep_worker, tasks))
        except BrokenProcessPool:
            logger.warning("Process pool crashed during sweep, falling back to sequential")
            metric_values = _run_sweep_sequential(config, parameter_path, values, metric)
    else:
        metric_values = _run_sweep_sequential(config, parameter_path, values, metric)

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

    n_cells = a_steps * b_steps
    if n_cells >= _PARALLEL_THRESHOLD:
        try:
            config_dict = config.model_dump()
            tasks = [
                (config_dict, param_a_path, va, param_b_path, vb, metric)
                for va in values_a
                for vb in values_b
            ]
            with ProcessPoolExecutor(max_workers=_max_workers(n_cells)) as pool:
                flat_results = list(pool.map(_heatmap_worker, tasks))
            # Reshape flat results into matrix[i][j]
            matrix: list[list[float]] = []
            idx = 0
            for _ in values_a:
                matrix.append([round(flat_results[idx + j], 2) for j in range(len(values_b))])
                idx += len(values_b)
        except BrokenProcessPool:
            logger.warning("Process pool crashed during heatmap, falling back to sequential")
            matrix = _run_heatmap_sequential(
                config, param_a_path, values_a, param_b_path, values_b, metric
            )
    else:
        matrix = _run_heatmap_sequential(
            config, param_a_path, values_a, param_b_path, values_b, metric
        )

    return HeatMapResult(
        param_a=param_a_path,
        param_b=param_b_path,
        values_a=[round(v, 10) for v in values_a],
        values_b=[round(v, 10) for v in values_b],
        matrix=matrix,
    )
