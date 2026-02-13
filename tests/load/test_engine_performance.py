"""Performance tests: engine and API latency SLAs (PERFORMANCE_SPEC)."""

from __future__ import annotations

import math
import time

from shared.fm_shared.model import generate_statements, run_engine
from shared.fm_shared.model.kpis import calculate_kpis
from tests.conftest import minimal_model_config

# PERFORMANCE_SPEC: Engine 12mo P95 500ms
ENGINE_12MO_P95_MS = 500


def test_engine_12mo_under_p95() -> None:
    """Deterministic 12-month run completes within P95 SLA (500ms)."""
    config = minimal_model_config(tenant_id="t_perf")
    runs = 20
    timings = []
    for _ in range(runs):
        t0 = time.perf_counter()
        run_engine(config)
        timings.append((time.perf_counter() - t0) * 1000)
    sorted_timings = sorted(timings)
    p95_idx = int(math.ceil(len(sorted_timings) * 0.95)) - 1
    p95 = sorted_timings[p95_idx]
    assert p95 < ENGINE_12MO_P95_MS, (
        f"Engine 12mo run exceeded P95 {ENGINE_12MO_P95_MS}ms: p95={p95:.1f}ms"
    )


def test_engine_plus_statements_plus_kpis_12mo_under_1s() -> None:
    """Full pipeline (engine + statements + KPIs) 12mo completes within 1s."""
    config = minimal_model_config(tenant_id="t_perf")
    t0 = time.perf_counter()
    time_series = run_engine(config)
    statements = generate_statements(config, time_series)
    calculate_kpis(statements)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 1000, f"Full pipeline 12mo exceeded 1s: {elapsed_ms:.1f}ms"
