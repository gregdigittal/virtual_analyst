"""AFS AI Analytics — anomaly detection, commentary suggestions, going concern assessment."""

from __future__ import annotations

from typing import Any

from apps.api.app.services.llm.provider import LLMResponse, Message
from apps.api.app.services.llm.router import LLMRouter


ANOMALY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "anomalies": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ratio_key": {"type": "string"},
                    "severity": {"type": "string", "enum": ["info", "warning", "critical"]},
                    "description": {"type": "string"},
                    "disclosure_impact": {"type": "string"},
                },
                "required": ["ratio_key", "severity", "description", "disclosure_impact"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["anomalies"],
    "additionalProperties": False,
}

COMMENTARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "key_highlights": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 key financial highlights for directors' report",
        },
        "risk_factors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Material risk factors to mention",
        },
        "outlook_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Forward-looking commentary suggestions",
        },
    },
    "required": ["key_highlights", "risk_factors", "outlook_points"],
    "additionalProperties": False,
}

GOING_CONCERN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "risk_level": {"type": "string", "enum": ["low", "moderate", "high", "critical"]},
        "factors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "factor": {"type": "string"},
                    "indicator": {"type": "string", "enum": ["positive", "neutral", "negative"]},
                    "detail": {"type": "string"},
                },
                "required": ["factor", "indicator", "detail"],
                "additionalProperties": False,
            },
        },
        "recommendation": {"type": "string"},
        "disclosure_required": {"type": "boolean"},
    },
    "required": ["risk_level", "factors", "recommendation", "disclosure_required"],
    "additionalProperties": False,
}


def _format_ratios_for_prompt(ratios: dict, benchmarks: dict | None = None) -> str:
    """Format ratio data into a readable prompt section."""
    lines = ["## Computed Financial Ratios\n"]
    for key, value in ratios.items():
        if key.startswith("_"):
            continue
        if value is None:
            continue
        label = key.replace("_", " ").title()
        bench_info = ""
        if benchmarks and key in benchmarks:
            b = benchmarks[key]
            bench_info = f"  [Industry: p25={b['p25']}, median={b['median']}, p75={b['p75']}]"
        lines.append(f"- {label}: {value}{bench_info}")
    return "\n".join(lines)


async def detect_anomalies(
    llm_router: LLMRouter,
    tenant_id: str,
    *,
    entity_name: str,
    ratios: dict,
    benchmarks: dict | None = None,
) -> LLMResponse:
    """Detect unusual ratio values that may require additional disclosure."""
    system = (
        "You are a financial analyst reviewing computed ratios for an entity's annual financial statements. "
        "Identify any unusual or concerning values. Compare against industry benchmarks where provided. "
        "Focus on ratios that deviate significantly from normal ranges or industry norms. "
        "For each anomaly, explain the potential disclosure impact under IFRS/GAAP."
    )
    user = f"Entity: {entity_name}\n\n{_format_ratios_for_prompt(ratios, benchmarks)}"

    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return await llm_router.complete_with_routing(
        tenant_id=tenant_id,
        messages=messages,
        response_schema=ANOMALY_SCHEMA,
        task_label="afs_anomaly_detection",
        max_tokens=4096,
        temperature=0.2,
    )


async def generate_commentary(
    llm_router: LLMRouter,
    tenant_id: str,
    *,
    entity_name: str,
    framework_name: str,
    ratios: dict,
    benchmarks: dict | None = None,
) -> LLMResponse:
    """Generate management commentary suggestions for directors' report."""
    system = (
        f"You are a financial reporting advisor helping prepare the directors' report for {entity_name} "
        f"under {framework_name}. Based on the financial ratios, suggest key talking points, "
        "risk factors, and forward-looking statements. Be specific and reference actual figures."
    )
    user = _format_ratios_for_prompt(ratios, benchmarks)

    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return await llm_router.complete_with_routing(
        tenant_id=tenant_id,
        messages=messages,
        response_schema=COMMENTARY_SCHEMA,
        task_label="afs_management_commentary",
        max_tokens=4096,
        temperature=0.3,
    )


async def assess_going_concern(
    llm_router: LLMRouter,
    tenant_id: str,
    *,
    entity_name: str,
    framework_name: str,
    ratios: dict,
) -> LLMResponse:
    """Assess going concern risk factors based on financial ratios."""
    system = (
        f"You are an auditor assessing going concern for {entity_name} under {framework_name}. "
        "Evaluate the financial ratios for indicators of going concern risk per IAS 1 / ASU 2014-15. "
        "Consider: liquidity, solvency, profitability trends, and the Altman Z-score proxy. "
        "Classify risk level and determine if additional disclosure is required."
    )
    user = _format_ratios_for_prompt(ratios)

    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return await llm_router.complete_with_routing(
        tenant_id=tenant_id,
        messages=messages,
        response_schema=GOING_CONCERN_SCHEMA,
        task_label="afs_going_concern",
        max_tokens=4096,
        temperature=0.1,
    )
