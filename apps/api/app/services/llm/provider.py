"""LLM provider abstraction: complete(messages, schema, task_label) -> structured JSON."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TypedDict

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class Message(TypedDict):
    """Single chat message."""

    role: str
    content: str


@dataclass
class TokenUsage:
    """Token counts from provider."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class LLMResponse:
    """Structured LLM response with parsed content and metadata."""

    content: dict[str, Any]
    raw_text: str
    tokens: TokenUsage
    latency_ms: int
    model: str
    provider: str
    cost_estimate_usd: float


def _ensure_additional_properties_false(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively set additionalProperties: false on object schemas for provider compatibility."""
    if not isinstance(schema, dict):
        return schema
    out = dict(schema)
    if out.get("type") == "object" and "additionalProperties" not in out:
        out["additionalProperties"] = False
    if "properties" in out and isinstance(out["properties"], dict):
        out["properties"] = {k: _ensure_additional_properties_false(v) for k, v in out["properties"].items()}
    for key in ("items", "schema"):
        if key not in out:
            continue
        val = out[key]
        if isinstance(val, dict):
            out[key] = _ensure_additional_properties_false(val)
        elif isinstance(val, list):
            out[key] = [_ensure_additional_properties_false(i) for i in val]
    return out


class LLMProvider(ABC):
    """Abstract LLM provider: structured JSON output with retry."""

    provider_name: str

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        response_schema: dict[str, Any],
        task_label: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Return structured output matching response_schema. Raises on failure after retries."""
        ...


# Approximate USD per 1M tokens (input, output) for cost estimate
ANTHROPIC_SONNET_RATE = (3.0, 15.0)
OPENAI_GPT4O_RATE = (2.5, 10.0)


def _estimate_cost_usd(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Rough cost estimate in USD."""
    if "claude" in model.lower() or "anthropic" in provider.lower():
        a, b = ANTHROPIC_SONNET_RATE
    else:
        a, b = OPENAI_GPT4O_RATE
    return (prompt_tokens / 1_000_000) * a + (completion_tokens / 1_000_000) * b


class AnthropicProvider(LLMProvider):
    """Anthropic Claude with JSON schema structured output."""

    provider_name = "anthropic"

    def __init__(self, api_key: str | None, model: str = "claude-sonnet-4-5-20250929") -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        self._api_key = api_key
        self._model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((TimeoutError, ConnectionError, httpx.HTTPStatusError)),
    )
    async def complete(
        self,
        messages: list[Message],
        response_schema: dict[str, Any],
        task_label: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        import anthropic

        schema = _ensure_additional_properties_false(response_schema)
        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        system = ""
        api_messages: list[dict[str, Any]] = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                api_messages.append({"role": m["role"], "content": m["content"]})
        if not api_messages:
            raise ValueError("At least one non-system message required")
        start = time.perf_counter()
        response = await client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system or None,
            messages=api_messages,
            temperature=temperature,
            output_config={
                "format": {"type": "json_schema", "schema": schema},
            },
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
        raw_text = text or ""
        content = json.loads(raw_text) if raw_text else {}
        if response_schema is not None:
            import jsonschema
            try:
                jsonschema.validate(content, response_schema)
            except jsonschema.ValidationError as ve:
                raise ValueError(f"LLM response does not match schema: {ve.message}") from ve
        usage = response.usage
        tokens = TokenUsage(
            prompt_tokens=usage.input_tokens,
            completion_tokens=usage.output_tokens,
            total_tokens=usage.input_tokens + usage.output_tokens,
        )
        cost = _estimate_cost_usd(
            self.provider_name, self._model, tokens.prompt_tokens, tokens.completion_tokens
        )
        return LLMResponse(
            content=content,
            raw_text=raw_text,
            tokens=tokens,
            latency_ms=latency_ms,
            model=self._model,
            provider=self.provider_name,
            cost_estimate_usd=cost,
        )


class OpenAIProvider(LLMProvider):
    """OpenAI GPT with JSON schema structured output."""

    provider_name = "openai"

    def __init__(self, api_key: str | None, model: str = "gpt-4o") -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        self._api_key = api_key
        self._model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type((TimeoutError, ConnectionError, httpx.HTTPStatusError)),
    )
    async def complete(
        self,
        messages: list[Message],
        response_schema: dict[str, Any],
        task_label: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        from openai import AsyncOpenAI

        schema = _ensure_additional_properties_false(response_schema)
        client = AsyncOpenAI(api_key=self._api_key)
        api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
        start = time.perf_counter()
        response = await client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=api_messages,
            temperature=temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": schema,
                    "strict": True,
                },
            },
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        choice = response.choices[0] if response.choices else None
        raw_text = (choice.message.content or "") if choice else ""
        content = json.loads(raw_text) if raw_text else {}
        if response_schema is not None:
            import jsonschema
            try:
                jsonschema.validate(content, response_schema)
            except jsonschema.ValidationError as ve:
                raise ValueError(f"LLM response does not match schema: {ve.message}") from ve
        usage = response.usage
        tokens = TokenUsage(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )
        cost = _estimate_cost_usd(
            self.provider_name, self._model, tokens.prompt_tokens, tokens.completion_tokens
        )
        return LLMResponse(
            content=content,
            raw_text=raw_text,
            tokens=tokens,
            latency_ms=latency_ms,
            model=self._model,
            provider=self.provider_name,
            cost_estimate_usd=cost,
        )
