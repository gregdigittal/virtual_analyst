"""
Monte Carlo runner: sample distributions, run engine per sim, aggregate percentiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from shared.fm_shared.analysis.distributions import sample, sample_correlated
from shared.fm_shared.model.engine import run_engine
from shared.fm_shared.model.kpis import calculate_kpis
from shared.fm_shared.model.schemas import ModelConfig, ScenarioOverride
from shared.fm_shared.model.statements import generate_statements

PERCENTILE_LEVELS = (5, 10, 25, 50, 75, 90, 95)
METRIC_KEYS = ("revenue", "ebitda", "net_income", "fcf")


@dataclass
class MCResult:
    """Result of a Monte Carlo run: percentiles per metric per period."""

    num_simulations: int
    seed: int
    percentiles: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    summary: dict = field(default_factory=dict)


MAX_SIMULATIONS = 10_000


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

    # Collect per-sim series: [sim][period] for each metric
    revenue_sims: list[list[float]] = []
    ebitda_sims: list[list[float]] = []
    net_income_sims: list[list[float]] = []
    fcf_sims: list[list[float]] = []

    report_every = max(1, num_simulations // 20) if progress_callback else 0

    for sim_i in range(num_simulations):
        if progress_callback and (sim_i + 1) % report_every == 0:
            progress_callback(sim_i + 1, num_simulations)
        overrides: list[ScenarioOverride] = []
        if config.correlation_matrix and len(config.distributions) > 1:
            sampled = sample_correlated(
                config.distributions, config.correlation_matrix, rng
            )
            overrides = [
                ScenarioOverride(ref=ref, field="value", value=val)
                for ref, val in sampled.items()
            ]
        else:
            for dist in config.distributions:
                val = sample(dist, 1, rng)[0]
                overrides.append(
                    ScenarioOverride(ref=dist.ref, field="value", value=float(val))
                )
        overrides.extend(scenario_overrides)

        time_series = run_engine(config, scenario_overrides=overrides or None)
        statements = generate_statements(config, time_series)
        kpis = calculate_kpis(statements)

        rev = [statements.income_statement[t]["revenue"] for t in range(horizon)]
        ebitda = [statements.income_statement[t]["ebitda"] for t in range(horizon)]
        ni = [statements.income_statement[t]["net_income"] for t in range(horizon)]
        fcf = [kpis[t]["fcf"] for t in range(horizon)]

        revenue_sims.append(rev)
        ebitda_sims.append(ebitda)
        net_income_sims.append(ni)
        fcf_sims.append(fcf)

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
