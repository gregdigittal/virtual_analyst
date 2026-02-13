"""Application dependencies: artifact store, LLM router, billing, etc."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apps.api.app.core.settings import get_settings
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.storage import ArtifactStore

if TYPE_CHECKING:
    from apps.api.app.services.billing import BillingService

_llm_router: LLMRouter | None = None
_billing_service: Any = None


def get_billing_service() -> "BillingService":
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
        _llm_router.set_billing_service(get_billing_service())
    return _llm_router


def reset_llm_router() -> None:
    global _llm_router
    _llm_router = None


def get_artifact_store() -> ArtifactStore:
    """Return ArtifactStore with Supabase client when configured, else in-memory."""
    settings = get_settings()
    client: Any = None
    if settings.supabase_url and (settings.supabase_service_key or settings.supabase_anon_key):
        try:
            from supabase import create_client

            client = create_client(
                settings.supabase_url,
                settings.supabase_service_key or settings.supabase_anon_key,
            )
        except Exception:
            pass
    return ArtifactStore(supabase_client=client)
