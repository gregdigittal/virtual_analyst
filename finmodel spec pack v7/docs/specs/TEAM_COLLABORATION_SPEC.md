# Team Collaboration & Workflow Specification
**Date:** 2026-02-13

## Overview
Virtual Analyst supports multi-user teams within a tenant, with organizational hierarchy, job-function-based roles, configurable review workflows, task assignment, and structured feedback. This enables enterprise use cases where junior analysts build models, seniors review and correct them, and managers assign and oversee work — all with full auditability and a learning feedback loop.

This specification extends the flat four-role model in `AUTH_AND_TENANCY.md` with a richer team layer. The existing roles (owner, admin, analyst, investor) become **system roles** that gate API access. The new **team roles** define workflow position, reporting lines, and review authority.

## Design Principles
- **Human-in-the-loop first:** Workflow is about routing human decisions, not automating them away.
- **LLM assists, never decides:** The AI provides methodology context and change summaries, but approval/rejection is always a human action.
- **Auditability:** Every assignment, submission, review, correction, and approval is an audit event.
- **Learning by doing:** Corrections flow back to the original author with context, turning every review into a coaching moment.

---

## Organizational Hierarchy

### Team Structure
Each tenant has one or more **teams**. A team has members with defined positions in a reporting hierarchy.

```
┌─────────────────────────────────────────────┐
│ Tenant (Organization)                       │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────────────────────────────┐        │
│  │ Team: Credit Analysis           │        │
│  │                                 │        │
│  │  Head of Credit ──┐             │        │
│  │                   ├── Senior 1  │        │
│  │                   │   ├── Jr A  │        │
│  │                   │   └── Jr B  │        │
│  │                   └── Senior 2  │        │
│  │                       └── Jr C  │        │
│  └─────────────────────────────────┘        │
│                                             │
│  ┌─────────────────────────────────┐        │
│  │ Team: Portfolio Management      │        │
│  │  PM Lead ── Analyst 1           │        │
│  │          └── Analyst 2          │        │
│  └─────────────────────────────────┘        │
│                                             │
└─────────────────────────────────────────────┘
```

### Job Functions
Job functions are tenant-configurable labels that describe what a user does. They are metadata — not permission gates — but are used by the workflow engine for routing and by the UI for context.

Default job functions (seeded on tenant creation, editable by admin/owner):

| Function ID | Label | Typical Level |
|---|---|---|
| `credit_analyst_jr` | Junior Credit Analyst | junior |
| `credit_analyst_sr` | Senior Credit Analyst | senior |
| `credit_manager` | Credit Manager | lead |
| `portfolio_analyst` | Portfolio Analyst | junior |
| `portfolio_manager` | Portfolio Manager | lead |
| `financial_modeller` | Financial Modeller | junior |
| `financial_modeller_sr` | Senior Financial Modeller | senior |
| `risk_analyst` | Risk Analyst | junior |
| `cfo` | CFO / Finance Director | executive |
| `custom` | Custom (user-defined) | — |

Level values: `junior`, `senior`, `lead`, `executive`. These drive workflow defaults (e.g., junior submissions route to the nearest senior in reporting line).

---

## Data Model

### Migration: `0011_teams_workflow.sql`

```sql
-- Teams
CREATE TABLE teams (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  name TEXT NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by TEXT,
  UNIQUE (tenant_id, name)
);

-- Team membership with hierarchy
CREATE TABLE team_members (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  user_id TEXT NOT NULL,
  job_function TEXT NOT NULL DEFAULT 'custom',
  job_title TEXT,                        -- Free-text display title
  level TEXT NOT NULL DEFAULT 'junior',  -- junior | senior | lead | executive
  reports_to TEXT,                       -- user_id of direct supervisor (NULL = team lead)
  can_review BOOLEAN NOT NULL DEFAULT false,
  can_assign BOOLEAN NOT NULL DEFAULT false,
  joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (team_id, user_id)
);

-- Job function catalog (tenant-configurable)
CREATE TABLE job_functions (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  label TEXT NOT NULL,
  level TEXT NOT NULL DEFAULT 'junior',
  description TEXT,
  UNIQUE (tenant_id, id)
);

-- Workflow templates
CREATE TABLE workflow_templates (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  name TEXT NOT NULL,
  description TEXT,
  stages JSONB NOT NULL,  -- Array of stage definitions (see below)
  is_default BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by TEXT
);

-- Workflow instances (attached to a draft or baseline)
CREATE TABLE workflow_instances (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  template_id TEXT NOT NULL REFERENCES workflow_templates(id),
  entity_type TEXT NOT NULL,            -- 'draft_session' | 'baseline' | 'changeset'
  entity_id TEXT NOT NULL,
  current_stage TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active', -- active | completed | cancelled
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_by TEXT,
  completed_at TIMESTAMPTZ,
  deadline TIMESTAMPTZ
);

-- Task assignments
CREATE TABLE task_assignments (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  workflow_instance_id TEXT REFERENCES workflow_instances(id),
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  assigned_to TEXT NOT NULL,            -- user_id or 'team:{team_id}' for group assignment
  assigned_by TEXT NOT NULL,
  assignment_type TEXT NOT NULL,        -- 'build' | 'review' | 'approve' | 'correct'
  instructions TEXT,                     -- Free-text instructions from assigner
  methodology_notes TEXT,                -- Approach/methodology context
  deadline TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'pending', -- pending | in_progress | submitted | completed | returned
  priority TEXT NOT NULL DEFAULT 'normal', -- low | normal | high | urgent
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at TIMESTAMPTZ,
  submitted_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

-- Review records
CREATE TABLE reviews (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  task_assignment_id TEXT NOT NULL REFERENCES task_assignments(id),
  reviewer_id TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  decision TEXT NOT NULL,               -- 'approve' | 'request_changes' | 'reject'
  review_notes TEXT,                     -- Narrative feedback
  changes_made JSONB,                   -- Array of {path, old_value, new_value, reason}
  methodology_assessment TEXT,           -- Assessment of approach used
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Change summaries (auto-generated for learning feedback)
CREATE TABLE change_summaries (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  review_id TEXT NOT NULL REFERENCES reviews(id),
  original_author_id TEXT NOT NULL,
  summary_text TEXT NOT NULL,           -- Human-readable summary of what changed and why
  changes JSONB NOT NULL,               -- Structured diff: [{path, old, new, reason}]
  learning_points JSONB,                -- AI-generated learning suggestions
  acknowledged_at TIMESTAMPTZ,          -- When the author read the feedback
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS policies (same pattern as all other tables)
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_functions ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_instances ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE change_summaries ENABLE ROW LEVEL SECURITY;

-- Each table gets tenant_id = current_setting('app.tenant_id') policies
-- (same pattern as AUTH_AND_TENANCY.md)

-- Indexes
CREATE INDEX idx_team_members_user ON team_members(user_id);
CREATE INDEX idx_team_members_reports_to ON team_members(reports_to);
CREATE INDEX idx_task_assignments_assigned_to ON task_assignments(tenant_id, assigned_to, status);
CREATE INDEX idx_task_assignments_entity ON task_assignments(tenant_id, entity_type, entity_id);
CREATE INDEX idx_workflow_instances_entity ON workflow_instances(tenant_id, entity_type, entity_id);
CREATE INDEX idx_reviews_task ON reviews(task_assignment_id);
CREATE INDEX idx_change_summaries_author ON change_summaries(original_author_id, acknowledged_at);
```

## Workflow Engine

### Workflow Template Structure
A workflow template defines a sequence of stages that an entity (draft, baseline, changeset) passes through. Stages are stored as JSONB:

```json
{
  "stages": [
    {
      "stage_id": "build",
      "label": "Build Model",
      "assignee_rule": "explicit",
      "required_level": null,
      "auto_advance": false,
      "description": "Analyst constructs the financial model and fills in assumptions."
    },
    {
      "stage_id": "peer_review",
      "label": "Peer Review",
      "assignee_rule": "reports_to",
      "required_level": "senior",
      "auto_advance": false,
      "description": "Senior analyst reviews methodology, checks assumptions, and validates outputs."
    },
    {
      "stage_id": "manager_approval",
      "label": "Manager Approval",
      "assignee_rule": "reports_to_chain",
      "required_level": "lead",
      "auto_advance": false,
      "description": "Team lead gives final approval before the model can be committed."
    }
  ]
}
```

Assignee rules:

| Rule | Behavior |
|------|----------|
| explicit | Assigner manually picks the user |
| reports_to | Routes to the assignee's direct supervisor |
| reports_to_chain | Routes up the chain until a user at required_level is found |
| team_pool | Assigns to the team; any member at required_level can claim it |
| same_user | Stays with the current assignee (e.g., for corrections) |

### Default Workflow Templates
Seeded on tenant creation:

1. **Standard Review (2-stage)**  
   Build (explicit) → Peer Review (reports_to, senior)

2. **Full Approval (3-stage)**  
   Build (explicit) → Peer Review (reports_to, senior) → Manager Approval (reports_to_chain, lead)

3. **Self-Service (1-stage)**  
   Build (explicit) — no review required

### Workflow State Machine

```
                    ┌─────────────┐
                    │   pending    │
                    └──────┬──────┘
                           │ assign / claim
                           ▼
                    ┌─────────────┐
              ┌─────│ in_progress  │
              │     └──────┬──────┘
              │            │ submit
              │            ▼
              │     ┌─────────────┐
              │     │  submitted   │──────────────┐
              │     └──────┬──────┘               │
              │            │ review                │
              │            ▼                       │
              │     ┌─────────────┐         ┌─────┴──────┐
              │     │  approved   │         │  returned   │
              │     └──────┬──────┘         └──────┬─────┘
              │            │                       │
              │            │ advance               │ rework
              │            ▼                       │
              │     ┌─────────────┐               │
              │     │  completed   │◄──────────────┘
              │     └─────────────┘         (after rework → re-submit)
              │
              │ cancel
              ▼
       ┌─────────────┐
       │  cancelled   │
       └─────────────┘
```

---

## Top-Down Assignment Flow

**Scenario: Senior Assigns Analysis to Junior**

1. Senior navigates to /assignments/new
2. Selects assignment type: "Build Model"
3. Chooses entity: new draft (auto-created) or existing draft
4. Assigns to: specific junior OR team pool
5. Writes instructions: *"Build a 3-year DCF for Acme Corp using the manufacturing template. Focus on revenue growth assumptions — we have Q1 actuals in the uploaded CSV. Deadline: Friday 5pm."*
6. Sets deadline and priority
7. Submits → junior receives notification

**Junior's view:** Task appears in /inbox with instructions, deadline, priority badge. Click to open the draft workspace with instructions panel visible. Work on model normally (chat, proposals, assumptions). When done, click "Submit for Review" → routes to senior per workflow.

**Scenario: Senior Defines Group Assignment**

1. Senior assigns to "Credit Analysis team" (pool)
2. Any junior on the team sees it in their inbox
3. First to click "Claim" gets the assignment
4. Others see it as "Claimed by [name]"

---

## Bottom-Up Review Flow

**Scenario: Junior Submits → Senior Reviews → Approve**

1. Junior completes model work in draft workspace and clicks "Submit for Review"
2. System determines next reviewer: looks up junior's reports_to in team_members; if that user has can_review=true and meets required_level → assign; else traverse reports_to_chain
3. Senior receives notification and opens /inbox → clicks task → enters **Review Mode**

**Review Mode** shows: Methodology panel (template, approach, chat history read-only); Assumptions (full assumption tree with confidence badges, evidence); Review Decision: [Approve] [Request Changes] [Reject] with Review Notes.

4. Senior can: **APPROVE** (advances to next stage or completes workflow); **REQUEST CHANGES** (writes notes, optionally makes corrections inline, task returns to junior as "returned"); **REJECT** (workflow cancelled, junior notified with reason)

**Scenario: Senior Corrects → Junior Learns**

1. Senior clicks "Request Changes", edits assumptions (each edit tracked as {path, old_value, new_value, reason}), writes review notes, submits review
2. System generates change_summary: structured diff and optional LLM learning_points
3. Junior receives notification, opens change summary with diff, reviewer notes, learning points, and [Acknowledge & Continue Working]
4. Junior acknowledges feedback (timestamps acknowledged_at), continues working, re-submits when ready

---

## API Routes

### Teams
- POST   /api/v1/teams — Create team
- GET    /api/v1/teams — List teams for tenant
- GET    /api/v1/teams/{team_id} — Get team detail + members
- PATCH  /api/v1/teams/{team_id} — Update team name/description
- DELETE /api/v1/teams/{team_id} — Archive team
- POST   /api/v1/teams/{team_id}/members — Add member
- PATCH  /api/v1/teams/{team_id}/members/{user_id} — Update role/reports_to/permissions
- DELETE /api/v1/teams/{team_id}/members/{user_id} — Remove member

### Job Functions
- GET    /api/v1/job-functions — List job functions for tenant
- POST   /api/v1/job-functions — Create custom job function
- PATCH  /api/v1/job-functions/{id} — Update
- DELETE /api/v1/job-functions/{id} — Delete (only custom)

### Workflow Templates
- GET    /api/v1/workflow-templates — List templates
- POST   /api/v1/workflow-templates — Create custom template
- GET    /api/v1/workflow-templates/{id} — Get template detail
- PATCH  /api/v1/workflow-templates/{id} — Update
- DELETE /api/v1/workflow-templates/{id} — Delete (not default)

### Task Assignments (Inbox)
- GET    /api/v1/assignments — List my assignments (inbox); ?status=pending,in_progress&assigned_to=me&team_id=...
- POST   /api/v1/assignments — Create assignment (top-down)
- GET    /api/v1/assignments/{id} — Get assignment detail
- PATCH  /api/v1/assignments/{id} — Update status (claim, start, submit)
- POST   /api/v1/assignments/{id}/submit — Submit work for review
- POST   /api/v1/assignments/{id}/claim — Claim a pool assignment

### Reviews
- POST   /api/v1/assignments/{id}/review — Submit review decision (body: decision, review_notes, changes_made, methodology_assessment)
- GET    /api/v1/reviews — List reviews I've given/received
- GET    /api/v1/reviews/{id} — Get review detail

### Change Summaries (Learning Feedback)
- GET    /api/v1/change-summaries — List my unacknowledged feedback
- GET    /api/v1/change-summaries/{id} — Get summary detail
- PATCH  /api/v1/change-summaries/{id}/acknowledge — Mark as read

### Workflow Instances
- GET    /api/v1/workflows — List active workflow instances
- GET    /api/v1/workflows/{id} — Get instance detail + stage history
- POST   /api/v1/workflows/{id}/cancel — Cancel workflow (owner/admin/lead only)

---

## UI Pages

- **/settings/teams** — Team Management (admin/owner): list teams, create team, team detail with member list and hierarchy tree, add/remove members, set reports_to, job function, permissions
- **/inbox** — Personal Task Inbox: My Assignments, Team Pool (unclaimed), Awaiting Review, Review Requests; cards show entity name, assignment type badge, priority, deadline, assignee/assigner, status
- **/inbox/{assignment_id}** — Assignment Detail: instructions panel, link to draft/baseline workspace, status controls (Claim, Start, Submit for Review), timeline
- **/inbox/{assignment_id}/review** — Review Workspace: split layout — methodology panel (chat read-only, template, approach summary), assumption tree (editable by reviewer), review form (decision buttons, notes, change tracking); every reviewer edit tracked with reason
- **/inbox/feedback** — Learning Feedback: list of change summaries with diff display, unacknowledged highlighted, acknowledge button
- **/assignments/new** — Create Assignment wizard: type, entity, assign to (user or team pool), instructions, methodology notes, deadline, priority, workflow template

---

## Notification Events

| Event | Recipients | Channel |
|-------|------------|---------|
| task_assigned | Assignee(s) | In-app + email |
| task_claimed | Assigner + other pool members | In-app |
| task_submitted | Next reviewer in workflow | In-app + email |
| review_approved | Original author + assigner | In-app + email |
| review_changes_requested | Original author | In-app + email |
| review_rejected | Original author + assigner | In-app + email |
| correction_feedback_ready | Original author | In-app + email |
| deadline_approaching | Assignee (24h, 4h before) | In-app + email |
| deadline_overdue | Assignee + assigner + reports_to | In-app + email |
| workflow_completed | All participants | In-app |

---

## LLM Integration

**Task: review_summary** — Trigger: Reviewer submits a review with changes_made.  
System prompt: *You are a financial analysis mentor. A senior reviewer has made corrections to a junior analyst's financial model. Summarize the changes in a constructive, educational tone. Focus on: 1) What was changed and why; 2) What the analyst should learn from each correction; 3) General principles to apply in future models. Do NOT fabricate data. Only reference the actual changes provided. Respond with JSON: { "summary_text": "...", "learning_points": ["...", "..."] }*

**Task: methodology_context** — Trigger: Review workspace opened.  
System prompt: *Summarize the methodology used to build this financial model based on the chat history and assumption tree. Focus on: 1) What approach was taken; 2) Key decisions made; 3) Areas where the analyst expressed uncertainty. Do NOT fabricate information. Respond with JSON: { "methodology_summary": "...", "key_decisions": ["..."], "uncertainty_areas": ["..."] }*

---

## Audit Events

team.created | team.member_added | team.member_removed | team.member_updated | assignment.created | assignment.claimed | assignment.submitted | assignment.returned | review.approved | review.changes_requested | review.rejected | workflow.completed | workflow.cancelled | feedback.acknowledged

---

## Permission Extensions

Extend the permission matrix from AUTH_AND_TENANCY.md:

| Resource | owner | admin | analyst | investor |
|----------|-------|-------|---------|----------|
| Teams (CRUD) | ✓ | ✓ | ✗ | ✗ |
| Team members (manage) | ✓ | ✓ | ✗ | ✗ |
| Workflow templates (CRUD) | ✓ | ✓ | ✗ | ✗ |
| Assignments (create) | ✓ | ✓ | ✓* | ✗ |
| Assignments (view own) | ✓ | ✓ | ✓ | ✓ |
| Reviews (submit) | ✓ | ✓ | ✓** | ✗ |
| Change summaries (view own) | ✓ | ✓ | ✓ | ✗ |

\* Analyst can create assignments only if can_assign=true in team_members.  
\** Analyst can submit reviews only if can_review=true in team_members.

---

## Security Constraints

- Team hierarchy data is tenant-scoped via RLS — no cross-tenant visibility
- reports_to must reference a user_id within the same team
- Review edits are tracked immutably — reviewers cannot hide their changes
- Change summaries are append-only; acknowledged_at timestamp cannot be unset
- Deadline enforcement is advisory (overdue tasks are flagged, not blocked)
- LLM-generated learning points are clearly labeled as AI-generated in the UI
