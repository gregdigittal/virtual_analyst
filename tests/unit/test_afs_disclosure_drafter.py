"""Unit tests for AFS Disclosure Drafter service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api.app.services.afs.disclosure_drafter import (
    DRAFT_SCHEMA,
    TASK_LABEL,
    VALIDATION_SCHEMA,
    draft_section,
    validate_sections,
)


def _mock_llm_router(return_content: dict | None = None) -> MagicMock:
    content = return_content or {
        "title": "Property, Plant and Equipment",
        "paragraphs": [{"type": "text", "content": "The entity holds PPE at cost."}],
        "references": ["IAS 16.73"],
        "warnings": [],
    }
    mock_response = MagicMock()
    mock_response.content = content

    router = MagicMock()
    router.complete_with_routing = AsyncMock(return_value=mock_response)
    return router


# ---------------------------------------------------------------------------
# draft_section — basic call contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_draft_section_basic_call() -> None:
    """draft_section calls LLMRouter with correct parameters and returns an LLMResponse."""
    llm = _mock_llm_router()

    result = await draft_section(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        period_start="2025-01-01",
        period_end="2025-12-31",
        entity_name="Acme Ltd",
        section_title="Property, Plant and Equipment",
        nl_instruction="Draft the PPE note per IAS 16",
        trial_balance_summary="PPE carrying value: 500,000",
    )

    assert result is not None
    llm.complete_with_routing.assert_called_once()
    kwargs = llm.complete_with_routing.call_args[1]
    assert kwargs["tenant_id"] == "t-1"
    assert kwargs["response_schema"] == DRAFT_SCHEMA
    assert kwargs["task_label"] == TASK_LABEL
    assert kwargs["max_tokens"] == 8192
    assert kwargs["temperature"] == 0.3


@pytest.mark.asyncio
async def test_draft_section_system_prompt_contains_entity_and_period() -> None:
    """System message contains entity_name, period_start, period_end, and framework_name."""
    llm = _mock_llm_router()

    await draft_section(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        period_start="2025-01-01",
        period_end="2025-12-31",
        entity_name="Acme Ltd",
        section_title="Revenue",
        nl_instruction="Draft revenue note",
        trial_balance_summary="Revenue: 1,000,000",
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    system_content = messages[0]["content"]
    assert messages[0]["role"] == "system"
    assert "Acme Ltd" in system_content
    assert "2025-01-01" in system_content
    assert "2025-12-31" in system_content
    assert "IFRS" in system_content


@pytest.mark.asyncio
async def test_draft_section_user_message_contains_section_title() -> None:
    """User message contains the section_title and nl_instruction."""
    llm = _mock_llm_router()

    await draft_section(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        period_start="2025-01-01",
        period_end="2025-12-31",
        entity_name="Acme Ltd",
        section_title="Provisions and Contingencies",
        nl_instruction="Include the legal dispute provision per IAS 37",
        trial_balance_summary="Provisions: 50,000",
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    assert messages[1]["role"] == "user"
    assert "Provisions and Contingencies" in user_content
    assert "Include the legal dispute provision per IAS 37" in user_content


@pytest.mark.asyncio
async def test_draft_section_without_existing_draft_says_from_scratch() -> None:
    """When existing_draft is None, user message instructs drafting from scratch."""
    llm = _mock_llm_router()

    await draft_section(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        period_start="2025-01-01",
        period_end="2025-12-31",
        entity_name="Acme Ltd",
        section_title="Inventories",
        nl_instruction="Draft inventory note per IAS 2",
        trial_balance_summary="Inventories: 200,000",
        existing_draft=None,
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    assert "from scratch" in user_content.lower()


@pytest.mark.asyncio
async def test_draft_section_with_existing_draft_says_revise() -> None:
    """When existing_draft is provided, user message instructs revision."""
    llm = _mock_llm_router()

    await draft_section(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        period_start="2025-01-01",
        period_end="2025-12-31",
        entity_name="Acme Ltd",
        section_title="Inventories",
        nl_instruction="Please expand the measurement policy section",
        trial_balance_summary="Inventories: 200,000",
        existing_draft="The entity values inventories at the lower of cost and NRV.",
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    # Revision instruction should appear
    assert "revise" in user_content.lower() or "revision" in user_content.lower() or "draft" in user_content.lower()
    # Existing draft should appear in the message
    assert "The entity values inventories at the lower of cost and NRV." in user_content


@pytest.mark.asyncio
async def test_draft_section_prior_afs_context_included() -> None:
    """Prior AFS context appears in user message when provided."""
    llm = _mock_llm_router()

    await draft_section(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        period_start="2025-01-01",
        period_end="2025-12-31",
        entity_name="Acme Ltd",
        section_title="Leases",
        nl_instruction="Draft lease note per IFRS 16",
        trial_balance_summary="ROU assets: 300,000",
        prior_afs_context="Prior year: ROU assets 280,000",
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    assert "Prior year: ROU assets 280,000" in user_content


@pytest.mark.asyncio
async def test_draft_section_returns_llm_response_directly() -> None:
    """draft_section returns the LLMResponse from the router unchanged."""
    expected = {
        "title": "Goodwill",
        "paragraphs": [{"type": "text", "content": "Goodwill is tested annually for impairment."}],
        "references": ["IFRS 3.32", "IAS 36.90"],
        "warnings": ["Impairment model assumptions should be disclosed"],
    }
    llm = _mock_llm_router(return_content=expected)

    result = await draft_section(
        llm,
        tenant_id="t-2",
        framework_name="IFRS",
        standard="ifrs",
        period_start="2025-01-01",
        period_end="2025-12-31",
        entity_name="Acme Ltd",
        section_title="Goodwill",
        nl_instruction="Draft goodwill note",
        trial_balance_summary="Goodwill: 1,000,000",
    )

    assert result.content == expected


# ---------------------------------------------------------------------------
# validate_sections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_sections_calls_correct_task_label() -> None:
    """validate_sections uses task_label 'afs_disclosure_validate'."""
    validate_content = {
        "compliant": True,
        "missing_disclosures": [],
        "suggestions": [],
    }
    mock_response = MagicMock()
    mock_response.content = validate_content
    router = MagicMock()
    router.complete_with_routing = AsyncMock(return_value=mock_response)

    await validate_sections(
        router,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        sections_summary="Note 1: Revenue...\nNote 2: PPE...",
        checklist_items="[ ] IFRS 15 revenue recognition policy\n[ ] IAS 16.73 PPE movement",
    )

    kwargs = router.complete_with_routing.call_args[1]
    assert kwargs["task_label"] == "afs_disclosure_validate"
    assert kwargs["response_schema"] == VALIDATION_SCHEMA


@pytest.mark.asyncio
async def test_validate_sections_system_message_mentions_framework() -> None:
    """validate_sections system message references the framework name and standard."""
    mock_response = MagicMock()
    mock_response.content = {"compliant": True, "missing_disclosures": [], "suggestions": []}
    router = MagicMock()
    router.complete_with_routing = AsyncMock(return_value=mock_response)

    await validate_sections(
        router,
        tenant_id="t-1",
        framework_name="US GAAP",
        standard="us-gaap",
        sections_summary="Note 1: Revenue",
        checklist_items="[ ] ASC 606 disclosures",
    )

    messages = router.complete_with_routing.call_args[1]["messages"]
    system_content = messages[0]["content"]
    assert "US GAAP" in system_content


@pytest.mark.asyncio
async def test_validate_sections_user_message_contains_sections_and_checklist() -> None:
    """validate_sections user message contains both sections_summary and checklist_items."""
    mock_response = MagicMock()
    mock_response.content = {"compliant": False, "missing_disclosures": [], "suggestions": []}
    router = MagicMock()
    router.complete_with_routing = AsyncMock(return_value=mock_response)

    await validate_sections(
        router,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        sections_summary="Note 3: Leases — IFRS 16 applied",
        checklist_items="[ ] IFRS 16.51 right-of-use assets movement table",
    )

    messages = router.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    assert "Note 3: Leases" in user_content
    assert "IFRS 16.51" in user_content
