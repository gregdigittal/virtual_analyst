"""Integration test fixtures: app client, in-memory artifact store."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.app.deps import get_artifact_store
from apps.api.app.main import app
from shared.fm_shared.storage import ArtifactStore


def _integration_enabled() -> bool:
    return os.environ.get("INTEGRATION_TESTS", "").lower() in ("1", "true", "yes")


integration_marker = pytest.mark.skipif(
    not _integration_enabled(),
    reason="Set INTEGRATION_TESTS=1 and DATABASE_URL with migrations applied to run",
)


@pytest.fixture
def in_memory_store() -> ArtifactStore:
    """In-memory artifact store so integration tests do not require Supabase."""
    return ArtifactStore(supabase_client=None)


@pytest.fixture
def client(in_memory_store: ArtifactStore) -> AsyncClient:
    """Async HTTP client with artifact store overridden to in-memory."""
    app.dependency_overrides[get_artifact_store] = lambda: in_memory_store
    try:
        transport = ASGITransport(app=app)
        yield AsyncClient(transport=transport, base_url="http://test")
    finally:
        app.dependency_overrides.pop(get_artifact_store, None)
