"""Integration tests for agent SDK: feature flags, metering, quota, error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.app.deps import get_agent_service, reset_agent_service
from apps.api.app.services.agent.service import AgentService
from shared.fm_shared.errors import LLMError


def test_feature_flag_disabled_returns_none() -> None:
    """When agent_sdk_enabled is False, get_agent_service returns None."""
    reset_agent_service()
    with patch("apps.api.app.deps.get_settings") as mock_settings:
        mock_settings.return_value.agent_sdk_enabled = False
        mock_settings.return_value.anthropic_api_key = "sk-test"
        assert get_agent_service() is None


def test_feature_flag_enabled_no_key_returns_none() -> None:
    """When agent_sdk_enabled is True but no anthropic key, get_agent_service returns None."""
    reset_agent_service()
    with patch("apps.api.app.deps.get_settings") as mock_settings:
        mock_settings.return_value.agent_sdk_enabled = True
        mock_settings.return_value.anthropic_api_key = ""
        assert get_agent_service() is None


def test_feature_flag_enabled_with_key_returns_service() -> None:
    """When agent_sdk_enabled and anthropic_api_key set, get_agent_service returns AgentService."""
    reset_agent_service()
    with patch("apps.api.app.deps.get_settings") as mock_settings:
        mock_settings.return_value.agent_sdk_enabled = True
        mock_settings.return_value.anthropic_api_key = "sk-test"
        svc = get_agent_service()
        assert svc is not None
        assert isinstance(svc, AgentService)


@pytest.mark.asyncio
async def test_agent_run_task_records_usage_via_metering() -> None:
    """AgentService.run_task calls add_usage when SDK yields cost/tokens."""
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
        with patch("apps.api.app.services.agent.service.check_limit", new_callable=AsyncMock, return_value=True):
            with patch("apps.api.app.services.agent.service.add_usage", new_callable=AsyncMock) as mock_add:
                with patch("apps.api.app.services.agent.service.get_settings") as mock_settings:
                    mock_settings.return_value.agent_sdk_max_turns = 15
                    mock_settings.return_value.agent_sdk_max_budget_usd = 0.50
                    mock_settings.return_value.agent_sdk_default_model = "sonnet"
                    mock_settings.return_value.llm_tokens_monthly_limit = 1_000_000
                service = AgentService(api_key="sk-test")
                await service.run_task("t_int", "Hello", task_label="integration_test")
    mock_add.assert_called_once()
    call_args = mock_add.call_args[0]
    assert call_args[0] == "t_int"
    assert call_args[1] == 200
    assert call_args[2] == 0.02


@pytest.mark.asyncio
async def test_agent_run_task_quota_exceeded_raises_llm_error() -> None:
    """When check_limit returns False, run_task raises LLMError with ERR_LLM_QUOTA_EXCEEDED."""
    with patch("apps.api.app.services.agent.service.check_limit", new_callable=AsyncMock, return_value=False):
        service = AgentService(api_key="sk-test")
        with pytest.raises(LLMError) as exc_info:
            await service.run_task("t_quota", "Hi", task_label="test")
        assert exc_info.value.code == "ERR_LLM_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_agent_run_task_sdk_error_propagates_llm_error() -> None:
    """When SDK query raises, run_task raises LLMError with ERR_LLM_PROVIDER_ERROR."""
    async def fake_query_raise(*, prompt: str, options: object):
        raise RuntimeError("Agent failed")
        yield

    fake_sdk = MagicMock()
    fake_sdk.ClaudeAgentOptions = MagicMock()
    fake_sdk.query = fake_query_raise

    with patch.dict("sys.modules", {"claude_agent_sdk": fake_sdk}):
        with patch("apps.api.app.services.agent.service.check_limit", new_callable=AsyncMock, return_value=True):
            service = AgentService(api_key="sk-test")
            with pytest.raises(LLMError) as exc_info:
                await service.run_task("t_err", "Hi", task_label="test")
            assert exc_info.value.code == "ERR_LLM_PROVIDER_ERROR"
