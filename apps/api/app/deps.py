"""Application dependencies: artifact store, LLM router, billing, role checks, etc."""

from __future__ import annotations

import json as _json
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import Depends, Header, Request
from fastapi.exceptions import HTTPException

from apps.api.app.core.settings import get_settings
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.storage import ArtifactStore

_logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from apps.api.app.services.agent.service import AgentService
    from apps.api.app.services.billing import BillingService

# Role hierarchy per AUTH_AND_TENANCY: owner, admin, analyst, investor
ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_ANALYST = "analyst"
ROLE_INVESTOR = "investor"

# Convenience role sets for require_role()
ROLES_OWNER_ONLY = (ROLE_OWNER,)
ROLES_OWNER_OR_ADMIN = (ROLE_OWNER, ROLE_ADMIN)
ROLES_CAN_WRITE = (ROLE_OWNER, ROLE_ADMIN, ROLE_ANALYST)  # analyst+ (no investor)
ROLES_ANY = (ROLE_OWNER, ROLE_ADMIN, ROLE_ANALYST, ROLE_INVESTOR)


def require_role(*allowed_roles: str):
    """FastAPI dependency: raise 403 if request.state.role is not in allowed_roles.
    When SUPABASE_JWT_SECRET is unset (dev), missing role is treated as analyst for backward compat.
    """

    def _check(request: Request) -> None:
        role = getattr(request.state, "role", None)
        if role is None and not get_settings().supabase_jwt_secret:
            role = ROLE_ANALYST
        if role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions",
            )

    return Depends(_check)

_llm_router: LLMRouter | None = None
_billing_service: Any = None


def get_billing_service() -> BillingService:
    global _billing_service
    if _billing_service is None:
        from apps.api.app.services.billing import BillingService as _BillingService
        _billing_service = _BillingService()
    return _billing_service


def reset_billing_service() -> None:
    global _billing_service
    _billing_service = None


def get_llm_router() -> LLMRouter:
    global _llm_router
    if _llm_router is None:
        _llm_router = LLMRouter()
        # Apply startup policy override from LLM_POLICY_OVERRIDE_JSON env var (REM-19).
        # This allows routing rules to be changed without modifying source code.
        # For runtime changes without restart, use PUT /api/v1/admin/llm-policy.
        _settings = get_settings()
        if _settings.llm_policy_override_json:
            try:
                override_policy = _json.loads(_settings.llm_policy_override_json)
                _llm_router.set_policy(override_policy)
            except (ValueError, TypeError, KeyError) as e:
                _logger.warning(
                    "llm_policy_override_invalid",
                    error=str(e),
                    hint="LLM_POLICY_OVERRIDE_JSON must be valid JSON with 'rules' list",
                )
        # TODO: Wire billing once billing module is fully implemented:
        # _llm_router.set_billing_service(get_billing_service())
        # Until then, LLM router falls back to simple token metering
        # (check_limit / add_usage in services.llm.metering).
    return _llm_router


def reset_llm_router() -> None:
    global _llm_router
    _llm_router = None


_artifact_store: ArtifactStore | None = None


def get_artifact_store() -> ArtifactStore:
    """Return ArtifactStore with Supabase client when configured, else in-memory."""
    global _artifact_store
    if _artifact_store is not None:
        return _artifact_store
    settings = get_settings()
    client: Any = None
    if settings.supabase_url and (settings.supabase_service_key or settings.supabase_anon_key):
        try:
            from supabase import create_client

            client = create_client(
                settings.supabase_url,
                settings.supabase_service_key or settings.supabase_anon_key,
            )
        except Exception as e:
            _logger.warning("supabase_client_init_failed", error=str(e))
    _artifact_store = ArtifactStore(supabase_client=client)
    return _artifact_store


def reset_artifact_store() -> None:
    global _artifact_store
    _artifact_store = None


# Hybrid LLM architecture:
# - get_llm_router() → single-turn structured output (review_summary, board_pack_narrative, template_init)
# - get_agent_service() → multi-step agent tasks (Excel ingestion, draft chat, budget NL query, reforecast)
# Feature flags in Settings control which tasks use agents. Both paths share the same metering.

_agent_service: AgentService | None = None


def get_agent_service() -> AgentService | None:
    """Return AgentService if Agent SDK is enabled, else None."""
    global _agent_service
    settings = get_settings()
    if not settings.agent_sdk_enabled:
        return None
    if _agent_service is None:
        if not settings.anthropic_api_key:
            return None
        from apps.api.app.services.agent.service import AgentService
        _agent_service = AgentService(
            api_key=settings.anthropic_api_key,
            billing=get_billing_service(),
        )
    return _agent_service


def reset_agent_service() -> None:
    global _agent_service
    _agent_service = None


async def require_pim_access(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),  # noqa: B008
) -> None:
    """FastAPI dependency: raise 403 if the tenant does not have an active PIM subscription.

    Also raises HTTP 400 if the X-Tenant-ID header is absent.
    Use via Depends(require_pim_access) in PIM router endpoints to replace the
    boilerplate check_pim_access call in each handler body.
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")
    from apps.api.app.db import tenant_conn
    from apps.api.app.services.pim.access import check_pim_access

    async with tenant_conn(x_tenant_id) as conn:
        await check_pim_access(x_tenant_id, conn)
