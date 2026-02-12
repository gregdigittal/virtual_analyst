from __future__ import annotations

import time

from fastapi import Request

from shared.fm_shared.metrics import (
    api_request_duration_seconds,
    api_requests_active,
    api_requests_total,
    record_request_latency,
)


async def metrics_middleware(request: Request, call_next):
    api_requests_active.inc()
    start = time.time()

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        status_code = 500
        raise
    finally:
        duration = time.time() - start
        api_requests_active.dec()
        api_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=str(status_code),
        ).inc()
        api_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path,
        ).observe(duration)
        if not request.url.path.startswith("/api/v1/metrics"):
            record_request_latency(request.url.path, duration)

    return response
