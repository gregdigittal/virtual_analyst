"""Agent-powered budget natural language queries."""

from __future__ import annotations

import json
from typing import Any

import structlog

from apps.api.app.services.agent import tools as agent_tools
from apps.api.app.services.agent.service import AgentService

logger = structlog.get_logger()

NL_QUERY_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["answer"],
    "properties": {
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "budget_id": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["source"],
            },
        },
    },
}

QUERY_PLAN_SCHEMA = {
    "type": "object",
    "required": ["queries"],
    "properties": {
        "queries": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["tool", "args"],
                "properties": {
                    "tool": {
                        "type": "string",
                        "enum": [
                            "query_budget_summary",
                            "query_budget_line_items",
                            "query_budget_actuals",
                            "query_department_breakdown",
                            "calculate_variance",
                        ],
                    },
                    "args": {"type": "object"},
                },
            },
        },
    },
}

TOOL_DESCRIPTIONS = """Available tools:
- query_budget_summary(budget_id?: string) — list all budgets or get a specific budget's metadata and total
- query_budget_line_items(budget_id: string, account_ref?: string, limit?: int) — get line items with per-period amounts
- query_budget_actuals(budget_id: string, account_ref?: string) — get actual spending data
- query_department_breakdown(budget_id: string) — get department-level allocation vs actuals
- calculate_variance(budget_id: string, account_ref?: string) — compute budget vs actual variance"""


async def run_budget_nl_query_agent(
    tenant_id: str,
    agent: AgentService,
    question: str,
    budget_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Two-step agent: plan queries → execute → answer."""
    plan_prompt = (
        f"The user asked a question about their budgets. Determine which data queries are needed to answer it.\n\n"
        f"{TOOL_DESCRIPTIONS}\n\n"
        f"Question: {question}\n\n"
    )
    if budget_ids:
        plan_prompt += f"Available budget IDs: {budget_ids}\n\n"
    plan_prompt += "Return a query plan (list of tool calls with args). Use the minimum number of queries needed."

    plan_result = await agent.run_task(
        tenant_id=tenant_id,
        prompt=plan_prompt,
        output_schema=QUERY_PLAN_SCHEMA,
        task_label="budget_nl_query_plan",
        max_turns=3,
        max_budget_usd=0.10,
        model="haiku",
    )

    queries = plan_result.content.get("queries", [])
    tool_dispatch = {
        "query_budget_summary": agent_tools.query_budget_summary,
        "query_budget_line_items": agent_tools.query_budget_line_items,
        "query_budget_actuals": agent_tools.query_budget_actuals,
        "query_department_breakdown": agent_tools.query_department_breakdown,
        "calculate_variance": agent_tools.calculate_variance,
    }

    query_results: list[dict[str, Any]] = []
    for q in queries[:5]:
        tool_name = q.get("tool", "")
        args = q.get("args", {})
        fn = tool_dispatch.get(tool_name)
        if fn:
            try:
                result = await fn(tenant_id=tenant_id, **args)
                query_results.append({"tool": tool_name, "args": args, "result": result})
            except Exception as e:
                query_results.append({"tool": tool_name, "args": args, "error": str(e)})

    results_json = json.dumps(query_results, indent=2, default=str)
    if len(results_json) > 20000:
        results_json = results_json[:20000] + "\n...[truncated]"

    answer_prompt = (
        f"Answer the user's question using ONLY the following queried data. "
        f"Do not invent or assume any numbers. If the answer cannot be determined from the data, say so clearly. "
        f"Keep the answer concise (1-3 sentences). Include citations referencing the data sources.\n\n"
        f"Queried data:\n{results_json}\n\n"
        f"Question: {question}"
    )

    answer_result = await agent.run_task(
        tenant_id=tenant_id,
        prompt=answer_prompt,
        output_schema=NL_QUERY_RESPONSE_SCHEMA,
        task_label="budget_nl_query_answer",
        max_turns=3,
        max_budget_usd=0.15,
    )

    return answer_result.content
