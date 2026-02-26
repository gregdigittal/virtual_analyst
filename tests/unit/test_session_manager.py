"""Tests for AgentSessionManager — SSE streaming, pause/resume, error handling.

The ``claude_agent_sdk`` package may not be installed in the test
environment, so every SDK import is mocked via ``sys.modules`` patching
before the module under test is imported.
"""

from __future__ import annotations

import json
import sys
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Mock the entire claude_agent_sdk module BEFORE importing session_manager
# ---------------------------------------------------------------------------


class _FakeTextBlock:
    """Stand-in for ``claude_agent_sdk.TextBlock``."""

    def __init__(self, text: str) -> None:
        self.text = text


class _FakeAssistantMessage:
    """Stand-in for ``claude_agent_sdk.AssistantMessage``."""

    def __init__(self, content: list[_FakeTextBlock] | None = None) -> None:
        self.content = content or []


class _FakeResultMessage:
    """Stand-in for ``claude_agent_sdk.ResultMessage``."""

    def __init__(self, result: str = "") -> None:
        self.result = result


class _FakeSystemMessage:
    """Stand-in for ``claude_agent_sdk.SystemMessage``."""

    pass


class _FakeClaudeAgentOptions:
    """Stand-in for ``claude_agent_sdk.ClaudeAgentOptions``."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeClaudeSDKClient:
    """Stand-in for ``claude_agent_sdk.ClaudeSDKClient``."""

    pass


class _FakeMCPServer:
    """Stand-in for the MCP server returned by create_sdk_mcp_server."""

    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}

    def tool(self, *, name: str, description: str, input_schema: dict) -> Any:
        def decorator(fn: Any) -> Any:
            self._tools[name] = {
                "handler": fn,
                "description": description,
                "input_schema": input_schema,
            }
            return fn
        return decorator


# Default no-op async generator for query
async def _default_query(prompt: str, options: Any):
    """Default no-op query. Override per test via _set_query_mock."""
    return
    yield  # make it an async generator


# Build the fake module
_fake_sdk = types.ModuleType("claude_agent_sdk")
_fake_sdk.TextBlock = _FakeTextBlock  # type: ignore[attr-defined]
_fake_sdk.AssistantMessage = _FakeAssistantMessage  # type: ignore[attr-defined]
_fake_sdk.ResultMessage = _FakeResultMessage  # type: ignore[attr-defined]
_fake_sdk.SystemMessage = _FakeSystemMessage  # type: ignore[attr-defined]
_fake_sdk.ClaudeAgentOptions = _FakeClaudeAgentOptions  # type: ignore[attr-defined]
_fake_sdk.ClaudeSDKClient = _FakeClaudeSDKClient  # type: ignore[attr-defined]
_fake_sdk.query = _default_query  # type: ignore[attr-defined]
_fake_sdk.create_sdk_mcp_server = lambda: _FakeMCPServer()  # type: ignore[attr-defined]

# Inject BEFORE importing session_manager
sys.modules["claude_agent_sdk"] = _fake_sdk

from apps.api.app.services.agent.session_manager import (  # noqa: E402
    AgentSessionManager,
    format_sse_event,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_SHEETS: dict[str, dict] = {
    "P&L": {
        "name": "P&L",
        "headers": ["Account", "Q1", "Q2"],
        "sample_rows": [["Revenue", 100, 200]],
        "row_count": 10,
        "col_count": 3,
        "formula_patterns": [],
        "referenced_sheets": [],
    },
}

MOCK_TEMPLATES: list[dict] = [
    {
        "template_id": "tpl_saas_001",
        "label": "SaaS Startup",
        "industry": "software",
        "model_type": "saas",
        "accounts": ["MRR"],
    },
]


async def _collect_events(gen) -> list[dict]:
    """Drain an async generator of SSE strings and parse each payload."""
    events = []
    async for raw in gen:
        assert raw.startswith("data: "), f"SSE frame must start with 'data: ', got: {raw!r}"
        assert raw.endswith("\n\n"), f"SSE frame must end with '\\n\\n', got: {raw!r}"
        payload_str = raw[len("data: "):-2]
        events.append(json.loads(payload_str))
    return events


def _set_query_mock(messages: list) -> None:
    """Set ``claude_agent_sdk.query`` to an async generator yielding *messages*."""

    async def _fake_query(prompt: str, options: Any):
        for msg in messages:
            yield msg

    _fake_sdk.query = _fake_query  # type: ignore[attr-defined]


def _set_query_fn(fn) -> None:
    """Set ``claude_agent_sdk.query`` to a custom async generator function."""
    _fake_sdk.query = fn  # type: ignore[attr-defined]


# ===================================================================
# format_sse_event
# ===================================================================


class TestFormatSSEEvent:
    """format_sse_event produces correct SSE frames."""

    def test_basic_event(self):
        result = format_sse_event("message", {"text": "hello"})
        assert result == 'data: {"type": "message", "text": "hello"}\n\n'

    def test_type_is_merged(self):
        result = format_sse_event("error", {"error": "boom"})
        parsed = json.loads(result[len("data: "):-2])
        assert parsed["type"] == "error"
        assert parsed["error"] == "boom"

    def test_empty_payload(self):
        result = format_sse_event("ping", {})
        parsed = json.loads(result[len("data: "):-2])
        assert parsed == {"type": "ping"}

    def test_nested_payload(self):
        result = format_sse_event("classification", {"data": {"sheets": [1, 2]}})
        parsed = json.loads(result[len("data: "):-2])
        assert parsed["data"]["sheets"] == [1, 2]

    def test_ends_with_double_newline(self):
        result = format_sse_event("test", {})
        assert result.endswith("\n\n")

    def test_starts_with_data_prefix(self):
        result = format_sse_event("test", {})
        assert result.startswith("data: ")

    def test_special_characters_in_payload(self):
        result = format_sse_event("msg", {"text": 'He said "hello" & <goodbye>'})
        parsed = json.loads(result[len("data: "):-2])
        assert parsed["text"] == 'He said "hello" & <goodbye>'


# ===================================================================
# AgentSessionManager.__init__
# ===================================================================


class TestAgentSessionManagerInit:
    """Constructor stores configuration correctly."""

    def test_defaults(self):
        mgr = AgentSessionManager(api_key="sk-test")
        assert mgr.api_key == "sk-test"
        assert mgr.model == "claude-opus-4-6"
        assert mgr.max_turns == 15
        assert mgr.max_budget_usd == 0.50

    def test_custom_params(self):
        mgr = AgentSessionManager(
            api_key="sk-custom",
            model="claude-sonnet-4-20250514",
            max_turns=5,
            max_budget_usd=0.10,
        )
        assert mgr.api_key == "sk-custom"
        assert mgr.model == "claude-sonnet-4-20250514"
        assert mgr.max_turns == 5
        assert mgr.max_budget_usd == 0.10

    def test_api_key_stored(self):
        mgr = AgentSessionManager(api_key="sk-abc123")
        assert mgr.api_key == "sk-abc123"


# ===================================================================
# start_session — basic message flow
# ===================================================================


class TestStartSession:
    """start_session yields SSE events in the correct order."""

    @pytest.fixture
    def manager(self):
        return AgentSessionManager(api_key="sk-test")

    async def test_emits_session_start_first(self, manager):
        """First event should always be session_start."""
        _set_query_mock([
            _FakeResultMessage(result="done"),
        ])
        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ):
            events = await _collect_events(
                manager.start_session(
                    ingestion_id="ing_001",
                    tenant_id="t_test",
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    initial_prompt="Classify this workbook.",
                )
            )
        assert events[0]["type"] == "session_start"
        assert "session_id" in events[0]
        assert events[0]["ingestion_id"] == "ing_001"

    async def test_text_blocks_yield_message_events(self, manager):
        """AssistantMessage with TextBlocks yields message events."""
        _set_query_mock([
            _FakeAssistantMessage(content=[
                _FakeTextBlock("I will analyze your workbook."),
                _FakeTextBlock("Starting with P&L sheet."),
            ]),
            _FakeResultMessage(result="done"),
        ])
        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ):
            events = await _collect_events(
                manager.start_session(
                    ingestion_id="ing_002",
                    tenant_id="t_test",
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    initial_prompt="Go.",
                )
            )
        # session_start + 2 messages + complete
        msg_events = [e for e in events if e["type"] == "message"]
        assert len(msg_events) == 2
        assert msg_events[0]["text"] == "I will analyze your workbook."
        assert msg_events[1]["text"] == "Starting with P&L sheet."

    async def test_result_message_yields_complete(self, manager):
        """ResultMessage should yield a complete event."""
        _set_query_mock([
            _FakeResultMessage(result="all done"),
        ])
        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ):
            events = await _collect_events(
                manager.start_session(
                    ingestion_id="ing_003",
                    tenant_id="t_test",
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    initial_prompt="Go.",
                )
            )
        complete_events = [e for e in events if e["type"] == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0]["ingestion_id"] == "ing_003"

    async def test_full_message_sequence(self, manager):
        """Verify the full event ordering: session_start -> messages -> complete."""
        _set_query_mock([
            _FakeAssistantMessage(content=[_FakeTextBlock("Analyzing...")]),
            _FakeResultMessage(result="done"),
        ])
        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ):
            events = await _collect_events(
                manager.start_session(
                    ingestion_id="ing_004",
                    tenant_id="t_test",
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    initial_prompt="Go.",
                )
            )
        event_types = [e["type"] for e in events]
        assert event_types == ["session_start", "message", "complete"]


# ===================================================================
# Classification detection
# ===================================================================


class TestClassificationDetection:
    """Classification event is yielded when state['classification'] is set."""

    @pytest.fixture
    def manager(self):
        return AgentSessionManager(api_key="sk-test")

    async def test_classification_event_emitted(self, manager):
        """When a tool sets state['classification'], a classification event is yielded."""
        classification_data = {
            "sheets": [{"name": "P&L", "type": "income_statement"}],
            "model_summary": {"entity_name": "Acme"},
        }

        # Patch _run_agent_loop to control state changes precisely.
        async def _patched_run(prompt, options, state, session_id, ingestion_id):
            yield format_sse_event("message", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "text": "I found an income statement.",
            })
            state["classification"] = classification_data
            yield format_sse_event("classification", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "classification": classification_data,
            })
            yield format_sse_event("complete", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "state": state,
            })

        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ), patch.object(
            AgentSessionManager,
            "_run_agent_loop",
            staticmethod(_patched_run),
        ):
            events = await _collect_events(
                manager.start_session(
                    ingestion_id="ing_cls",
                    tenant_id="t_test",
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    initial_prompt="Go.",
                )
            )

        event_types = [e["type"] for e in events]
        assert "classification" in event_types
        cls_event = [e for e in events if e["type"] == "classification"][0]
        assert cls_event["classification"]["model_summary"]["entity_name"] == "Acme"

    async def test_classification_only_emitted_once(self, manager):
        """Even if classification stays in state, event should only be yielded once."""

        async def _patched_run(prompt, options, state, session_id, ingestion_id):
            state["classification"] = {"sheets": []}
            yield format_sse_event("classification", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "classification": state["classification"],
            })
            # Second message — classification still in state, no second event
            yield format_sse_event("message", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "text": "Continuing...",
            })
            yield format_sse_event("complete", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "state": state,
            })

        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ), patch.object(
            AgentSessionManager,
            "_run_agent_loop",
            staticmethod(_patched_run),
        ):
            events = await _collect_events(
                manager.start_session(
                    ingestion_id="ing_cls2",
                    tenant_id="t_test",
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    initial_prompt="Go.",
                )
            )

        cls_events = [e for e in events if e["type"] == "classification"]
        assert len(cls_events) == 1


# ===================================================================
# Pause / resume — question detection
# ===================================================================


class TestPauseResume:
    """Question detection pauses the generator; resume_session continues."""

    @pytest.fixture
    def manager(self):
        return AgentSessionManager(api_key="sk-test")

    async def test_question_pauses_generator(self, manager):
        """When state['pending_question'] is set, generator yields question event and returns."""

        async def _patched_run(prompt, options, state, session_id, ingestion_id):
            yield format_sse_event("message", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "text": "I need to ask something.",
            })
            # Simulate ask_user_question tool setting pending_question
            yield format_sse_event("question", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "question": "What currency is used?",
                "options": ["USD", "EUR", "GBP"],
            })
            # Generator returns here — no complete event

        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ), patch.object(
            AgentSessionManager,
            "_run_agent_loop",
            staticmethod(_patched_run),
        ):
            events = await _collect_events(
                manager.start_session(
                    ingestion_id="ing_q",
                    tenant_id="t_test",
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    initial_prompt="Go.",
                )
            )

        event_types = [e["type"] for e in events]
        assert "question" in event_types
        assert "complete" not in event_types  # paused, not completed

        q_event = [e for e in events if e["type"] == "question"][0]
        assert q_event["question"] == "What currency is used?"
        assert q_event["options"] == ["USD", "EUR", "GBP"]

    async def test_resume_session_emits_session_resume(self, manager):
        """resume_session should emit session_resume as its first event."""

        async def _patched_run(prompt, options, state, session_id, ingestion_id):
            yield format_sse_event("message", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "text": "Thank you for the answer.",
            })
            yield format_sse_event("complete", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "state": state,
            })

        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ), patch.object(
            AgentSessionManager,
            "_run_agent_loop",
            staticmethod(_patched_run),
        ):
            events = await _collect_events(
                manager.resume_session(
                    ingestion_id="ing_r",
                    session_id="sess_123",
                    answers=[{"question": "What currency?", "answer": "USD"}],
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    prior_state={"classification": {"sheets": []}},
                )
            )

        assert events[0]["type"] == "session_resume"
        assert events[0]["session_id"] == "sess_123"

    async def test_resume_session_full_flow(self, manager):
        """resume_session should yield session_resume, messages, and complete."""

        async def _patched_run(prompt, options, state, session_id, ingestion_id):
            yield format_sse_event("message", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "text": "Using USD as currency.",
            })
            state["mapping"] = {"metadata": {"currency": "USD"}}
            yield format_sse_event("mapping", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "mapping": state["mapping"],
            })
            yield format_sse_event("complete", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "state": state,
            })

        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ), patch.object(
            AgentSessionManager,
            "_run_agent_loop",
            staticmethod(_patched_run),
        ):
            events = await _collect_events(
                manager.resume_session(
                    ingestion_id="ing_r2",
                    session_id="sess_456",
                    answers=[{"question": "Currency?", "answer": "USD"}],
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    prior_state={"classification": {"sheets": []}},
                )
            )

        event_types = [e["type"] for e in events]
        assert event_types == ["session_resume", "message", "mapping", "complete"]

    async def test_resume_does_not_mutate_prior_state(self, manager):
        """resume_session should not mutate the prior_state dict passed in."""
        prior = {"classification": {"sheets": []}}
        original_keys = set(prior.keys())

        async def _patched_run(prompt, options, state, session_id, ingestion_id):
            state["mapping"] = {"metadata": {}}
            yield format_sse_event("complete", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "state": state,
            })

        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ), patch.object(
            AgentSessionManager,
            "_run_agent_loop",
            staticmethod(_patched_run),
        ):
            await _collect_events(
                manager.resume_session(
                    ingestion_id="ing_r3",
                    session_id="sess_789",
                    answers=[],
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    prior_state=prior,
                )
            )

        # prior_state should not have been mutated
        assert set(prior.keys()) == original_keys
        assert "mapping" not in prior


# ===================================================================
# Error handling
# ===================================================================


class TestErrorHandling:
    """Agent errors are caught and yielded as error events."""

    @pytest.fixture
    def manager(self):
        return AgentSessionManager(api_key="sk-test")

    async def test_exception_yields_error_event(self, manager):
        """If query() raises, an error SSE event should be yielded."""

        async def _failing_query(prompt, options):
            raise RuntimeError("API connection failed")
            yield  # make this an async generator  # noqa: E501

        _set_query_fn(_failing_query)

        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ):
            events = await _collect_events(
                manager.start_session(
                    ingestion_id="ing_err",
                    tenant_id="t_test",
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    initial_prompt="Go.",
                )
            )

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "API connection failed" in error_events[0]["error"]

    async def test_error_event_includes_session_metadata(self, manager):
        """Error events should include session_id and ingestion_id."""

        async def _failing_query(prompt, options):
            raise ValueError("Invalid model config")
            yield  # noqa: E501

        _set_query_fn(_failing_query)

        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ):
            events = await _collect_events(
                manager.start_session(
                    ingestion_id="ing_err2",
                    tenant_id="t_test",
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    initial_prompt="Go.",
                )
            )

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["ingestion_id"] == "ing_err2"
        assert "session_id" in error_events[0]


# ===================================================================
# Integration: mock SDK to simulate full message sequence
# ===================================================================


class TestIntegrationMockSDK:
    """End-to-end test with mocked Agent SDK simulating a realistic flow."""

    @pytest.fixture
    def manager(self):
        return AgentSessionManager(api_key="sk-test")

    async def test_classify_then_map_flow(self, manager):
        """Simulate: message -> classification -> message -> mapping -> complete."""
        classification = {
            "sheets": [
                {"name": "P&L", "type": "income_statement", "confidence": "high"},
            ],
            "model_summary": {"entity_name": "TestCo", "industry": "software"},
        }
        mapping = {
            "metadata": {"entity_name": "TestCo", "currency": "USD"},
            "revenue_streams": [{"label": "MRR"}],
        }

        # Simulate the full agent loop with state mutations
        async def _patched_run(prompt, options, state, session_id, ingestion_id):
            # Agent says it's analyzing
            yield format_sse_event("message", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "text": "Analyzing the P&L sheet...",
            })

            # Tool submits classification
            state["classification"] = classification
            yield format_sse_event("classification", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "classification": classification,
            })

            # Agent continues with mapping
            yield format_sse_event("message", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "text": "Now mapping revenue streams...",
            })

            # Tool submits mapping
            state["mapping"] = mapping
            yield format_sse_event("mapping", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "mapping": mapping,
            })

            # Done
            yield format_sse_event("complete", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "state": state,
            })

        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ), patch.object(
            AgentSessionManager,
            "_run_agent_loop",
            staticmethod(_patched_run),
        ):
            events = await _collect_events(
                manager.start_session(
                    ingestion_id="ing_int",
                    tenant_id="t_test",
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    initial_prompt="Classify and map.",
                )
            )

        event_types = [e["type"] for e in events]
        assert event_types == [
            "session_start",
            "message",
            "classification",
            "message",
            "mapping",
            "complete",
        ]

        # Verify classification content
        cls = [e for e in events if e["type"] == "classification"][0]
        assert cls["classification"]["model_summary"]["entity_name"] == "TestCo"

        # Verify mapping content
        mp = [e for e in events if e["type"] == "mapping"][0]
        assert mp["mapping"]["revenue_streams"][0]["label"] == "MRR"

        # Verify complete includes full state
        comp = [e for e in events if e["type"] == "complete"][0]
        assert "classification" in comp["state"]
        assert "mapping" in comp["state"]

    async def test_question_then_resume_flow(self, manager):
        """Simulate: start -> question -> pause, then resume -> mapping -> complete."""

        # Phase 1: start_session with question
        async def _start_run(prompt, options, state, session_id, ingestion_id):
            yield format_sse_event("message", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "text": "I need clarification.",
            })
            yield format_sse_event("question", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "question": "Is this in USD?",
                "options": ["Yes", "No"],
            })
            # No complete — paused

        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ), patch.object(
            AgentSessionManager,
            "_run_agent_loop",
            staticmethod(_start_run),
        ):
            start_events = await _collect_events(
                manager.start_session(
                    ingestion_id="ing_qr",
                    tenant_id="t_test",
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    initial_prompt="Go.",
                )
            )

        start_types = [e["type"] for e in start_events]
        assert start_types == ["session_start", "message", "question"]
        session_id = start_events[0]["session_id"]

        # Phase 2: resume_session with answer
        async def _resume_run(prompt, options, state, session_id, ingestion_id):
            yield format_sse_event("message", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "text": "Great, using USD.",
            })
            state["mapping"] = {"metadata": {"currency": "USD"}}
            yield format_sse_event("mapping", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "mapping": state["mapping"],
            })
            yield format_sse_event("complete", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "state": state,
            })

        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ), patch.object(
            AgentSessionManager,
            "_run_agent_loop",
            staticmethod(_resume_run),
        ):
            resume_events = await _collect_events(
                manager.resume_session(
                    ingestion_id="ing_qr",
                    session_id=session_id,
                    answers=[{"question": "Is this in USD?", "answer": "Yes"}],
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    prior_state={"classification": {"sheets": []}},
                )
            )

        resume_types = [e["type"] for e in resume_events]
        assert resume_types == ["session_resume", "message", "mapping", "complete"]


# ===================================================================
# _run_agent_loop — direct unit tests with mocked query()
# ===================================================================


class TestRunAgentLoopDirect:
    """Direct tests of _run_agent_loop with mocked Agent SDK query()."""

    async def test_text_block_yields_message(self):
        """AssistantMessage with TextBlock yields a message event."""
        state: dict[str, Any] = {}
        _set_query_mock([
            _FakeAssistantMessage(content=[_FakeTextBlock("Hello world")]),
            _FakeResultMessage(result="done"),
        ])

        events = await _collect_events(
            AgentSessionManager._run_agent_loop(
                prompt="test",
                options=MagicMock(),
                state=state,
                session_id="s1",
                ingestion_id="i1",
            )
        )

        msg_events = [e for e in events if e["type"] == "message"]
        assert len(msg_events) == 1
        assert msg_events[0]["text"] == "Hello world"

    async def test_classification_state_change_detected(self):
        """When state['classification'] is set between messages, classification event fires."""
        state: dict[str, Any] = {}
        cls_data = {"sheets": [{"name": "BS", "type": "balance_sheet"}]}

        async def _query_that_mutates_state(prompt, options):
            yield _FakeAssistantMessage(content=[_FakeTextBlock("Analyzing...")])
            # Simulate the tool setting state (happens between messages)
            state["classification"] = cls_data
            yield _FakeAssistantMessage(content=[_FakeTextBlock("Classification done.")])
            yield _FakeResultMessage(result="done")

        _set_query_fn(_query_that_mutates_state)

        events = await _collect_events(
            AgentSessionManager._run_agent_loop(
                prompt="test",
                options=MagicMock(),
                state=state,
                session_id="s2",
                ingestion_id="i2",
            )
        )

        cls_events = [e for e in events if e["type"] == "classification"]
        assert len(cls_events) == 1
        assert cls_events[0]["classification"]["sheets"][0]["type"] == "balance_sheet"

    async def test_pending_question_pauses_loop(self):
        """When state['pending_question'] is set, the loop yields question and returns."""
        state: dict[str, Any] = {}

        async def _query_with_question(prompt, options):
            yield _FakeAssistantMessage(content=[_FakeTextBlock("Analyzing...")])
            # Tool sets pending_question
            state["pending_question"] = {
                "question": "Which entity?",
                "options": ["Entity A", "Entity B"],
            }
            yield _FakeAssistantMessage(content=[_FakeTextBlock("Asking user...")])
            # This should NOT be reached:
            yield _FakeResultMessage(result="should not see this")

        _set_query_fn(_query_with_question)

        events = await _collect_events(
            AgentSessionManager._run_agent_loop(
                prompt="test",
                options=MagicMock(),
                state=state,
                session_id="s3",
                ingestion_id="i3",
            )
        )

        event_types = [e["type"] for e in events]
        # Should have: message, message, question — then STOP (no complete)
        assert "question" in event_types
        assert "complete" not in event_types

        q = [e for e in events if e["type"] == "question"][0]
        assert q["question"] == "Which entity?"
        assert q["options"] == ["Entity A", "Entity B"]

    async def test_pending_question_is_consumed(self):
        """After yielding question, pending_question should be removed from state."""
        state: dict[str, Any] = {}

        async def _query_with_question(prompt, options):
            state["pending_question"] = {
                "question": "Currency?",
                "options": ["USD", "EUR"],
            }
            yield _FakeAssistantMessage(content=[_FakeTextBlock("Asking...")])

        _set_query_fn(_query_with_question)

        await _collect_events(
            AgentSessionManager._run_agent_loop(
                prompt="test",
                options=MagicMock(),
                state=state,
                session_id="s4",
                ingestion_id="i4",
            )
        )

        # pending_question should have been popped from state
        assert "pending_question" not in state

    async def test_mapping_state_change_detected(self):
        """When state['mapping'] is set, mapping event fires."""
        state: dict[str, Any] = {}
        mapping_data = {"metadata": {"entity_name": "TestCo"}, "revenue_streams": []}

        async def _query_with_mapping(prompt, options):
            yield _FakeAssistantMessage(content=[_FakeTextBlock("Mapping...")])
            state["mapping"] = mapping_data
            yield _FakeAssistantMessage(content=[_FakeTextBlock("Done mapping.")])
            yield _FakeResultMessage(result="done")

        _set_query_fn(_query_with_mapping)

        events = await _collect_events(
            AgentSessionManager._run_agent_loop(
                prompt="test",
                options=MagicMock(),
                state=state,
                session_id="s5",
                ingestion_id="i5",
            )
        )

        map_events = [e for e in events if e["type"] == "mapping"]
        assert len(map_events) == 1
        assert map_events[0]["mapping"]["metadata"]["entity_name"] == "TestCo"

    async def test_exception_in_query_yields_error(self):
        """Exception during query() yields an error event."""
        state: dict[str, Any] = {}

        async def _failing_query(prompt, options):
            raise ConnectionError("Lost connection to API")
            yield  # noqa

        _set_query_fn(_failing_query)

        events = await _collect_events(
            AgentSessionManager._run_agent_loop(
                prompt="test",
                options=MagicMock(),
                state=state,
                session_id="s6",
                ingestion_id="i6",
            )
        )

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "Lost connection" in error_events[0]["error"]

    async def test_exhausted_loop_sends_complete(self):
        """If the query loop ends without ResultMessage, complete is still sent."""
        state: dict[str, Any] = {}

        async def _query_no_result(prompt, options):
            yield _FakeAssistantMessage(content=[_FakeTextBlock("Only a message.")])
            # No ResultMessage

        _set_query_fn(_query_no_result)

        events = await _collect_events(
            AgentSessionManager._run_agent_loop(
                prompt="test",
                options=MagicMock(),
                state=state,
                session_id="s7",
                ingestion_id="i7",
            )
        )

        event_types = [e["type"] for e in events]
        assert "complete" in event_types

    async def test_empty_content_assistant_message(self):
        """AssistantMessage with no content blocks should not yield message events."""
        state: dict[str, Any] = {}
        _set_query_mock([
            _FakeAssistantMessage(content=[]),
            _FakeResultMessage(result="done"),
        ])

        events = await _collect_events(
            AgentSessionManager._run_agent_loop(
                prompt="test",
                options=MagicMock(),
                state=state,
                session_id="s8",
                ingestion_id="i8",
            )
        )

        msg_events = [e for e in events if e["type"] == "message"]
        assert len(msg_events) == 0

    async def test_multiple_text_blocks_in_one_message(self):
        """Multiple TextBlocks in one AssistantMessage each yield a message event."""
        state: dict[str, Any] = {}
        _set_query_mock([
            _FakeAssistantMessage(content=[
                _FakeTextBlock("First block."),
                _FakeTextBlock("Second block."),
                _FakeTextBlock("Third block."),
            ]),
            _FakeResultMessage(result="done"),
        ])

        events = await _collect_events(
            AgentSessionManager._run_agent_loop(
                prompt="test",
                options=MagicMock(),
                state=state,
                session_id="s9",
                ingestion_id="i9",
            )
        )

        msg_events = [e for e in events if e["type"] == "message"]
        assert len(msg_events) == 3
        assert msg_events[0]["text"] == "First block."
        assert msg_events[2]["text"] == "Third block."


# ===================================================================
# _build_mcp_server
# ===================================================================


class TestBuildMCPServer:
    """_build_mcp_server converts tool definitions into an SDK MCP server."""

    def test_registers_tools_on_server(self):
        """All tool definitions should be registered on the MCP server."""
        tool_defs = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "input_schema": {"type": "object", "properties": {}},
                "handler": lambda args: {"ok": True},
            },
        ]
        server = AgentSessionManager._build_mcp_server(tool_defs)
        assert isinstance(server, _FakeMCPServer)
        assert "test_tool" in server._tools

    def test_multiple_tools_registered(self):
        """Multiple tools should all be registered."""
        tool_defs = [
            {
                "name": f"tool_{i}",
                "description": f"Tool {i}",
                "input_schema": {"type": "object", "properties": {}},
                "handler": lambda args, n=i: {"tool": n},
            }
            for i in range(5)
        ]
        server = AgentSessionManager._build_mcp_server(tool_defs)
        assert len(server._tools) == 5
        for i in range(5):
            assert f"tool_{i}" in server._tools


# ===================================================================
# _build_agent_options
# ===================================================================


class TestBuildAgentOptions:
    """_build_agent_options creates ClaudeAgentOptions with correct parameters."""

    def test_options_contain_model(self):
        mgr = AgentSessionManager(api_key="sk-test", model="claude-opus-4-6")
        opts = mgr._build_agent_options("You are a test agent.", _FakeMCPServer())
        assert opts.model == "claude-opus-4-6"

    def test_options_contain_system_prompt(self):
        mgr = AgentSessionManager(api_key="sk-test")
        opts = mgr._build_agent_options("Custom prompt.", _FakeMCPServer())
        assert opts.system_prompt == "Custom prompt."

    def test_options_contain_mcp_servers(self):
        mgr = AgentSessionManager(api_key="sk-test")
        server = _FakeMCPServer()
        opts = mgr._build_agent_options("Prompt.", server)
        assert opts.mcp_servers == [server]

    def test_options_contain_budget(self):
        mgr = AgentSessionManager(api_key="sk-test", max_budget_usd=1.00)
        opts = mgr._build_agent_options("Prompt.", _FakeMCPServer())
        assert opts.max_budget_usd == 1.00

    def test_options_contain_max_turns(self):
        mgr = AgentSessionManager(api_key="sk-test", max_turns=20)
        opts = mgr._build_agent_options("Prompt.", _FakeMCPServer())
        assert opts.max_turns == 20

    def test_options_bypass_permissions(self):
        mgr = AgentSessionManager(api_key="sk-test")
        opts = mgr._build_agent_options("Prompt.", _FakeMCPServer())
        assert opts.permission_mode == "bypassPermissions"


# ===================================================================
# Resume session — continuation prompt construction
# ===================================================================


class TestResumePromptConstruction:
    """Verify that resume_session builds the correct continuation prompt."""

    @pytest.fixture
    def manager(self):
        return AgentSessionManager(api_key="sk-test")

    async def test_resume_prompt_contains_answers(self, manager):
        """The continuation prompt passed to _run_agent_loop should contain user answers."""
        captured_prompts: list[str] = []

        async def _capturing_run(prompt, options, state, session_id, ingestion_id):
            captured_prompts.append(prompt)
            yield format_sse_event("complete", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "state": state,
            })

        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ), patch.object(
            AgentSessionManager,
            "_run_agent_loop",
            staticmethod(_capturing_run),
        ):
            await _collect_events(
                manager.resume_session(
                    ingestion_id="ing_cp",
                    session_id="sess_cp",
                    answers=[
                        {"question": "What currency?", "answer": "USD"},
                        {"question": "Which entity?", "answer": "Acme Corp"},
                    ],
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    prior_state={},
                )
            )

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        assert "What currency?" in prompt
        assert "USD" in prompt
        assert "Which entity?" in prompt
        assert "Acme Corp" in prompt

    async def test_resume_with_empty_answers(self, manager):
        """resume_session should work even with empty answers list."""
        captured_prompts: list[str] = []

        async def _capturing_run(prompt, options, state, session_id, ingestion_id):
            captured_prompts.append(prompt)
            yield format_sse_event("complete", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "state": state,
            })

        with patch.object(
            AgentSessionManager,
            "_build_mcp_server",
            return_value=_FakeMCPServer(),
        ), patch.object(
            AgentSessionManager,
            "_run_agent_loop",
            staticmethod(_capturing_run),
        ):
            events = await _collect_events(
                manager.resume_session(
                    ingestion_id="ing_cp2",
                    session_id="sess_cp2",
                    answers=[],
                    sheets=MOCK_SHEETS,
                    templates=MOCK_TEMPLATES,
                    prior_state={},
                )
            )

        assert len(captured_prompts) == 1
        event_types = [e["type"] for e in events]
        assert "session_resume" in event_types
        assert "complete" in event_types
