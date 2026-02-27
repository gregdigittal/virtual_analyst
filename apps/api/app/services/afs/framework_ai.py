"""AFS Framework AI — LLM-powered framework inference from natural-language descriptions."""

from __future__ import annotations

from typing import Any

from apps.api.app.services.llm.provider import LLMResponse, Message
from apps.api.app.services.llm.router import LLMRouter

TASK_LABEL = "afs_framework_inference"

FRAMEWORK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "disclosure_schema": {
            "type": "object",
            "properties": {
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [
                                    "note",
                                    "statement",
                                    "directors_report",
                                    "accounting_policy",
                                ],
                            },
                            "title": {"type": "string"},
                            "reference": {"type": "string"},
                            "required": {"type": "boolean"},
                            "sub_items": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "type",
                            "title",
                            "reference",
                            "required",
                            "sub_items",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["sections"],
            "additionalProperties": False,
        },
        "statement_templates": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "line_items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["title", "line_items"],
                "additionalProperties": False,
            },
        },
        "suggested_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "reference": {"type": "string"},
                    "description": {"type": "string"},
                    "required": {"type": "boolean"},
                },
                "required": ["section", "reference", "description", "required"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "name",
        "disclosure_schema",
        "statement_templates",
        "suggested_items",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You are an expert accounting standards advisor. Given a natural-language "
    "description of an entity's reporting requirements, generate a complete "
    "disclosure framework including:\n"
    "1. All required financial statement sections (SOFP, SOPL, SOCE, SOCF)\n"
    "2. All required disclosure notes with standard references\n"
    "3. Statement templates with line items\n"
    "4. A suggested disclosure checklist\n\n"
    "Base your recommendations on IFRS, US GAAP, and local jurisdictional "
    "requirements as described.\n"
    'Always include standard references (e.g. "IAS 1.54", "ASC 220-10-45").\n'
    "Generate a concise but descriptive framework name based on the requirements described."
)


async def infer_framework(
    llm_router: LLMRouter,
    tenant_id: str,
    *,
    description: str,
    jurisdiction: str | None = None,
    entity_type: str | None = None,
) -> LLMResponse:
    """Infer a custom accounting framework from a natural-language description.

    Returns an LLMResponse whose `.content` dict has keys:
    name, disclosure_schema, statement_templates, suggested_items.
    """
    parts = [
        f"Generate a disclosure framework for the following entity:\n\n{description}"
    ]
    if jurisdiction:
        parts.append(f"\nJurisdiction: {jurisdiction}")
    if entity_type:
        parts.append(f"\nEntity type: {entity_type}")
    user_prompt = "\n".join(parts)

    messages: list[Message] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    return await llm_router.complete_with_routing(
        tenant_id=tenant_id,
        messages=messages,
        response_schema=FRAMEWORK_SCHEMA,
        task_label=TASK_LABEL,
        max_tokens=8192,
        temperature=0.3,
    )
