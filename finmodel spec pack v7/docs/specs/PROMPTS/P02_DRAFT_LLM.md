# Phase 2 Prompt — Draft Layer + LLM Integration

## Pre-requisites
- Phase 1 gate passed (all Phase 1 tests green)
- Read: `DRAFT_COMMIT_SPEC.md` (state machine, workspace structure, commit pipeline)
- Read: `LLM_INTEGRATION_SPEC.md` (providers, routing, prompts, validation)
- Schemas: `llm_call_log_v1`, `llm_routing_policy_v1`, `usage_meter_v1`

## Tasks

### 1. Draft Session Service
```
File: apps/api/app/services/draft_service.py

Implement the state machine from DRAFT_COMMIT_SPEC.md:
  - create_draft(tenant_id, template_id?, parent_baseline_id?) -> DraftSession
  - get_draft(tenant_id, draft_session_id) -> DraftWorkspace
  - update_draft_workspace(tenant_id, draft_session_id, changes: dict) -> DraftWorkspace
  - mark_ready(tenant_id, draft_session_id) -> IntegrityCheckResult
  - commit(tenant_id, draft_session_id, acknowledge_warnings: bool) -> CommitResult
  - abandon(tenant_id, draft_session_id) -> None

Draft workspace stored as JSON in Supabase Storage (see DRAFT_COMMIT_SPEC.md structure).
On mark_ready: run all integrity checks (IC_SCHEMA_VALID through IC_SCENARIO_COVERAGE).
On commit: validate → compile → create baseline → update status.
```

### 2. LLM Provider Abstraction
```
File: apps/api/app/services/llm/provider.py
File: apps/api/app/services/llm/anthropic_provider.py
File: apps/api/app/services/llm/openai_provider.py

Implement the provider interface from LLM_INTEGRATION_SPEC.md.
Both providers must:
  - Accept messages + response JSON Schema
  - Return structured JSON (validated against schema)
  - Retry 3x with exponential backoff
  - Record tokens, latency, cost

Use Anthropic tool_use for structured output. Use OpenAI response_format for structured output.
```

### 3. Routing Policy Engine
```
File: apps/api/app/services/llm/router.py

Load llm_routing_policy_v1 from storage (seed a default policy on first run).
Route by task_label: match rules by priority, try in order, fallback on failure.
Before each call: check usage_meter against plan limits → 429 if exceeded.
```

### 4. Call Logging + Metering
```
File: apps/api/app/services/llm/logging.py
File: apps/api/app/services/llm/metering.py

After every LLM call:
  - Write llm_call_log_v1 artifact
  - Update usage_meter_v1 for current billing period (upsert: create if not exists)

Correlation: attach draft_session_id, user_id, request_id to every log entry.
```

### 5. Chat Endpoint
```
File: apps/api/app/routers/drafts.py

POST /api/v1/drafts/{id}/chat
Body: { "message": "...", "context": {} }

Implementation:
  1. Load draft workspace
  2. Build system prompt (see LLM_INTEGRATION_SPEC.md task: draft_assumptions)
  3. Include: template context, current assumptions, evidence, last 10 chat messages
  4. Route to LLM via router
  5. Validate response proposals (path exists, type matches, bounds reasonable)
  6. Store valid proposals in workspace.pending_proposals
  7. Append to workspace.chat_history
  8. Return proposals + commentary to user

Also implement:
  POST /api/v1/drafts/{id}/proposals/{proposal_id}/accept
  POST /api/v1/drafts/{id}/proposals/{proposal_id}/reject
```

### 6. Changeset Service
```
File: apps/api/app/services/changeset_service.py
File: apps/api/app/routers/changesets.py

POST /api/v1/changesets — { baseline_id, baseline_version, overrides: [...] }
GET /api/v1/changesets/{id} — retrieve with computed diff
POST /api/v1/changesets/{id}/test — dry-run: apply → engine → return results (no persist)
POST /api/v1/changesets/{id}/merge — apply → new baseline version
```

### 7. Venture Template Wizard
```
File: apps/api/app/routers/ventures.py

POST /api/v1/ventures — { template_id, entity_name }
POST /api/v1/ventures/{id}/answers — { answers: { question_id: answer } }
POST /api/v1/ventures/{id}/generate-draft — LLM generates initial assumptions from answers

Load template from default_catalog.json. Use question_plan to structure the wizard.
LLM task_label: "template_initialization"
```

### 8. Draft Workspace UI
```
Directory: apps/web/app/drafts/

/drafts — list active draft sessions
/drafts/[id] — split layout workspace:
  Left (60%): Assumption tree editor
    - Expandable tree matching model_config structure
    - Inline value editing
    - Evidence badges (colored dots by confidence)
    - Pending proposal indicators
  Right (40%): Chat panel
    - Message history (scrollable)
    - Text input + send button
    - Proposal cards with Accept/Reject buttons
  Bottom bar: draft status, Mark Ready, Commit buttons
  On commit: show integrity check results dialog → confirm → redirect to baseline

/ventures/new — multi-step wizard:
  Step 1: Template selection (card grid)
  Step 2: Question form (grouped by section)
  Step 3: Review generated assumptions
  Step 4: Edit/commit
```

### 9. Tests
```
tests/unit/services/test_commit_pipeline.py — all integrity checks
tests/unit/services/test_llm_router.py — routing logic, fallback
tests/llm/test_draft_chat.py — structured proposals (use cassettes)
tests/integration/test_draft_commit_flow.py — create → modify → commit
tests/integration/test_changeset_flow.py — create → test → merge
tests/integration/test_auth_roles.py — role enforcement
```

## Verification
Verify Phase 2 gate criteria from BUILD_PLAN.md.
