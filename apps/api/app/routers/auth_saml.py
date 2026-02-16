"""VA-P8-02: SSO/SAML — tenant IdP config, login redirect, ACS callback (create/link user, issue JWT)."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
import zlib
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
import structlog

from apps.api.app.core.settings import get_settings
from apps.api.app.db import ensure_tenant, tenant_conn
from apps.api.app.db.connection import get_conn
from apps.api.app.deps import require_role, ROLES_OWNER_OR_ADMIN

logger = structlog.get_logger()
router = APIRouter(prefix="/auth/saml", tags=["auth-saml"])

SAML_TOKEN_LIFETIME_SECONDS = 3600  # 1 hour

NS = {"saml": "urn:oasis:names:tc:SAML:2.0:assertion", "samlp": "urn:oasis:names:tc:SAML:2.0:protocol"}


class SamlConfigBody(BaseModel):
    idp_metadata_url: str | None = None
    idp_metadata_xml: str | None = None
    entity_id: str = Field(..., min_length=1)
    acs_url: str = Field(..., min_length=1)
    idp_sso_url: str | None = None
    attribute_mapping: dict[str, str] = Field(default_factory=dict, description="IdP attribute name -> tenant_id | email | name")


@router.get("/login")
async def saml_login(
    tenant_id: str = Query(..., alias="tenant"),
) -> RedirectResponse:
    """Redirect user to IdP for SAML login (VA-P8-02). Client calls with ?tenant=."""
    conn = await get_conn()
    try:
        await conn.execute("SET app.tenant_id = $1", tenant_id)
        row = await conn.fetchrow(
            "SELECT idp_sso_url, entity_id, acs_url FROM tenant_saml_config WHERE tenant_id = $1",
            tenant_id,
        )
    finally:
        await conn.close()
    if not row or not row["idp_sso_url"]:
        raise HTTPException(404, "SAML not configured for this tenant")
    # Build minimal AuthnRequest (SAML 2.0)
    acs_url = row["acs_url"]
    entity_id = row["entity_id"]
    req_id = f"_{uuid.uuid4().hex}"
    authn_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
  ID="{req_id}" Version="2.0" IssueInstant="{datetime.now(UTC).isoformat()}"
  AssertionConsumerServiceURL="{acs_url}" ProviderName="Virtual Analyst">
  <saml:Issuer>{entity_id}</saml:Issuer>
</samlp:AuthnRequest>"""
    # R11-09: DEFLATE compress, base64 encode, URL encode (SAML HTTP-Redirect binding)
    deflated = zlib.compress(authn_request.encode())[2:-4]  # strip zlib header/checksum
    saml_request_b64 = base64.b64encode(deflated).decode()
    idp_url = row["idp_sso_url"]
    sep = "&" if "?" in idp_url else "?"
    return RedirectResponse(
        url=f"{idp_url}{sep}SAMLRequest={quote(saml_request_b64)}&RelayState={quote(tenant_id)}",
    )


@router.post("/acs")
async def saml_acs(
    request: Request,
) -> RedirectResponse:
    """SAML ACS: IdP POSTs SAMLResponse here. Parse, create/link user, issue JWT, redirect (VA-P8-02)."""
    form = await request.form()
    saml_response_b64 = form.get("SAMLResponse")
    relay_state = form.get("RelayState", "").strip()
    if not saml_response_b64:
        raise HTTPException(400, "Missing SAMLResponse")
    tenant_id = relay_state or None
    try:
        raw = base64.b64decode(saml_response_b64)
        root = ET.fromstring(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except Exception as e:
        raise HTTPException(400, f"Invalid SAML response: {e}") from e
    # R11-01: Reject unsigned SAML in production until IdP signature verification is implemented
    # TODO(VA-P8-02): Integrate signxml or python3-saml to verify the IdP's XML signature
    # against the certificate from tenant_saml_config.
    settings = get_settings()
    if settings.environment not in ("development", "test"):
        raise HTTPException(
            501,
            "SAML signature verification not yet implemented; "
            "SSO is disabled in production until IdP signature validation is added.",
        )
    logger.warning("saml_acs_no_signature_verification", tenant_id=relay_state or "unknown")
    # Extract NameID and attributes from first Assertion
    assertion = root.find(".//saml:Assertion", NS) or root.find(".//{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
    if assertion is None:
        raise HTTPException(400, "No Assertion in SAML response")
    name_id_el = assertion.find(".//saml:NameID", NS) or assertion.find(".//{urn:oasis:names:tc:SAML:2.0:assertion}NameID")
    name_id = name_id_el.text if name_id_el is not None and name_id_el.text else None
    attrs: dict[str, str] = {}
    for attr in assertion.findall(".//saml:Attribute", NS) or assertion.findall(".//{urn:oasis:names:tc:SAML:2.0:assertion}Attribute"):
        name = attr.get("Name")
        val_el = attr.find(".//saml:AttributeValue", NS) or attr.find(".//{urn:oasis:names:tc:SAML:2.0:assertion}AttributeValue")
        if name and val_el is not None and val_el.text:
            attrs[name] = val_el.text
    if not name_id and not attrs:
        raise HTTPException(400, "No NameID or attributes in Assertion")
    # Resolve tenant_id from config (if not in RelayState) via entity_id in response (R11-10: security-definer)
    conn = await get_conn()
    try:
        if not tenant_id:
            issuer = root.find(".//saml:Issuer", NS) or root.find(".//{urn:oasis:names:tc:SAML:2.0:assertion}Issuer")
            entity_id_val = issuer.text if issuer is not None and issuer.text else None
            if entity_id_val:
                resolved = await conn.fetchval(
                    "SELECT lookup_saml_tenant_by_entity_id($1)",
                    entity_id_val,
                )
                if resolved:
                    tenant_id = resolved
        if not tenant_id:
            raise HTTPException(400, "Could not determine tenant (set RelayState or configure entity_id)")
        await conn.execute("SET app.tenant_id = $1", tenant_id)
        await ensure_tenant(conn, tenant_id)
        cfg = await conn.fetchrow(
            "SELECT attribute_mapping_json FROM tenant_saml_config WHERE tenant_id = $1",
            tenant_id,
        )
        mapping = (cfg["attribute_mapping_json"] or {}) if cfg else {}
        tenant_from_attr = mapping.get("tenant_id")
        email_attr = mapping.get("email", "email")
        name_attr = mapping.get("name", "name")
        tenant_id = attrs.get(tenant_from_attr, tenant_id) if tenant_from_attr else tenant_id
        email = attrs.get(email_attr) or name_id
        name = attrs.get(name_attr) or ""
        # R11-02: Derive SAML-scoped user ID; never use attacker-controlled value as PK or overwrite tenant_id
        raw_name_id = name_id or attrs.get("email") or attrs.get("sub") or ""
        if not raw_name_id:
            raise HTTPException(400, "No NameID, email, or sub in SAML assertion")
        user_id = "saml_" + hashlib.sha256(
            f"{tenant_id}:{raw_name_id}".encode(),
        ).hexdigest()[:24]
        await conn.execute(
            """INSERT INTO users (id, tenant_id, email, role) VALUES ($1, $2, $3, 'analyst')
               ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email""",
            user_id,
            tenant_id,
            email,
        )
    finally:
        await conn.close()
    settings = get_settings()
    if not settings.supabase_jwt_secret:
        raise HTTPException(503, "SAML requires SUPABASE_JWT_SECRET for issuing tokens")
    try:
        from jose import jwt as jose_jwt
    except ImportError:
        raise HTTPException(503, "SAML requires python-jose for issuing tokens")
    # R11-04: JWT must include exp and iat so tokens expire
    now = datetime.now(UTC)
    token = jose_jwt.encode(
        {
            "sub": user_id,
            "app_metadata": {"tenant_id": tenant_id},
            "aud": "va-saml",
            "email": email,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=SAML_TOKEN_LIFETIME_SECONDS)).timestamp()),
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    frontend_url = getattr(settings, "integration_callback_base_url", "http://localhost:3000")
    return RedirectResponse(url=f"{frontend_url}/auth/callback?token={token}&tenant_id={tenant_id}", status_code=302)


# Config API (admin): get/put SAML config for tenant (requires auth)
@router.get("/config")
async def get_saml_config(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_role(*ROLES_OWNER_OR_ADMIN)),
) -> dict[str, Any]:
    """Get SAML config for current tenant (if configured)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT entity_id, acs_url, idp_sso_url, attribute_mapping_json FROM tenant_saml_config WHERE tenant_id = $1",
            x_tenant_id,
        )
    if not row:
        return {"configured": False}
    return {
        "configured": True,
        "entity_id": row["entity_id"],
        "acs_url": row["acs_url"],
        "idp_sso_url": row["idp_sso_url"],
        "attribute_mapping": row["attribute_mapping_json"] or {},
    }


@router.put("/config")
async def put_saml_config(
    body: SamlConfigBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    _: None = Depends(require_role(*ROLES_OWNER_OR_ADMIN)),
) -> dict[str, Any]:
    """Create or update SAML config for tenant (VA-P8-02)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if not body.idp_metadata_url and not body.idp_metadata_xml and not body.idp_sso_url:
        raise HTTPException(400, "Provide idp_metadata_url, idp_metadata_xml, or idp_sso_url")
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO tenant_saml_config (tenant_id, idp_metadata_url, idp_metadata_xml, entity_id, acs_url, idp_sso_url, attribute_mapping_json, updated_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, now())
               ON CONFLICT (tenant_id) DO UPDATE SET
                 idp_metadata_url = COALESCE(EXCLUDED.idp_metadata_url, tenant_saml_config.idp_metadata_url),
                 idp_metadata_xml = COALESCE(EXCLUDED.idp_metadata_xml, tenant_saml_config.idp_metadata_xml),
                 entity_id = EXCLUDED.entity_id, acs_url = EXCLUDED.acs_url, idp_sso_url = COALESCE(EXCLUDED.idp_sso_url, tenant_saml_config.idp_sso_url),
                 attribute_mapping_json = EXCLUDED.attribute_mapping_json, updated_at = now()""",
            x_tenant_id,
            body.idp_metadata_url,
            body.idp_metadata_xml,
            body.entity_id,
            body.acs_url,
            body.idp_sso_url,
            json.dumps(body.attribute_mapping),
        )
    return {"ok": True}