"""Excel model ingestion: upload, parse, classify, analyze, create draft."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

logger = structlog.get_logger()

from apps.api.app.core.settings import get_settings
from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_agent_service, get_artifact_store, get_llm_router, require_role, ROLES_CAN_WRITE
from apps.api.app.services.excel_ingestion import (
    analyze_and_map,
    create_draft_from_mapping,
    parse_and_classify,
    parse_classify_and_map_agent,
    start_ingestion,
)
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(
    prefix="/excel-ingestion",
    tags=["excel-ingestion"],
    dependencies=[require_role(*ROLES_CAN_WRITE)],
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB


class AnswerQuestionsBody(BaseModel):
    """Request body for submitting answers to mapping questions."""

    answers: list[dict[str, Any]] = Field(default_factory=list, description="List of {question_index, answer}")


@router.post("/upload")
async def upload_and_parse(
    file: UploadFile,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Upload .xlsx, start ingestion, run parse and classify. Returns ingestion_id, status, classification, model_summary."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Only .xlsx files are allowed")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, f"File exceeds {MAX_UPLOAD_BYTES // (1024*1024)}MB limit")
    async with tenant_conn(x_tenant_id) as conn:
        try:
            ingestion_id = await start_ingestion(x_tenant_id, x_user_id or None, file.filename or "upload.xlsx", content, store, conn)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        agent = get_agent_service()
        if agent and get_settings().agent_excel_ingestion_enabled:
            try:
                combined = await parse_classify_and_map_agent(
                    x_tenant_id, ingestion_id, store, agent, conn
                )
                classification = combined.get("classification", {})
                mapping = combined.get("mapping", {})
            except Exception as e:
                logger.error("excel_agent_error", ingestion_id=ingestion_id, error=str(e))
                raise HTTPException(500, "Internal error during agent ingestion") from e
        else:
            try:
                classification = await parse_and_classify(x_tenant_id, ingestion_id, store, llm, conn)
                mapping = {}
            except Exception as e:
                logger.error("excel_ingestion_error", ingestion_id=ingestion_id, error=str(e))
                raise HTTPException(500, "Internal error during ingestion") from e
        row = await conn.fetchrow(
            "SELECT sheet_count, formula_count, cross_ref_count FROM excel_ingestion_sessions WHERE tenant_id = $1 AND ingestion_id = $2",
            x_tenant_id,
            ingestion_id,
        )
    response: dict[str, Any] = {
        "ingestion_id": ingestion_id,
        "status": "analyzed" if mapping else "parsed",
        "sheet_count": row["sheet_count"] if row else None,
        "formula_count": row["formula_count"] if row else None,
        "cross_ref_count": row["cross_ref_count"] if row else None,
        "classification": classification,
        "model_summary": classification.get("model_summary", {}),
    }
    if mapping:
        response["mapping"] = mapping
        response["questions"] = mapping.get("questions", [])
        response["unmapped_count"] = len(mapping.get("unmapped_items", []))
    return response


@router.get("/{ingestion_id}")
async def get_ingestion(
    ingestion_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get ingestion session state."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT ingestion_id, filename, status, sheet_count, formula_count, cross_ref_count,
                      classification_json, mapping_json, unmapped_items_json, draft_session_id, error_message, created_at
               FROM excel_ingestion_sessions WHERE tenant_id = $1 AND ingestion_id = $2""",
            x_tenant_id,
            ingestion_id,
        )
    if not row:
        raise HTTPException(404, "Ingestion not found")
    mapping = row["mapping_json"] or {}
    questions = (mapping.get("questions") or []) if mapping else []
    return {
        "ingestion_id": row["ingestion_id"],
        "filename": row["filename"],
        "status": row["status"],
        "sheet_count": row["sheet_count"],
        "formula_count": row["formula_count"],
        "cross_ref_count": row["cross_ref_count"],
        "classification": row["classification_json"] or {},
        "mapping": mapping,
        "unmapped_items": row["unmapped_items_json"] or [],
        "questions": questions,
        "draft_session_id": row["draft_session_id"],
        "error_message": row["error_message"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.post("/{ingestion_id}/analyze")
async def trigger_analyze(
    ingestion_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Run analyze_and_map (LLM model mapping)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT status FROM excel_ingestion_sessions WHERE tenant_id = $1 AND ingestion_id = $2",
            x_tenant_id,
            ingestion_id,
        )
        if not row:
            raise HTTPException(404, "Ingestion not found")
        if row["status"] not in ("parsed", "analyzed"):
            raise HTTPException(400, f"Invalid status for analyze: {row['status']}")
        try:
            mapping = await analyze_and_map(x_tenant_id, ingestion_id, store, llm, conn)
        except Exception as e:
            logger.error("excel_analyze_error", ingestion_id=ingestion_id, error=str(e))
            raise HTTPException(500, "Internal error during analysis") from e
    questions = mapping.get("questions", [])
    return {
        "status": "analyzed",
        "mapping_summary": {k: v for k, v in mapping.items() if k not in ("questions", "unmapped_items")},
        "unmapped_count": len(mapping.get("unmapped_items", [])),
        "question_count": len(questions),
        "questions": questions,
    }


@router.post("/{ingestion_id}/answer")
async def answer_questions(
    ingestion_id: str,
    body: AnswerQuestionsBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Submit answers and re-run mapping."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    answers = body.answers
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT status FROM excel_ingestion_sessions WHERE tenant_id = $1 AND ingestion_id = $2",
            x_tenant_id,
            ingestion_id,
        )
        if not row:
            raise HTTPException(404, "Ingestion not found")
        if row["status"] not in ("analyzed",):
            raise HTTPException(400, f"Invalid status for answering questions: {row['status']}")
        try:
            mapping = await analyze_and_map(x_tenant_id, ingestion_id, store, llm, conn, user_answers=answers)
        except Exception as e:
            logger.error("excel_answer_error", ingestion_id=ingestion_id, error=str(e))
            raise HTTPException(500, "Internal error during re-mapping") from e
    return {"mapping": mapping, "questions": mapping.get("questions", [])}


@router.post("/{ingestion_id}/create-draft")
async def create_draft(
    ingestion_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Create draft session from mapping; returns draft_session_id."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT filename, mapping_json, status FROM excel_ingestion_sessions WHERE tenant_id = $1 AND ingestion_id = $2",
            x_tenant_id,
            ingestion_id,
        )
        if not row:
            raise HTTPException(404, "Ingestion not found")
        if row["status"] != "analyzed":
            raise HTTPException(400, "Run analyze first")
        mapping = row["mapping_json"] or {}
        draft_session_id = await create_draft_from_mapping(
            x_tenant_id,
            x_user_id or None,
            ingestion_id,
            mapping,
            row["filename"] or "upload.xlsx",
            store,
            conn,
        )
    rev = mapping.get("revenue_streams") or []
    cost = mapping.get("cost_items") or []
    unmapped = mapping.get("unmapped_items") or []
    return {
        "draft_session_id": draft_session_id,
        "ingestion_id": ingestion_id,
        "revenue_streams_count": len(rev),
        "cost_items_count": len(cost),
        "unmapped_count": len(unmapped),
    }


@router.get("")
async def list_ingestions(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List ingestion sessions for tenant."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT ingestion_id, filename, status, sheet_count, draft_session_id, created_at
               FROM excel_ingestion_sessions WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
            x_tenant_id,
            limit,
            offset,
        )
        total = await conn.fetchval(
            "SELECT count(*) FROM excel_ingestion_sessions WHERE tenant_id = $1",
            x_tenant_id,
        )
    return {
        "items": [
            {
                "ingestion_id": r["ingestion_id"],
                "filename": r["filename"],
                "status": r["status"],
                "sheet_count": r["sheet_count"],
                "draft_session_id": r["draft_session_id"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.delete("/{ingestion_id}", status_code=204)
async def delete_ingestion(
    ingestion_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> None:
    """Delete an ingestion session."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            "DELETE FROM excel_ingestion_sessions WHERE tenant_id = $1 AND ingestion_id = $2",
            x_tenant_id,
            ingestion_id,
        )
    if result == "DELETE 0":
        raise HTTPException(404, "Ingestion not found")
