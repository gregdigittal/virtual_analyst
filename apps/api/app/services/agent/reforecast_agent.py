"""Agent-powered budget reforecast."""

from __future__ import annotations

import json
from typing import Any

from apps.api.app.services.agent import tools as agent_tools
from apps.api.app.services.agent.service import AgentService

BUDGET_REFORECAST_SCHEMA = {
    "type": "object",
    "required": ["revisions"],
    "properties": {
        "revisions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["account_ref", "amounts"],
                "properties": {
                    "account_ref": {"type": "string"},
                    "amounts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["period_ordinal", "amount"],
                            "properties": {
                                "period_ordinal": {"type": "integer"},
                                "amount": {"type": "number"},
                            },
                        },
                    },
                    "confidence": {"type": "number"},
                    "variance_note": {"type": "string"},
                },
            },
        },
    },
}

REFORECAST_SYSTEM_PROMPT = """You are a financial analyst preparing a rolling budget reforecast.
Given YTD actual spending and original budget amounts for remaining periods, propose revised forecast amounts.

RULES:
- Base revisions on observable trends in the YTD actuals (run-rates, seasonality).
- If spending is tracking close to budget (within 5%), keep the original amounts.
- If spending diverges significantly, compute a revised run-rate and extrapolate.
- Set confidence 0.0-1.0: high (>0.8) when trend is clear, low (<0.5) when volatile.
- Do NOT fabricate data. Only use the numbers provided.
- Include a brief variance_note explaining the rationale for each revision.
"""


async def run_reforecast_agent(
    tenant_id: str,
    agent: AgentService,
    budget_id: str,
    ytd_actuals: list[dict[str, Any]],
    remaining_by_account: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Agent-powered reforecast: analyze trends and propose revisions."""
    try:
        variance_data = await agent_tools.calculate_variance(tenant_id, budget_id)
    except Exception:
        variance_data = {"variances": []}

    prompt = (
        f"Analyze the following budget data and propose revised forecasts for remaining periods.\n\n"
        f"## YTD Actuals\n{json.dumps(ytd_actuals[:50], indent=2)}\n\n"
        f"## Remaining Periods by Account (original budget)\n{json.dumps(remaining_by_account, indent=2)}\n\n"
        f"## Current Variance Analysis\n{json.dumps(variance_data.get('variances', [])[:20], indent=2)}\n\n"
        f"Propose revised amounts for remaining periods. Keep original amounts where spending is on-track."
    )

    result = await agent.run_task(
        tenant_id=tenant_id,
        prompt=prompt,
        system_prompt=REFORECAST_SYSTEM_PROMPT,
        output_schema=BUDGET_REFORECAST_SCHEMA,
        task_label="budget_reforecast_agent",
        max_turns=5,
        max_budget_usd=0.25,
    )

    return result.content
