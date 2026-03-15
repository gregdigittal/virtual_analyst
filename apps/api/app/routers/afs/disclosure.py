"""AFS disclosure endpoints — sections, AI drafting, locking, validation."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_llm_router
from apps.api.app.routers.afs._common import (
    VALID_SECTION_TYPES,
    DraftSectionBody,
    UpdateSectionBody,
    _history_id,
    _section_id,
    _validate_engagement,
)
from apps.api.app.services.afs.disclosure_drafter import draft_section, validate_sections
from apps.api.app.services.llm.router import LLMRouter

router = APIRouter()


@router.get("/engagements/{engagement_id}/sections")
async def list_sections(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List all sections for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        rows = await conn.fetch(
            """SELECT * FROM afs_sections
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY section_number ASC, created_at ASC""",
            x_tenant_id, engagement_id,
        )
        return {"items": [dict(r) for r in rows]}


@router.post("/engagements/{engagement_id}/sections/draft", status_code=201)
async def draft_new_section(
    engagement_id: str,
    body: DraftSectionBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """AI-draft a new section for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.section_type not in VALID_SECTION_TYPES:
        raise HTTPException(400, f"Invalid section_type; must be one of {sorted(VALID_SECTION_TYPES)}")

    async with tenant_conn(x_tenant_id) as conn:
        # Load engagement with framework info
        eng = await conn.fetchrow(
            """SELECT e.*, f.name AS framework_name, f.standard
               FROM afs_engagements e
               JOIN afs_frameworks f ON e.tenant_id = f.tenant_id AND e.framework_id = f.framework_id
               WHERE e.tenant_id = $1 AND e.engagement_id = $2""",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        # Load trial balance data for context
        tb_row = await conn.fetchrow(
            """SELECT data_json FROM afs_trial_balances
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY uploaded_at DESC LIMIT 1""",
            x_tenant_id, engagement_id,
        )
        tb_summary = ""
        if tb_row and tb_row["data_json"]:
            accounts = tb_row["data_json"] if isinstance(tb_row["data_json"], list) else []
            lines = []
            for acct in accounts[:100]:  # limit context size
                name = acct.get("account_name", "")
                net = acct.get("net", 0)
                lines.append(f"- {name}: {net:,.2f}")
            tb_summary = "\n".join(lines) if lines else "No trial balance data available."

        # Load prior AFS context
        prior_row = await conn.fetchrow(
            """SELECT extracted_json FROM afs_prior_afs
               WHERE tenant_id = $1 AND engagement_id = $2 AND source_type = 'pdf'
               ORDER BY uploaded_at DESC LIMIT 1""",
            x_tenant_id, engagement_id,
        )
        prior_context = ""
        if prior_row and prior_row["extracted_json"]:
            extracted = prior_row["extracted_json"] if isinstance(prior_row["extracted_json"], dict) else {}
            sections = extracted.get("sections", [])
            parts = []
            for s in sections[:10]:
                title = s.get("title", "")
                text = s.get("text", "")[:500]
                parts.append(f"### {title}\n{text}")
            prior_context = "\n\n".join(parts)

        # Call AI drafter
        llm_result = await draft_section(
            llm,
            x_tenant_id,
            framework_name=eng["framework_name"],
            standard=eng["standard"],
            period_start=str(eng["period_start"]),
            period_end=str(eng["period_end"]),
            entity_name=eng["entity_name"],
            section_title=body.title,
            nl_instruction=body.nl_instruction,
            trial_balance_summary=tb_summary,
            prior_afs_context=prior_context,
        )

        # Determine next section number
        max_num = await conn.fetchval(
            """SELECT COALESCE(MAX(section_number), 0) FROM afs_sections
               WHERE tenant_id = $1 AND engagement_id = $2""",
            x_tenant_id, engagement_id,
        )
        section_number = max_num + 1

        # Insert section
        s_id = _section_id()
        content_json = json.dumps(llm_result.content)
        row = await conn.fetchrow(
            """INSERT INTO afs_sections
               (tenant_id, section_id, engagement_id, section_type, section_number,
                title, content_json, version, status, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, 1, 'draft', $8)
               RETURNING *""",
            x_tenant_id, s_id, engagement_id, body.section_type, section_number,
            body.title, content_json, x_user_id or None,
        )

        # Record history
        h_id = _history_id()
        await conn.execute(
            """INSERT INTO afs_section_history
               (tenant_id, history_id, section_id, version,
                content_json, nl_instruction, changed_by)
               VALUES ($1, $2, $3, 1, $4::jsonb, $5, $6)""",
            x_tenant_id, h_id, s_id,
            content_json, body.nl_instruction, x_user_id or None,
        )

        result = dict(row)
        result["llm_cost_usd"] = llm_result.cost_estimate_usd
        result["llm_tokens"] = llm_result.tokens.total_tokens
        return result


@router.get("/engagements/{engagement_id}/sections/{section_id}")
async def get_section(
    engagement_id: str,
    section_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get a single section by ID."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT * FROM afs_sections
               WHERE tenant_id = $1 AND engagement_id = $2 AND section_id = $3""",
            x_tenant_id, engagement_id, section_id,
        )
        if not row:
            raise HTTPException(404, f"Section {section_id} not found")
        return dict(row)


@router.patch("/engagements/{engagement_id}/sections/{section_id}")
async def update_section(
    engagement_id: str,
    section_id: str,
    body: UpdateSectionBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Update a section: manual edit (content_json) or AI re-draft (nl_instruction only)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        existing = await conn.fetchrow(
            """SELECT * FROM afs_sections
               WHERE tenant_id = $1 AND engagement_id = $2 AND section_id = $3""",
            x_tenant_id, engagement_id, section_id,
        )
        if not existing:
            raise HTTPException(404, f"Section {section_id} not found")
        if existing["status"] == "locked":
            raise HTTPException(409, "Section is locked; unlock it before editing")

        new_version = existing["version"] + 1
        new_title = body.title if body.title is not None else existing["title"]
        llm_cost = None
        llm_tokens = None

        if body.nl_instruction and not body.content_json:
            # AI re-draft: load context and call drafter with existing content
            eng = await conn.fetchrow(
                """SELECT e.*, f.name AS framework_name, f.standard
                   FROM afs_engagements e
                   JOIN afs_frameworks f ON e.tenant_id = f.tenant_id AND e.framework_id = f.framework_id
                   WHERE e.tenant_id = $1 AND e.engagement_id = $2""",
                x_tenant_id, engagement_id,
            )
            _validate_engagement(eng, engagement_id)

            # Load TB data
            tb_row = await conn.fetchrow(
                """SELECT data_json FROM afs_trial_balances
                   WHERE tenant_id = $1 AND engagement_id = $2
                   ORDER BY uploaded_at DESC LIMIT 1""",
                x_tenant_id, engagement_id,
            )
            tb_summary = ""
            if tb_row and tb_row["data_json"]:
                accounts = tb_row["data_json"] if isinstance(tb_row["data_json"], list) else []
                lines = []
                for acct in accounts[:100]:
                    name = acct.get("account_name", "")
                    net = acct.get("net", 0)
                    lines.append(f"- {name}: {net:,.2f}")
                tb_summary = "\n".join(lines) if lines else "No trial balance data available."

            # Load prior AFS context
            prior_row = await conn.fetchrow(
                """SELECT extracted_json FROM afs_prior_afs
                   WHERE tenant_id = $1 AND engagement_id = $2 AND source_type = 'pdf'
                   ORDER BY uploaded_at DESC LIMIT 1""",
                x_tenant_id, engagement_id,
            )
            prior_context = ""
            if prior_row and prior_row["extracted_json"]:
                extracted = prior_row["extracted_json"] if isinstance(prior_row["extracted_json"], dict) else {}
                sections = extracted.get("sections", [])
                parts = []
                for s in sections[:10]:
                    title = s.get("title", "")
                    text = s.get("text", "")[:500]
                    parts.append(f"### {title}\n{text}")
                prior_context = "\n\n".join(parts)

            # Pass existing draft for revision
            existing_draft_json = existing["content_json"]
            existing_draft_str = json.dumps(existing_draft_json) if existing_draft_json else None
            llm_result = await draft_section(
                llm,
                x_tenant_id,
                framework_name=eng["framework_name"],
                standard=eng["standard"],
                period_start=str(eng["period_start"]),
                period_end=str(eng["period_end"]),
                entity_name=eng["entity_name"],
                section_title=new_title,
                nl_instruction=body.nl_instruction,
                trial_balance_summary=tb_summary,
                prior_afs_context=prior_context,
                existing_draft=existing_draft_str,
            )
            content_json = json.dumps(llm_result.content)
            nl_instruction = body.nl_instruction
            llm_cost = llm_result.cost_estimate_usd
            llm_tokens = llm_result.tokens.total_tokens
        elif body.content_json is not None:
            # Manual edit
            content_json = json.dumps(body.content_json)
            nl_instruction = body.nl_instruction
        else:
            # Title-only update or no-op
            content_json = json.dumps(existing["content_json"]) if existing["content_json"] else None
            nl_instruction = body.nl_instruction

        row = await conn.fetchrow(
            """UPDATE afs_sections
               SET title = $4, content_json = $5::jsonb,
                   version = $6, updated_at = now()
               WHERE tenant_id = $1 AND engagement_id = $2 AND section_id = $3
               RETURNING *""",
            x_tenant_id, engagement_id, section_id,
            new_title, content_json, new_version,
        )

        # Record history
        h_id = _history_id()
        await conn.execute(
            """INSERT INTO afs_section_history
               (tenant_id, history_id, section_id, version,
                content_json, nl_instruction, changed_by)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7)""",
            x_tenant_id, h_id, section_id,
            new_version, content_json, nl_instruction, x_user_id or None,
        )

        result = dict(row)
        if llm_cost is not None:
            result["llm_cost_usd"] = llm_cost
            result["llm_tokens"] = llm_tokens
        return result


@router.post("/engagements/{engagement_id}/sections/{section_id}/lock")
async def lock_section(
    engagement_id: str,
    section_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Lock a section to prevent further edits."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """UPDATE afs_sections
               SET status = 'locked', updated_at = now()
               WHERE tenant_id = $1 AND engagement_id = $2 AND section_id = $3
               RETURNING *""",
            x_tenant_id, engagement_id, section_id,
        )
        if not row:
            raise HTTPException(404, f"Section {section_id} not found")
        return dict(row)


@router.post("/engagements/{engagement_id}/sections/{section_id}/unlock")
async def unlock_section(
    engagement_id: str,
    section_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Unlock a section to allow edits."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """UPDATE afs_sections
               SET status = 'draft', updated_at = now()
               WHERE tenant_id = $1 AND engagement_id = $2 AND section_id = $3
               RETURNING *""",
            x_tenant_id, engagement_id, section_id,
        )
        if not row:
            raise HTTPException(404, f"Section {section_id} not found")
        return dict(row)


@router.post("/engagements/{engagement_id}/validate")
async def validate_engagement_sections(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Validate all sections against the disclosure checklist via AI."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        # Load engagement with framework
        eng = await conn.fetchrow(
            """SELECT e.*, f.name AS framework_name, f.standard
               FROM afs_engagements e
               JOIN afs_frameworks f ON e.tenant_id = f.tenant_id AND e.framework_id = f.framework_id
               WHERE e.tenant_id = $1 AND e.engagement_id = $2""",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        # Load all sections
        section_rows = await conn.fetch(
            """SELECT section_type, section_number, title, content_json
               FROM afs_sections
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY section_number ASC""",
            x_tenant_id, engagement_id,
        )

        if not section_rows:
            raise HTTPException(400, "No sections to validate; draft sections first")

        # Build sections summary
        parts = []
        for s in section_rows:
            content = s["content_json"] if s["content_json"] else {}
            title = content.get("title", s["title"]) if isinstance(content, dict) else s["title"]
            paragraphs = content.get("paragraphs", []) if isinstance(content, dict) else []
            text_preview = " ".join(
                p.get("content", "")[:200] for p in paragraphs[:5]
            ) if paragraphs else "(empty)"
            parts.append(f"### {s['section_number']}. {title}\n{text_preview}")
        sections_summary = "\n\n".join(parts)

        # Load disclosure checklist
        checklist_rows = await conn.fetch(
            """SELECT section, reference, description, required
               FROM afs_disclosure_items
               WHERE tenant_id = $1 AND framework_id = $2
               ORDER BY section, reference""",
            x_tenant_id, eng["framework_id"],
        )

        checklist_parts = []
        for item in checklist_rows:
            mandatory = " [MANDATORY]" if item["required"] else ""
            checklist_parts.append(f"- {item['reference']}: {item['description']}{mandatory}")
        checklist_items = "\n".join(checklist_parts) if checklist_parts else "No disclosure checklist items found."

        # Call AI validator
        llm_result = await validate_sections(
            llm,
            x_tenant_id,
            framework_name=eng["framework_name"],
            standard=eng["standard"],
            sections_summary=sections_summary,
            checklist_items=checklist_items,
        )

        result = {**llm_result.content}
        result["llm_cost_usd"] = llm_result.cost_estimate_usd
        result["llm_tokens"] = llm_result.tokens.total_tokens
        result["sections_validated"] = len(section_rows)
        result["checklist_items_checked"] = len(checklist_rows)
        return result
