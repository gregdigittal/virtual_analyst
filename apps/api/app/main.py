from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import traceback

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.app.core.settings import get_settings
from apps.api.app.db.connection import close_pool, init_pool
from apps.api.app.middleware.auth import auth_middleware
from apps.api.app.middleware.logging import logging_middleware
from apps.api.app.middleware.metrics import metrics_middleware
from apps.api.app.middleware.security import init_rate_limiting, security_headers_middleware
from apps.api.app.routers import activity, afs, assignments, audit, auth_saml, baselines, benchmark, billing, board_pack_schedules, board_packs, budgets, changesets, comments, compliance, connectors, covenants, currency, documents, drafts, excel, excel_ingestion, feedback, health, import_csv, integrations, jobs, marketplace, memos, metrics_summary, notifications, org_structures, pim_sentiment, pim_universe, runs, scenarios, teams, ventures, workflows
from shared.fm_shared.errors import FinModelError, get_http_status
from shared.fm_shared.logging import configure_logging
from shared.fm_shared.metrics import metrics_app

settings = get_settings()
configure_logging(environment=settings.environment, log_level=settings.log_level)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_pool()
    except Exception as e:
        logger.warning(
            "db_pool_init_skipped",
            error=str(e),
            msg="DB unreachable at startup; connections will use direct connect",
        )
    try:
        from signxml import XMLVerifier  # noqa: F401
    except ImportError:
        if settings.environment not in ("development", "test"):
            logger.error("signxml not installed — SAML signature verification unavailable in production")
    yield
    await close_pool()


app = FastAPI(
    title="Virtual Analyst API",
    version="0.1.0",
    description="Deterministic financial modeling platform",
    lifespan=lifespan,
)

if settings.sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=settings.environment,
    )

MAX_BODY_SIZE = 10 * 1024 * 1024  # 10MB


async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE:
        return JSONResponse(
            status_code=413,
            content={"error": "Request body too large", "max_bytes": MAX_BODY_SIZE},
        )
    return await call_next(request)


app.middleware("http")(limit_body_size)
app.middleware("http")(metrics_middleware)
app.middleware("http")(security_headers_middleware)
app.middleware("http")(auth_middleware)

# CORSMiddleware MUST wrap auth so that error responses (401/403) include CORS
# headers. Otherwise browsers block auth errors as CORS failures ("Failed to fetch").
_cors_kwargs: dict[str, Any] = dict(
    allow_origins=settings.cors_allowed_origins_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Tenant-ID", "X-User-ID", "X-Request-ID"],
)
_origin_regex = settings.cors_origin_regex()
if _origin_regex:
    _cors_kwargs["allow_origin_regex"] = _origin_regex
app.add_middleware(CORSMiddleware, **_cors_kwargs)

app.middleware("http")(logging_middleware)

init_rate_limiting(app, settings.rate_limit)


@app.exception_handler(FinModelError)
async def finmodel_error_handler(request: Request, exc: FinModelError) -> JSONResponse:
    logger.error(
        "FinModel error",
        error_code=exc.code,
        error_message=exc.message,
        category=exc.category.value,
        severity=exc.severity.value,
        context=exc.context,
    )

    return JSONResponse(
        status_code=get_http_status(exc.code),
        content={
            "error": exc.to_dict(),
            "meta": {
                "request_id": getattr(request.state, "request_id", ""),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions.

    Without this, unhandled errors produce a raw 500 response that bypasses
    CORSMiddleware — the browser then reports a CORS error instead of the
    real server error, making debugging very difficult.
    """
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
    logger.error(
        "unhandled_exception",
        error_type=type(exc).__name__,
        error_message=str(exc),
        path=request.url.path,
        method=request.method,
        traceback="".join(tb),
    )
    # Include detail/traceback in non-production for debugging (or via X-Debug header)
    _debug_secret = settings.metrics_secret
    include_detail = (
        settings.environment in ("development", "test")
        or (bool(_debug_secret) and request.headers.get("X-Debug") == _debug_secret)
    )
    body: dict[str, Any] = {
        "detail": str(exc) if include_detail else "Internal server error",
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "meta": {
            "request_id": getattr(request.state, "request_id", ""),
            "timestamp": datetime.now(UTC).isoformat(),
        },
    }
    if include_detail:
        body["traceback"] = "".join(tb)
    return JSONResponse(status_code=500, content=body)


app.include_router(health.router, prefix="/api/v1")
app.include_router(auth_saml.router, prefix="/api/v1")
app.include_router(benchmark.router, prefix="/api/v1")
app.include_router(metrics_summary.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(drafts.router, prefix="/api/v1")
app.include_router(baselines.router, prefix="/api/v1")
app.include_router(changesets.router, prefix="/api/v1")
app.include_router(runs.router, prefix="/api/v1")
app.include_router(scenarios.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(ventures.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(connectors.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(compliance.router, prefix="/api/v1")
app.include_router(import_csv.router, prefix="/api/v1")
app.include_router(covenants.router, prefix="/api/v1")
app.include_router(excel.router, prefix="/api/v1")
app.include_router(excel_ingestion.router, prefix="/api/v1")
app.include_router(org_structures.router, prefix="/api/v1")
app.include_router(memos.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(comments.router, prefix="/api/v1")
app.include_router(activity.router, prefix="/api/v1")
app.include_router(teams.router, prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")
app.include_router(assignments.router, prefix="/api/v1")
app.include_router(budgets.router, prefix="/api/v1")
app.include_router(currency.router, prefix="/api/v1")
app.include_router(marketplace.router, prefix="/api/v1")
app.include_router(board_pack_schedules.router, prefix="/api/v1")
app.include_router(board_pack_schedules.cron_router, prefix="/api/v1")
app.include_router(board_packs.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(afs.router, prefix="/api/v1")
app.include_router(pim_universe.router, prefix="/api/v1")
app.include_router(pim_sentiment.router, prefix="/api/v1")
@app.get("/metrics")
async def metrics_endpoint(request: Request):
    ms = settings.metrics_secret
    if ms:
        token = request.query_params.get("token", "")
        if token != ms:
            return JSONResponse(status_code=401, content={"error": "Invalid metrics token"})
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from starlette.responses import Response
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root() -> dict:
    return {"name": "Virtual Analyst API", "version": "0.1.0", "status": "ok"}
