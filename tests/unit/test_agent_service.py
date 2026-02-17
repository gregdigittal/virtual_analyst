"""Unit tests for AgentService (Claude Agent SDK wrapper)."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.app.services.agent.service import AgentResult, AgentService
from shared.fm_shared.errors import LLMError


@pytest.mark.asyncio
async def test_run_task_quota_exceeded() -> None:
    """run_task raises LLMError when check_limit returns False."""
    with patch("apps.api.app.services.agent.service.check_limit", new_callable=AsyncMock, return_value=False):
        service = AgentService(api_key="sk-test")
        with pytest.raises(LLMError) as exc_info:
            await service.run_task("t1", "Hello", task_label="test")
        assert exc_info.value.code == "ERR_LLM_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_run_task_sdk_import_error() -> None:
    """run_task raises LLMError when claude_agent_sdk import fails."""
    real_import = __import__
    def raise_for_sdk(name, *args, **kwargs):
        if name == "claude_agent_sdk":
            raise ImportError("No module named 'claude_agent_sdk'")
        return real_import(name, *args, **kwargs)

    saved = sys.modules.pop("claude_agent_sdk", None)
    try:
        with patch("apps.api.app.services.agent.service.check_limit", new_callable=AsyncMock, return_value=True):
            with patch("builtins.__import__", side_effect=raise_for_sdk):
                service = AgentService(api_key="sk-test")
                with pytest.raises(LLMError) as exc_info:
                    await service.run_task("t1", "Hello", task_label="test")
                assert exc_info.value.code == "ERR_LLM_PROVIDER_ERROR"
    finally:
        if saved is not None:
            sys.modules["claude_agent_sdk"] = saved


@pytest.mark.asyncio
async def test_run_task_records_usage() -> None:
    """run_task calls add_usage when SDK yields messages with tokens/cost."""
    fake_message = MagicMock()
    fake_message.structured_output = {"answer": "42"}
    fake_message.total_cost_usd = 0.01
    fake_message.total_tokens = 100
    fake_message.result = "42"

    async def fake_query(*, prompt: str, options: object):
        yield fake_message

    fake_sdk = MagicMock()
    fake_sdk.ClaudeAgentOptions = MagicMock()
    fake_sdk.query = fake_query

    with patch("apps.api.app.services.agent.service.check_limit", new_callable=AsyncMock, return_value=True):
        with patch.dict("sys.modules", {"claude_agent_sdk": fake_sdk}):
            with patch("apps.api.app.services.agent.service.add_usage", new_callable=AsyncMock) as mock_add:
                with patch("apps.api.app.services.agent.service.get_settings") as mock_settings:
                    mock_settings.return_value.agent_sdk_max_turns = 15
                    mock_settings.return_value.agent_sdk_max_budget_usd = 0.50
                    mock_settings.return_value.agent_sdk_default_model = "sonnet"
                    mock_settings.return_value.llm_tokens_monthly_limit = 1_000_000
                service = AgentService(api_key="sk-test")
                result = await service.run_task("t1", "Hello", task_label="test")
    assert result.content == {"answer": "42"}
    assert result.total_tokens == 100
    assert result.cost_usd == 0.01
    mock_add.assert_called_once()
    call_args = mock_add.call_args[0]
    assert call_args[0] == "t1"
    assert call_args[1] == 100
    assert call_args[2] == 0.01
    assert mock_add.call_args[1].get("provider") == "agent_sdk_sonnet"


@pytest.mark.asyncio
async def test_run_task_agent_failure_raises_llm_error() -> None:
    """run_task raises LLMError when SDK query raises."""
    async def fake_query_gen(*, prompt: str, options: object):
        raise RuntimeError("Agent failed")
        yield  # unreachable; makes this an async generator

    fake_sdk = MagicMock()
    fake_sdk.ClaudeAgentOptions = MagicMock()
    fake_sdk.query = fake_query_gen

    with patch("apps.api.app.services.agent.service.check_limit", new_callable=AsyncMock, return_value=True):
        with patch.dict("sys.modules", {"claude_agent_sdk": fake_sdk}):
            service = AgentService(api_key="sk-test")
            with pytest.raises(LLMError) as exc_info:
                await service.run_task("t1", "Hello", task_label="test")
            assert exc_info.value.code == "ERR_LLM_PROVIDER_ERROR"


def test_agent_result_slots() -> None:
    """AgentResult has expected attributes."""
    r = AgentResult(
        content={"x": 1},
        raw_text="text",
        total_tokens=10,
        cost_usd=0.01,
        model="sonnet",
        task_label="test",
    )
    assert r.content == {"x": 1}
    assert r.raw_text == "text"
    assert r.total_tokens == 10
    assert r.cost_usd == 0.01
    assert r.model == "sonnet"
    assert r.task_label == "test"


@pytest.mark.asyncio
async def test_run_task_uses_billing_service_when_available() -> None:
    """run_task checks quota and records usage via billing service when provided."""
    billing = MagicMock()
    billing.check_llm_limit = AsyncMock(return_value=(True, 500, 1_000_000))
    billing.record_llm_usage = AsyncMock()

    fake_message = MagicMock()
    fake_message.structured_output = {"answer": "ok"}
    fake_message.total_cost_usd = 0.02
    fake_message.total_tokens = 200
    fake_message.result = "ok"

    async def fake_query(*, prompt: str, options: object):
        yield fake_message

    fake_sdk = MagicMock()
    fake_sdk.ClaudeAgentOptions = MagicMock()
    fake_sdk.query = fake_query

    with patch.dict("sys.modules", {"claude_agent_sdk": fake_sdk}):
        with patch("apps.api.app.services.agent.service.get_settings") as mock_settings:
            mock_settings.return_value.agent_sdk_max_turns = 15
            mock_settings.return_value.agent_sdk_max_budget_usd = 0.50
            mock_settings.return_value.agent_sdk_default_model = "sonnet"
            mock_settings.return_value.llm_tokens_monthly_limit = 1_000_000
            service = AgentService(api_key="sk-test", billing=billing)
            result = await service.run_task("t1", "Hello", task_label="test")

    assert result.content == {"answer": "ok"}
    billing.check_llm_limit.assert_called_once()
    billing.record_llm_usage.assert_called_once()
    call_args = billing.record_llm_usage.call_args[0]
    assert call_args[0] == "t1"
    assert call_args[1] == 200
    assert call_args[2] == 0.02


@pytest.mark.asyncio
async def test_run_task_billing_quota_exceeded() -> None:
    """run_task raises LLMError when billing service says quota exceeded."""
    billing = MagicMock()
    billing.check_llm_limit = AsyncMock(return_value=(False, 999_000, 1_000_000))

    service = AgentService(api_key="sk-test", billing=billing)
    with pytest.raises(LLMError) as exc_info:
        await service.run_task("t1", "Hello", task_label="test")
    assert exc_info.value.code == "ERR_LLM_QUOTA_EXCEEDED"
    billing.check_llm_limit.assert_called_once()
