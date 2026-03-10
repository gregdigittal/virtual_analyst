"""
Monte Carlo runner: sample distributions, run engine per sim, aggregate percentiles.

REM-07 / CR-T1: Uses ProcessPoolExecutor for parallel simulation when num_simulations
exceeds PARALLEL_THRESHOLD. Falls back to sequential loop for small runs.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from shared.fm_shared.analysis.distributions import sample, sample_correlated
from shared.fm_shared.model.engine import run_engine
from shared.fm_shared.model.kpis import calculate_kpis
from shared.fm_shared.model.schemas import ModelConfig, ScenarioOverride
from shared.fm_shared.model.statements import generate_statements

PERCENTILE_LEVELS = (5, 10, 25, 50, 75, 90, 95)
METRIC_KEYS = ("revenue", "ebitda", "net_income", "fcf")

# Parallelism thresholds
PARALLEL_THRESHOLD = 50  # Use ProcessPool above this count
MAX_WORKERS = min(os.cpu_count() or 4, 8)  # Cap at 8 workers


@dataclass
class MCResult:
    """Result of a Monte Carlo run: percentiles per metric per period."""

    num_simulations: int
    seed: int
    percentiles: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    summary: dict = field(default_factory=dict)


MAX_SIMULATIONS = 10_000


def _run_single_sim(args: tuple) -> dict[str, list[float]]:
    """Run a single MC simulation. Designed to be picklable for ProcessPoolExecutor.

    Args is a tuple of (config_dict, overrides_dicts, scenario_overrides_dicts, horizon).
    Returns dict with revenue, ebitda, net_income, fcf series.
    """
    config_dict, overrides_dicts, scenario_overrides_dicts, horizon = args
    config = ModelConfig.model_validate(config_dict)
    overrides = [ScenarioOverride(**o) for o in overrides_dicts]
    if scenario_overrides_dicts:
        overrides.extend(ScenarioOverride(**o) for o in scenario_overrides_dicts)

    time_series = run_engine(config, scenario_overrides=overrides or None)
    statements = generate_statements(config, time_series)
    kpis = calculate_kpis(statements)

    return {
        "revenue": [statements.income_statement[t]["revenue"] for t in range(horizon)],
        "ebitda": [statements.income_statement[t]["ebitda"] for t in range(horizon)],
        "net_income": [statements.income_statement[t]["net_income"] for t in range(horizon)],
        "fcf": [kpis[t]["fcf"] for t in range(horizon)],
    }


def _prepare_sim_args(
    config: ModelConfig,
    rng: np.random.Generator,
    scenario_overrides: list[ScenarioOverride],
) -> list[dict[str, Any]]:
    """Sample distributions and return override dicts (picklable)."""
    overrides: list[dict[str, Any]] = []
    if config.correlation_matrix and len(config.distributions) > 1:
        sampled = sample_correlated(
            config.distributions, config.correlation_matrix, rng
        )
        overrides = [
            {"ref": ref, "field": "value", "value": val}
            for ref, val in sampled.items()
        ]
    else:
        for dist in config.distributions:
            val = sample(dist, 1, rng)[0]
            overrides.append(
                {"ref": dist.ref, "field": "value", "value": float(val)}
            )
    return overrides


def run_monte_carlo(
    config: ModelConfig,
    num_simulations: int,
    seed: int,
    scenario_id: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> MCResult:
    """
    Run num_simulations with seeded RNG. For each sim: sample distributions into
    scenario overrides, run engine + statements + KPIs, collect revenue/ebitda/net_income/fcf.
    Returns percentiles (P5..P95) per metric per period and optional summary.
    progress_callback(sims_done, total) is called periodically for async progress reporting.

    REM-07: Uses ProcessPoolExecutor for num_simulations > PARALLEL_THRESHOLD.
    """
    if num_simulations > MAX_SIMULATIONS:
        raise ValueError(f"num_simulations must be <= {MAX_SIMULATIONS}")
    rng = np.random.default_rng(seed)
    horizon = config.metadata.horizon_months

    scenario_overrides: list[ScenarioOverride] = []
    if scenario_id:
        for sc in config.scenarios:
            if sc.scenario_id == scenario_id:
                scenario_overrides = list(sc.overrides)
                break

    # Pre-sample all override sets (sampling must be sequential for RNG determinism)
    config_dict = config.model_dump()
    scenario_overrides_dicts = [{"ref": o.ref, "field": o.field, "value": o.value} for o in scenario_overrides]
    all_sim_args: list[tuple] = []
    for _ in range(num_simulations):
        overrides_dicts = _prepare_sim_args(config, rng, scenario_overrides)
        all_sim_args.append((config_dict, overrides_dicts, scenario_overrides_dicts, horizon))

    # Execute simulations
    revenue_sims: list[list[float]] = []
    ebitda_sims: list[list[float]] = []
    net_income_sims: list[list[float]] = []
    fcf_sims: list[list[float]] = []

    use_parallel = num_simulations > PARALLEL_THRESHOLD and MAX_WORKERS > 1

    if use_parallel:
        report_every = max(1, num_simulations // 20) if progress_callback else 0
        done = 0
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for result in executor.map(_run_single_sim, all_sim_args):
                revenue_sims.append(result["revenue"])
                ebitda_sims.append(result["ebitda"])
                net_income_sims.append(result["net_income"])
                fcf_sims.append(result["fcf"])
                done += 1
                if progress_callback and report_every and done % report_every == 0:
                    progress_callback(done, num_simulations)
    else:
        # Sequential fallback for small sim counts (avoids process overhead)
        report_every = max(1, num_simulations // 20) if progress_callback else 0
        for sim_i, sim_args in enumerate(all_sim_args):
            if progress_callback and report_every and (sim_i + 1) % report_every == 0:
                progress_callback(sim_i + 1, num_simulations)
            result = _run_single_sim(sim_args)
            revenue_sims.append(result["revenue"])
            ebitda_sims.append(result["ebitda"])
            net_income_sims.append(result["net_income"])
            fcf_sims.append(result["fcf"])

    if progress_callback:
        progress_callback(num_simulations, num_simulations)

    def percentile_series(sims: list[list[float]]) -> dict[str, list[float]]:
        arr = np.array(sims)
        out: dict[str, list[float]] = {}
        for q in PERCENTILE_LEVELS:
            out[f"p{q}"] = np.percentile(arr, q, axis=0).tolist()
        return out

    percentiles: dict[str, dict[str, list[float]]] = {
        "revenue": percentile_series(revenue_sims),
        "ebitda": percentile_series(ebitda_sims),
        "net_income": percentile_series(net_income_sims),
        "fcf": percentile_series(fcf_sims),
    }

    summary: dict = {}
    if horizon > 0:
        last = horizon - 1
        summary = {
            "terminal_revenue": {
                f"p{q}": percentiles["revenue"][f"p{q}"][last] for q in PERCENTILE_LEVELS
            },
            "terminal_fcf": {
                f"p{q}": percentiles["fcf"][f"p{q}"][last] for q in PERCENTILE_LEVELS
            },
        }

    return MCResult(
        num_simulations=num_simulations,
        seed=seed,
        percentiles=percentiles,
        summary=summary,
    )
