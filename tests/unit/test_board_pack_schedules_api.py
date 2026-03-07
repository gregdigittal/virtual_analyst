"""H-01: Board pack schedules API tests — CRUD, run-now, distribute, history, cron."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.deps import get_artifact_store, get_llm_router
from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-h01"
USER = "user-h01"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": USER}


def _mock_tenant_conn(_tenant_id: str):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _setup_di():
    mock_store = MagicMock()
    mock_store.save = MagicMock(return_value="path")
    mock_store.load = MagicMock(return_value={})
    mock_llm = MagicMock()
    app.dependency_overrides[get_artifact_store] = lambda: mock_store
    app.dependency_overrides[get_llm_router] = lambda: mock_llm
    return mock_store, mock_llm


def _cleanup():
    app.dependency_overrides.pop(get_artifact_store, None)
    app.dependency_overrides.pop(get_llm_router, None)


def test_create_schedule_requires_tenant() -> None:
    r = client.post(
        "/api/v1/board-packs/schedules",
        json={"label": "Q1", "run_id": "r1", "cron_expr": "0 9 5 * *"},
    )
    assert r.status_code == 400


def test_create_schedule_success() -> None:
    with patch("apps.api.app.routers.board_pack_schedules.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.post(
            "/api/v1/board-packs/schedules",
            json={"label": "Q1", "run_id": "r1", "cron_expr": "0 9 5 * *"},
            headers=HEADERS,
        )
    assert r.status_code == 201
    assert "schedule_id" in r.json()


def test_list_schedules_success() -> None:
    with patch("apps.api.app.routers.board_pack_schedules.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get("/api/v1/board-packs/schedules", headers=HEADERS)
    assert r.status_code == 200
    assert "items" in r.json()


def test_list_history_success() -> None:
    with patch("apps.api.app.routers.board_pack_schedules.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get("/api/v1/board-packs/schedules/history", headers=HEADERS)
    assert r.status_code == 200
    assert "items" in r.json()


def test_distribute_not_found() -> None:
    with patch("apps.api.app.routers.board_pack_schedules.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.post(
            "/api/v1/board-packs/schedules/history/hist-999/distribute",
            json={"emails": ["a@b.com"]},
            headers=HEADERS,
        )
    assert r.status_code == 404


def test_distribute_success() -> None:
    def _conn_with_history(_tid: str):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={
            "history_id": "hist-1",
            "pack_id": "pk-1",
            "label": "Q1 Pack",
            "narrative_json": '{"executive_summary": "Good quarter."}',
        })
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with (
        patch("apps.api.app.routers.board_pack_schedules.tenant_conn", side_effect=_conn_with_history),
        patch(
            "apps.api.app.routers.board_pack_schedules.send_board_pack_email",
            new_callable=AsyncMock,
            return_value={"sent": False, "recipients": ["cfo@example.com"], "reason": "sendgrid_not_configured"},
        ) as mock_send,
    ):
        r = client.post(
            "/api/v1/board-packs/schedules/history/hist-1/distribute",
            json={"emails": ["cfo@example.com"]},
            headers=HEADERS,
        )
    assert r.status_code == 200
    # In dev mode (sent=False), distributed should be False
    assert r.json()["distributed"] is False
    assert r.json()["emails_sent_to"] == ["cfo@example.com"]
    mock_send.assert_called_once_with(
        ["cfo@example.com"],
        "Q1 Pack",
        {"executive_summary": "Good quarter."},
    )


def test_distribute_emails_sent_marks_distributed() -> None:
    """When SendGrid succeeds, the endpoint marks distributed=True and updates DB."""
    def _conn_with_history(_tid: str):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={
            "history_id": "hist-1",
            "pack_id": "pk-1",
            "label": "Q1 Pack",
            "narrative_json": '{"executive_summary": "Good quarter."}',
        })
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with (
        patch("apps.api.app.routers.board_pack_schedules.tenant_conn", side_effect=_conn_with_history),
        patch(
            "apps.api.app.routers.board_pack_schedules.send_board_pack_email",
            new_callable=AsyncMock,
            return_value={"sent": True, "recipients": ["cfo@example.com"]},
        ),
    ):
        r = client.post(
            "/api/v1/board-packs/schedules/history/hist-1/distribute",
            json={"emails": ["cfo@example.com"]},
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert r.json()["distributed"] is True


def test_distribute_email_failure_returns_502() -> None:
    """When SendGrid returns an error, the endpoint returns 502."""
    from apps.api.app.services.email import EmailError

    def _conn_with_history(_tid: str):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={
            "history_id": "hist-1",
            "pack_id": "pk-1",
            "label": "Q1 Pack",
            "narrative_json": None,
        })
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with (
        patch("apps.api.app.routers.board_pack_schedules.tenant_conn", side_effect=_conn_with_history),
        patch(
            "apps.api.app.routers.board_pack_schedules.send_board_pack_email",
            new_callable=AsyncMock,
            side_effect=EmailError("SendGrid returned 403: Forbidden"),
        ),
    ):
        r = client.post(
            "/api/v1/board-packs/schedules/history/hist-1/distribute",
            json={"emails": ["cfo@example.com"]},
            headers=HEADERS,
        )
    assert r.status_code == 502


def test_patch_schedule_no_fields() -> None:
    with patch("apps.api.app.routers.board_pack_schedules.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.patch(
            "/api/v1/board-packs/schedules/sch-1",
            json={},
            headers=HEADERS,
        )
    assert r.status_code == 400


def test_delete_schedule_not_found() -> None:
    def _conn_delete_0(_tid: str):
        conn = MagicMock()
        conn.execute = AsyncMock(return_value="DELETE 0")
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.board_pack_schedules.tenant_conn", side_effect=_conn_delete_0):
        r = client.delete("/api/v1/board-packs/schedules/sch-999", headers=HEADERS)
    assert r.status_code == 404


# --- compute_next_run + cron endpoint tests ---


def test_compute_next_run_valid() -> None:
    from apps.api.app.routers.board_pack_schedules import compute_next_run

    base = datetime(2026, 3, 1, 8, 0, 0, tzinfo=timezone.utc)
    result = compute_next_run("0 9 5 * *", base)
    assert result is not None
    # Should be 5th of March 2026 at 09:00 UTC
    assert result.day == 5
    assert result.hour == 9
    assert result.month == 3
    assert result.tzinfo is not None


def test_compute_next_run_invalid() -> None:
    from apps.api.app.routers.board_pack_schedules import compute_next_run

    result = compute_next_run("not a cron expr")
    assert result is None


def test_create_schedule_sets_next_run_at() -> None:
    """Creating a schedule should include next_run_at in response."""
    with patch("apps.api.app.routers.board_pack_schedules.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.post(
            "/api/v1/board-packs/schedules",
            json={"label": "Monthly", "run_id": "r1", "cron_expr": "0 9 5 * *"},
            headers=HEADERS,
        )
    assert r.status_code == 201
    data = r.json()
    assert "next_run_at" in data
    assert data["next_run_at"] is not None


def test_cron_execute_rejects_bad_secret() -> None:
    """Cron endpoint should reject requests with wrong secret."""
    with patch("apps.api.app.routers.board_pack_schedules.get_pool", return_value=None):
        with patch(
            "apps.api.app.core.settings.get_settings",
            return_value=MagicMock(cron_secret="correct-secret", database_url="postgres://localhost/test"),
        ):
            r = client.post(
                "/api/v1/board-packs/schedules/cron/execute",
                headers={"X-Cron-Secret": "wrong-secret"},
            )
    assert r.status_code == 403


def test_cron_execute_no_due_schedules() -> None:
    """Cron endpoint should succeed with 0 executed when no schedules are due."""
    mock_pool = MagicMock()
    mock_pool_conn = MagicMock()
    mock_pool_conn.fetch = AsyncMock(return_value=[{"id": "t-1"}])
    mock_pool_cm = MagicMock()
    mock_pool_cm.__aenter__ = AsyncMock(return_value=mock_pool_conn)
    mock_pool_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = mock_pool_cm

    def _tenant_conn_empty(_tid: str):
        conn = MagicMock()
        conn.fetch = AsyncMock(return_value=[])  # no due schedules
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    _setup_di()
    try:
        with (
            patch("apps.api.app.routers.board_pack_schedules.get_pool", return_value=mock_pool),
            patch("apps.api.app.routers.board_pack_schedules.tenant_conn", side_effect=_tenant_conn_empty),
            patch(
                "apps.api.app.core.settings.get_settings",
                return_value=MagicMock(cron_secret=None, database_url="postgres://localhost/test"),
            ),
        ):
            r = client.post("/api/v1/board-packs/schedules/cron/execute")
    finally:
        _cleanup()
    assert r.status_code == 200
    data = r.json()
    assert data["executed"] == 0
    assert data["checked_tenants"] == 1


def test_cron_execute_runs_due_schedule() -> None:
    """Cron endpoint executes a due schedule: generates pack, records history, advances next_run_at."""
    import json as json_mod

    mock_pool = MagicMock()
    mock_pool_conn = MagicMock()
    mock_pool_conn.fetch = AsyncMock(return_value=[{"id": "t-1"}])
    mock_pool_cm = MagicMock()
    mock_pool_cm.__aenter__ = AsyncMock(return_value=mock_pool_conn)
    mock_pool_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = mock_pool_cm

    due_schedule = {
        "schedule_id": "sch-abc",
        "label": "Monthly Pack",
        "run_id": "run-1",
        "budget_id": None,
        "section_order": json_mod.dumps(["executive_summary", "financial_overview"]),
        "cron_expr": "0 9 5 * *",
        "distribution_emails": ["cfo@example.com"],
        "created_by": "user-1",
    }

    call_count = 0

    def _tenant_conn_with_schedule(_tid: str):
        nonlocal call_count
        call_count += 1
        conn = MagicMock()
        if call_count == 1:
            # First call: return due schedules
            conn.fetch = AsyncMock(return_value=[due_schedule])
        else:
            # Subsequent calls: history insert, email fetch, updates
            conn.fetch = AsyncMock(return_value=[])
            conn.fetchrow = AsyncMock(return_value={"narrative_json": '{"summary": "ok"}'})
            conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    _setup_di()
    try:
        with (
            patch("apps.api.app.routers.board_pack_schedules.get_pool", return_value=mock_pool),
            patch("apps.api.app.routers.board_pack_schedules.tenant_conn", side_effect=_tenant_conn_with_schedule),
            patch(
                "apps.api.app.core.settings.get_settings",
                return_value=MagicMock(cron_secret=None, database_url="postgres://localhost/test"),
            ),
            patch(
                "apps.api.app.routers.board_pack_schedules.create_board_pack_impl",
                new_callable=AsyncMock,
                return_value={"pack_id": "pk-cron-1"},
            ) as mock_create,
            patch(
                "apps.api.app.routers.board_pack_schedules.generate_board_pack_impl",
                new_callable=AsyncMock,
            ) as mock_gen,
            patch(
                "apps.api.app.routers.board_pack_schedules.send_board_pack_email",
                new_callable=AsyncMock,
                return_value={"sent": True, "recipients": ["cfo@example.com"]},
            ) as mock_email,
        ):
            r = client.post("/api/v1/board-packs/schedules/cron/execute")
    finally:
        _cleanup()

    assert r.status_code == 200
    data = r.json()
    assert data["executed"] == 1
    assert data["errors"] == 0
    mock_create.assert_called_once()
    mock_gen.assert_called_once()
    mock_email.assert_called_once()
