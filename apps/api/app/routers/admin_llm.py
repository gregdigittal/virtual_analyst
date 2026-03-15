"""Admin endpoints for LLM routing policy management.

REM-19 (CR-N5): Make LLM retry policy runtime-configurable.

GET  /admin/llm-policy           — view current active policy
PUT  /admin/llm-policy           — replace active policy (in-memory, until restart)
POST /admin/llm-policy/reset     — restore DEFAULT_POLICY

These endpoints require owner role. The policy change is applied to the in-memory
LLMRouter singleton immediately without a process restart.

To make a policy change persistent across restarts, set LLM_POLICY_OVERRIDE_JSON
in the environment — get_llm_router() applies it at startup.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from apps.api.app.deps import get_llm_router, require_role
from apps.api.app.services.llm.router import DEFAULT_POLICY, LLMRouter

logger = structlog.get_logger()

router = APIRouter(prefix="/admin/llm-policy", tags=["admin"])

_OWNER_ONLY = ("owner",)


class PolicyRuleInput(BaseModel):
    task_label: str
    priority: int = 1
    provider: str
    model: str
    max_tokens: int = 4096
    temperature: float = 0.2


class PolicyFallbackInput(BaseModel):
    provider: str
    model: str
    max_tokens: int = 4096
    temperature: float = 0.2


class UpdatePolicyBody(BaseModel):
    rules: list[PolicyRuleInput]
    fallback: PolicyFallbackInput | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def get_llm_policy(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    llm: LLMRouter = Depends(get_llm_router),  # noqa: B008
    _: None = require_role(*_OWNER_ONLY),  # noqa: B008
) -> dict[str, Any]:
    """Return the currently active LLM routing policy.

    Shows the runtime-active policy (which may differ from DEFAULT_POLICY if
    set_policy() has been called or LLM_POLICY_OVERRIDE_JSON is set).
    """
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    active_policy = llm._policy or DEFAULT_POLICY
    return {
        "source": "override" if llm._policy is not None else "default",
        "policy": active_policy,
        "hint": (
            "To persist across restarts, set LLM_POLICY_OVERRIDE_JSON env var. "
            "Use POST /admin/llm-policy/reset to restore DEFAULT_POLICY."
        ),
    }


@router.put("")
async def update_llm_policy(
    body: UpdatePolicyBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    llm: LLMRouter = Depends(get_llm_router),  # noqa: B008
    _: None = require_role(*_OWNER_ONLY),  # noqa: B008
) -> dict[str, Any]:
    """Replace the active LLM routing policy in-memory (runtime, no restart needed).

    REM-19 (CR-N5): Runtime-configurable retry/routing policy.

    The new policy takes effect immediately for all subsequent LLM calls.
    It is lost on process restart unless also set via LLM_POLICY_OVERRIDE_JSON.

    Args:
        body: New policy with rules list and optional fallback.
    """
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    new_policy: dict[str, Any] = {
        "rules": [r.model_dump() for r in body.rules],
    }
    if body.fallback:
        new_policy["fallback"] = body.fallback.model_dump()

    llm.set_policy(new_policy)

    logger.info(
        "llm_policy_updated",
        tenant_id=x_tenant_id,
        n_rules=len(body.rules),
        has_fallback=body.fallback is not None,
    )
    return {
        "status": "applied",
        "n_rules": len(body.rules),
        "has_fallback": body.fallback is not None,
        "warning": (
            "This change is in-memory only. Set LLM_POLICY_OVERRIDE_JSON to persist across restarts."
        ),
    }


@router.post("/reset")
async def reset_llm_policy(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    llm: LLMRouter = Depends(get_llm_router),  # noqa: B008
    _: None = require_role(*_OWNER_ONLY),  # noqa: B008
) -> dict[str, Any]:
    """Restore DEFAULT_POLICY by clearing any runtime override.

    Does not affect LLM_POLICY_OVERRIDE_JSON (env-based overrides reapply on restart).
    """
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    llm.set_policy(DEFAULT_POLICY)
    logger.info("llm_policy_reset_to_default", tenant_id=x_tenant_id)
    return {"status": "reset", "source": "default"}
