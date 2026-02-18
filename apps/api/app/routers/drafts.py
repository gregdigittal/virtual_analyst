"""Draft session CRUD: create, list, get, patch (status/workspace), delete (abandon)."""

from __future__ import annotations

import re
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from apps.api.app.db import ensure_tenant, tenant_conn
from apps.api.app.db.notifications import create_notification
from apps.api.app.db.audit import (
    EVENT_DRAFT_ABANDONED,
    EVENT_DRAFT_ACCESSED,
    EVENT_DRAFT_COMMITTED,
    EVENT_DRAFT_CREATED,
    EVENT_DRAFT_UPDATED,
    create_audit_event,
)
from apps.api.app.core.settings import get_settings
from apps.api.app.deps import get_agent_service, get_artifact_store, get_llm_router, require_role, ROLES_CAN_WRITE
from apps.api.app.services.agent.draft_agent import run_draft_chat_agent
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.errors import LLMError, StorageError
from shared.fm_shared.model.graph import CalcGraph, GraphCycleError
from shared.fm_shared.model.schemas import DriverBlueprint, ModelConfig
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/drafts", tags=["drafts"], dependencies=[require_role(*ROLES_CAN_WRITE)])

DRAFT_WORKSPACE_TYPE = "draft_workspace"
STATUS_ACTIVE = "active"
STATUS_READY_TO_COMMIT = "ready_to_commit"
STATUS_COMMITTED = "committed"
STATUS_ABANDONED = "abandoned"

VALID_TRANSITIONS: dict[str, set[str]] = {
    STATUS_ACTIVE: {STATUS_READY_TO_COMMIT, STATUS_ABANDONED},
    STATUS_READY_TO_COMMIT: {STATUS_ACTIVE, STATUS_COMMITTED, STATUS_ABANDONED},
    STATUS_COMMITTED: set(),
    STATUS_ABANDONED: set(),
}


class CreateDraftBody(BaseModel):
    """Optional template and parent baseline for new draft."""

    template_id: str | None = None
    parent_baseline_id: str | None = None
    parent_baseline_version: str | None = None


PROPOSAL_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["proposals"],
    "properties": {
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["path", "value", "evidence", "confidence"],
                "properties": {
                    "path": {"type": "string"},
                    "value": {},
                    "evidence": {"type": "string", "maxLength": 500},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "reasoning": {"type": "string", "maxLength": 500},
                },
            },
        },
        "clarification": {"type": ["string", "null"]},
        "commentary": {"type": ["string", "null"]},
    },
}


def _build_draft_assumptions_prompt(workspace: dict[str, Any]) -> str:
    assumptions = workspace.get("assumptions") or {}
    blueprint = workspace.get("driver_blueprint") or {}
    evidence = workspace.get("evidence") or []
    parts = [
        "You are a financial analyst assistant helping build a financial model.",
        "",
        "## CRITICAL RULES",
        "- Do NOT invent, fabricate, or hallucinate any data, facts, statistics, or financial figures.",
        "- Every proposed value MUST be grounded in one of: (a) the user's explicit input, (b) evidence provided below, (c) standard industry benchmarks you can cite by name.",
        "- If you lack sufficient information to propose a value, set confidence to 'low' and clearly state in the evidence field that this is a placeholder requiring user verification.",
        "- Do NOT present assumptions as facts. Always qualify uncertain values.",
        "- Do NOT propose values outside physically reasonable bounds for the business type.",
        "",
        "## Confidence Rating Guide",
        "- high: Direct evidence from user input, uploaded documents, or named industry benchmark",
        "- medium: Reasonable inference from available context, clearly stated as such",
        "- low: Placeholder or educated guess — MUST be flagged for user review",
        "",
        "Driver blueprint (nodes/edges/formulas):",
        str(blueprint),
        "",
        "Current assumptions (already set):",
        str(assumptions),
        "",
        "Evidence collected so far:",
        str(evidence[:20]),
        "",
        "Respond ONLY with a JSON object: proposals (array of {path, value, evidence, confidence, reasoning}), optional clarification, optional commentary.",
        "For each proposal, the 'evidence' field MUST cite the source (e.g. 'User stated...', 'Industry benchmark: XYZ report', 'Derived from...'). Never leave evidence empty.",
    ]
    return "\n".join(parts)


_UNSAFE_CONTENT_PATTERN = re.compile(
    r"(https?://|<script|javascript:|eval\(|exec\()", re.IGNORECASE
)


def _validate_proposal_content(proposal: dict[str, Any]) -> str | None:
    """Return error message if proposal content is unsafe, else None."""
    for field in ("evidence", "reasoning"):
        text = proposal.get(field, "")
        if isinstance(text, str) and _UNSAFE_CONTENT_PATTERN.search(text):
            return f"Unsafe content in {field}"
    value = proposal.get("value")
    if isinstance(value, (int, float)):
        if not (-1e15 < value < 1e15):
            return f"Value {value} outside reasonable bounds"
    return None


def _path_under_assumptions(path: str) -> bool:
    if not path or ".." in path:
        return False
    top = path.split(".")[0].split("[")[0]
    return top in ("revenue_streams", "cost_structure", "working_capital", "capex", "funding")


def _set_by_path(obj: dict[str, Any], path: str, value: Any) -> None:
    if path.startswith("assumptions."):
        if isinstance(obj, dict) and "assumptions" in obj:
            obj = obj["assumptions"]
        path = path[len("assumptions."):]
    path = path.strip(".")
    segments = path.replace("[", ".").replace("]", "").split(".")
    segments = [s for s in segments if s]
    if not segments:
        return
    current: Any = obj
    for seg in segments[:-1]:
        if seg.isdigit():
            current = current[int(seg)]
        else:
            current = current[seg]
    last = segments[-1]
    if last.isdigit():
        current[int(last)] = value
    else:
        current[last] = value


def _run_integrity_checks(workspace: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    blueprint_dict = workspace.get("driver_blueprint") or {}
    try:
        bp = DriverBlueprint.model_validate(blueprint_dict)
        g = CalcGraph.from_blueprint(bp)
        g.topo_sort()
        checks.append({"check_id": "IC_GRAPH_ACYCLIC", "severity": "info", "message": "Graph is acyclic"})
    except GraphCycleError as e:
        checks.append({"check_id": "IC_GRAPH_ACYCLIC", "severity": "error", "message": str(e)})
    except Exception as e:
        checks.append({"check_id": "IC_GRAPH_ACYCLIC", "severity": "error", "message": f"Blueprint invalid: {e}"})
    assumptions = workspace.get("assumptions") or {}
    revenue_streams = assumptions.get("revenue_streams") or []
    if not revenue_streams:
        checks.append({
            "check_id": "IC_ASSUMPTIONS_REVENUE",
            "severity": "warning",
            "message": "No revenue streams defined in assumptions",
        })
    return checks


def _compile_workspace_to_model_config(
    workspace: dict[str, Any],
    tenant_id: str,
    baseline_id: str,
    baseline_version: str,
    integrity_checks: list[dict[str, Any]],
    created_by: str | None,
) -> dict[str, Any]:
    from datetime import UTC, datetime
    assumptions = dict(workspace.get("assumptions") or {})
    if not assumptions.get("revenue_streams"):
        assumptions.setdefault("revenue_streams", [{"stream_id": "rs_1", "label": "Revenue", "stream_type": "unit_sale", "drivers": {"volume": [], "pricing": [], "direct_costs": []}}])
    wc = assumptions.get("working_capital") or {}
    if not wc.get("ar_days"):
        wc["ar_days"] = {"ref": "drv:ar_days", "value_type": "constant", "value": 0}
    if not wc.get("ap_days"):
        wc["ap_days"] = {"ref": "drv:ap_days", "value_type": "constant", "value": 0}
    if not wc.get("inv_days"):
        wc["inv_days"] = {"ref": "drv:inv_days", "value_type": "constant", "value": 0}
    wc.setdefault("minimum_cash", 0)
    assumptions["working_capital"] = wc
    assumptions.setdefault("cost_structure", {"variable_costs": [], "fixed_costs": [], "depreciation_method": "straight_line"})
    evidence = workspace.get("evidence") or []
    evidence_summary = [{"assumption_path": e.get("assumption_path", ""), "source": e.get("source", ""), "confidence": e.get("confidence", "medium")} for e in evidence[:100]]
    errors = [c for c in integrity_checks if c.get("severity") == "error"]
    warnings = [c for c in integrity_checks if c.get("severity") == "warning"]
    status = "failed" if errors else ("warning" if warnings else "passed")
    integrity = {"status": status, "checks": [{"check_id": c["check_id"], "severity": c["severity"], "message": c["message"]} for c in integrity_checks]}
    metadata = workspace.get("metadata") or {}
    metadata.setdefault("entity_name", "Draft")
    metadata.setdefault("currency", "USD")
    metadata.setdefault("start_date", datetime.now(UTC).strftime("%Y-%m-%d"))
    metadata.setdefault("horizon_months", 12)
    metadata.setdefault("resolution", "monthly")
    return {
        "artifact_type": "model_config_v1",
        "artifact_version": "1.0.0",
        "tenant_id": tenant_id,
        "baseline_id": baseline_id,
        "baseline_version": baseline_version,
        "created_at": datetime.now(UTC).isoformat(),
        "created_by": created_by,
        "parent_baseline_id": workspace.get("parent_baseline_id"),
        "parent_baseline_version": workspace.get("parent_baseline_version"),
        "template_id": workspace.get("template_id"),
        "metadata": metadata,
        "assumptions": assumptions,
        "driver_blueprint": workspace.get("driver_blueprint") or {"nodes": [], "edges": [], "formulas": []},
        "distributions": workspace.get("distributions") or [],
        "scenarios": workspace.get("scenarios") or [],
        "evidence_summary": evidence_summary,
        "integrity": integrity,
    }


def _empty_workspace(draft_session_id: str, template_id: str | None, parent_baseline_id: str | None, parent_baseline_version: str | None) -> dict[str, Any]:
    return {
        "draft_session_id": draft_session_id,
        "template_id": template_id,
        "parent_baseline_id": parent_baseline_id,
        "parent_baseline_version": parent_baseline_version,
        "assumptions": {
            "revenue_streams": [],
            "cost_structure": {"variable_costs": [], "fixed_costs": []},
            "working_capital": {},
            "capex": {},
            "funding": {},
        },
        "driver_blueprint": {"nodes": [], "edges": [], "formulas": []},
        "distributions": [],
        "scenarios": [],
        "evidence": [],
        "chat_history": [],
        "pending_proposals": [],
    }


@router.post("", status_code=201)
async def create_draft(
    body: CreateDraftBody | None = None,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Create a new draft session. Optionally from existing baseline (future: load workspace from baseline)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    b = body or CreateDraftBody()
    draft_session_id = f"ds_{uuid.uuid4().hex[:12]}"
    storage_path = f"{x_tenant_id}/{DRAFT_WORKSPACE_TYPE}/{draft_session_id}.json"
    workspace = _empty_workspace(
        draft_session_id, b.template_id, b.parent_baseline_id, b.parent_baseline_version
    )
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            await ensure_tenant(conn, x_tenant_id)
            await conn.execute(
                """INSERT INTO draft_sessions (tenant_id, draft_session_id, parent_baseline_id, parent_baseline_version, status, storage_path, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                x_tenant_id,
                draft_session_id,
                b.parent_baseline_id,
                b.parent_baseline_version,
                STATUS_ACTIVE,
                storage_path,
                x_user_id or None,
            )
            store.save(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id, workspace)
            await create_audit_event(
                conn,
                x_tenant_id,
                EVENT_DRAFT_CREATED,
                "draft",
                "draft_session",
                draft_session_id,
                user_id=x_user_id or None,
                event_data={"storage_path": storage_path},
            )
        return {
            "draft_session_id": draft_session_id,
            "status": STATUS_ACTIVE,
            "storage_path": storage_path,
        }


@router.get("")
async def list_drafts(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    status: Literal["active", "ready_to_commit", "committed", "abandoned"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        if status:
            total = await conn.fetchval(
                "SELECT count(*) FROM draft_sessions WHERE tenant_id = $1 AND status = $2",
                x_tenant_id,
                status,
            )
            rows = await conn.fetch(
                """SELECT draft_session_id, parent_baseline_id, parent_baseline_version, status, created_at
                   FROM draft_sessions WHERE tenant_id = $1 AND status = $2 ORDER BY created_at DESC LIMIT $3 OFFSET $4""",
                x_tenant_id,
                status,
                limit,
                offset,
            )
        else:
            total = await conn.fetchval(
                "SELECT count(*) FROM draft_sessions WHERE tenant_id = $1",
                x_tenant_id,
            )
            rows = await conn.fetch(
                """SELECT draft_session_id, parent_baseline_id, parent_baseline_version, status, created_at
                   FROM draft_sessions WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
                x_tenant_id,
                limit,
                offset,
            )
        items = [
            {
                "draft_session_id": r["draft_session_id"],
                "parent_baseline_id": r["parent_baseline_id"],
                "parent_baseline_version": r["parent_baseline_version"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{draft_session_id}")
async def get_draft(
    draft_session_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Return draft workspace and meta. Rejects abandoned/committed unless we allow read."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        try:
            row = await conn.fetchrow(
                """SELECT draft_session_id, parent_baseline_id, parent_baseline_version, status, storage_path, created_at
                   FROM draft_sessions WHERE tenant_id = $1 AND draft_session_id = $2""",
                x_tenant_id,
                draft_session_id,
            )
            if not row:
                raise HTTPException(404, "Draft not found")
            if row["status"] == STATUS_ABANDONED:
                raise HTTPException(410, "Draft abandoned")
            workspace = store.load(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id)
            await create_audit_event(
                conn,
                x_tenant_id,
                EVENT_DRAFT_ACCESSED,
                "draft",
                "draft_session",
                draft_session_id,
                user_id=x_user_id or None,
                event_data={"status": row["status"]},
            )
            return {
                "draft_session_id": row["draft_session_id"],
                "parent_baseline_id": row["parent_baseline_id"],
                "parent_baseline_version": row["parent_baseline_version"],
                "status": row["status"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "workspace": workspace,
            }
        except StorageError as e:
            if e.code == "ERR_STOR_NOT_FOUND":
                raise HTTPException(404, "Draft workspace not found") from e
            raise


@router.patch("/{draft_session_id}")
async def patch_draft(
    draft_session_id: str,
    body: dict[str, Any],
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    new_status: str | None = body.get("status")
    workspace_update: dict[str, Any] | None = body.get("workspace")
    async with tenant_conn(x_tenant_id) as conn:
        try:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """SELECT draft_session_id, status, storage_path FROM draft_sessions
                       WHERE tenant_id = $1 AND draft_session_id = $2 FOR UPDATE""",
                    x_tenant_id,
                    draft_session_id,
                )
                if not row:
                    raise HTTPException(404, "Draft not found")
                if row["status"] in (STATUS_ABANDONED, STATUS_COMMITTED):
                    raise HTTPException(410, f"Draft is {row['status']}")

                if new_status is not None:
                    allowed = VALID_TRANSITIONS.get(row["status"], set())
                    if new_status not in allowed:
                        raise HTTPException(
                            409,
                            f"Invalid transition from {row['status']} to {new_status}",
                        )
                    await conn.execute(
                        "UPDATE draft_sessions SET status = $1 WHERE tenant_id = $2 AND draft_session_id = $3",
                        new_status,
                        x_tenant_id,
                        draft_session_id,
                    )
                    if new_status == STATUS_ABANDONED:
                        await create_audit_event(
                            conn,
                            x_tenant_id,
                            EVENT_DRAFT_ABANDONED,
                            "draft",
                            "draft_session",
                            draft_session_id,
                            user_id=x_user_id or None,
                        )
                    else:
                        await create_audit_event(
                            conn,
                            x_tenant_id,
                            EVENT_DRAFT_UPDATED,
                            "draft",
                            "draft_session",
                            draft_session_id,
                            user_id=x_user_id or None,
                            event_data={"status": new_status},
                        )
                        if new_status == STATUS_READY_TO_COMMIT:
                            await create_notification(
                                conn,
                                x_tenant_id,
                                "draft_ready",
                                "Draft ready to commit",
                                body=f"Draft {draft_session_id} is ready to commit.",
                                entity_type="draft_session",
                                entity_id=draft_session_id,
                                user_id=x_user_id or None,
                            )

                if workspace_update is not None:
                    _ALLOWED_WORKSPACE_KEYS = {
                        "assumptions", "driver_blueprint", "distributions", "metadata",
                        "evidence", "debt_facilities", "cost_centres", "revenue_streams",
                    }
                    current = store.load(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id)
                    for k, v in workspace_update.items():
                        if k in _ALLOWED_WORKSPACE_KEYS:
                            current[k] = v
                    store.save(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id, current)

            row2 = await conn.fetchrow(
                """SELECT draft_session_id, status FROM draft_sessions
                   WHERE tenant_id = $1 AND draft_session_id = $2""",
                x_tenant_id,
                draft_session_id,
            )
            return {
                "draft_session_id": draft_session_id,
                "status": row2["status"] if row2 else new_status or row["status"],
            }
        except StorageError as e:
            if e.code == "ERR_STOR_NOT_FOUND":
                raise HTTPException(404, "Draft workspace not found") from e
            raise


@router.delete("/{draft_session_id}", status_code=200)
async def delete_draft(
    draft_session_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Abandon draft (soft delete: set status=abandoned)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            res = await conn.execute(
                """UPDATE draft_sessions SET status = $1
                   WHERE tenant_id = $2 AND draft_session_id = $3 AND status NOT IN ($4, $5)
                   RETURNING draft_session_id""",
                STATUS_ABANDONED,
                x_tenant_id,
                draft_session_id,
                STATUS_ABANDONED,
                STATUS_COMMITTED,
            )
            if res == "UPDATE 0":
                row = await conn.fetchrow(
                    "SELECT status FROM draft_sessions WHERE tenant_id = $1 AND draft_session_id = $2",
                    x_tenant_id,
                    draft_session_id,
                )
                if not row:
                    raise HTTPException(404, "Draft not found")
                raise HTTPException(410, f"Draft is already {row['status']}")
            await create_audit_event(
                conn,
                x_tenant_id,
                EVENT_DRAFT_ABANDONED,
                "draft",
                "draft_session",
                draft_session_id,
                user_id=x_user_id or None,
            )
        return {"draft_session_id": draft_session_id, "status": STATUS_ABANDONED}


class ChatBody(BaseModel):
    message: str
    context: dict[str, Any] | None = None


@router.post("/{draft_session_id}/chat")
async def draft_chat(
    draft_session_id: str,
    body: ChatBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT draft_session_id, status FROM draft_sessions
                   WHERE tenant_id = $1 AND draft_session_id = $2 FOR UPDATE""",
                x_tenant_id,
                draft_session_id,
            )
            if not row:
                raise HTTPException(404, "Draft not found")
            if row["status"] != STATUS_ACTIVE:
                raise HTTPException(409, f"Draft is {row['status']}; chat only in active state")
            try:
                workspace = store.load(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id)
            except StorageError as e:
                if e.code == "ERR_STOR_NOT_FOUND":
                    raise HTTPException(404, "Draft workspace not found") from e
                raise
            agent = get_agent_service()
            settings = get_settings()
            if agent and settings.agent_draft_chat_enabled:
                try:
                    content = await run_draft_chat_agent(
                        x_tenant_id, agent, workspace, body.message,
                    )
                except LLMError as e:
                    if e.code == "ERR_LLM_QUOTA_EXCEEDED":
                        raise HTTPException(429, e.message) from e
                    raise HTTPException(503, e.message) from e
            else:
                system_text = _build_draft_assumptions_prompt(workspace)
                chat_history = workspace.get("chat_history") or []
                last_10 = chat_history[-10:] if len(chat_history) > 10 else chat_history
                messages = [{"role": "system", "content": system_text}]
                for entry in last_10:
                    messages.append({"role": entry.get("role", "user"), "content": entry.get("content", "")})
                messages.append({"role": "user", "content": body.message})
                try:
                    response = await llm.complete_with_routing(
                        x_tenant_id,
                        messages,
                        PROPOSAL_RESPONSE_SCHEMA,
                        "draft_assumptions",
                    )
                except LLMError as e:
                    if e.code == "ERR_LLM_QUOTA_EXCEEDED":
                        raise HTTPException(429, e.message) from e
                    raise HTTPException(503, e.message) from e
                content = response.content
            proposals_in = content.get("proposals") or []
            valid = []
            for p in proposals_in:
                path = p.get("path") or ""
                if not _path_under_assumptions(path):
                    continue
                safety_err = _validate_proposal_content(p)
                if safety_err:
                    continue
                valid.append({
                    "id": f"prop_{uuid.uuid4().hex[:12]}",
                    "path": path,
                    "value": p.get("value"),
                    "evidence": p.get("evidence", ""),
                    "confidence": p.get("confidence", "medium"),
                    "reasoning": p.get("reasoning"),
                })
            pending = workspace.get("pending_proposals") or []
            pending.extend(valid)
            workspace["pending_proposals"] = pending
            chat_history = workspace.get("chat_history") or []
            chat_history.append({"role": "user", "content": body.message})
            chat_history.append({
                "role": "assistant",
                "content": content.get("commentary") or "",
                "proposals": valid,
                "clarification": content.get("clarification"),
            })
            workspace["chat_history"] = chat_history
            store.save(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id, workspace)
    return {
        "proposals": valid,
        "clarification": content.get("clarification"),
        "commentary": content.get("commentary"),
    }


@router.post("/{draft_session_id}/proposals/{proposal_id}/accept")
async def accept_proposal(
    draft_session_id: str,
    proposal_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT draft_session_id, status FROM draft_sessions
                   WHERE tenant_id = $1 AND draft_session_id = $2 FOR UPDATE""",
                x_tenant_id,
                draft_session_id,
            )
            if not row:
                raise HTTPException(404, "Draft not found")
            try:
                workspace = store.load(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id)
            except StorageError as e:
                if e.code == "ERR_STOR_NOT_FOUND":
                    raise HTTPException(404, "Draft workspace not found") from e
                raise
            pending = workspace.get("pending_proposals") or []
            found = None
            for i, p in enumerate(pending):
                if p.get("id") == proposal_id:
                    found = (i, p)
                    break
            if not found:
                raise HTTPException(404, "Proposal not found")
            idx, proposal = found
            assumptions = workspace.get("assumptions") or {}
            try:
                _set_by_path(assumptions, proposal["path"], proposal["value"])
            except (KeyError, IndexError, TypeError):
                raise HTTPException(422, f"Path {proposal['path']} not applicable") from None
            workspace["assumptions"] = assumptions
            workspace["pending_proposals"] = pending[:idx] + pending[idx + 1:]
            store.save(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id, workspace)
    return {"proposal_id": proposal_id, "status": "accepted"}


@router.post("/{draft_session_id}/proposals/{proposal_id}/reject")
async def reject_proposal(
    draft_session_id: str,
    proposal_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT draft_session_id, status FROM draft_sessions
                   WHERE tenant_id = $1 AND draft_session_id = $2 FOR UPDATE""",
                x_tenant_id,
                draft_session_id,
            )
            if not row:
                raise HTTPException(404, "Draft not found")
            try:
                workspace = store.load(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id)
            except StorageError as e:
                if e.code == "ERR_STOR_NOT_FOUND":
                    raise HTTPException(404, "Draft workspace not found") from e
                raise
            pending = workspace.get("pending_proposals") or []
            new_pending = [p for p in pending if p.get("id") != proposal_id]
            if len(new_pending) == len(pending):
                raise HTTPException(404, "Proposal not found")
            workspace["pending_proposals"] = new_pending
            store.save(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id, workspace)
    return {"proposal_id": proposal_id, "status": "rejected"}


class CommitBody(BaseModel):
    acknowledge_warnings: bool = False


@router.post("/{draft_session_id}/commit")
async def commit_draft(
    draft_session_id: str,
    body: CommitBody | None = None,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    b = body or CommitBody()
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT draft_session_id, status, parent_baseline_id, parent_baseline_version FROM draft_sessions
                   WHERE tenant_id = $1 AND draft_session_id = $2 FOR UPDATE""",
                x_tenant_id,
                draft_session_id,
            )
            if not row:
                raise HTTPException(404, "Draft not found")
            if row["status"] != STATUS_READY_TO_COMMIT:
                raise HTTPException(409, f"Draft is {row['status']}; must be ready_to_commit to commit")
            try:
                workspace = store.load(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id)
            except StorageError as e:
                if e.code == "ERR_STOR_NOT_FOUND":
                    raise HTTPException(404, "Draft workspace not found") from e
                raise
            integrity_checks = _run_integrity_checks(workspace)
            errors = [c for c in integrity_checks if c.get("severity") == "error"]
            warnings = [c for c in integrity_checks if c.get("severity") == "warning"]
            if errors:
                raise HTTPException(422, detail={"integrity": {"status": "failed", "checks": integrity_checks}})
            if warnings and not b.acknowledge_warnings:
                raise HTTPException(409, detail={"integrity": {"status": "warning", "checks": integrity_checks}})
            baseline_id = f"bl_{uuid.uuid4().hex[:12]}"
            baseline_version = "v1"
            compiled = _compile_workspace_to_model_config(
                workspace, x_tenant_id, baseline_id, baseline_version, integrity_checks, x_user_id or None
            )
            try:
                ModelConfig.model_validate(compiled)
            except Exception as e:
                raise HTTPException(422, detail={"message": f"Workspace does not compile to valid model_config: {e}"}) from e
            storage_path = f"{x_tenant_id}/model_config_v1/{baseline_id}_{baseline_version}.json"
            await ensure_tenant(conn, x_tenant_id)
            await conn.execute(
                "UPDATE model_baselines SET is_active = false WHERE tenant_id = $1",
                x_tenant_id,
            )
            await conn.execute(
                """INSERT INTO model_baselines (tenant_id, baseline_id, baseline_version, status, storage_path, is_active)
                   VALUES ($1, $2, $3, 'active', $4, true)""",
                x_tenant_id,
                baseline_id,
                baseline_version,
                storage_path,
            )
            store.save(x_tenant_id, "model_config_v1", f"{baseline_id}_{baseline_version}", compiled)
            await conn.execute(
                "UPDATE draft_sessions SET status = $1 WHERE tenant_id = $2 AND draft_session_id = $3",
                STATUS_COMMITTED,
                x_tenant_id,
                draft_session_id,
            )
            await create_audit_event(
                conn,
                x_tenant_id,
                EVENT_DRAFT_COMMITTED,
                "draft",
                "draft_session",
                draft_session_id,
                user_id=x_user_id or None,
                event_data={"baseline_id": baseline_id, "baseline_version": baseline_version},
            )
    return {
        "baseline_id": baseline_id,
        "baseline_version": baseline_version,
        "integrity": {"status": "passed" if not warnings else "warning", "checks": integrity_checks},
    }
