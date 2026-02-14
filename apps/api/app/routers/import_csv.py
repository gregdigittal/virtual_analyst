"""CSV import (VA-P4-05): upload CSV, map columns to refs, create draft + scenario."""

from __future__ import annotations

import csv
import io
import json as _json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, UploadFile

from apps.api.app.db import ensure_tenant, tenant_conn
from apps.api.app.db.audit import EVENT_DRAFT_CREATED, create_audit_event
from apps.api.app.deps import get_artifact_store
from apps.api.app.routers.drafts import (
    DRAFT_WORKSPACE_TYPE,
    STATUS_ACTIVE,
    _empty_workspace,
)
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/import", tags=["import"])

# Max CSV size 2MB
MAX_CSV_BYTES = 2 * 1024 * 1024


def _parse_csv_to_overrides(
    content: bytes,
    column_mapping: dict[str, str],
    use_first_data_row: bool,
) -> list[dict[str, Any]]:
    """Parse CSV and return list of {ref, field, value}. Uses first data row if use_first_data_row."""
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []
    row = rows[0] if use_first_data_row else rows[-1]
    overrides: list[dict[str, Any]] = []
    for col_key, ref in column_mapping.items():
        if not ref:
            continue
        # Support column name or 0-based index
        if col_key.isdigit():
            idx = int(col_key)
            keys = list(row.keys())
            if idx < len(keys):
                val = row.get(keys[idx], "")
            else:
                continue
        else:
            val = row.get(col_key, "")
        try:
            num = float(val.replace(",", "").strip())
        except (ValueError, AttributeError):
            continue
        overrides.append({"ref": ref, "field": "value", "value": num})
    return overrides


def _infer_mapping_from_header(reader: csv.DictReader) -> dict[str, str]:
    """Build column_mapping from header: column name -> drv:csv_<sanitized>."""
    keys = reader.fieldnames or []
    mapping: dict[str, str] = {}
    for i, k in enumerate(keys):
        safe = "".join(c if c.isalnum() or c == "_" else "_" for c in (k or "").strip())[:30] or f"col_{i}"
        mapping[k] = f"drv:csv_{safe}"
    return mapping


@router.post("/csv", status_code=201)
async def import_csv(
    file: UploadFile,
    parent_baseline_id: str,
    parent_baseline_version: str = "v1",
    label: str = "CSV Import",
    column_mapping: str | None = Query(None, description="JSON: column name or index -> model ref"),
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """
    Upload CSV and create a draft + scenario. Map columns via column_mapping (JSON).
    If omitted, header columns are mapped to drv:csv_<sanitized_name>.
    """
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Upload a CSV file")

    content = await file.read()
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(400, f"CSV too large (max {MAX_CSV_BYTES // 1024}KB)")

    mapping: dict[str, str] = {}
    if column_mapping:
        try:
            mapping = _json.loads(column_mapping)
            if not isinstance(mapping, dict):
                mapping = {}
        except Exception as e:
            raise HTTPException(400, "column_mapping must be a JSON object") from e

    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not mapping and reader.fieldnames:
        mapping = _infer_mapping_from_header(reader)
    if not mapping:
        raise HTTPException(400, "CSV has no columns; provide column_mapping or use CSV with header row")

    overrides = _parse_csv_to_overrides(content, mapping, use_first_data_row=True)

    scenario_id = f"sc_{uuid.uuid4().hex[:12]}"
    draft_session_id = f"ds_{uuid.uuid4().hex[:12]}"
    storage_path = f"{x_tenant_id}/{DRAFT_WORKSPACE_TYPE}/{draft_session_id}.json"
    overrides_json = _json.dumps([{"ref": o["ref"], "field": o["field"], "value": o["value"]} for o in overrides])

    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            await ensure_tenant(conn, x_tenant_id)
            baseline = await conn.fetchval(
                "SELECT baseline_id FROM model_baselines WHERE tenant_id = $1 AND baseline_id = $2",
                x_tenant_id,
                parent_baseline_id,
            )
            if not baseline:
                raise HTTPException(404, f"Baseline {parent_baseline_id} not found")
            await conn.execute(
                """INSERT INTO scenarios (tenant_id, scenario_id, baseline_id, baseline_version, label, description, overrides_json)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                x_tenant_id,
                scenario_id,
                parent_baseline_id,
                parent_baseline_version,
                label or "CSV Import",
                "Created from CSV import",
                overrides_json,
            )
            workspace = _empty_workspace(
                draft_session_id, None, parent_baseline_id, parent_baseline_version
            )
            workspace["csv_import_scenario_id"] = scenario_id
            workspace["csv_import_overrides"] = overrides
            store.save(x_tenant_id, DRAFT_WORKSPACE_TYPE, draft_session_id, workspace)
            await conn.execute(
                """INSERT INTO draft_sessions (tenant_id, draft_session_id, parent_baseline_id, parent_baseline_version, status, storage_path, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                x_tenant_id,
                draft_session_id,
                parent_baseline_id,
                parent_baseline_version,
                STATUS_ACTIVE,
                storage_path,
                x_user_id or None,
            )
            await create_audit_event(
                conn,
                x_tenant_id,
                EVENT_DRAFT_CREATED,
                "draft",
                "draft_session",
                draft_session_id,
                user_id=x_user_id or None,
                event_data={"source": "csv_import", "scenario_id": scenario_id, "overrides_count": len(overrides)},
            )

    return {
        "draft_session_id": draft_session_id,
        "scenario_id": scenario_id,
        "overrides_count": len(overrides),
        "status": STATUS_ACTIVE,
    }
