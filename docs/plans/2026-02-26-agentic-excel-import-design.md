# Phase 2: Agentic Excel Import with Claude SDK

**Status:** Approved
**Date:** 2026-02-26
**Replaces:** Current 4-step Excel import wizard

## 1. Goals

Replace the existing single-pass LLM Excel import with an agentic, multi-turn
flow powered by the Claude Agent SDK. The agent classifies sheets, maps
financial data to the VA schema, and asks the user clarifying questions when
uncertain — all streamed in real time via SSE.

### User decisions

| Decision | Choice |
|----------|--------|
| Focus | Smarter extraction — agentic multi-turn |
| Interaction | Human-in-the-loop (agent pauses to ask) |
| UI style | Guided chat wizard (steps + chat thread) |
| Backend | Claude Agent SDK (existing integration) |
| Tools | Full toolkit (8+ custom MCP tools) |
| Rollout | Replace entirely (old wizard removed) |
| Architecture | Agent SDK + SSE streaming |

---

## 2. Architecture

```
Frontend (Next.js)                    Backend (FastAPI)
─────────────────                     ─────────────────

ImportWizard page                     POST /excel-ingestion/upload-stream
  ├─ ImportStepper                      ├─ Parse workbook (openpyxl)
  ├─ ChatThread ◄──── SSE ────────────  ├─ AgentSessionManager
  │    ├─ ChatMessage (agent)            │   ├─ Agent SDK query()
  │    ├─ ChatMessage (user)             │   ├─ MCP Tool Server (10 tools)
  │    └─ QuestionCard                   │   └─ SSE event generator
  ├─ MappingPreview                      │
  └─ ReviewPanel                       POST /excel-ingestion/{id}/answer
                                         └─ Resume agent session

                                      POST /excel-ingestion/{id}/create-draft
                                         └─ (existing, unchanged)
```

### SSE event types

| Event type | Payload | When |
|------------|---------|------|
| `status` | `{step, message}` | Agent changes phase or reports progress |
| `tool_call` | `{tool, args}` | Agent invokes an MCP tool (live visibility) |
| `classification` | `{sheets[], model_summary}` | Agent submits sheet classifications |
| `question` | `{id, text, options[]}` | Agent pauses, needs user input |
| `mapping` | `{revenue_streams[], cost_items[], ...}` | Agent submits financial mapping |
| `complete` | `{mapping, unmapped[], questions_asked}` | Agent finished successfully |
| `error` | `{message, recoverable}` | Agent hit an error |

---

## 3. Backend

### 3.1 MCP Tool Server

**New file:** `apps/api/app/services/agent/excel_tools.py`

Each tool receives the parsed workbook context and the ingestion session state.

| Tool | Description | Input | Returns |
|------|-------------|-------|---------|
| `read_sheet_data` | Read headers + sample rows | `{sheet_name, max_rows?}` | Headers, sample rows, total row count |
| `read_cell_range` | Read specific cell range | `{sheet_name, range: "B2:F20"}` | Cell values with types |
| `get_formula_patterns` | Extract formulas + cross-sheet refs | `{sheet_name}` | Formula list, dependency graph |
| `get_sheet_dependencies` | Map inter-sheet references | `{}` | Adjacency list of sheet links |
| `compare_sheets` | Compare two sheets structurally | `{sheet_a, sheet_b}` | Structural diff summary |
| `search_template_catalog` | Search templates by industry/type | `{industry?, model_type?}` | Matching templates with schemas |
| `validate_mapping` | Validate partial mapping against schema | `{mapping}` | Errors, warnings, coverage % |
| `submit_classification` | Submit sheet classifications | `{sheets[], model_summary}` | Confirmation + stored |
| `submit_mapping` | Submit final financial mapping | `{mapping}` | Validated mapping or errors |
| `ask_user_question` | Pause agent, send question to user | `{text, options[], context?}` | **Suspends agent** until answered |

Tools are registered via `create_sdk_mcp_server("excel-tools", tools=[...])`.

### 3.2 Agent Session Manager

**New file:** `apps/api/app/services/agent/session_manager.py`

```python
class AgentSessionManager:
    async def start_session(
        ingestion_id: str,
        tenant_id: str,
        parsed_workbook: dict,
    ) -> AsyncGenerator[str, None]:
        """
        Start Agent SDK session, yield SSE events.
        On ask_user_question: pause, store question, yield question event.
        """

    async def resume_session(
        ingestion_id: str,
        answers: list[dict],
    ) -> AsyncGenerator[str, None]:
        """
        Resume paused session with user answers.
        Uses Agent SDK session resumption.
        """
```

State stored in ingestion session row:
- `agent_session_id` — Agent SDK session ID for resumption
- `agent_messages` — JSONB array of chat messages (for frontend hydration)
- `agent_status` — `running | paused | complete | error`
- `pending_question` — JSONB of current question (null when not paused)

### 3.3 SSE Endpoint

**Modified file:** `apps/api/app/routers/excel_ingestion.py`

```python
@router.post("/excel-ingestion/upload-stream")
async def upload_and_stream(
    file: UploadFile,
    tenant_id: str = Depends(get_tenant_id),
    user_id: str = Depends(get_user_id),
):
    # 1. Save file + parse workbook (reuse existing logic)
    ingestion_id = await start_ingestion(tenant_id, user_id, file)
    parsed = await parse_workbook(ingestion_id)

    # 2. Stream agent session as SSE
    return StreamingResponse(
        session_manager.start_session(ingestion_id, tenant_id, parsed),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

### 3.4 System Prompt

**New file:** `apps/api/app/services/agent/excel_system_prompt.py`

> You are a financial model analyst for Virtual Analyst. You have tools to read
> and analyze an uploaded Excel workbook. Your job:
>
> 1. **Explore** the workbook — read each sheet's headers and sample data
> 2. **Classify** every sheet using the 15 standard categories
> 3. **Submit classification** via the submit_classification tool
> 4. **Map** financial data from core sheets to the VA schema
> 5. If uncertain about any item, use ask_user_question to clarify
> 6. **Validate** your mapping via validate_mapping before finalizing
> 7. **Submit** the final mapping via submit_mapping
>
> Rules:
> - Never fabricate data — only map what you can see in the workbook
> - Put uncertain items in unmapped_items
> - Cross-reference sheets for consistency
> - Prefer asking the user over guessing

### 3.5 DB Migration

Add columns to `excel_ingestion_sessions`:

```sql
ALTER TABLE excel_ingestion_sessions ADD COLUMN agent_session_id TEXT;
ALTER TABLE excel_ingestion_sessions ADD COLUMN agent_messages JSONB DEFAULT '[]';
ALTER TABLE excel_ingestion_sessions ADD COLUMN agent_status TEXT DEFAULT 'pending';
ALTER TABLE excel_ingestion_sessions ADD COLUMN pending_question JSONB;
```

---

## 4. Frontend

### 4.1 Page Rewrite

**Rewrite:** `apps/web/app/(app)/excel-import/page.tsx`

The page becomes a guided chat wizard with 4 steps:

```
┌──────────────────────────────────────────────────────┐
│  Import Excel Model                                  │
├──────────────────────────────────────────────────────┤
│  ● Upload  ○ Classify  ○ Map  ○ Review               │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━            │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  Chat Thread (scrollable)                      │  │
│  │                                                │  │
│  │  🤖 Analyzing "Financial Model v3.xlsx"...     │  │
│  │     Reading sheet "P&L" (45 rows, 8 cols)      │  │
│  │                                                │  │
│  │  🤖 Classification complete:                   │  │
│  │     ✓ P&L → income_statement (high)            │  │
│  │     ✓ Balance Sheet → balance_sheet (high)     │  │
│  │                                                │  │
│  │  🤖 Question: "Row 12 shows 'Prof. Fees'.     │  │
│  │     Classify as:"                              │  │
│  │     [Operating Expense] [SG&A] [Cost of Rev]   │  │
│  │                                                │  │
│  │  👤 Operating Expense                          │  │
│  │                                                │  │
│  │  🤖 Mapping complete. 94% coverage.            │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  Type a message...                    [Send ➤] │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│           [Create Draft →]  (when complete)          │
└──────────────────────────────────────────────────────┘
```

### 4.2 New Components

| Component | File | Purpose |
|-----------|------|---------|
| `ImportStepper` | `components/ImportStepper.tsx` | 4-step horizontal stepper (Upload → Classify → Map → Review) |
| `ChatThread` | `components/excel-import/ChatThread.tsx` | Scrollable list of ChatMessage components |
| `ChatMessage` | `components/excel-import/ChatMessage.tsx` | Single message bubble (agent or user role) |
| `QuestionCard` | `components/excel-import/QuestionCard.tsx` | Inline card with option buttons for agent questions |
| `MappingPreview` | `components/excel-import/MappingPreview.tsx` | Collapsible accordion showing current mapping state |
| `ReviewPanel` | `components/excel-import/ReviewPanel.tsx` | Final review: mapped/unmapped items, edit toggle |

### 4.3 SSE Hook

**New file:** `apps/web/hooks/useAgentStream.ts`

```typescript
interface UseAgentStreamReturn {
  messages: ChatMessage[];
  currentStep: "upload" | "classify" | "map" | "review";
  isComplete: boolean;
  isPaused: boolean;
  pendingQuestion: AgentQuestion | null;
  classification: Classification | null;
  mapping: Mapping | null;
  error: string | null;
  startStream: (ingestionId: string) => void;
  answerQuestion: (questionId: string, answer: string) => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
}

function useAgentStream(): UseAgentStreamReturn {
  // Connects to SSE endpoint via EventSource
  // Parses events, appends to messages[]
  // On "question" event: sets isPaused, populates pendingQuestion
  // answerQuestion: POST /answer, reconnects SSE
  // Auto-advances currentStep based on events
}
```

### 4.4 API Client Additions

**Modified file:** `apps/web/lib/api.ts`

```typescript
excelIngestion: {
  // Existing methods preserved...

  // New: returns URL for SSE connection
  uploadStreamUrl(tenantId: string, userId: string): string,

  // New: answer during streaming session
  answerStream(tenantId: string, ingestionId: string, answers: Answer[]): Promise<void>,
}
```

---

## 5. Data Flow

```
User drops .xlsx
  │
  ▼
POST /upload-stream (multipart file)
  │
  ├── Parse workbook (openpyxl) → store parse result
  │
  ├── Start Agent SDK session
  │   ├── Agent calls read_sheet_data for each sheet
  │   │   └── SSE: tool_call, status events
  │   ├── Agent calls submit_classification
  │   │   └── SSE: classification event → step advances to "Map"
  │   ├── Agent reads financial core sheets in detail
  │   ├── Agent calls ask_user_question (if uncertain)
  │   │   └── SSE: question event → frontend shows QuestionCard
  │   │       User clicks option → POST /answer
  │   │       └── Agent resumes with answer
  │   ├── Agent calls validate_mapping
  │   ├── Agent calls submit_mapping
  │   │   └── SSE: mapping event → step advances to "Review"
  │   └── SSE: complete event
  │
  ▼
User reviews in ReviewPanel
  │
  ▼
POST /create-draft (existing) → redirect to /drafts/{id}
```

---

## 6. Migration Strategy

- The current 4-step wizard in `excel-import/page.tsx` is **replaced entirely**
- Existing service functions (`parse_and_classify`, `analyze_and_map`) are kept as
  internal utilities — the MCP tools call into them
- All existing REST endpoints remain for backwards compatibility (history, delete, get)
- Feature gate: `agent_excel_ingestion_enabled` setting controls whether the agent
  path is available; if disabled, show fallback banner
- The old `excel_agent.py` one-shot agent is superseded by the new session-based agent

---

## 7. Implementation Tasks

| # | Task | Area | Depends on |
|---|------|------|------------|
| 1 | DB migration: add agent columns to ingestion sessions | Backend | — |
| 2 | MCP tool server: read tools (read_sheet_data, read_cell_range, get_formula_patterns, get_sheet_dependencies, compare_sheets) | Backend | — |
| 3 | MCP tool server: action tools (search_template_catalog, validate_mapping, submit_classification, submit_mapping) | Backend | 2 |
| 4 | MCP tool server: ask_user_question (suspend/resume) | Backend | 2 |
| 5 | Agent system prompt | Backend | — |
| 6 | AgentSessionManager (start_session, resume_session) | Backend | 2, 3, 4, 5 |
| 7 | SSE endpoint (upload-stream) | Backend | 6 |
| 8 | useAgentStream hook | Frontend | 7 |
| 9 | ChatMessage + ChatThread components | Frontend | — |
| 10 | QuestionCard component | Frontend | — |
| 11 | ImportStepper component | Frontend | — |
| 12 | MappingPreview + ReviewPanel components | Frontend | — |
| 13 | ImportWizard page (wire everything together) | Frontend | 8-12 |
| 14 | API client additions (uploadStreamUrl, answerStream) | Frontend | 7 |
| 15 | Tests: MCP tools + session manager | Backend | 2-6 |
| 16 | Tests: frontend components + hook | Frontend | 8-13 |

---

## 8. Cost & Performance

| Metric | Estimate |
|--------|----------|
| Agent budget per import | $0.50 max (configurable) |
| Max turns | 15 (configurable) |
| Timeout | 180 seconds |
| Model | claude-opus-4-6 (configurable, default) |
| Avg questions asked | 2-4 per import |
| Avg tool calls | 15-25 per import |
| SSE latency | <500ms per event |
