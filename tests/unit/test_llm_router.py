from __future__ import annotations

from contextlib import asynccontextmanager
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


def test_budget_nl_query_routed_to_claude_sonnet_not_fallback() -> None:
    """budget_nl_query has explicit rules; first candidate is anthropic/claude-sonnet, not gpt-4o-mini fallback."""
    candidates = _resolve_candidates("budget_nl_query", DEFAULT_POLICY)
    assert len(candidates) >= 2
    first_provider, first_model, *_ = candidates[0]
    assert first_provider == "anthropic"
    assert "sonnet" in first_model.lower()
    fallback_provider, fallback_model, *_ = candidates[-1]
    assert fallback_provider == DEFAULT_POLICY["fallback"]["provider"]
    assert fallback_model == DEFAULT_POLICY["fallback"]["model"]
    assert first_model != fallback_model


@pytest.mark.asyncio
async def test_metering_check_limit_and_add_usage() -> None:
    """Metering persists to DB; mock tenant_conn (C-03) to simulate llm_usage_log."""
    tenant = "t_meter_test"
    store: dict[tuple[str, str], list[tuple[int, float]]] = {}

    async def mock_execute(query: str, *args: object) -> None:
        if "INSERT INTO llm_usage_log" in query and args:
            key = (args[0], args[4]) if len(args) >= 5 else (args[0], "")
            store.setdefault(key, []).append((int(args[2]), float(args[3])))

    async def mock_fetchrow(query: str, *args: object) -> dict | None:
        if "SUM(tokens_total)" in query and args:
            key = (args[0], args[1])
            rows = store.get(key, [])
            tokens = sum(r[0] for r in rows)
            calls = len(rows)
            usd = sum(r[1] for r in rows)
            return {"llm_tokens_total": tokens, "llm_calls": calls, "llm_estimated_usd": usd}
        return None

    conn = AsyncMock()
    conn.execute = mock_execute
    conn.fetchrow = mock_fetchrow
    conn.close = AsyncMock()

    @asynccontextmanager
    async def mock_tenant_conn(tenant_id: str):
        yield conn

    def _tenant_conn(_tenant_id: str):
        return mock_tenant_conn(_tenant_id)
    with patch("apps.api.app.services.llm.metering.tenant_conn", side_effect=_tenant_conn):
        assert await check_limit(tenant, 1000) is True
        await add_usage(tenant, 500, 0.01)
        u = await get_usage(tenant)
        assert u["llm_tokens_total"] == 500
        assert u["llm_calls"] == 1
        await add_usage(tenant, 500, 0.02)
        assert await check_limit(tenant, 1000) is False
        assert await check_limit(tenant, 2000) is True


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
    # Use 2s timeout and 2.2s sleep so CI/slow envs have headroom (L-09)
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=2)
    cb.record_failure("openai")
    cb.record_failure("openai")
    assert cb.is_open("openai") is True
    time.sleep(2.2)
    assert cb.is_open("openai") is False
    cb.record_failure("openai")
    assert cb.is_open("openai") is True


@pytest.mark.asyncio
async def test_complete_with_routing_raises_429_when_over_limit() -> None:
    router = LLMRouter()
    tenant = "t_quota_429"
    with patch("apps.api.app.services.llm.router.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(llm_tokens_monthly_limit=1_000_000)
        with patch("apps.api.app.services.llm.metering.get_usage", new_callable=AsyncMock) as mock_get_usage:
            mock_get_usage.return_value = {"llm_tokens_total": 2_000_000, "llm_calls": 1, "llm_estimated_usd": 10.0}
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
    from apps.api.app.services.llm.provider import LLMResponse, TokenUsage
    primary = MagicMock()
    primary.complete = AsyncMock(side_effect=Exception("anthropic down"))
    secondary = MagicMock()
    secondary.complete = AsyncMock(return_value=LLMResponse(
        content={"answer": "42"},
        raw_text='{"answer":"42"}',
        tokens=TokenUsage(10, 5, 15),
        latency_ms=100,
        model="gpt-4o-mini",
        provider="openai",
        cost_estimate_usd=0.001,
    ))

    def mock_get_provider(provider_key: str, model: str):
        if provider_key == "anthropic":
            return primary
        if provider_key == "openai":
            return secondary
        return None

    router = LLMRouter()
    router._get_provider = mock_get_provider
    tenant = "t_fallback"
    with patch("apps.api.app.services.llm.router.get_settings") as mock_settings:
        s = MagicMock()
        s.llm_tokens_monthly_limit = 10_000_000
        mock_settings.return_value = s
        with patch("apps.api.app.services.llm.router.check_limit", new_callable=AsyncMock, return_value=True):
            with patch("apps.api.app.services.llm.router.add_usage", new_callable=AsyncMock):
                resp = await router.complete_with_routing(
                    tenant,
                    [{"role": "user", "content": "Hi"}],
                    {"type": "object", "properties": {"answer": {"type": "string"}}},
                    "draft_assumptions",
                )
                assert resp.provider == "openai"
                assert resp.content == {"answer": "42"}
