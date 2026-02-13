"""Application dependencies: artifact store, LLM router, etc."""

from __future__ import annotations

from typing import Any

from apps.api.app.core.settings import get_settings
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.storage import ArtifactStore

_llm_router: LLMRouter | None = None


def get_llm_router() -> LLMRouter:
    global _llm_router
    if _llm_router is None:
        _llm_router = LLMRouter()
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
