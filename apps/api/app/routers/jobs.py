"""Job status: query Celery task state and enqueue tasks."""

from __future__ import annotations

import asyncio
from typing import Any

from celery.result import AsyncResult
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.deps import require_role, ROLES_CAN_WRITE
from apps.worker.celery_app import celery_app
from apps.worker.tasks import add

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[require_role(*ROLES_CAN_WRITE)])

TASK_REGISTRY: dict[str, Any] = {"add": add}

# Track task-to-tenant mapping for authorization
_task_tenant_map: dict[str, str] = {}


class EnqueueBody(BaseModel):
    """Enqueue a known task by name with JSON-serializable args/kwargs."""

    task: str = Field(..., description="Task name, e.g. 'add'")
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)


def _get_task_status(task_id: str) -> dict[str, Any]:
    """Synchronous read of task state from Celery result backend."""
    result = AsyncResult(task_id, app=celery_app)
    out: dict[str, Any] = {
        "task_id": task_id,
        "state": result.state,
    }
    if result.state == "SUCCESS" and result.result is not None:
        out["result"] = result.result
    if result.state == "FAILURE" and result.result is not None:
        out["error"] = str(result.result)
    if result.state == "RETRY":
        out["error"] = str(result.info) if result.info else None
    if getattr(result, "retries", None) is not None:
        out["retries"] = result.retries
    return out


@router.post("/enqueue", status_code=202)
async def enqueue_job(
    body: EnqueueBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Enqueue a task by name; returns task_id for status polling."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    task_cls = TASK_REGISTRY.get(body.task)
    if not task_cls:
        raise HTTPException(400, f"Unknown task: {body.task}")
    try:
        merged_kwargs = {**(body.kwargs or {}), "_tenant_id": x_tenant_id}
        result = task_cls.apply_async(args=body.args, kwargs=merged_kwargs)
        _task_tenant_map[result.id] = x_tenant_id
        return {"task_id": result.id}
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@router.get("/{task_id}")
async def get_job_status(
    task_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Return task state (PENDING, STARTED, SUCCESS, FAILURE, RETRY) and result or error."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    owner = _task_tenant_map.get(task_id)
    if owner and owner != x_tenant_id:
        raise HTTPException(403, "Not authorized to view this task")
    try:
        return await asyncio.to_thread(_get_task_status, task_id)
    except Exception as e:
        raise HTTPException(500, str(e)) from e
