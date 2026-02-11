# Draft → Commit Specification
**Date:** 2026-02-08

## Overview
The Draft → Commit boundary is the central architectural principle of FinModel. LLMs operate exclusively in Draft mode — proposing assumptions, suggesting drivers, explaining evidence. The deterministic runtime operates exclusively on Committed artifacts (model_config_v1). The two worlds never mix.

## State Machine

```
                    ┌─────────────┐
        create      │   active    │  ← LLM can propose, user can edit
                    └──────┬──────┘
                           │ mark_ready (user action)
                    ┌──────▼──────┐
                    │  ready_to   │  ← Integrity checks run automatically
                    │   commit    │
                    └──┬──────┬───┘
             commit    │      │  reject (user action, back to active)
                    ┌──▼──┐   │
                    │comm-│   │
                    │itted│   │
                    └─────┘   │
                           ┌──▼──────┐
                           │abandoned │  ← Can happen from any state
                           └──────────┘
```

### Transitions
| From | To | Trigger | Side Effects |
|---|---|---|---|
| — | active | `POST /api/v1/drafts` | Create draft workspace in storage |
| active | ready_to_commit | User clicks "Mark Ready" | Run integrity checks; store results |
| ready_to_commit | active | User clicks "Back to Edit" | Clear check results |
| ready_to_commit | committed | `POST /api/v1/drafts/{id}/commit` | Validate → compile → create baseline |
| active | abandoned | User or timeout | Soft delete workspace |
| ready_to_commit | abandoned | User or timeout | Soft delete workspace |

## Draft Workspace Structure
A draft workspace is a mutable JSON document stored in Supabase Storage at `drafts/{tenant_id}/{draft_session_id}/workspace.json`.

```json
{
  "draft_session_id": "ds_001",
  "template_id": "manufacturing_discrete",
  "parent_baseline_id": null,
  "parent_baseline_version": null,
  "assumptions": {
    "revenue_streams": [...],
    "cost_structure": {...},
    "working_capital": {...},
    "capex": {...},
    "funding": {...}
  },
  "driver_blueprint": { "nodes": [...], "edges": [...], "formulas": [...] },
  "distributions": [...],
  "scenarios": [...],
  "evidence": [
    {
      "assumption_path": "/assumptions/revenue_streams/0/price",
      "source": "Management input: CEO call 2026-01-15",
      "confidence": "high",
      "proposed_by": "llm",
      "accepted_by": "u_001",
      "accepted_at": "2026-02-01T10:00:00Z"
    }
  ],
  "chat_history": [
    { "role": "user", "content": "...", "timestamp": "..." },
    { "role": "assistant", "content": "...", "proposals": [...], "timestamp": "..." }
  ],
  "pending_proposals": [
    {
      "proposal_id": "prop_001",
      "path": "/assumptions/cost_structure/variable_cost_per_unit",
      "current_value": null,
      "proposed_value": 42.50,
      "evidence": "Industry benchmark: avg variable cost for discrete mfg is R40-45/unit",
      "confidence": "medium",
      "status": "pending"
    }
  ]
}
```

## LLM Interaction in Draft Mode
1. User sends message via `POST /api/v1/drafts/{id}/chat`
2. System constructs prompt with: template context, current assumptions, evidence, chat history
3. LLM responds with structured JSON proposals
4. Proposals are validated:
   - Path must exist in model_config schema
   - Value must be correct type for that path
   - Confidence must be one of: high, medium, low, unvalidated
5. Valid proposals stored in `pending_proposals`
6. Invalid proposals returned to user with explanation
7. User accepts/rejects each proposal individually
8. Accepted proposals update `assumptions` and create `evidence` entry

## Integrity Checks (run at ready_to_commit)
Checks are categorized by severity: error (blocks commit), warning (allows commit with acknowledgement), info (informational).

### Error-level checks
| Check ID | Description |
|---|---|
| `IC_SCHEMA_VALID` | Workspace compiles to valid model_config_v1 JSON Schema |
| `IC_REQUIRED_FIELDS` | All required_inputs from template are populated |
| `IC_GRAPH_ACYCLIC` | Driver blueprint has no cycles |
| `IC_FORMULAS_RESOLVE` | All formula inputs reference existing nodes/drivers |
| `IC_BS_PLUGGABLE` | Balance sheet has a cash plug mechanism configured |

### Warning-level checks
| Check ID | Description |
|---|---|
| `IC_EVIDENCE_COVERAGE` | % of assumptions with evidence (warn if < 50%) |
| `IC_CONFIDENCE_MIX` | Warn if > 30% of assumptions are "low" or "unvalidated" |
| `IC_DISTRIBUTION_BOUNDS` | Stochastic distributions have reasonable min/max (e.g., utilization not > 1.0) |
| `IC_WC_DAYS_RANGE` | AR/AP/Inventory days within industry-reasonable bounds |
| `IC_CAPEX_FUNDED` | Total capex does not exceed available funding sources |

### Info-level checks
| Check ID | Description |
|---|---|
| `IC_TEMPLATE_MATCH` | Assumptions align with template defaults (flag deviations) |
| `IC_SCENARIO_COVERAGE` | At least base + one downside scenario defined |

## Commit Pipeline (what happens at POST .../commit)
```
1. Load draft workspace
2. Run all integrity checks
3. If any ERROR checks fail → return 422 with check results
4. If WARNINGS exist and user has not acknowledged → return 409 with warnings
5. Compile workspace → model_config_v1:
   a. Strip chat_history, pending_proposals
   b. Freeze assumptions, driver_blueprint, distributions, scenarios
   c. Attach evidence summary (path → source + confidence)
   d. Compute integrity_block from check results
   e. Generate baseline_id (or increment version if parent exists)
   f. Set artifact_version, created_at, created_by
6. Validate compiled artifact against model_config_v1 JSON Schema
7. Save to storage: baselines/{tenant_id}/{baseline_id}/{version}/model_config.json
8. Insert into model_baselines table (status=active)
9. Update draft_sessions table (status=committed)
10. Return: { baseline_id, version, integrity }
```

## Changeset Flow (alternative to full draft)
For incremental changes to an existing baseline:
1. Create changeset referencing baseline_id + version
2. Specify overrides: `[{ "path": "...", "value": ..., "reason": "..." }]`
3. Test (dry-run): apply overrides to copy of baseline → run engine → return results
4. Merge: apply overrides → create new baseline version
5. Changesets are immutable once created; can be abandoned but not edited

## Immutability Guarantees
- A committed model_config_v1 is **never modified**. Changes create new versions.
- Baselines are versioned: `bl_001/v1`, `bl_001/v2`, etc.
- Only one baseline can be `is_active=true` per tenant (enforced by unique partial index).
- Archived baselines remain readable but cannot be used for new runs.
