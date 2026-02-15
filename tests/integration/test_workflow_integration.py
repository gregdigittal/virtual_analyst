"""VA-P6-12: Workflow integration test — assign → submit → review → approve/return.

Requires INTEGRATION_TESTS=1 and DATABASE_URL. Skips when not configured.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("INTEGRATION_TESTS") != "1" or not os.environ.get("DATABASE_URL"),
    reason="INTEGRATION_TESTS=1 and DATABASE_URL required",
)


@pytest.mark.asyncio
async def test_workflow_lifecycle_placeholder() -> None:
    """Placeholder for full flow: create assignment → claim → submit → review → approve.
    Expand with real DB setup and API calls when integration env is available.
    """
    assert os.environ.get("INTEGRATION_TESTS") == "1"
