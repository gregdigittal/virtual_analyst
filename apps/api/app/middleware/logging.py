from __future__ import annotations

import uuid

import structlog
from fastapi import Request

from shared.fm_shared.logging import correlation_id_var, tenant_id_var, user_id_var


logger = structlog.get_logger()


async def logging_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    tenant_id = request.headers.get("X-Tenant-Id", "")
    user_id = request.headers.get("X-User-Id", "")

    correlation_id_var.set(correlation_id)
    tenant_id_var.set(tenant_id)
    user_id_var.set(user_id)

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else "",
    )

    request.state.request_id = correlation_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = correlation_id

    return response
