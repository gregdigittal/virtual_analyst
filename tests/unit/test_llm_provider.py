"""Unit tests for LLM provider abstraction (VA-P2-03): structured JSON output."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from apps.api.app.services.llm.provider import (
    LLMResponse,
    TokenUsage,
    AnthropicProvider,
    OpenAIProvider,
    _ensure_additional_properties_false,
)


def test_ensure_additional_properties_false_adds_to_objects() -> None:
    """Object schemas get additionalProperties: false for provider compatibility."""
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "nested": {"type": "object", "properties": {"x": {"type": "number"}}},
        },
        "required": ["name"],
    }
    out = _ensure_additional_properties_false(schema)
    assert out.get("additionalProperties") is False
    assert out["properties"]["nested"].get("additionalProperties") is False


async def _run_anthropic_mocked() -> LLMResponse:
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}
    messages = [{"role": "user", "content": "What is 2+2?"}]
    provider = AnthropicProvider(api_key="test-key")
    mock_resp = MagicMock()
    mock_resp.content = [type("Block", (), {"text": '{"answer": "4"}'})()]
    mock_resp.usage = type("Usage", (), {"input_tokens": 10, "output_tokens": 5})()

    with patch("anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_resp)
        return await provider.complete(messages, schema, "test_task")


def test_anthropic_provider_returns_valid_structured_output() -> None:
    """AnthropicProvider.complete returns LLMResponse with parsed dict content (mocked)."""
    result = asyncio.run(_run_anthropic_mocked())
    assert isinstance(result, LLMResponse)
    assert result.content == {"answer": "4"}
    assert result.provider == "anthropic"
    assert result.tokens.prompt_tokens == 10
    assert result.tokens.completion_tokens == 5


async def _run_openai_mocked() -> LLMResponse:
    schema = {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]}
    messages = [{"role": "user", "content": "Return value 42"}]
    provider = OpenAIProvider(api_key="test-key")
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 8
    mock_usage.completion_tokens = 3
    mock_usage.total_tokens = 11
    mock_msg = MagicMock()
    mock_msg.content = '{"value": 42}'
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_resp.usage = mock_usage

    with patch("openai.AsyncOpenAI") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
        return await provider.complete(messages, schema, "test_task")


def test_openai_provider_returns_valid_structured_output() -> None:
    """OpenAIProvider.complete returns LLMResponse with parsed dict content (mocked)."""
    result = asyncio.run(_run_openai_mocked())
    assert isinstance(result, LLMResponse)
    assert result.content == {"value": 42}
    assert result.provider == "openai"


def test_llm_response_has_required_fields() -> None:
    """LLMResponse dataclass has content, tokens, latency_ms, model, provider, cost_estimate_usd."""
    r = LLMResponse(
        content={"k": "v"},
        raw_text="{}",
        tokens=TokenUsage(1, 2, 3),
        latency_ms=100,
        model="gpt-4o",
        provider="openai",
        cost_estimate_usd=0.001,
    )
    assert r.content == {"k": "v"}
    assert r.tokens.total_tokens == 3
    assert r.latency_ms == 100
    assert r.cost_estimate_usd == 0.001
