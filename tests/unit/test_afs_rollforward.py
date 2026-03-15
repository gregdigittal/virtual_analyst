"""Unit tests for AFS roll-forward service functions."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from apps.api.app.services.afs.rollforward import rollforward_comparatives, rollforward_sections


def _mock_conn() -> MagicMock:
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    return conn


# ---------------------------------------------------------------------------
# rollforward_sections
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollforward_sections_happy_path() -> None:
    """Copies sections from source to target, returns correct count and shape."""
    conn = _mock_conn()
    source_rows = [
        {
            "section_id": "asc_src1",
            "section_type": "note",
            "section_number": 1,
            "title": "Property, Plant & Equipment",
            "content_json": json.dumps({"text": "Prior year PP&E note"}),
        },
        {
            "section_id": "asc_src2",
            "section_type": "statement",
            "section_number": 2,
            "title": "Statement of Financial Position",
            "content_json": None,
        },
    ]
    conn.fetch = AsyncMock(return_value=source_rows)
    conn.execute = AsyncMock()  # simulate successful insert (no exception = row inserted)

    result = await rollforward_sections(
        conn,
        tenant_id="t-1",
        source_engagement_id="eng-src",
        target_engagement_id="eng-tgt",
        created_by="user-1",
    )

    assert result["sections_copied"] == 2
    assert len(result["sections"]) == 2
    # First section
    assert result["sections"][0]["rolled_forward_from"] == "asc_src1"
    assert result["sections"][0]["section_type"] == "note"
    assert result["sections"][0]["title"] == "Property, Plant & Equipment"
    # New IDs generated (not the source IDs)
    assert result["sections"][0]["section_id"] != "asc_src1"
    assert result["sections"][1]["section_id"] != "asc_src2"
    # Execute was called twice
    assert conn.execute.call_count == 2


@pytest.mark.asyncio
async def test_rollforward_sections_empty_source() -> None:
    """Returns zero when source engagement has no sections."""
    conn = _mock_conn()
    conn.fetch = AsyncMock(return_value=[])

    result = await rollforward_sections(
        conn,
        tenant_id="t-1",
        source_engagement_id="eng-src",
        target_engagement_id="eng-tgt",
    )

    assert result["sections_copied"] == 0
    assert result["sections"] == []
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_rollforward_sections_idempotent_on_conflict() -> None:
    """ON CONFLICT path: execute raises exception (asyncpg conflict), section not counted."""
    conn = _mock_conn()
    source_rows = [
        {
            "section_id": "asc_src1",
            "section_type": "note",
            "section_number": 1,
            "title": "Tax Note",
            "content_json": None,
        },
    ]
    conn.fetch = AsyncMock(return_value=source_rows)
    # Simulate asyncpg raising on conflict (the except block swallows it)
    conn.execute = AsyncMock(side_effect=asyncpg.exceptions.UniqueViolationError())

    result = await rollforward_sections(
        conn,
        tenant_id="t-1",
        source_engagement_id="eng-src",
        target_engagement_id="eng-tgt",
    )

    # Exception is caught, section not added to copied list
    assert result["sections_copied"] == 0
    assert result["sections"] == []


@pytest.mark.asyncio
async def test_rollforward_sections_preserves_fields() -> None:
    """Verifies section_type, section_number, content_json, and rolled_forward_from are preserved."""
    conn = _mock_conn()
    content = json.dumps({"text": "some content", "line_items": ["a", "b"]})
    source_rows = [
        {
            "section_id": "asc_original",
            "section_type": "accounting_policy",
            "section_number": 5,
            "title": "Accounting Policies",
            "content_json": content,
        },
    ]
    conn.fetch = AsyncMock(return_value=source_rows)
    conn.execute = AsyncMock()

    result = await rollforward_sections(
        conn,
        tenant_id="t-1",
        source_engagement_id="eng-src",
        target_engagement_id="eng-tgt",
    )

    assert result["sections_copied"] == 1
    s = result["sections"][0]
    assert s["section_type"] == "accounting_policy"
    assert s["title"] == "Accounting Policies"
    assert s["rolled_forward_from"] == "asc_original"

    # Verify the INSERT was called with correct args
    # execute(query, tenant_id, new_id, target_id, section_type, section_number, title, content_json, rolled_from, created_by)
    call_args = conn.execute.call_args
    positional = call_args[0]
    assert positional[4] == "accounting_policy"  # section_type ($4)
    assert positional[5] == 5  # section_number ($5)
    assert positional[6] == "Accounting Policies"  # title ($6)
    assert positional[7] == content  # content_json ($7)


# ---------------------------------------------------------------------------
# rollforward_comparatives
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rollforward_comparatives_no_source_tb() -> None:
    """Returns comparatives_copied=False when source has no trial balance."""
    conn = _mock_conn()
    conn.fetchrow = AsyncMock(return_value=None)

    result = await rollforward_comparatives(
        conn,
        tenant_id="t-1",
        source_engagement_id="eng-src",
        target_engagement_id="eng-tgt",
    )

    assert result["comparatives_copied"] is False
    assert result["trial_balance_id"] is None
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_rollforward_comparatives_happy_path() -> None:
    """Copies source TB, returns comparatives_copied=True with a new TB ID."""
    conn = _mock_conn()
    source_data = json.dumps({"accounts": [{"code": "1000", "balance": 50000}]})
    source_mapping = json.dumps({"1000": "cash_and_equivalents"})
    source_tb = {
        "data_json": source_data,
        "mapped_accounts_json": source_mapping,
        "entity_id": "ent-1",
    }
    conn.fetchrow = AsyncMock(return_value=source_tb)
    conn.execute = AsyncMock()

    result = await rollforward_comparatives(
        conn,
        tenant_id="t-1",
        source_engagement_id="eng-src",
        target_engagement_id="eng-tgt",
    )

    assert result["comparatives_copied"] is True
    assert result["trial_balance_id"] is not None
    assert result["trial_balance_id"].startswith("atb_")


@pytest.mark.asyncio
async def test_rollforward_comparatives_preserves_source_mapping() -> None:
    """The comparative's mapped_accounts_json preserves source accounts AND adds _comparative_source."""
    conn = _mock_conn()
    source_mapping = json.dumps({"1000": "cash_and_equivalents", "2000": "trade_payables"})
    source_tb = {
        "data_json": json.dumps({"accounts": []}),
        "mapped_accounts_json": source_mapping,
        "entity_id": "ent-2",
    }
    conn.fetchrow = AsyncMock(return_value=source_tb)
    conn.execute = AsyncMock()

    await rollforward_comparatives(
        conn,
        tenant_id="t-1",
        source_engagement_id="eng-src",
        target_engagement_id="eng-tgt",
    )

    # Verify execute was called with mapped_accounts_json that preserves source mapping
    # execute(query, tenant, tb_id, target, entity_id, data_json, mapped_json)
    call_args = conn.execute.call_args[0]
    mapped_json_arg = call_args[6]
    mapped = json.loads(mapped_json_arg)
    # Source mapping preserved
    assert mapped["1000"] == "cash_and_equivalents"
    assert mapped["2000"] == "trade_payables"
    # Marker added
    assert mapped["_comparative_source"] == "eng-src"


@pytest.mark.asyncio
async def test_rollforward_comparatives_null_source_mapping_fallback() -> None:
    """When source mapping is null, falls back to {'_comparative_source': eid}."""
    conn = _mock_conn()
    source_tb = {
        "data_json": json.dumps({"accounts": []}),
        "mapped_accounts_json": None,
        "entity_id": "ent-3",
    }
    conn.fetchrow = AsyncMock(return_value=source_tb)
    conn.execute = AsyncMock()

    result = await rollforward_comparatives(
        conn,
        tenant_id="t-1",
        source_engagement_id="eng-src-null",
        target_engagement_id="eng-tgt",
    )

    assert result["comparatives_copied"] is True
    # mapped_accounts_json fallback = {"_comparative_source": "eng-src-null"}
    call_args = conn.execute.call_args[0]
    mapped_json_arg = call_args[6]
    mapped = json.loads(mapped_json_arg)
    assert mapped["_comparative_source"] == "eng-src-null"
