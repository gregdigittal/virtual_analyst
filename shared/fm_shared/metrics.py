from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, make_asgi_app


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
