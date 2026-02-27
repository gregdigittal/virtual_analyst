"""AI Disclosure Drafter — generates AFS note/section content from NL instructions."""

from __future__ import annotations

import json
from typing import Any

from apps.api.app.services.llm.provider import LLMResponse, Message
from apps.api.app.services.llm.router import LLMRouter

TASK_LABEL = "afs_disclosure_draft"

DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Section/note title"},
        "paragraphs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["text", "table", "heading"]},
                    "content": {"type": "string", "description": "Paragraph text or markdown table"},
                },
                "required": ["type", "content"],
                "additionalProperties": False,
            },
            "description": "Ordered list of content blocks",
        },
        "references": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Standard references cited (e.g. 'IAS 16.73', 'IFRS 15.113')",
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Any compliance warnings or items needing attention",
        },
    },
    "required": ["title", "paragraphs", "references", "warnings"],
    "additionalProperties": False,
}

VALIDATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "compliant": {"type": "boolean"},
        "missing_disclosures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "reference": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {"type": "string", "enum": ["critical", "important", "minor"]},
                },
                "required": ["reference", "description", "severity"],
                "additionalProperties": False,
            },
        },
        "suggestions": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["compliant", "missing_disclosures", "suggestions"],
    "additionalProperties": False,
}


def _build_system_prompt(
    framework_name: str,
    standard: str,
    period_start: str,
    period_end: str,
    entity_name: str,
) -> str:
    return f"""You are an expert financial reporting assistant specialising in {framework_name} ({standard}).

You are preparing the Annual Financial Statements for {entity_name} for the period {period_start} to {period_end}.

Rules:
1. All financial figures in disclosures MUST come from the trial balance data provided — never invent numbers.
2. Follow the disclosure requirements of the applicable standard precisely.
3. Use formal financial reporting language appropriate for published annual financial statements.
4. Where the standard requires specific wording, use it exactly.
5. Include standard references (e.g. "IAS 16.73") in your references array.
6. Flag any areas where additional information from the preparer is needed in the warnings array.
7. If prior-year comparatives are available, include them.
8. Output structured content as paragraphs of type "text", "table" (markdown table format), or "heading"."""


def _build_draft_prompt(
    section_title: str,
    nl_instruction: str,
    trial_balance_summary: str,
    prior_afs_context: str,
    existing_draft: str | None,
) -> str:
    parts = [f"## Section: {section_title}\n"]

    if existing_draft:
        parts.append(f"### Current Draft\n{existing_draft}\n")
        parts.append(f"### User Feedback / Instruction\n{nl_instruction}\n")
        parts.append("Please revise the draft based on the user's feedback above. Keep what's good, fix what's flagged.\n")
    else:
        parts.append(f"### Instruction\n{nl_instruction}\n")
        parts.append("Please draft this section from scratch based on the instruction above.\n")

    parts.append(f"### Trial Balance Data\n{trial_balance_summary}\n")

    if prior_afs_context:
        parts.append(f"### Prior Year AFS Reference\n{prior_afs_context}\n")

    return "\n".join(parts)


async def draft_section(
    llm_router: LLMRouter,
    tenant_id: str,
    *,
    framework_name: str,
    standard: str,
    period_start: str,
    period_end: str,
    entity_name: str,
    section_title: str,
    nl_instruction: str,
    trial_balance_summary: str,
    prior_afs_context: str = "",
    existing_draft: str | None = None,
) -> LLMResponse:
    system = _build_system_prompt(framework_name, standard, period_start, period_end, entity_name)
    user = _build_draft_prompt(section_title, nl_instruction, trial_balance_summary, prior_afs_context, existing_draft)

    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    return await llm_router.complete_with_routing(
        tenant_id=tenant_id,
        messages=messages,
        response_schema=DRAFT_SCHEMA,
        task_label=TASK_LABEL,
        max_tokens=8192,
        temperature=0.3,
    )


async def validate_sections(
    llm_router: LLMRouter,
    tenant_id: str,
    *,
    framework_name: str,
    standard: str,
    sections_summary: str,
    checklist_items: str,
) -> LLMResponse:
    messages: list[Message] = [
        {
            "role": "system",
            "content": f"You are a financial reporting compliance reviewer for {framework_name} ({standard}). "
            "Compare the generated disclosure sections against the required disclosure checklist. "
            "Identify any missing or incomplete disclosures.",
        },
        {
            "role": "user",
            "content": f"## Generated Sections\n{sections_summary}\n\n## Disclosure Checklist\n{checklist_items}\n\n"
            "Please validate completeness and flag any missing required disclosures.",
        },
    ]

    return await llm_router.complete_with_routing(
        tenant_id=tenant_id,
        messages=messages,
        response_schema=VALIDATION_SCHEMA,
        task_label="afs_disclosure_validate",
        max_tokens=4096,
        temperature=0.1,
    )
