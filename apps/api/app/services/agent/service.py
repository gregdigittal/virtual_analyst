"""Claude Agent SDK service: manages agent execution with tenant-scoped tools."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from apps.api.app.core.settings import get_settings
from apps.api.app.services.llm.metering import add_usage, check_limit
from shared.fm_shared.errors import LLMError

logger = structlog.get_logger()

AGENT_TIMEOUT_SECONDS = 120  # 2 minute hard timeout per agent task


class AgentService:
    """Wraps Claude Agent SDK for Virtual Analyst agent tasks."""

    def __init__(self, api_key: str, billing: Any = None) -> None:
        self._api_key = api_key
        self._billing = billing

    async def run_task(
        self,
        tenant_id: str,
        prompt: str,
        system_prompt: str | None = None,
        output_schema: dict[str, Any] | None = None,
        task_label: str = "agent_task",
        max_turns: int | None = None,
        max_budget_usd: float | None = None,
        model: str | None = None,
        tool_context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Execute an agent task with cost tracking and tenant quota enforcement."""
        settings = get_settings()

        effective_turns = max_turns or settings.agent_sdk_max_turns
        effective_budget = max_budget_usd or settings.agent_sdk_max_budget_usd
        effective_model = model or settings.agent_sdk_default_model

        if self._billing:
            allowed, current, limit = await self._billing.check_llm_limit(
                tenant_id, estimated_tokens=4096,
            )
            if not allowed:
                raise LLMError(
                    "Token quota exceeded",
                    code="ERR_LLM_QUOTA_EXCEEDED",
                    context={"limit": limit, "current": current, "tenant_id": tenant_id},
                )
        else:
            if not await check_limit(tenant_id, settings.llm_tokens_monthly_limit):
                raise LLMError(
                    "Token quota exceeded",
                    code="ERR_LLM_QUOTA_EXCEEDED",
                    context={"limit": settings.llm_tokens_monthly_limit, "tenant_id": tenant_id},
                )

        try:
            from claude_agent_sdk import ClaudeAgentOptions, query
        except ImportError as e:
            raise LLMError(
                "Claude Agent SDK not installed. Install with: pip install claude-agent-sdk",
                code="ERR_LLM_PROVIDER_ERROR",
            ) from e

        # bypassPermissions: safe for server-side execution where all tools are tenant-scoped
        options = ClaudeAgentOptions(
            model=effective_model,
            max_turns=effective_turns,
            max_budget_usd=effective_budget,
            permission_mode="bypassPermissions",
        )
        if system_prompt:
            options.system_prompt = system_prompt
        if output_schema:
            options.output_format = {"type": "json_schema", "schema": output_schema}

        result_content: dict[str, Any] = {}
        total_cost_usd: float = 0.0
        total_tokens: int = 0
        raw_text: str = ""

        try:
            async with asyncio.timeout(AGENT_TIMEOUT_SECONDS):
                async for message in query(prompt=prompt, options=options):
                    if hasattr(message, "structured_output") and message.structured_output:
                        result_content = message.structured_output
                    if hasattr(message, "total_cost_usd") and message.total_cost_usd:
                        total_cost_usd = message.total_cost_usd
                    if hasattr(message, "total_tokens") and message.total_tokens:
                        total_tokens = message.total_tokens
                    if hasattr(message, "result") and message.result:
                        raw_text = str(message.result)
        except TimeoutError as e:
            logger.error(
                "agent_task_timeout",
                tenant_id=tenant_id,
                task_label=task_label,
                timeout_seconds=AGENT_TIMEOUT_SECONDS,
            )
            raise LLMError(
                f"Agent task timed out after {AGENT_TIMEOUT_SECONDS}s",
                code="ERR_LLM_PROVIDER_ERROR",
                context={"task_label": task_label, "tenant_id": tenant_id},
            ) from e
        except Exception as e:
            logger.error("agent_task_failed", tenant_id=tenant_id, task_label=task_label, error=str(e))
            raise LLMError(
                f"Agent task failed: {e}",
                code="ERR_LLM_PROVIDER_ERROR",
                context={"task_label": task_label, "tenant_id": tenant_id},
            ) from e

        if total_tokens > 0 or total_cost_usd > 0:
            if self._billing:
                await self._billing.record_llm_usage(
                    tenant_id,
                    total_tokens,
                    total_cost_usd,
                    task_label,
                    f"agent_sdk_{effective_model}",
                    effective_model,
                    {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": total_tokens,
                    },
                    0,
                )
            else:
                await add_usage(
                    tenant_id,
                    total_tokens,
                    total_cost_usd,
                    provider=f"agent_sdk_{effective_model}",
                )

        logger.info(
            "agent_task_complete",
            tenant_id=tenant_id,
            task_label=task_label,
            model=effective_model,
            tokens=total_tokens,
            cost_usd=total_cost_usd,
            has_output=bool(result_content),
        )

        return AgentResult(
            content=result_content,
            raw_text=raw_text,
            total_tokens=total_tokens,
            cost_usd=total_cost_usd,
            model=effective_model,
            task_label=task_label,
        )


class AgentResult:
    """Result from an agent task execution."""

    __slots__ = ("content", "raw_text", "total_tokens", "cost_usd", "model", "task_label")

    def __init__(
        self,
        content: dict[str, Any],
        raw_text: str,
        total_tokens: int,
        cost_usd: float,
        model: str,
        task_label: str,
    ) -> None:
        self.content = content
        self.raw_text = raw_text
        self.total_tokens = total_tokens
        self.cost_usd = cost_usd
        self.model = model
        self.task_label = task_label
