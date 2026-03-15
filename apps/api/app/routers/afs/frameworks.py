"""AFS frameworks CRUD endpoints."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_llm_router
from apps.api.app.routers.afs._common import (
    BUILTIN_FRAMEWORKS,
    VALID_STANDARDS,
    CreateDisclosureItemBody,
    CreateFrameworkBody,
    InferFrameworkBody,
    _disclosure_item_id,
    _framework_id,
    _load_schemas,
)
from apps.api.app.services.llm.router import LLMRouter

router = APIRouter()


@router.get("/frameworks")
async def list_frameworks(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List all frameworks for the tenant (built-in + custom)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            "SELECT * FROM afs_frameworks WHERE tenant_id = $1 ORDER BY is_builtin DESC, name",
            x_tenant_id,
        )
        return {"items": [dict(r) for r in rows]}


@router.post("/frameworks", status_code=201)
async def create_framework(
    body: CreateFrameworkBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a custom framework."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.standard not in VALID_STANDARDS:
        raise HTTPException(400, f"Invalid standard; must be one of {sorted(VALID_STANDARDS)}")

    fid = _framework_id()
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO afs_frameworks
               (tenant_id, framework_id, name, standard, version, jurisdiction,
                disclosure_schema_json, statement_templates_json, is_builtin, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, false, $9)
               RETURNING *""",
            x_tenant_id,
            fid,
            body.name,
            body.standard,
            body.version,
            body.jurisdiction,
            json.dumps(body.disclosure_schema_json) if body.disclosure_schema_json else None,
            json.dumps(body.statement_templates_json) if body.statement_templates_json else None,
            x_user_id or None,
        )
        return dict(row)


@router.post("/frameworks/infer")
async def infer_framework_endpoint(
    body: InferFrameworkBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Use AI to infer a custom framework from a natural-language description."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    from apps.api.app.services.afs.framework_ai import infer_framework

    result = await infer_framework(
        llm_router, tenant_id=x_tenant_id,
        description=body.description,
        jurisdiction=body.jurisdiction,
        entity_type=body.entity_type,
    )

    # Extract the parsed result
    parsed = result.content if hasattr(result, 'content') else result

    # Create the framework
    fid = _framework_id()
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO afs_frameworks
               (tenant_id, framework_id, name, standard, version, jurisdiction,
                disclosure_schema_json, statement_templates_json, is_builtin, created_by)
               VALUES ($1, $2, $3, 'custom', '1.0', $4, $5, $6, false, $7)
               RETURNING *""",
            x_tenant_id, fid,
            parsed.get("name", "Custom Framework"),
            body.jurisdiction,
            json.dumps(parsed.get("disclosure_schema")),
            json.dumps(parsed.get("statement_templates")),
            x_user_id or None,
        )

        # Seed disclosure items from suggested_items
        items_count = 0
        for item in parsed.get("suggested_items", []):
            await conn.execute(
                """INSERT INTO afs_disclosure_items
                   (tenant_id, item_id, framework_id, section, reference, description, required)
                   VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT DO NOTHING""",
                x_tenant_id, _disclosure_item_id(), fid,
                item.get("section", ""),
                item.get("reference", ""),
                item.get("description", ""),
                item.get("required", True),
            )
            items_count += 1

        result_dict = dict(row)
        result_dict["items_count"] = items_count
        return result_dict


@router.get("/frameworks/{framework_id}")
async def get_framework(
    framework_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get a single framework by ID."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM afs_frameworks WHERE tenant_id = $1 AND framework_id = $2",
            x_tenant_id,
            framework_id,
        )
        if not row:
            raise HTTPException(404, "Framework not found")
        return dict(row)


@router.get("/frameworks/{framework_id}/checklist")
async def list_disclosure_items(
    framework_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List disclosure checklist items for a framework."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            "SELECT * FROM afs_disclosure_items WHERE tenant_id = $1 AND framework_id = $2 ORDER BY section, reference",
            x_tenant_id,
            framework_id,
        )
        return {"items": [dict(r) for r in rows]}


@router.post("/frameworks/{framework_id}/items", status_code=201)
async def add_disclosure_item(
    framework_id: str,
    body: CreateDisclosureItemBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Add a disclosure checklist item to a framework."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        # Validate framework exists
        fw = await conn.fetchval(
            "SELECT framework_id FROM afs_frameworks WHERE tenant_id = $1 AND framework_id = $2",
            x_tenant_id, framework_id,
        )
        if not fw:
            raise HTTPException(404, "Framework not found")

        item_id = _disclosure_item_id()
        row = await conn.fetchrow(
            """INSERT INTO afs_disclosure_items
               (tenant_id, item_id, framework_id, section, reference, description, required, applicable_entity_types)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               RETURNING *""",
            x_tenant_id, item_id, framework_id,
            body.section, body.reference, body.description, body.required,
            body.applicable_entity_types,
        )
        return dict(row)


@router.post("/frameworks/seed")
async def seed_builtin_frameworks(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Seed the 4 built-in accounting frameworks for this tenant."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    seeded = 0
    schemas = _load_schemas()
    async with tenant_conn(x_tenant_id) as conn:
        for fw in BUILTIN_FRAMEWORKS:
            fid = _framework_id()
            result = await conn.execute(
                """INSERT INTO afs_frameworks
                   (tenant_id, framework_id, name, standard, version, jurisdiction, is_builtin, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, true, $7)
                   ON CONFLICT (tenant_id, framework_id) DO NOTHING""",
                x_tenant_id,
                fid,
                fw["name"],
                fw["standard"],
                fw["version"],
                fw["jurisdiction"],
                x_user_id or None,
            )
            # asyncpg returns "INSERT 0 1" or "INSERT 0 0"
            if result and result.endswith("1"):
                seeded += 1

                # Populate disclosure schema & statement templates from built-in data
                standard_key = fw["standard"]
                if standard_key in schemas:
                    schema_data = schemas[standard_key]
                    await conn.execute(
                        """UPDATE afs_frameworks
                           SET disclosure_schema_json = $1, statement_templates_json = $2
                           WHERE tenant_id = $3 AND framework_id = $4""",
                        json.dumps(schema_data.get("disclosure_schema")),
                        json.dumps(schema_data.get("statement_templates")),
                        x_tenant_id,
                        fid,
                    )
                    # Seed individual disclosure items for checklist tracking
                    for section in schema_data.get("disclosure_schema", {}).get("sections", []):
                        await conn.execute(
                            """INSERT INTO afs_disclosure_items
                               (tenant_id, item_id, framework_id, section, reference, description, required)
                               VALUES ($1, $2, $3, $4, $5, $6, $7)
                               ON CONFLICT DO NOTHING""",
                            x_tenant_id,
                            _disclosure_item_id(),
                            fid,
                            section["type"],
                            section.get("reference", ""),
                            section["title"],
                            section.get("required", True),
                        )

    return {"seeded": seeded, "message": f"Seeded {seeded} built-in framework(s)"}
