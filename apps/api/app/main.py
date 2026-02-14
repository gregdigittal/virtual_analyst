from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.app.core.settings import get_settings
from apps.api.app.db.connection import close_pool, init_pool
from apps.api.app.middleware.logging import logging_middleware
from apps.api.app.middleware.metrics import metrics_middleware
from apps.api.app.middleware.security import init_rate_limiting, security_headers_middleware
from apps.api.app.routers import activity, audit, baselines, billing, changesets, comments, compliance, covenants, documents, drafts, excel, health, import_csv, integrations, jobs, memos, metrics_summary, notifications, runs, scenarios, teams, ventures
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
    yield
    await close_pool()


app = FastAPI(
    title="Virtual Analyst API",
    version="0.1.0",
    description="Deterministic financial modeling platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Tenant-ID", "X-User-ID", "X-Request-ID"],
)

app.middleware("http")(metrics_middleware)
app.middleware("http")(security_headers_middleware)
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


app.include_router(health.router, prefix="/api/v1")
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
app.include_router(billing.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(compliance.router, prefix="/api/v1")
app.include_router(import_csv.router, prefix="/api/v1")
app.include_router(covenants.router, prefix="/api/v1")
app.include_router(excel.router, prefix="/api/v1")
app.include_router(memos.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(comments.router, prefix="/api/v1")
app.include_router(activity.router, prefix="/api/v1")
app.include_router(teams.router, prefix="/api/v1")
app.mount("/metrics", metrics_app)


@app.get("/")
async def root() -> dict:
    return {"name": "Virtual Analyst API", "version": "0.1.0", "status": "ok"}
