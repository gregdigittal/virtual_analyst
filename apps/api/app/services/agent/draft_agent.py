"""Agent-powered draft assumptions chat with full context."""

from __future__ import annotations

import json
from typing import Any

from apps.api.app.services.agent.service import AgentService

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

DRAFT_AGENT_SYSTEM_PROMPT = """You are a financial analyst assistant helping build a financial model.

## CRITICAL RULES
- Do NOT invent, fabricate, or hallucinate any data, facts, statistics, or financial figures.
- Every proposed value MUST be grounded in one of: (a) the user's explicit input, (b) evidence provided below, (c) standard industry benchmarks you can cite by name.
- If you lack sufficient information to propose a value, set confidence to 'low' and clearly state in the evidence field that this is a placeholder requiring user verification.
- Do NOT present assumptions as facts. Always qualify uncertain values.
- Do NOT propose values outside physically reasonable bounds for the business type.

## Confidence Rating Guide
- high: Direct evidence from user input, uploaded documents, or named industry benchmark
- medium: Reasonable inference from available context, clearly stated as such
- low: Placeholder or educated guess — MUST be flagged for user review

## Output Format
Return proposals as structured JSON with: path (e.g. 'assumptions.revenue_streams[0].drivers.unit_price'), value, evidence, confidence, optional reasoning.
Also include optional clarification (question for user) and commentary (narrative explanation).

## Valid Proposal Paths (prefix with 'assumptions.')
- assumptions.revenue_streams[N].label, .stream_type, .drivers.*
- assumptions.cost_structure.variable_costs[N].*, .fixed_costs[N].*
- assumptions.working_capital.ar_days, .ap_days, .inventory_days
- assumptions.capex.items[N].*, .capex.maintenance_pct
- assumptions.funding.equity.initial_equity, .funding.debt.*
"""


async def run_draft_chat_agent(
    tenant_id: str,
    agent: AgentService,
    workspace: dict[str, Any],
    user_message: str,
) -> dict[str, Any]:
    """Run agent-powered draft chat. Returns proposals, clarification, commentary."""
    assumptions = workspace.get("assumptions", {})
    blueprint = workspace.get("driver_blueprint", {})
    evidence = workspace.get("evidence", [])
    chat_history = workspace.get("chat_history", [])

    context = (
        f"## Current Assumptions\n{json.dumps(assumptions, default=str)}\n\n"
        f"## Driver Blueprint\n{json.dumps(blueprint, default=str)}\n\n"
        f"## Evidence\n{json.dumps(evidence[:20], default=str)}\n\n"
        f"## Chat History ({len(chat_history)} messages)\n"
    )
    for entry in chat_history:
        role = entry.get("role", "user")
        content = entry.get("content", "")
        context += f"[{role}]: {content[:500]}\n"

    # Truncate to avoid exceeding agent context window
    if len(context) > 25000:
        context = context[:25000] + "\n...[truncated]"

    prompt = f"{context}\n\n## New User Message\n{user_message}"

    result = await agent.run_task(
        tenant_id=tenant_id,
        prompt=prompt,
        system_prompt=DRAFT_AGENT_SYSTEM_PROMPT,
        output_schema=PROPOSAL_RESPONSE_SCHEMA,
        task_label="draft_assumptions_agent",
        max_turns=8,
        max_budget_usd=0.40,
    )

    return result.content
