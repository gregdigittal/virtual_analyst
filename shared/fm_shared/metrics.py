from __future__ import annotations

import math
from collections import deque
from threading import Lock

from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

# In-memory ring buffer for latency summary (last N requests)
_LATENCY_BUFFER_SIZE = 1000
_latency_buffer: deque[tuple[str, float]] = deque(maxlen=_LATENCY_BUFFER_SIZE)
_latency_lock = Lock()


def record_request_latency(path: str, duration_seconds: float) -> None:
    """Record a request for latency summary (used by dashboard)."""
    with _latency_lock:
        _latency_buffer.append((path, duration_seconds))


def get_latency_summary() -> dict:
    """Return request count and p50/p95 latency in ms for dashboard."""
    with _latency_lock:
        if not _latency_buffer:
            return {
                "request_count": 0,
                "latency_p50_ms": 0,
                "latency_p95_ms": 0,
                "by_endpoint": {},
            }
        items = list(_latency_buffer)
    n = len(items)
    sorted_durations = sorted(d[1] for d in items)
    p50 = sorted_durations[min(int(math.ceil(n * 0.5)) - 1, n - 1)] * 1000 if n else 0
    p95 = sorted_durations[min(int(math.ceil(n * 0.95)) - 1, n - 1)] * 1000 if n else 0
    by_endpoint: dict[str, list[float]] = {}
    for path, dur in items:
        by_endpoint.setdefault(path, []).append(dur * 1000)
    return {
        "request_count": n,
        "latency_p50_ms": round(p50, 2),
        "latency_p95_ms": round(p95, 2),
        "by_endpoint": {k: round(sum(v) / len(v), 2) for k, v in by_endpoint.items()},
    }


api_requests_total = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status_code"],
)

api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "API request duration",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30],
)

api_requests_active = Gauge(
    "api_requests_active",
    "Currently active API requests",
)

metrics_app = make_asgi_app()
