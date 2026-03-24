"""Unit tests for AFS Tax Note Drafter service.

Bug coverage:
  - reconciliation_json as invalid JSON string raises JSONDecodeError (RED before fix)
  - deferred_tax_json as invalid JSON string raises JSONDecodeError (RED before fix)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api.app.services.afs.tax_note_drafter import (
    TASK_LABEL,
    TAX_NOTE_SCHEMA,
    draft_tax_note,
)


def _mock_llm_router(return_content: dict | None = None) -> MagicMock:
    content = return_content or {
        "title": "Income Tax",
        "paragraphs": [{"type": "text", "content": "The effective tax rate is 28%."}],
        "references": ["IAS 12.79"],
        "warnings": [],
    }
    mock_response = MagicMock()
    mock_response.content = content

    router = MagicMock()
    router.complete_with_routing = AsyncMock(return_value=mock_response)
    return router


_BASE_COMPUTATION: dict = {
    "jurisdiction": "South Africa",
    "statutory_rate": 0.27,
    "taxable_income": 1_000_000.0,
    "current_tax": 270_000.0,
    "reconciliation_json": [],
    "deferred_tax_json": {},
}


# ---------------------------------------------------------------------------
# Happy path — pre-parsed data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_draft_tax_note_basic_call() -> None:
    """draft_tax_note calls LLMRouter with correct task_label, schema, and params."""
    llm = _mock_llm_router()

    result = await draft_tax_note(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        computation=_BASE_COMPUTATION,
        differences=[],
    )

    assert result is not None
    llm.complete_with_routing.assert_called_once()
    kwargs = llm.complete_with_routing.call_args[1]
    assert kwargs["tenant_id"] == "t-1"
    assert kwargs["task_label"] == TASK_LABEL
    assert kwargs["response_schema"] == TAX_NOTE_SCHEMA
    assert kwargs["max_tokens"] == 8192
    assert kwargs["temperature"] == 0.3


@pytest.mark.asyncio
async def test_draft_tax_note_ifrs_standard_uses_ias12() -> None:
    """System prompt for IFRS standard references IAS 12."""
    llm = _mock_llm_router()

    await draft_tax_note(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        computation=_BASE_COMPUTATION,
        differences=[],
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    system_content = messages[0]["content"]
    assert "IAS 12" in system_content


@pytest.mark.asyncio
async def test_draft_tax_note_gaap_standard_uses_asc740() -> None:
    """System prompt for non-IFRS standard references ASC 740."""
    llm = _mock_llm_router()

    await draft_tax_note(
        llm,
        tenant_id="t-1",
        framework_name="US GAAP",
        standard="us-gaap",
        computation=_BASE_COMPUTATION,
        differences=[],
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    system_content = messages[0]["content"]
    assert "ASC 740" in system_content


@pytest.mark.asyncio
async def test_draft_tax_note_with_pre_parsed_reconciliation_list() -> None:
    """reconciliation_json as a pre-parsed list is accepted without error."""
    llm = _mock_llm_router()
    computation = {
        **_BASE_COMPUTATION,
        "reconciliation_json": [
            {"description": "Non-deductible expenses", "amount": 50_000.0, "tax_effect": 13_500.0}
        ],
    }

    result = await draft_tax_note(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        computation=computation,
        differences=[],
    )

    assert result is not None
    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    assert "Non-deductible expenses" in user_content


@pytest.mark.asyncio
async def test_draft_tax_note_with_valid_reconciliation_json_string() -> None:
    """reconciliation_json as a valid JSON string is parsed and included in the prompt."""
    llm = _mock_llm_router()
    recon = [{"description": "Depreciation difference", "amount": 10_000.0, "tax_effect": 2_700.0}]
    computation = {
        **_BASE_COMPUTATION,
        "reconciliation_json": json.dumps(recon),
    }

    result = await draft_tax_note(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        computation=computation,
        differences=[],
    )

    assert result is not None
    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    assert "Depreciation difference" in user_content


@pytest.mark.asyncio
async def test_draft_tax_note_with_valid_deferred_tax_json_string() -> None:
    """deferred_tax_json as a valid JSON string is parsed and included in the prompt."""
    llm = _mock_llm_router()
    dtj = {
        "total_deferred_tax_asset": 50_000.0,
        "total_deferred_tax_liability": 80_000.0,
        "net_deferred_tax": -30_000.0,
    }
    computation = {
        **_BASE_COMPUTATION,
        "deferred_tax_json": json.dumps(dtj),
    }

    result = await draft_tax_note(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        computation=computation,
        differences=[],
    )

    assert result is not None
    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    assert "50,000.00" in user_content or "50000" in user_content


@pytest.mark.asyncio
async def test_draft_tax_note_with_differences_in_prompt() -> None:
    """Temporary differences appear in the user prompt."""
    llm = _mock_llm_router()
    differences = [
        {
            "description": "Finance lease",
            "carrying_amount": 200_000.0,
            "tax_base": 150_000.0,
            "difference": 50_000.0,
            "deferred_tax_effect": 13_500.0,
            "diff_type": "liability",
        }
    ]

    await draft_tax_note(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        computation=_BASE_COMPUTATION,
        differences=differences,
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    assert "Finance lease" in user_content


@pytest.mark.asyncio
async def test_draft_tax_note_nl_instruction_included() -> None:
    """When nl_instruction is provided, it appears in the user prompt."""
    llm = _mock_llm_router()

    await draft_tax_note(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        computation=_BASE_COMPUTATION,
        differences=[],
        nl_instruction="Please include a detailed rate reconciliation table.",
    )

    messages = llm.complete_with_routing.call_args[1]["messages"]
    user_content = messages[1]["content"]
    assert "Please include a detailed rate reconciliation table." in user_content


# ---------------------------------------------------------------------------
# Bug tests (RED) — invalid JSON strings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_draft_tax_note_invalid_reconciliation_json_string_handled_gracefully() -> None:
    """[BUG] reconciliation_json as invalid JSON string must not raise JSONDecodeError.

    Before fix: json.loads("not-json") raises JSONDecodeError.
    After fix: the call completes successfully (treated as empty list).
    """
    llm = _mock_llm_router()
    computation = {
        **_BASE_COMPUTATION,
        "reconciliation_json": "not-valid-json",
    }

    # This must NOT raise json.JSONDecodeError after the fix is applied.
    result = await draft_tax_note(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        computation=computation,
        differences=[],
    )
    assert result is not None


@pytest.mark.asyncio
async def test_draft_tax_note_invalid_deferred_tax_json_string_handled_gracefully() -> None:
    """[BUG] deferred_tax_json as invalid JSON string must not raise JSONDecodeError.

    Before fix: json.loads("{broken") raises JSONDecodeError.
    After fix: the call completes successfully (treated as empty dict).
    """
    llm = _mock_llm_router()
    computation = {
        **_BASE_COMPUTATION,
        "deferred_tax_json": "{broken json here",
    }

    # This must NOT raise json.JSONDecodeError after the fix is applied.
    result = await draft_tax_note(
        llm,
        tenant_id="t-1",
        framework_name="IFRS",
        standard="ifrs",
        computation=computation,
        differences=[],
    )
    assert result is not None
