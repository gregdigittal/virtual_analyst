"""AI Tax Note Drafter — generates IAS 12 / ASC 740 tax disclosure notes."""

from __future__ import annotations

import json
from typing import Any

from apps.api.app.services.llm.provider import LLMResponse, Message
from apps.api.app.services.llm.router import LLMRouter

TASK_LABEL = "afs_tax_note"

TAX_NOTE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Tax note title (e.g. 'Income Tax')"},
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
            "description": "Standard references cited (e.g. 'IAS 12.79', 'ASC 740-10-50-2')",
        },
        "warnings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Areas needing attention or additional information",
        },
    },
    "required": ["title", "paragraphs", "references", "warnings"],
    "additionalProperties": False,
}


def _build_system_prompt(framework_name: str, standard: str) -> str:
    tax_standard = "IAS 12 (Income Taxes)" if "ifrs" in standard.lower() else "ASC 740 (Income Taxes)"
    return f"""You are an expert tax disclosure drafter for {framework_name} ({standard}).

You are preparing the income tax note for the Annual Financial Statements.

Applicable standard: {tax_standard}

Rules:
1. All figures MUST come from the computation data provided — never invent numbers.
2. Follow {tax_standard} disclosure requirements precisely.
3. Include a current tax expense table, deferred tax movement table, and tax rate reconciliation.
4. Use formal financial reporting language appropriate for published annual financial statements.
5. Include standard references in the references array.
6. Flag any areas needing additional information in the warnings array.
7. Output structured content as paragraphs of type "text", "table" (markdown table format), or "heading"."""


def _build_tax_prompt(
    computation: dict,
    differences: list[dict],
    nl_instruction: str | None,
) -> str:
    parts = ["## Tax Computation Data\n"]

    parts.append(f"- Jurisdiction: {computation.get('jurisdiction', 'N/A')}")
    parts.append(f"- Statutory rate: {computation.get('statutory_rate', 0):.2%}")
    parts.append(f"- Taxable income: {computation.get('taxable_income', 0):,.2f}")
    parts.append(f"- Current tax: {computation.get('current_tax', 0):,.2f}")
    parts.append("")

    # Reconciliation
    recon = computation.get("reconciliation_json", [])
    if isinstance(recon, str):
        try:
            recon = json.loads(recon)
        except json.JSONDecodeError:
            recon = []
    if recon:
        parts.append("### Tax Rate Reconciliation Items")
        for item in recon:
            desc = item.get("description", "")
            amount = item.get("amount", 0)
            effect = item.get("tax_effect", 0)
            parts.append(f"- {desc}: amount={amount:,.2f}, tax effect={effect:,.2f}")
        parts.append("")

    # Deferred tax summary
    dtj = computation.get("deferred_tax_json", {})
    if isinstance(dtj, str):
        try:
            dtj = json.loads(dtj)
        except json.JSONDecodeError:
            dtj = {}
    if dtj:
        parts.append("### Deferred Tax Summary")
        parts.append(f"- Total deferred tax asset: {dtj.get('total_deferred_tax_asset', 0):,.2f}")
        parts.append(f"- Total deferred tax liability: {dtj.get('total_deferred_tax_liability', 0):,.2f}")
        parts.append(f"- Net deferred tax: {dtj.get('net_deferred_tax', 0):,.2f}")
        parts.append("")

    # Temporary differences
    if differences:
        parts.append("### Temporary Differences")
        for d in differences:
            parts.append(
                f"- {d.get('description', 'N/A')}: carrying={d.get('carrying_amount', 0):,.2f}, "
                f"tax base={d.get('tax_base', 0):,.2f}, difference={d.get('difference', 0):,.2f}, "
                f"deferred tax={d.get('deferred_tax_effect', 0):,.2f} ({d.get('diff_type', 'liability')})"
            )
        parts.append("")

    if nl_instruction:
        parts.append(f"### Additional Instructions\n{nl_instruction}\n")

    parts.append("Please draft the complete income tax note for the financial statements.")

    return "\n".join(parts)


async def draft_tax_note(
    llm_router: LLMRouter,
    tenant_id: str,
    *,
    framework_name: str,
    standard: str,
    computation: dict,
    differences: list[dict],
    nl_instruction: str | None = None,
) -> LLMResponse:
    system = _build_system_prompt(framework_name, standard)
    user = _build_tax_prompt(computation, differences, nl_instruction)

    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    return await llm_router.complete_with_routing(
        tenant_id=tenant_id,
        messages=messages,
        response_schema=TAX_NOTE_SCHEMA,
        task_label=TASK_LABEL,
        max_tokens=8192,
        temperature=0.3,
    )
