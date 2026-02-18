from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from defusedxml.common import DefusedXmlException
from fastapi.testclient import TestClient

from apps.api.app.main import app
from apps.api.app.routers import auth_saml
from tests.conftest import minimal_model_config_dict

client = TestClient(app)


def test_xss_in_baseline_name_rejected() -> None:
    payload = minimal_model_config_dict()
    payload["metadata"]["entity_name"] = "<script>alert(1)</script>"
    r = client.post(
        "/api/v1/baselines",
        json={"model_config": payload},
        headers={"X-Tenant-ID": "t1"},
    )
    assert r.status_code == 400


def test_sql_injection_in_query_param_safe() -> None:
    injection = "' OR 1=1 --"
    queries: list[str] = []
    params: list[tuple] = []

    async def mock_fetch(query: str, *args: object):
        queries.append(query)
        params.append(args)
        return []

    async def mock_fetchval(query: str, *args: object):
        queries.append(query)
        params.append(args)
        return 0

    def mock_tenant_conn(_: str):
        conn = MagicMock()
        conn.fetch = mock_fetch
        conn.fetchval = mock_fetchval
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.activity.tenant_conn", side_effect=mock_tenant_conn):
        r = client.get(
            "/api/v1/activity",
            headers={"X-Tenant-ID": "t1"},
            params={"resource_type": injection},
        )
    assert r.status_code == 200
    assert all(injection not in q for q in queries)
    flat_params = [p for args in params for p in args]
    assert injection in flat_params


def test_oversized_body_rejected() -> None:
    oversized = "x" * (10 * 1024 * 1024 + 1)
    r = client.post(
        "/api/v1/drafts",
        data=oversized,
        headers={"Content-Type": "application/json", "X-Tenant-ID": "t1"},
    )
    assert r.status_code == 413


def test_saml_xxe_blocked() -> None:
    malicious = """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<foo>&xxe;</foo>"""
    with pytest.raises(DefusedXmlException):
        auth_saml.ET.fromstring(malicious)
