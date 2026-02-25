"""Integration test fixtures: app client, in-memory artifact store, seed data."""

from __future__ import annotations

import os

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.app.core.settings import get_settings
from apps.api.app.deps import get_artifact_store
from apps.api.app.main import app
from shared.fm_shared.storage import ArtifactStore


def _integration_enabled() -> bool:
    return os.environ.get("INTEGRATION_TESTS", "").lower() in ("1", "true", "yes")


integration_marker = pytest.mark.skipif(
    not _integration_enabled(),
    reason="Set INTEGRATION_TESTS=1 and DATABASE_URL with migrations applied to run",
)

# Tenants and users referenced by integration tests.
_SEED_TENANTS = [
    "t_integration",
    "t_integration_run",
    "t_integration_boardpack",
    "t_integration_budgets",
    "t_integration_var",
    "t_tenant_a",
    "t_tenant_b",
    "t_tenant_a_rls",
    "t_tenant_b_rls",
    "t_sec_a",
    "t_sec_b",
    "t1",
]

# (user_id, tenant_id, role) — user_id is PK so each appears once;
# mapped to the first tenant that uses it.
_SEED_USERS = [
    ("u1", "t_integration", "owner"),
    ("u2", "t_integration", "analyst"),
    ("u_a", "t_tenant_a", "analyst"),
    ("u_b", "t_tenant_b", "analyst"),
]


@pytest.fixture(scope="session", autouse=True)
async def _seed_integration_data():
    """Insert tenants and users needed by integration tests (idempotent)."""
    if not _integration_enabled():
        yield
        return
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url)
    try:
        for tid in _SEED_TENANTS:
            await conn.execute(
                "INSERT INTO tenants (id, name) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING",
                tid,
                tid,
            )
        for uid, tid, role in _SEED_USERS:
            await conn.execute(
                "INSERT INTO users (id, tenant_id, role) VALUES ($1, $2, $3) ON CONFLICT (id) DO NOTHING",
                uid,
                tid,
                role,
            )
        yield
    finally:
        await conn.close()


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
