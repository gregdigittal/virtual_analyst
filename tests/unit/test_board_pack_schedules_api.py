"""H-01: Board pack schedules API tests — CRUD, run-now, distribute, history."""
from __future__ import annotations

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
