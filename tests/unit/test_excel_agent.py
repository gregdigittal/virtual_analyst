"""Unit tests for Excel ingestion agent."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.app.services.agent.excel_agent import run_excel_ingestion_agent
from apps.api.app.services.agent.service import AgentResult


@pytest.mark.asyncio
async def test_run_excel_ingestion_agent_produces_output_structure() -> None:
    """run_excel_ingestion_agent returns dict with classification and mapping keys."""
    fake_classification = {
        "sheets": [{"sheet_name": "Sheet1", "classification": "assumptions", "role": "input", "confidence": "high", "is_financial_core": True}],
        "model_summary": {"entity_name": "Test Co", "industry": "tech", "model_type": "startup", "currency_guess": "USD", "horizon_months_guess": 36},
    }
    fake_mapping = {
        "metadata": {"entity_name": "Test Co", "currency": "USD", "horizon_months": 36},
        "revenue_streams": [],
        "cost_items": [],
        "capex_items": [],
        "working_capital": {},
        "funding": {},
        "unmapped_items": [],
        "questions": [],
    }
    agent = MagicMock()
    agent.run_task = AsyncMock(
        return_value=AgentResult(
            content={"classification": fake_classification, "mapping": fake_mapping},
            raw_text="",
            total_tokens=0,
            cost_usd=0.0,
            model="sonnet",
            task_label="excel_ingestion_agent",
        )
    )

    parse_dict = {
        "sheets": [
            {
                "name": "Sheet1",
                "dimensions": "A1:Z10",
                "row_count": 10,
                "col_count": 26,
                "formula_count": 2,
                "headers": ["Revenue", "Cost"],
                "sample_rows": [["100", "50"]],
                "formula_patterns": ["SUM"],
                "referenced_sheets": [],
            }
        ],
    }
    heuristic = {"Sheet1": "assumptions"}

    result = await run_excel_ingestion_agent("t1", agent, parse_dict, heuristic)

    assert "classification" in result
    assert "mapping" in result
    assert result["classification"]["sheets"][0]["sheet_name"] == "Sheet1"
    assert result["mapping"]["metadata"]["entity_name"] == "Test Co"
    agent.run_task.assert_called_once()
    call_kw = agent.run_task.call_args[1]
    assert call_kw["task_label"] == "excel_ingestion_agent"
    assert call_kw["output_schema"] is not None
    assert "classification" in call_kw["output_schema"]["properties"]


@pytest.mark.asyncio
async def test_run_excel_ingestion_agent_includes_user_answers_in_prompt() -> None:
    """run_excel_ingestion_agent passes user_answers into the prompt."""
    agent = MagicMock()
    agent.run_task = AsyncMock(
        return_value=AgentResult(
            content={"classification": {"sheets": [], "model_summary": {}}, "mapping": {"metadata": {}, "revenue_streams": [], "cost_items": [], "capex_items": [], "working_capital": {}, "funding": {}, "unmapped_items": [], "questions": []}},
            raw_text="",
            total_tokens=0,
            cost_usd=0.0,
            model="sonnet",
            task_label="excel_ingestion_agent",
        )
    )

    await run_excel_ingestion_agent(
        "t1",
        agent,
        {"sheets": []},
        {},
        user_answers=[{"question_index": 0, "answer": "Yes"}],
    )

    call_kw = agent.run_task.call_args[1]
    assert "User answers" in call_kw["prompt"]
    assert "question_index" in call_kw["prompt"]
    assert "Yes" in call_kw["prompt"]


@pytest.mark.asyncio
async def test_parse_classify_and_map_agent_calls_agent_and_updates_db() -> None:
    """parse_classify_and_map_agent runs agent and sets status to analyzed."""
    from apps.api.app.services import excel_ingestion

    fake_combined = {
        "classification": {"sheets": [], "model_summary": {}, "heuristic": {}},
        "mapping": {"metadata": {}, "revenue_streams": [], "cost_items": [], "capex_items": [], "working_capital": {}, "funding": {}, "unmapped_items": [], "questions": []},
    }
    store = MagicMock()
    store.load.return_value = {"content_base64": base64.b64encode(b"x").decode(), "filename": "test.xlsx"}
    conn = MagicMock()
    conn.execute = AsyncMock()

    with patch.object(excel_ingestion, "parse_workbook") as mock_parse:
        from apps.api.app.services.excel_parser import ExcelParseResult, SheetInfo

        mock_parse.return_value = ExcelParseResult(
            filename="test.xlsx",
            file_size_bytes=1,
            sheet_count=1,
            total_formulas=0,
            total_cross_refs=0,
            total_external_refs=0,
            has_external_refs=False,
            named_ranges=[],
            dependency_graph={},
            sheets=[SheetInfo(name="S1", dimensions="A1", row_count=1, col_count=1, formula_count=0, value_count=0, empty_count=0, merged_cell_count=0, cross_sheet_ref_count=0, external_ref_count=0, headers=[], sample_rows=[], formula_patterns=[], referenced_sheets=[])],
        )
        with patch.object(excel_ingestion, "classify_sheets", return_value={"S1": "other"}):
            with patch("apps.api.app.services.agent.excel_agent.run_excel_ingestion_agent", new_callable=AsyncMock, return_value=fake_combined):
                result = await excel_ingestion.parse_classify_and_map_agent(
                    "t1", "ing1", store, MagicMock(), conn
                )

    assert result["classification"] == fake_combined["classification"]
    assert result["mapping"] == fake_combined["mapping"]
    assert conn.execute.call_count >= 2
    update_calls = [c for c in conn.execute.call_args_list if len(c[0]) >= 1 and "UPDATE excel_ingestion_sessions" in str(c[0][0])]
    statuses = [str(c[0][0]) for c in update_calls]
    assert any("analyzed" in s for s in statuses)


@pytest.mark.asyncio
async def test_upload_and_parse_fallback_when_agent_disabled() -> None:
    """When get_agent_service returns None, upload_and_parse uses parse_and_classify."""
    from apps.api.app.routers import excel_ingestion as router_module

    with patch.object(router_module, "get_agent_service", return_value=None):
        with patch.object(router_module, "parse_and_classify", new_callable=AsyncMock) as mock_legacy:
            mock_legacy.return_value = {"sheets": [], "model_summary": {}}
            with patch.object(router_module, "start_ingestion", new_callable=AsyncMock, return_value="ing-id"):
                with patch.object(router_module, "tenant_conn") as mock_conn:
                    conn = MagicMock()
                    conn.execute = AsyncMock()
                    conn.fetchrow = AsyncMock(return_value={"sheet_count": 1, "formula_count": 0, "cross_ref_count": 0})
                    mock_conn.return_value.__aenter__ = AsyncMock(return_value=conn)
                    mock_conn.return_value.__aexit__ = AsyncMock(return_value=None)

                    from fastapi import UploadFile

                    file = MagicMock(spec=UploadFile)
                    file.filename = "test.xlsx"
                    file.read = AsyncMock(return_value=b"PK\x03\x04")

                    response = await router_module.upload_and_parse(
                        file,
                        x_tenant_id="t1",
                        x_user_id="u1",
                        store=MagicMock(),
                        llm=MagicMock(),
                    )

            mock_legacy.assert_called_once()
    assert response["status"] == "parsed"
    assert "mapping" not in response or response.get("unmapped_count") is None
