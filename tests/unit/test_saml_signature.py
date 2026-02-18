"""Tests for SAML ACS: signature verification, tenant resolution, and error paths (FIX-C01, FIX-C02).

Note: TestClient(app) is created per test via the client fixture. If app startup performs DB
access, these tests may require a running DB or mocked dependencies (L-10).
Auth SAML uses get_pool() and tenant_conn() (no get_conn); tests patch those.
"""

from __future__ import annotations

import base64
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import app


@pytest.fixture
def client() -> TestClient:
    """Per-test TestClient so app lifecycle is isolated; may require DB if app startup connects."""
    return TestClient(app)


def _minimal_saml_response_xml(entity_id: str = "https://idp.example.com/entity") -> bytes:
    """Minimal SAML 2.0 Response with Issuer (no signature, for tests that expect 400)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
  xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
  <saml:Issuer>{entity_id}</saml:Issuer>
  <samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>
  <saml:Assertion>
    <saml:Subject><saml:NameID>user@example.com</saml:NameID></saml:Subject>
    <saml:AttributeStatement>
      <saml:Attribute Name="email"><saml:AttributeValue>user@example.com</saml:AttributeValue></saml:Attribute>
    </saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>""".encode()


def test_acs_missing_saml_response_returns_400(client: TestClient) -> None:
    """POST /auth/saml/acs without SAMLResponse returns 400."""
    r = client.post("/api/v1/auth/saml/acs", data={})
    assert r.status_code == 400


def test_acs_invalid_base64_returns_400(client: TestClient) -> None:
    """POST /auth/saml/acs with invalid base64 returns 400."""
    r = client.post("/api/v1/auth/saml/acs", data={"SAMLResponse": "not-valid-base64!!"})
    assert r.status_code == 400


def test_acs_no_issuer_returns_400(client: TestClient) -> None:
    """SAML response with no Issuer returns 400 (FIX-C02: cannot resolve tenant)."""
    xml = b'<?xml version="1.0"?><samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"/>'
    r = client.post(
        "/api/v1/auth/saml/acs",
        data={"SAMLResponse": base64.b64encode(xml).decode()},
    )
    assert r.status_code == 400


def test_acs_entity_id_not_mapped_returns_400(client: TestClient) -> None:
    """When entity_id lookup returns no tenant, return 400 — never use RelayState (FIX-C02)."""
    raw = _minimal_saml_response_xml(entity_id="https://unknown-idp.example/entity")
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)  # no tenant for this entity_id
    pool = MagicMock()
    pool.acquire = AsyncMock(return_value=conn)
    pool.release = AsyncMock()
    with patch("apps.api.app.routers.auth_saml.get_pool", return_value=pool):
        r = client.post(
            "/api/v1/auth/saml/acs",
            data={"SAMLResponse": base64.b64encode(raw).decode()},
        )
    assert r.status_code == 400
    conn.fetchval.assert_called_once()


def test_acs_production_requires_idp_certificate(client: TestClient) -> None:
    """In production, missing idp_certificate returns 400 (FIX-C01)."""
    raw = _minimal_saml_response_xml()
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value="tenant-1")
    conn.fetchrow = AsyncMock(return_value={"idp_certificate": None, "attribute_mapping_json": {}})
    conn.execute = AsyncMock()
    pool = MagicMock()
    pool.acquire = AsyncMock(return_value=conn)
    pool.release = AsyncMock()

    @asynccontextmanager
    async def mock_tenant_conn(_tid: str):
        yield conn

    with patch("apps.api.app.routers.auth_saml.get_pool", return_value=pool):
        with patch("apps.api.app.routers.auth_saml.tenant_conn", side_effect=mock_tenant_conn):
            with patch("apps.api.app.routers.auth_saml.get_settings") as settings_mock:
                settings_mock.return_value.environment = "production"
                settings_mock.return_value.supabase_jwt_secret = None
                r = client.post(
                    "/api/v1/auth/saml/acs",
                    data={"SAMLResponse": base64.b64encode(raw).decode()},
                )
    assert r.status_code == 400


def test_acs_invalid_signature_returns_400(client: TestClient) -> None:
    """When signature verification fails, return 400 (FIX-C01)."""
    pytest.importorskip("signxml")
    raw = _minimal_saml_response_xml()
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value="tenant-1")
    conn.fetchrow = AsyncMock(
        return_value={
            "idp_certificate": "-----BEGIN CERTIFICATE-----\nMOCK\n-----END CERTIFICATE-----",
            "attribute_mapping_json": {},
        }
    )
    conn.execute = AsyncMock()
    pool = MagicMock()
    pool.acquire = AsyncMock(return_value=conn)
    pool.release = AsyncMock()

    @asynccontextmanager
    async def mock_tenant_conn(_tid: str):
        yield conn

    with patch("apps.api.app.routers.auth_saml.get_pool", return_value=pool):
        with patch("apps.api.app.routers.auth_saml.tenant_conn", side_effect=mock_tenant_conn):
            with patch("apps.api.app.routers.auth_saml.get_settings") as settings_mock:
                settings_mock.return_value.environment = "production"
                with patch("apps.api.app.routers.auth_saml.XMLVerifier") as verifier_mock:
                    from signxml.exceptions import InvalidSignature
                    verifier_mock.return_value.verify.side_effect = InvalidSignature("bad signature")
                    r = client.post(
                        "/api/v1/auth/saml/acs",
                        data={"SAMLResponse": base64.b64encode(raw).decode()},
                    )
    assert r.status_code == 400
