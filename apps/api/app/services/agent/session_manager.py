"""AgentSessionManager — orchestrates Agent SDK calls and yields SSE events.

The session manager is the bridge between the MCP tools (Task 4), the system
prompt (Task 5), and the HTTP streaming endpoint (Task 7).  It creates an
``AsyncGenerator[str, None]`` of SSE-formatted strings that
``StreamingResponse`` can consume directly.

Usage::

    mgr = AgentSessionManager(api_key="sk-...")
    async for event in mgr.start_session(ingestion_id, tenant_id, sheets, templates, prompt):
        yield event  # already formatted as ``data: {...}\\n\\n``
"""

from __future__ import annotations

import json
import uuid
from typing import Any, AsyncGenerator

import structlog

from apps.api.app.services.agent.excel_mcp_server import (
    create_excel_mcp_server,
)
from apps.api.app.services.agent.excel_system_prompt import (
    AGENTIC_EXCEL_SYSTEM_PROMPT,
)

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# SSE event formatting
# ---------------------------------------------------------------------------


def format_sse_event(event_type: str, payload: dict[str, Any]) -> str:
    """Encode one SSE ``data:`` frame.

    Parameters
    ----------
    event_type:
        Logical event name (e.g. ``"message"``, ``"classification"``,
        ``"question"``, ``"mapping"``, ``"complete"``, ``"error"``).
    payload:
        Arbitrary JSON-serialisable dict merged into the envelope.

    Returns
    -------
    str
        A single SSE frame: ``data: {json}\\n\\n``
    """
    data = {"type": event_type, **payload}
    return f"data: {json.dumps(data)}\n\n"


# ---------------------------------------------------------------------------
# AgentSessionManager
# ---------------------------------------------------------------------------


class AgentSessionManager:
    """Manages a single agent session with SSE streaming and pause/resume.

    Each call to :meth:`start_session` or :meth:`resume_session` returns an
    async generator of SSE-formatted strings.  The generator pauses (returns)
    when the agent calls ``ask_user_question``, and the caller can later
    invoke :meth:`resume_session` with the user's answer.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-6",
        max_turns: int = 15,
        max_budget_usd: float = 0.50,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.max_turns = max_turns
        self.max_budget_usd = max_budget_usd

    # ------------------------------------------------------------------
    # Internal: build SDK objects
    # ------------------------------------------------------------------

    @staticmethod
    def _build_mcp_server(
        tool_definitions: list[dict[str, Any]],
    ) -> Any:
        """Convert plain tool-definition dicts into an SDK MCP server.

        This calls ``create_sdk_mcp_server`` from the Agent SDK.  Isolated
        as a static method so tests can easily patch it.
        """
        from claude_agent_sdk import create_sdk_mcp_server  # type: ignore[import-untyped]

        server = create_sdk_mcp_server()
        for defn in tool_definitions:
            server.tool(
                name=defn["name"],
                description=defn["description"],
                input_schema=defn["input_schema"],
            )(defn["handler"])
        return server

    def _build_agent_options(
        self,
        system_prompt: str,
        mcp_server: Any,
    ) -> Any:
        """Create ``ClaudeAgentOptions`` with the given MCP server."""
        from claude_agent_sdk import ClaudeAgentOptions  # type: ignore[import-untyped]

        return ClaudeAgentOptions(
            model=self.model,
            max_turns=self.max_turns,
            max_budget_usd=self.max_budget_usd,
            permission_mode="bypassPermissions",
            system_prompt=system_prompt,
            mcp_servers=[mcp_server],
        )

    # ------------------------------------------------------------------
    # Core: iterate over agent messages and yield SSE events
    # ------------------------------------------------------------------

    @staticmethod
    async def _run_agent_loop(
        prompt: str,
        options: Any,
        state: dict[str, Any],
        session_id: str,
        ingestion_id: str,
    ) -> AsyncGenerator[str, None]:
        """Iterate over Agent SDK messages, yielding SSE frames.

        State-change detection:
        - ``state["classification"]`` set  ->  ``classification`` event
        - ``state["pending_question"]`` set  ->  ``question`` event + return
        - ``state["mapping"]`` set  ->  ``mapping`` event
        - ``ResultMessage``  ->  ``complete`` event
        """
        from claude_agent_sdk import (  # type: ignore[import-untyped]
            AssistantMessage,
            ResultMessage,
            TextBlock,
            query,
        )

        seen_classification = "classification" in state
        seen_mapping = "mapping" in state

        try:
            async for message in query(prompt=prompt, options=options):
                # --- AssistantMessage: stream text blocks -----------------
                if isinstance(message, AssistantMessage):
                    for block in getattr(message, "content", []):
                        if isinstance(block, TextBlock):
                            yield format_sse_event("message", {
                                "session_id": session_id,
                                "ingestion_id": ingestion_id,
                                "text": block.text,
                            })

                    # Detect state changes that tools may have caused ------

                    # 1. Classification submitted
                    if not seen_classification and "classification" in state:
                        seen_classification = True
                        yield format_sse_event("classification", {
                            "session_id": session_id,
                            "ingestion_id": ingestion_id,
                            "classification": state["classification"],
                        })

                    # 2. Pending question — pause the loop
                    if "pending_question" in state:
                        question_data = state.pop("pending_question")
                        yield format_sse_event("question", {
                            "session_id": session_id,
                            "ingestion_id": ingestion_id,
                            "question": question_data["question"],
                            "options": question_data.get("options", []),
                        })
                        return  # pause — caller will resume later

                    # 3. Mapping submitted
                    if not seen_mapping and "mapping" in state:
                        seen_mapping = True
                        yield format_sse_event("mapping", {
                            "session_id": session_id,
                            "ingestion_id": ingestion_id,
                            "mapping": state["mapping"],
                        })

                # --- ResultMessage: agent is done -------------------------
                elif isinstance(message, ResultMessage):
                    yield format_sse_event("complete", {
                        "session_id": session_id,
                        "ingestion_id": ingestion_id,
                        "state": state,
                    })
                    return

        except Exception as exc:
            logger.error(
                "agent_session_error",
                session_id=session_id,
                ingestion_id=ingestion_id,
                error=str(exc),
            )
            yield format_sse_event("error", {
                "session_id": session_id,
                "ingestion_id": ingestion_id,
                "error": str(exc),
            })
            return

        # If the loop exhausts without a ResultMessage, still send complete.
        yield format_sse_event("complete", {
            "session_id": session_id,
            "ingestion_id": ingestion_id,
            "state": state,
        })

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_session(
        self,
        ingestion_id: str,
        tenant_id: str,
        sheets: dict[str, Any],
        templates: list[dict[str, Any]],
        initial_prompt: str,
    ) -> AsyncGenerator[str, None]:
        """Start a brand-new agent session.

        Parameters
        ----------
        ingestion_id:
            Unique identifier for the Excel ingestion job.
        tenant_id:
            Tenant / organisation identifier (for logging).
        sheets:
            Parsed workbook data keyed by sheet name.
        templates:
            Template catalog entries.
        initial_prompt:
            The first user prompt (e.g. ``"Classify and map this workbook."``).

        Yields
        ------
        str
            SSE-formatted ``data: {...}\\n\\n`` strings.
        """
        session_id = str(uuid.uuid4())
        state: dict[str, Any] = {}

        logger.info(
            "agent_session_start",
            session_id=session_id,
            ingestion_id=ingestion_id,
            tenant_id=tenant_id,
        )

        # 1. Build MCP tools from factory
        server_spec = create_excel_mcp_server(sheets, templates, state)
        tool_definitions = server_spec["tool_definitions"]

        # 2. Convert to SDK MCP server
        mcp_server = self._build_mcp_server(tool_definitions)

        # 3. Build agent options
        options = self._build_agent_options(AGENTIC_EXCEL_SYSTEM_PROMPT, mcp_server)

        # 4. Emit session_start event
        yield format_sse_event("session_start", {
            "session_id": session_id,
            "ingestion_id": ingestion_id,
        })

        # 5. Run agent loop
        async for event in self._run_agent_loop(
            prompt=initial_prompt,
            options=options,
            state=state,
            session_id=session_id,
            ingestion_id=ingestion_id,
        ):
            yield event

    async def resume_session(
        self,
        ingestion_id: str,
        session_id: str,
        answers: list[dict[str, Any]],
        sheets: dict[str, Any],
        templates: list[dict[str, Any]],
        prior_state: dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """Resume a paused session with user answers.

        Parameters
        ----------
        ingestion_id:
            Unique identifier for the Excel ingestion job.
        session_id:
            Session ID from the original ``session_start`` event.
        answers:
            List of ``{"question": str, "answer": str}`` dicts from the user.
        sheets:
            Parsed workbook data (same as original).
        templates:
            Template catalog entries (same as original).
        prior_state:
            Session state snapshot from before the pause. This includes any
            ``classification`` or ``mapping`` already submitted.

        Yields
        ------
        str
            SSE-formatted ``data: {...}\\n\\n`` strings.
        """
        state = dict(prior_state)  # shallow copy so we don't mutate caller's dict

        logger.info(
            "agent_session_resume",
            session_id=session_id,
            ingestion_id=ingestion_id,
            answer_count=len(answers),
        )

        # Rebuild MCP tools with the existing state
        server_spec = create_excel_mcp_server(sheets, templates, state)
        tool_definitions = server_spec["tool_definitions"]
        mcp_server = self._build_mcp_server(tool_definitions)
        options = self._build_agent_options(AGENTIC_EXCEL_SYSTEM_PROMPT, mcp_server)

        # Build the continuation prompt with user answers
        answer_lines = []
        for ans in answers:
            q = ans.get("question", "")
            a = ans.get("answer", "")
            answer_lines.append(f"Q: {q}\nA: {a}")
        answers_text = "\n\n".join(answer_lines)

        continuation_prompt = (
            "The user has answered your clarification questions. "
            "Here are their answers:\n\n"
            f"{answers_text}\n\n"
            "Please continue the analysis with these answers in mind. "
            "If you have already submitted a classification, proceed to mapping. "
            "If you need more information, ask another question."
        )

        # Emit session_resume event
        yield format_sse_event("session_resume", {
            "session_id": session_id,
            "ingestion_id": ingestion_id,
        })

        # Run agent loop
        async for event in self._run_agent_loop(
            prompt=continuation_prompt,
            options=options,
            state=state,
            session_id=session_id,
            ingestion_id=ingestion_id,
        ):
            yield event
