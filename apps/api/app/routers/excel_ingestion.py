"""Excel model ingestion: upload, parse, classify, analyze, create draft."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = structlog.get_logger()

from apps.api.app.core.settings import get_settings
from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_agent_service, get_artifact_store, get_llm_router, require_role, ROLES_CAN_WRITE
from apps.api.app.services.agent.session_manager import AgentSessionManager
from apps.api.app.services.excel_ingestion import (
    EXCEL_UPLOAD_TYPE,
    analyze_and_map,
    create_draft_from_mapping,
    parse_and_classify,
    parse_classify_and_map_agent,
    start_ingestion,
)
from apps.api.app.services.excel_parser import parse_workbook
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.errors import StorageError
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(
    prefix="/excel-ingestion",
    tags=["excel-ingestion"],
    dependencies=[require_role(*ROLES_CAN_WRITE)],
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB

_BUDGET_TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "data" / "budget_templates.json"

_budget_templates_cache: list[dict[str, Any]] | None = None


def _load_budget_templates() -> list[dict[str, Any]]:
    """Load budget templates from JSON file, cached after first read."""
    global _budget_templates_cache  # noqa: PLW0603
    if _budget_templates_cache is None:
        raw = _BUDGET_TEMPLATES_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        _budget_templates_cache = data.get("templates", [])
    return _budget_templates_cache


class AnswerQuestionsBody(BaseModel):
    """Request body for submitting answers to mapping questions."""

    answers: list[dict[str, Any]] = Field(default_factory=list, description="List of {question_index, answer}")


# ---------------------------------------------------------------------------
# SSE state persistence wrapper
# ---------------------------------------------------------------------------


async def _persist_stream_state(
    stream: AsyncGenerator[str, None],
    *,
    tenant_id: str,
    ingestion_id: str,
) -> AsyncGenerator[str, None]:
    """Wrap an SSE generator, persisting agent state to the DB on key events.

    Intercepts ``session_start``, ``question``, ``complete``, and ``error``
    events emitted by :class:`AgentSessionManager` and writes corresponding
    state updates to ``excel_ingestion_sessions``.
    """
    async for frame in stream:
        yield frame

        # Parse the SSE frame to detect lifecycle events
        if not frame.startswith("data: "):
            continue
        try:
            data = json.loads(frame[6:].strip())
        except (json.JSONDecodeError, IndexError):
            continue

        event_type = data.get("type")

        if event_type == "session_start":
            session_id = data.get("session_id", "")
            async with tenant_conn(tenant_id) as conn:
                await conn.execute(
                    """UPDATE excel_ingestion_sessions
                          SET agent_session_id = $1, agent_status = 'running'
                        WHERE tenant_id = $2 AND ingestion_id = $3""",
                    session_id,
                    tenant_id,
                    ingestion_id,
                )

        elif event_type == "session_resume":
            async with tenant_conn(tenant_id) as conn:
                await conn.execute(
                    """UPDATE excel_ingestion_sessions
                          SET agent_status = 'running', pending_question = NULL
                        WHERE tenant_id = $1 AND ingestion_id = $2""",
                    tenant_id,
                    ingestion_id,
                )

        elif event_type == "question":
            async with tenant_conn(tenant_id) as conn:
                await conn.execute(
                    """UPDATE excel_ingestion_sessions
                          SET agent_status = 'paused',
                              pending_question = $1::jsonb
                        WHERE tenant_id = $2 AND ingestion_id = $3""",
                    json.dumps(data),
                    tenant_id,
                    ingestion_id,
                )

        elif event_type == "complete":
            state_json = json.dumps({
                "mapping": data.get("mapping"),
                "classification": data.get("classification"),
                "unmapped": data.get("unmapped", []),
            })
            async with tenant_conn(tenant_id) as conn:
                await conn.execute(
                    """UPDATE excel_ingestion_sessions
                          SET agent_status = 'complete',
                              agent_state_json = $1::jsonb,
                              pending_question = NULL
                        WHERE tenant_id = $2 AND ingestion_id = $3""",
                    state_json,
                    tenant_id,
                    ingestion_id,
                )

        elif event_type == "error":
            async with tenant_conn(tenant_id) as conn:
                await conn.execute(
                    """UPDATE excel_ingestion_sessions
                          SET agent_status = 'error'
                        WHERE tenant_id = $1 AND ingestion_id = $2""",
                    tenant_id,
                    ingestion_id,
                )

        elif event_type in ("classification", "mapping"):
            # Persist intermediate state snapshots (merge into existing)
            async with tenant_conn(tenant_id) as conn:
                existing = await conn.fetchval(
                    """SELECT agent_state_json FROM excel_ingestion_sessions
                        WHERE tenant_id = $1 AND ingestion_id = $2""",
                    tenant_id,
                    ingestion_id,
                )
                current_state: dict[str, Any] = json.loads(existing) if existing else {}
                if event_type == "classification":
                    current_state["classification"] = data.get("classification")
                else:
                    current_state["mapping"] = data.get("mapping")
                await conn.execute(
                    """UPDATE excel_ingestion_sessions
                          SET agent_state_json = $1::jsonb
                        WHERE tenant_id = $2 AND ingestion_id = $3""",
                    json.dumps(current_state),
                    tenant_id,
                    ingestion_id,
                )


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


# ---------------------------------------------------------------------------
# SSE streaming endpoints (agentic Excel import)
# ---------------------------------------------------------------------------


@router.post("/upload-stream")
async def upload_and_stream(
    file: UploadFile,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> StreamingResponse:
    """Upload .xlsx and stream agentic ingestion events via SSE.

    The response is a ``text/event-stream`` body.  Each frame is a JSON
    object with a ``type`` field (``session_start``, ``message``,
    ``classification``, ``question``, ``mapping``, ``complete``, ``error``).
    """
    settings = get_settings()
    if not settings.agent_excel_ingestion_enabled:
        raise HTTPException(501, "Agentic Excel ingestion is not enabled")

    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Only .xlsx files are allowed")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit")

    # 1. Persist file and create ingestion session
    async with tenant_conn(x_tenant_id) as conn:
        try:
            ingestion_id = await start_ingestion(
                x_tenant_id,
                x_user_id or None,
                file.filename or "upload.xlsx",
                content,
                store,
                conn,
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    # 2. Parse workbook into sheet metadata
    parsed = parse_workbook(content, file.filename or "upload.xlsx")
    sheets: dict[str, Any] = {
        s.name: {
            "name": s.name,
            "headers": s.headers,
            "sample_rows": s.sample_rows,
            "row_count": s.row_count,
            "col_count": s.col_count,
            "formula_patterns": s.formula_patterns,
            "referenced_sheets": s.referenced_sheets,
        }
        for s in parsed.sheets
    }

    # 3. Load budget templates
    templates = _load_budget_templates()

    # 4. Create session manager
    session_mgr = AgentSessionManager(
        api_key=settings.anthropic_api_key or "",
        model=settings.agent_sdk_default_model,
        max_turns=settings.agent_sdk_max_turns,
        max_budget_usd=settings.agent_sdk_max_budget_usd,
    )

    # 5. Build initial prompt
    sheet_names = ", ".join(sheets.keys())
    initial_prompt = (
        f"I have uploaded an Excel file named '{file.filename}' with the "
        f"following sheets: {sheet_names}. Please classify and map this "
        f"workbook into a budget model."
    )

    # 6. Return SSE stream (with state persistence)
    return StreamingResponse(
        _persist_stream_state(
            session_mgr.start_session(
                ingestion_id=ingestion_id,
                tenant_id=x_tenant_id,
                sheets=sheets,
                templates=templates,
                initial_prompt=initial_prompt,
            ),
            tenant_id=x_tenant_id,
            ingestion_id=ingestion_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Ingestion-Id": ingestion_id,
        },
    )


@router.post("/{ingestion_id}/answer-stream")
async def answer_and_stream(
    ingestion_id: str,
    body: AnswerQuestionsBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> StreamingResponse:
    """Resume a paused agent session with user answers, streaming SSE events.

    The agent must have previously paused (``agent_status = 'paused'``) after
    emitting a ``question`` event.  The frontend collects answers and POSTs
    them here to continue the session.
    """
    settings = get_settings()
    if not settings.agent_excel_ingestion_enabled:
        raise HTTPException(501, "Agentic Excel ingestion is not enabled")

    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    # 1. Fetch session row and validate state
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT ingestion_id, filename, agent_status, agent_session_id,
                      agent_messages, agent_state_json
               FROM excel_ingestion_sessions
              WHERE tenant_id = $1 AND ingestion_id = $2""",
            x_tenant_id,
            ingestion_id,
        )

    if not row:
        raise HTTPException(404, "Ingestion not found")
    if row["agent_status"] != "paused":
        raise HTTPException(400, f"Session is not paused (status: {row['agent_status']})")
    if not row["agent_session_id"]:
        raise HTTPException(400, "No agent session ID found — cannot resume")

    session_id: str = row["agent_session_id"]
    prior_state: dict[str, Any] = row["agent_state_json"] or {}
    filename: str = row["filename"] or "upload.xlsx"

    # 2. Rebuild sheets data from artifact store (re-parse stored file)
    try:
        raw = store.load(x_tenant_id, EXCEL_UPLOAD_TYPE, ingestion_id)
    except StorageError as e:
        raise HTTPException(404, "Stored file metadata not found — cannot resume session") from e

    file_storage_path = raw.get("file_storage_path")
    if file_storage_path:
        file_bytes: bytes = store.download_bytes("excel-uploads", file_storage_path)
    elif "content_base64" in raw:
        import base64
        file_bytes = base64.b64decode(raw["content_base64"])
    else:
        raise HTTPException(404, "Stored file not found — cannot resume session")

    if not file_bytes:
        raise HTTPException(404, "Stored file is empty — cannot resume session")

    parsed = parse_workbook(file_bytes, filename)
    sheets: dict[str, Any] = {
        s.name: {
            "name": s.name,
            "headers": s.headers,
            "sample_rows": s.sample_rows,
            "row_count": s.row_count,
            "col_count": s.col_count,
            "formula_patterns": s.formula_patterns,
            "referenced_sheets": s.referenced_sheets,
        }
        for s in parsed.sheets
    }

    # 3. Load budget templates
    templates = _load_budget_templates()

    # 4. Create session manager
    session_mgr = AgentSessionManager(
        api_key=settings.anthropic_api_key or "",
        model=settings.agent_sdk_default_model,
        max_turns=settings.agent_sdk_max_turns,
        max_budget_usd=settings.agent_sdk_max_budget_usd,
    )

    # 5. Return SSE stream for resumed session (with state persistence)
    return StreamingResponse(
        _persist_stream_state(
            session_mgr.resume_session(
                ingestion_id=ingestion_id,
                session_id=session_id,
                answers=body.answers,
                sheets=sheets,
                templates=templates,
                prior_state=prior_state,
            ),
            tenant_id=x_tenant_id,
            ingestion_id=ingestion_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
