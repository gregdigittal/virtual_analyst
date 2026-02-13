from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.app.services.llm.circuit_breaker import CircuitBreaker
from apps.api.app.services.llm.metering import add_usage, check_limit, get_usage
from apps.api.app.services.llm.router import (
    DEFAULT_POLICY,
    LLMRouter,
    _resolve_candidates,
)
from shared.fm_shared.errors import LLMError


def test_resolve_candidates_returns_rules_then_fallback() -> None:
    candidates = _resolve_candidates("draft_assumptions")
    assert len(candidates) >= 2
    providers = [c[0] for c in candidates]
    assert "anthropic" in providers or "openai" in providers
    assert candidates[-1][0] == DEFAULT_POLICY["fallback"]["provider"]


def test_resolve_candidates_sorted_by_priority() -> None:
    candidates = _resolve_candidates("draft_assumptions", DEFAULT_POLICY)
    rules = [r for r in DEFAULT_POLICY["rules"] if r["task_label"] == "draft_assumptions"]
    rules.sort(key=lambda r: r["priority"])
    for i, r in enumerate(rules):
        if i < len(candidates) - 1:
            assert candidates[i][0] == r["provider"]


def test_metering_check_limit_and_add_usage() -> None:
    tenant = "t_meter_test"
    assert check_limit(tenant, 1000) is True
    add_usage(tenant, 500, 0.01)
    u = get_usage(tenant)
    assert u["llm_tokens_total"] == 500
    assert u["llm_calls"] == 1
    add_usage(tenant, 500, 0.02)
    assert check_limit(tenant, 1000) is False
    assert check_limit(tenant, 2000) is True


def test_circuit_breaker_opens_after_threshold() -> None:
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=60)
    assert cb.is_open("anthropic") is False
    cb.record_failure("anthropic")
    cb.record_failure("anthropic")
    assert cb.is_open("anthropic") is False
    cb.record_failure("anthropic")
    assert cb.is_open("anthropic") is True
    cb.record_success("anthropic")
    assert cb.is_open("anthropic") is False


def test_circuit_breaker_half_open_failure_reopens() -> None:
    import time
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=1)
    cb.record_failure("openai")
    cb.record_failure("openai")
    assert cb.is_open("openai") is True
    time.sleep(1.1)
    assert cb.is_open("openai") is False
    cb.record_failure("openai")
    assert cb.is_open("openai") is True


@pytest.mark.asyncio
async def test_complete_with_routing_raises_429_when_over_limit() -> None:
    router = LLMRouter()
    tenant = "t_quota_429"
    add_usage(tenant, 2_000_000, 10.0)
    with patch("apps.api.app.services.llm.router.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(llm_tokens_monthly_limit=1_000_000)
        with pytest.raises(LLMError) as exc_info:
            await router.complete_with_routing(
                tenant,
                [{"role": "user", "content": "Hi"}],
                {"type": "object", "properties": {"x": {"type": "string"}}},
                "draft_assumptions",
            )
        assert exc_info.value.code == "ERR_LLM_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_complete_with_routing_fallback_when_primary_fails() -> None:
    router = LLMRouter()
    tenant = "t_fallback"
    with patch("apps.api.app.services.llm.router.get_settings") as mock_settings:
        s = MagicMock()
        s.llm_tokens_monthly_limit = 10_000_000
        s.anthropic_api_key = "sk-ant-test"
        s.openai_api_key = "sk-openai-test"
        s.circuit_breaker_failure_threshold = 5
        s.circuit_breaker_recovery_seconds = 60
        mock_settings.return_value = s
        with patch("apps.api.app.services.llm.router._build_provider") as mock_build:
            primary = MagicMock()
            primary.complete = AsyncMock(side_effect=Exception("anthropic down"))
            secondary = MagicMock()
            from apps.api.app.services.llm.provider import LLMResponse, TokenUsage
            secondary.complete = AsyncMock(return_value=LLMResponse(
                content={"answer": "42"},
                raw_text='{"answer":"42"}',
                tokens=TokenUsage(10, 5, 15),
                latency_ms=100,
                model="gpt-4o-mini",
                provider="openai",
                cost_estimate_usd=0.001,
            ))
            def build(key: str, model: str):
                if key == "anthropic":
                    return primary
                if key == "openai":
                    return secondary
                return None
            mock_build.side_effect = build
            resp = await router.complete_with_routing(
                tenant,
                [{"role": "user", "content": "Hi"}],
                {"type": "object", "properties": {"answer": {"type": "string"}}},
                "draft_assumptions",
            )
            assert resp.provider == "openai"
            assert resp.content == {"answer": "42"}
