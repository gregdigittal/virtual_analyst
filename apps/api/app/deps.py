"""Application dependencies: artifact store, etc."""

from __future__ import annotations

from typing import Any

from apps.api.app.core.settings import get_settings
from shared.fm_shared.storage import ArtifactStore


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
