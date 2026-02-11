# LLM Integration Specification
**Date:** 2026-02-08

## Overview
The LLM is a tool, not a decision-maker. It proposes structured data (JSON) that humans review and the commit pipeline validates. LLM output never reaches the runtime engine without passing through schema validation and human approval.

## Provider Abstraction

### Interface
```python
class LLMProvider(ABC):
    provider_name: str  # "anthropic" | "openai"

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        response_schema: dict,      # JSON Schema for structured output
        task_label: str,             # For routing + logging
        max_tokens: int = 4096,
        temperature: float = 0.2,   # Low by default for financial work
    ) -> LLMResponse:
        ...

@dataclass
class LLMResponse:
    content: dict              # Parsed structured output
    raw_text: str              # Original response text
    tokens: TokenUsage         # prompt_tokens, completion_tokens, total_tokens
    latency_ms: int
    model: str                 # Actual model used
    provider: str
    cost_estimate_usd: float   # Computed from token counts + model pricing

@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
```

### Implementations

**AnthropicProvider:**
- Models: claude-sonnet-4-5-20250929 (default), claude-haiku-4-5-20251001 (low-cost)
- Structured output: use tool_use with JSON Schema
- Retry: 3 attempts with exponential backoff (1s, 2s, 4s)
- Handle: rate limits (429), overload (529), context too long (400)

**OpenAIProvider:**
- Models: gpt-4o (default), gpt-4o-mini (low-cost)
- Structured output: use response_format with JSON Schema
- Retry: same strategy as Anthropic

### BYO-Key Support
Enterprise tenants can provide their own API keys:
- Keys stored encrypted in Supabase (tenant-level setting)
- If BYO key present, use it; otherwise use platform key
- BYO calls still logged and metered (platform fee, not token cost)

## Routing Policy

The `llm_routing_policy_v1` artifact defines how tasks map to providers:

```json
{
  "rules": [
    {
      "task_label": "draft_assumptions",
      "priority": 1,
      "provider": "anthropic",
      "model": "claude-sonnet-4-5-20250929",
      "max_tokens": 4096,
      "temperature": 0.2,
      "cost_tier": "standard"
    },
    {
      "task_label": "draft_assumptions",
      "priority": 2,
      "provider": "openai",
      "model": "gpt-4o",
      "max_tokens": 4096,
      "temperature": 0.2,
      "cost_tier": "standard"
    },
    {
      "task_label": "evidence_extraction",
      "priority": 1,
      "provider": "anthropic",
      "model": "claude-haiku-4-5-20251001",
      "max_tokens": 2048,
      "temperature": 0.1,
      "cost_tier": "low"
    },
    {
      "task_label": "memo_generation",
      "priority": 1,
      "provider": "anthropic",
      "model": "claude-sonnet-4-5-20250929",
      "max_tokens": 8192,
      "temperature": 0.3,
      "cost_tier": "standard"
    }
  ],
  "fallback": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "max_tokens": 4096,
    "temperature": 0.2,
    "cost_tier": "low"
  }
}
```

**Routing logic:**
1. Filter rules by task_label
2. Sort by priority (ascending)
3. Try priority 1 provider
4. If fails after retries, try priority 2
5. If all task-specific rules fail, use fallback
6. If fallback fails, return error to user

## Task Labels and Prompt Templates

### Task: `draft_assumptions`
**Trigger:** User chat message in draft session
**System prompt:**
```
You are a financial analyst assistant for {venture_template.label} businesses.
You are helping build a financial model with the following structure:
{driver_blueprint summary}

Current assumptions (already set):
{current_assumptions as key-value pairs}

Evidence collected so far:
{evidence entries}

Respond ONLY with a JSON object matching this schema:
{proposal_response_schema}

Guidelines:
- Propose specific numeric values with units
- Cite evidence sources (management input, industry benchmark, historical data, assumption)
- Rate confidence: high (direct evidence), medium (reasonable inference), low (placeholder/guess)
- If the user's request is unclear, ask a clarifying question in the "clarification" field
- Do not propose values outside physically reasonable bounds
```

**Response schema:**
```json
{
  "type": "object",
  "required": ["proposals"],
  "properties": {
    "proposals": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["path", "value", "evidence", "confidence"],
        "properties": {
          "path": { "type": "string", "description": "JSON path in model_config assumptions" },
          "value": { "description": "Proposed value (number, string, or object)" },
          "evidence": { "type": "string", "maxLength": 500 },
          "confidence": { "type": "string", "enum": ["high", "medium", "low"] },
          "reasoning": { "type": "string", "maxLength": 500 }
        }
      }
    },
    "clarification": {
      "type": ["string", "null"],
      "description": "Question back to user if request is ambiguous"
    },
    "commentary": {
      "type": ["string", "null"],
      "description": "Brief explanation of the analysis approach"
    }
  }
}
```

### Task: `evidence_extraction`
**Trigger:** User uploads a document (PDF, Excel) during draft
**System prompt:** Extract financial data points relevant to the model structure. Return structured extractions with page/cell references.

### Task: `memo_generation`
**Trigger:** User requests memo pack generation
**System prompt:** Generate narrative sections for the specified memo_type, drawing on run results, assumptions, and evidence. Maintain professional financial writing style. Do not invent data — only reference values from the provided results.

### Task: `template_matching`
**Trigger:** New venture creation (match business description to template)
**System prompt:** Given the business description, select the most appropriate template from the catalog and explain why.

## Validation Pipeline (Post-LLM)

Every LLM response goes through validation before being stored:

```python
async def validate_llm_output(response: LLMResponse, task_label: str) -> ValidationResult:
    # 1. Parse JSON (already done by provider's structured output)
    data = response.content

    # 2. Schema validation
    validate(data, get_response_schema(task_label))

    # 3. Task-specific validation
    if task_label == "draft_assumptions":
        for proposal in data["proposals"]:
            # Check path exists in model_config schema
            assert_valid_path(proposal["path"])
            # Check value type matches expected type at path
            assert_type_match(proposal["path"], proposal["value"])
            # Check value is within reasonable bounds
            assert_reasonable_bounds(proposal["path"], proposal["value"])

    # 4. Safety check — no code, no URLs, no PII in evidence/reasoning
    assert_safe_content(data)

    return ValidationResult(valid=True, data=data)
```

## Call Logging

Every LLM invocation produces an `llm_call_log_v1`:
```json
{
  "artifact_type": "llm_call_log_v1",
  "call_id": "call_abc123",
  "tenant_id": "t_001",
  "created_at": "2026-02-08T10:30:00Z",
  "task_label": "draft_assumptions",
  "provider": "anthropic",
  "model": "claude-sonnet-4-5-20250929",
  "tokens": {
    "prompt_tokens": 1523,
    "completion_tokens": 487,
    "total_tokens": 2010
  },
  "latency_ms": 2340,
  "cost_estimate_usd": 0.0089,
  "correlation": {
    "draft_session_id": "ds_001",
    "user_id": "u_001",
    "request_id": "req_xyz"
  }
}
```

## Usage Metering

Aggregated per tenant per billing period (calendar month):
```json
{
  "usage": {
    "llm_calls": 145,
    "llm_tokens_total": 892340,
    "llm_tokens_by_provider": {
      "anthropic": 654000,
      "openai": 238340
    },
    "llm_tokens_by_task": {
      "draft_assumptions": 520000,
      "evidence_extraction": 180000,
      "memo_generation": 192340
    }
  },
  "costs": {
    "llm_estimated_usd": 12.45,
    "llm_by_provider": {
      "anthropic": 8.90,
      "openai": 3.55
    }
  }
}
```

## Limit Enforcement
Before every LLM call:
1. Load current usage_meter for tenant
2. Load tenant's billing_subscription → plan → limits
3. If `usage.llm_tokens_total + estimated_tokens > plan.limits.llm_tokens_monthly`:
   - Return 429 with `{ "error": "token_limit_exceeded", "current": N, "limit": M }`
4. If within limit, proceed with call

## Security Constraints
- LLM output is treated as **untrusted user input** — always validated
- No `eval()` or `exec()` of LLM output
- LLM never sees other tenants' data
- API keys stored encrypted; never logged; never sent to LLM
- Prompt injection mitigations: structured output mode, output validation, content safety checks
