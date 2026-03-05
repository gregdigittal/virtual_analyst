"""Venture template wizard: create venture, submit answers, generate draft from LLM."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from apps.api.app.data.catalog import get_template
from apps.api.app.db import ensure_tenant, tenant_conn
from apps.api.app.db.audit import EVENT_DRAFT_CREATED, create_audit_event
from apps.api.app.deps import get_artifact_store, get_llm_router, require_role, ROLES_CAN_WRITE
from apps.api.app.routers.drafts import DRAFT_WORKSPACE_TYPE, STATUS_ACTIVE, _empty_workspace
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.errors import LLMError, StorageError
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/ventures", tags=["ventures"], dependencies=[require_role(*ROLES_CAN_WRITE)])

VENTURE_STATE_TYPE = "venture"

TEMPLATE_INITIALIZATION_SCHEMA = {
    "type": "object",
    "required": ["assumptions"],
    "properties": {
        "assumptions": {
            "type": "object",
            "description": (
                "Model assumptions: revenue_streams, cost_structure, working_capital, etc. "
                "Every numeric value SHOULD have sibling '_confidence' (high/medium/low) "
                "and '_evidence' (source citation) fields."
            ),
            "properties": {
                "revenue_streams": {"type": "array"},
                "cost_structure": {"type": "object"},
                "working_capital": {"type": "object"},
                "capex": {"type": "object"},
                "funding": {"type": "object"},
            },
        },
    },
}


class CreateVentureBody(BaseModel):
    template_id: str
    entity_name: str = ""


class AnswersBody(BaseModel):
    answers: dict[str, str] = {}


def _build_template_initialization_prompt(
    template_label: str,
    entity_name: str,
    question_plan: list[dict[str, Any]],
    answers: dict[str, str],
) -> str:
    parts = [
        f"You are a financial analyst. Generate initial model assumptions for a {template_label} business.",
        f"Entity name: {entity_name or 'Unnamed'}.",
        "",
        "## CRITICAL RULES",
        "- Do NOT invent, fabricate, or hallucinate any data, facts, statistics, or financial figures.",
        "- Base all numeric values on: (a) the user's questionnaire answers below, (b) named industry benchmarks you can cite, or (c) reasonable defaults clearly marked as placeholders.",
        "- For EVERY numeric value, include a '_confidence' sibling field set to 'high', 'medium', or 'low'.",
        "- For EVERY numeric value, include an '_evidence' sibling field citing the source.",
        "- 'high' = directly from user input or named benchmark; 'medium' = reasonable inference; 'low' = placeholder needing verification.",
        "- Do NOT present placeholders as established facts.",
        "",
        "Questionnaire answers (question_id -> answer):",
        str(answers),
    ]
    if question_plan:
        parts.append("")
        parts.append("Question plan (for context):")
        for section in question_plan:
            parts.append(f"  {section.get('section', '')}:")
            for q in section.get("questions", []):
                parts.append(f"    - {q.get('id', '')}: {q.get('q', '')}")
    parts.append("")
    parts.append(
        "Respond ONLY with a JSON object: { \"assumptions\": { ... } }. "
        "Populate assumptions.revenue_streams (array of stream objects with drivers), "
        "assumptions.cost_structure (variable_costs, fixed_costs), assumptions.working_capital, as needed for the template. "
        "Remember: every numeric value needs a sibling '_confidence' and '_evidence' field."
    )
    return "\n".join(parts)


def _deep_merge_assumptions(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge_assumptions(out[k], v)
        else:
            out[k] = v
    return out


@router.get("/templates")
async def list_templates():
    """Return the list of available venture templates (id + label only)."""
    from apps.api.app.data.catalog import load_catalog
    catalog = load_catalog()
    return [
        {"template_id": t["template_id"], "label": t.get("label", t["template_id"])}
        for t in catalog.get("templates", [])
    ]


@router.post("", status_code=201)
async def create_venture(
    body: CreateVentureBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    template = get_template(body.template_id)
    if not template:
        raise HTTPException(404, f"Template not found: {body.template_id}")
    venture_id = f"vc_{uuid.uuid4().hex[:12]}"
    state = {
        "venture_id": venture_id,
        "template_id": body.template_id,
        "entity_name": body.entity_name or "",
        "answers": {},
    }
    store.save(x_tenant_id, VENTURE_STATE_TYPE, venture_id, state)
    question_plan = template.get("question_plan", [])
    return {
        "venture_id": venture_id,
        "template_id": body.template_id,
        "entity_name": body.entity_name or "",
        "question_plan": question_plan,
    }


@router.post("/{venture_id}/answers")
async def submit_answers(
    venture_id: str,
    body: AnswersBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    try:
        state = store.load(x_tenant_id, VENTURE_STATE_TYPE, venture_id)
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Venture not found") from e
        raise
    state["answers"] = {**state.get("answers", {}), **(body.answers or {})}
    store.save(x_tenant_id, VENTURE_STATE_TYPE, venture_id, state)
    return {"venture_id": venture_id, "answers": state["answers"]}


@router.post("/{venture_id}/generate-draft")
async def generate_draft(
    venture_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    try:
        state = store.load(x_tenant_id, VENTURE_STATE_TYPE, venture_id)
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Venture not found") from e
        raise
    template_id = state.get("template_id")
    entity_name = state.get("entity_name", "")
    answers = state.get("answers", {})
    template = get_template(template_id) if template_id else None
    if not template:
        raise HTTPException(404, f"Template not found: {template_id}")
    question_plan = template.get("question_plan", [])
    system_text = _build_template_initialization_prompt(
        template.get("label", ""),
        entity_name,
        question_plan,
        answers,
    )
    messages = [
        {"role": "user", "content": "Generate initial assumptions from the questionnaire context above."},
    ]
    try:
        response = await llm.complete_with_routing(
            x_tenant_id,
            [{"role": "system", "content": system_text}, *messages],
            TEMPLATE_INITIALIZATION_SCHEMA,
            "template_initialization",
        )
    except LLMError as e:
        raise HTTPException(
            503 if e.code == "ERR_LLM_ALL_PROVIDERS_FAILED" else 429,
            detail=f"{e.message}: {e.details}" if e.details else e.message,
        ) from e
    content = response.content or {}
    if not isinstance(content, dict):
        content = {}
    llm_assumptions = content.get("assumptions") or {}
    if not isinstance(llm_assumptions, dict):
        llm_assumptions = {}
    draft_session_id = f"ds_{uuid.uuid4().hex[:12]}"
    base_workspace = _empty_workspace(draft_session_id, template_id, None, None)
    base_workspace["driver_blueprint"] = template.get("driver_blueprint", {"nodes": [], "edges": [], "formulas": []})
    base_assumptions = base_workspace.get("assumptions") or {}
    base_workspace["assumptions"] = _deep_merge_assumptions(base_assumptions, llm_assumptions)
    base_workspace["distributions"] = template.get("default_distributions", [])
    storage_path = f"{x_tenant_id}/{DRAFT_WORKSPACE_TYPE}/{draft_session_id}.json"
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            await ensure_tenant(conn, x_tenant_id)
            await conn.execute(
                """INSERT INTO draft_sessions (tenant_id, draft_session_id, parent_baseline_id, parent_baseline_version, status, storage_path, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                x_tenant_id,
                draft_session_id,
                None,
                None,
                STATUS_ACTIVE,
                storage_path,
                x_user_id or None,
            )
            store.save(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id, base_workspace)
            await create_audit_event(
                conn,
                x_tenant_id,
                EVENT_DRAFT_CREATED,
                "draft",
                "draft_session",
                draft_session_id,
                user_id=x_user_id or None,
                event_data={"storage_path": storage_path, "from_venture": venture_id},
            )
    return {
        "draft_session_id": draft_session_id,
        "venture_id": venture_id,
        "status": STATUS_ACTIVE,
    }
