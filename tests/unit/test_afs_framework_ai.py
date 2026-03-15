"""Unit tests for AFS framework AI inference service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api.app.services.afs.framework_ai import (
    FRAMEWORK_SCHEMA,
    SYSTEM_PROMPT,
    TASK_LABEL,
    infer_framework,
)


def _mock_llm_router(return_content: dict | None = None) -> MagicMock:
    content = return_content or {
        "name": "Test Framework",
        "disclosure_schema": {"sections": []},
        "statement_templates": {},
        "suggested_items": [],
    }
    mock_response = MagicMock()
    mock_response.content = content

    router = MagicMock()
    router.complete_with_routing = AsyncMock(return_value=mock_response)
    return router


# ---------------------------------------------------------------------------
# infer_framework
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_infer_framework_basic_call() -> None:
    """Calls LLMRouter with correct parameters and returns an LLMResponse."""
    llm = _mock_llm_router()

    result = await infer_framework(
        llm,
        tenant_id="t-1",
        description="A small manufacturing company in South Africa",
    )

    assert result is not None
    assert result.content["name"] == "Test Framework"

    llm.complete_with_routing.assert_called_once()
    call_kwargs = llm.complete_with_routing.call_args[1]
    assert call_kwargs["tenant_id"] == "t-1"
    assert call_kwargs["response_schema"] == FRAMEWORK_SCHEMA
    assert call_kwargs["task_label"] == TASK_LABEL
    assert call_kwargs["max_tokens"] == 8192
    assert call_kwargs["temperature"] == 0.3


@pytest.mark.asyncio
async def test_infer_framework_system_prompt_used() -> None:
    """System prompt is passed as the first message."""
    llm = _mock_llm_router()

    await infer_framework(
        llm,
        tenant_id="t-1",
        description="A tech startup",
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_infer_framework_description_in_user_prompt() -> None:
    """Description is included in the user message."""
    llm = _mock_llm_router()
    desc = "A publicly listed fintech company with subsidiaries in Kenya and Nigeria"

    await infer_framework(llm, tenant_id="t-1", description=desc)

    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_msg = messages[1]
    assert user_msg["role"] == "user"
    assert desc in user_msg["content"]


@pytest.mark.asyncio
async def test_infer_framework_with_jurisdiction() -> None:
    """Jurisdiction is appended to the user prompt when provided."""
    llm = _mock_llm_router()

    await infer_framework(
        llm,
        tenant_id="t-1",
        description="A retail company",
        jurisdiction="South Africa",
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    assert "Jurisdiction: South Africa" in user_content


@pytest.mark.asyncio
async def test_infer_framework_with_entity_type() -> None:
    """Entity type is appended to the user prompt when provided."""
    llm = _mock_llm_router()

    await infer_framework(
        llm,
        tenant_id="t-1",
        description="A healthcare provider",
        entity_type="non-profit",
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    assert "Entity type: non-profit" in user_content


@pytest.mark.asyncio
async def test_infer_framework_without_optional_params() -> None:
    """When jurisdiction and entity_type are omitted, they do not appear in the prompt."""
    llm = _mock_llm_router()

    await infer_framework(
        llm,
        tenant_id="t-1",
        description="A sole trader",
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    assert "Jurisdiction:" not in user_content
    assert "Entity type:" not in user_content


@pytest.mark.asyncio
async def test_infer_framework_with_all_optional_params() -> None:
    """Both jurisdiction and entity_type appear when both are provided."""
    llm = _mock_llm_router()

    await infer_framework(
        llm,
        tenant_id="t-1",
        description="A bank",
        jurisdiction="United States",
        entity_type="listed-bank",
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    assert "Jurisdiction: United States" in user_content
    assert "Entity type: listed-bank" in user_content


@pytest.mark.asyncio
async def test_infer_framework_returns_llm_response_directly() -> None:
    """infer_framework returns the LLMResponse object from the router unchanged."""
    expected_content = {
        "name": "IFRS-Lite for SMEs",
        "disclosure_schema": {"sections": [{"type": "note", "title": "Revenue", "reference": "IFRS 15", "required": True, "sub_items": []}]},
        "statement_templates": {"income_statement": {"title": "P&L", "line_items": ["Revenue"]}},
        "suggested_items": [{"section": "Revenue", "reference": "IFRS 15.1", "description": "Revenue recognition policy", "required": True}],
    }
    llm = _mock_llm_router(return_content=expected_content)

    result = await infer_framework(llm, tenant_id="t-2", description="A small services company")

    assert result.content == expected_content
