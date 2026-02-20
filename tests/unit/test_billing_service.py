from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.api.app.core.settings import Settings
from apps.api.app.main import app
from apps.api.app.services.billing import BillingService

client = TestClient(app)


def _async_cm(conn: MagicMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.asyncio
async def test_get_plans() -> None:
    conn = MagicMock()
    plans = [{"plan_id": "plan_starter"}]
    with patch("apps.api.app.services.billing.service.tenant_conn", return_value=_async_cm(conn)):
        with patch(
            "apps.api.app.services.billing.service.get_plans",
            new_callable=AsyncMock,
            return_value=plans,
        ) as mock_get_plans:
            service = BillingService()
            result = await service.get_plans()
    assert result == plans
    mock_get_plans.assert_awaited_once_with(conn)


@pytest.mark.asyncio
async def test_create_subscription() -> None:
    conn = MagicMock()
    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=None)
    txn.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=txn)

    with patch("apps.api.app.services.billing.service.tenant_conn", return_value=_async_cm(conn)):
        with patch(
            "apps.api.app.services.billing.service.ensure_tenant",
            new_callable=AsyncMock,
        ) as mock_ensure:
            with patch(
                "apps.api.app.services.billing.service.get_plan_by_id",
                new_callable=AsyncMock,
                return_value={"plan_id": "plan_starter"},
            ):
                with patch(
                    "apps.api.app.services.billing.service.db_create_subscription",
                    new_callable=AsyncMock,
                ) as mock_create:
                    with patch.object(
                        BillingService,
                        "get_subscription",
                        new_callable=AsyncMock,
                        return_value={"subscription_id": "sub_1"},
                    ):
                        service = BillingService()
                        result = await service.create_subscription("t1", "plan_starter")
    assert result["subscription_id"] == "sub_1"
    mock_ensure.assert_awaited()
    mock_create.assert_awaited()


@pytest.mark.asyncio
async def test_cancel_subscription() -> None:
    conn = MagicMock()
    with patch("apps.api.app.services.billing.service.tenant_conn", return_value=_async_cm(conn)):
        with patch(
            "apps.api.app.services.billing.service.db_get_subscription",
            new_callable=AsyncMock,
            return_value={"subscription_id": "sub_1"},
        ):
            with patch(
                "apps.api.app.services.billing.service.db_cancel_subscription",
                new_callable=AsyncMock,
            ) as mock_cancel:
                service = BillingService()
                result = await service.cancel_subscription("t1")
    assert result is True
    mock_cancel.assert_awaited()


@pytest.mark.asyncio
async def test_get_usage() -> None:
    conn = MagicMock()
    usage = {"period": "2026-02", "usage": {"llm_calls": 1}}
    with patch("apps.api.app.services.billing.service.tenant_conn", return_value=_async_cm(conn)):
        with patch(
            "apps.api.app.services.billing.service.get_usage_meter",
            new_callable=AsyncMock,
            return_value=usage,
        ) as mock_get_usage:
            service = BillingService()
            result = await service.get_usage("t1", period="2026-02")
    assert result == usage
    mock_get_usage.assert_awaited_once_with(conn, "t1", "2026-02")


def test_stripe_webhook_valid_signature() -> None:
    settings = Settings(STRIPE_WEBHOOK_SECRET="whsec_test", ENVIRONMENT="test")
    event = MagicMock()
    event.type = "subscription.updated"
    event.data.object = {"id": "sub_123", "status": "active"}

    def _mock_tenant_conn(_: str):
        return _async_cm(MagicMock())

    with patch("apps.api.app.core.settings.get_settings", return_value=settings):
        with patch("stripe.Webhook.construct_event", return_value=event):
            with patch("apps.api.app.routers.billing.tenant_conn", side_effect=_mock_tenant_conn):
                with patch(
                    "apps.api.app.db.billing.get_tenant_by_stripe_subscription_id",
                    new_callable=AsyncMock,
                    return_value=("t1", "sub_123"),
                ):
                    with patch(
                        "apps.api.app.db.billing.update_subscription_status",
                        new_callable=AsyncMock,
                    ) as mock_update:
                        r = client.post(
                            "/api/v1/billing/webhook",
                            data=b"{}",
                            headers={"stripe-signature": "sig"},
                        )
    assert r.status_code == 200
    mock_update.assert_awaited()


def test_stripe_webhook_invalid_signature_returns_400() -> None:
    settings = Settings(STRIPE_WEBHOOK_SECRET="whsec_test", ENVIRONMENT="test")
    with patch("apps.api.app.core.settings.get_settings", return_value=settings):
        with patch("stripe.Webhook.construct_event", side_effect=Exception("bad sig")):
            r = client.post(
                "/api/v1/billing/webhook",
                data=b"{}",
                headers={"stripe-signature": "sig"},
            )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_usage_recording_atomic_increment() -> None:
    conn = MagicMock()
    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=None)
    txn.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=txn)
    conn.fetchrow = AsyncMock(side_effect=[
        None,
        {"usage_json": {"llm_calls": 0, "llm_tokens_total": 0, "llm_tokens_by_provider": {}, "llm_tokens_by_task": {}, "mc_runs": 0, "sync_events": 0},
         "costs_json": {"currency": "USD", "llm_estimated_cents": 0}},
    ])
    conn.execute = AsyncMock()

    with patch("apps.api.app.services.billing.service.tenant_conn", return_value=_async_cm(conn)):
        with patch(
            "apps.api.app.services.billing.service.ensure_tenant",
            new_callable=AsyncMock,
        ):
            with patch(
                "apps.api.app.services.billing.service.replace_usage_meter",
                new_callable=AsyncMock,
            ) as mock_replace:
                with patch(
                    "apps.api.app.services.billing.service.insert_llm_call_log",
                    new_callable=AsyncMock,
                ) as mock_insert:
                    service = BillingService()
                    await service.record_llm_usage(
                        "t1",
                        tokens=100,
                        cost_estimate_usd=0.5,
                        task_label="draft_assumptions",
                        provider="openai",
                        model="gpt-4o-mini",
                        tokens_json={"prompt": 50, "completion": 50, "total": 100},
                        latency_ms=123,
                        call_id="call_1",
                        correlation_json={"req_id": "r1"},
                    )

    first_query = conn.fetchrow.call_args_list[0][0][0]
    assert "FOR UPDATE" in first_query
    # ON CONFLICT is inside replace_usage_meter (mocked); verify the mock was called instead
    mock_replace.assert_awaited()
    mock_insert.assert_awaited()
