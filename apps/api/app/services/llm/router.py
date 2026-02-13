from __future__ import annotations

from typing import Any

from apps.api.app.core.settings import get_settings
from apps.api.app.services.llm.circuit_breaker import CircuitBreaker
from apps.api.app.services.llm.metering import add_usage, check_limit
from apps.api.app.services.llm.provider import (
    LLMProvider,
    LLMResponse,
    AnthropicProvider,
    OpenAIProvider,
)
from shared.fm_shared.errors import LLMError

DEFAULT_POLICY = {
    "rules": [
        {"task_label": "draft_assumptions", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 4096, "temperature": 0.2},
        {"task_label": "draft_assumptions", "priority": 2, "provider": "openai", "model": "gpt-4o", "max_tokens": 4096, "temperature": 0.2},
        {"task_label": "evidence_extraction", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 2048, "temperature": 0.1},
        {"task_label": "memo_generation", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 8192, "temperature": 0.3},
    ],
    "fallback": {"provider": "openai", "model": "gpt-4o-mini", "max_tokens": 4096, "temperature": 0.2},
}


def _resolve_candidates(task_label: str, policy: dict[str, Any] | None = None) -> list[tuple[str, str, int, float]]:
    policy = policy or DEFAULT_POLICY
    rules = [r for r in policy.get("rules", []) if r.get("task_label") == task_label]
    rules.sort(key=lambda r: r.get("priority", 99))
    out = []
    for r in rules:
        out.append((
            r["provider"],
            r.get("model", "gpt-4o" if r["provider"] == "openai" else "claude-sonnet-4-5-20250929"),
            r.get("max_tokens", 4096),
            r.get("temperature", 0.2),
        ))
    fb = policy.get("fallback") or {}
    out.append((
        fb.get("provider", "openai"),
        fb.get("model", "gpt-4o-mini"),
        fb.get("max_tokens", 4096),
        fb.get("temperature", 0.2),
    ))
    return out


def _build_provider(provider_key: str, model: str) -> LLMProvider | None:
    settings = get_settings()
    if provider_key == "anthropic":
        if not settings.anthropic_api_key:
            return None
        return AnthropicProvider(api_key=settings.anthropic_api_key, model=model)
    if provider_key == "openai":
        if not settings.openai_api_key:
            return None
        return OpenAIProvider(api_key=settings.openai_api_key, model=model)
    return None


class LLMRouter:
    def __init__(self) -> None:
        settings = get_settings()
        self._circuit = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_failure_threshold,
            recovery_timeout_sec=settings.circuit_breaker_recovery_seconds,
        )
        self._policy: dict[str, Any] | None = None

    def set_policy(self, policy: dict[str, Any]) -> None:
        self._policy = policy

    def resolve(self, task_label: str) -> list[tuple[str, str, int, float]]:
        return _resolve_candidates(task_label, self._policy)

    async def complete_with_routing(
        self,
        tenant_id: str,
        messages: list[dict[str, str]],
        response_schema: dict[str, Any],
        task_label: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        settings = get_settings()
        if not check_limit(tenant_id, settings.llm_tokens_monthly_limit):
            raise LLMError(
                "Token quota exceeded",
                code="ERR_LLM_QUOTA_EXCEEDED",
                context={"limit": settings.llm_tokens_monthly_limit, "tenant_id": tenant_id},
            )
        candidates = self.resolve(task_label)
        last_error: Exception | None = None
        for provider_key, model, rule_max_tokens, rule_temp in candidates:
            if self._circuit.is_open(provider_key):
                continue
            provider = _build_provider(provider_key, model)
            if provider is None:
                continue
            try:
                resp = await provider.complete(
                    messages,
                    response_schema,
                    task_label,
                    max_tokens=rule_max_tokens,
                    temperature=rule_temp,
                )
                self._circuit.record_success(provider_key)
                add_usage(tenant_id, resp.tokens.total_tokens, resp.cost_estimate_usd)
                return resp
            except Exception as e:
                last_error = e
                self._circuit.record_failure(provider_key)
                continue
        raise LLMError(
            "All providers failed",
            code="ERR_LLM_ALL_PROVIDERS_FAILED",
            details=str(last_error) if last_error else None,
        )
