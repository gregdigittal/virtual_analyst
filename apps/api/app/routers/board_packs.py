"""Board pack composer API (VA-P7-07): create, list, get, generate narrative from run/budget data. VA-P8-01: currency toggle on export."""

from __future__ import annotations

import copy
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.db.budgets import get_budget
from apps.api.app.deps import get_artifact_store, get_llm_router, require_role, ROLES_CAN_WRITE
from apps.api.app.services.board_pack_export import (
    build_board_pack_html,
    build_board_pack_pptx,
    html_to_pdf,
)
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.errors import LLMError, StorageError
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/board-packs", tags=["board-packs"], dependencies=[require_role(*ROLES_CAN_WRITE)])

DEFAULT_SECTION_ORDER = [
    "executive_summary",
    "income_statement",
    "balance_sheet",
    "cash_flow",
    "budget_variance",
    "kpi_dashboard",
    "scenario_comparison",
    "strategic_commentary",
]

BOARD_PACK_NARRATIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string", "description": "Factual executive summary based only on the provided data"},
        "strategic_commentary": {"type": "string", "description": "Factual strategic commentary; no speculation or unsourced claims"},
    },
    "required": ["executive_summary", "strategic_commentary"],
    "additionalProperties": False,
}


class CreateBoardPackBody(BaseModel):
    label: str = Field(..., description="Display label for the pack")
    run_id: str = Field(..., description="Source run ID for statements and KPIs")
    budget_id: str | None = Field(default=None, description="Optional budget ID for variance section")
    section_order: list[str] | None = Field(default=None, description="Section keys in display order; default all sections")
    branding_json: dict[str, Any] | None = Field(default=None, description="Optional branding for export: logo_url, primary_color, terms_footer (Phase 10)")


async def create_board_pack_impl(
    tenant_id: str,
    user_id: str | None,
    label: str,
    run_id: str,
    budget_id: str | None = None,
    section_order: list[str] | None = None,
    branding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Internal: create draft board pack; returns dict with pack_id, label, run_id, budget_id, section_order, branding_json, status."""
    pack_id = f"pack_{uuid.uuid4().hex[:12]}"
    so = section_order if section_order is not None else DEFAULT_SECTION_ORDER
    br = branding if branding is not None else {}
    async with tenant_conn(tenant_id) as conn:
        await conn.execute(
            """INSERT INTO board_packs (tenant_id, pack_id, label, run_id, budget_id, section_order, status, branding_json, created_by)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, 'draft', $7::jsonb, $8)""",
            tenant_id,
            pack_id,
            label,
            run_id,
            budget_id,
            json.dumps(so),
            json.dumps(br),
            user_id,
        )
    return {
        "pack_id": pack_id,
        "label": label,
        "run_id": run_id,
        "budget_id": budget_id,
        "section_order": so,
        "branding_json": br,
        "status": "draft",
    }


@router.post("", status_code=201)
async def create_board_pack(
    body: CreateBoardPackBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a draft board pack linked to a run (and optionally a budget). VA-P7-07."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    return await create_board_pack_impl(
        x_tenant_id,
        x_user_id or None,
        body.label,
        body.run_id,
        body.budget_id,
        body.section_order,
        body.branding_json,
    )


@router.get("")
async def list_board_packs(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    status: str | None = None,
) -> dict[str, Any]:
    """List board packs for the tenant, optionally filtered by status."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        if status:
            rows = await conn.fetch(
                """SELECT pack_id, label, run_id, budget_id, section_order, status, branding_json, created_at
                   FROM board_packs WHERE tenant_id = $1 AND status = $2 ORDER BY created_at DESC""",
                x_tenant_id,
                status,
            )
        else:
            rows = await conn.fetch(
                """SELECT pack_id, label, run_id, budget_id, section_order, status, branding_json, created_at
                   FROM board_packs WHERE tenant_id = $1 ORDER BY created_at DESC""",
                x_tenant_id,
            )
    items = []
    for r in rows:
        so = r["section_order"]
        if so is not None and not isinstance(so, list):
            so = json.loads(so) if isinstance(so, str) else list(so)
        br = r.get("branding_json")
        if br is not None and isinstance(br, str):
            br = json.loads(br) if br else {}
        items.append({
            "pack_id": r["pack_id"],
            "label": r["label"],
            "run_id": r["run_id"],
            "budget_id": r["budget_id"],
            "section_order": so or DEFAULT_SECTION_ORDER,
            "status": r["status"],
            "branding_json": br if br is not None else {},
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        })
    return {"items": items}


@router.get("/{pack_id}")
async def get_board_pack(
    pack_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get a single board pack by pack_id."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT pack_id, label, run_id, budget_id, section_order, status, narrative_json, error_message, branding_json, created_at
               FROM board_packs WHERE tenant_id = $1 AND pack_id = $2""",
            x_tenant_id,
            pack_id,
        )
    if not row:
        raise HTTPException(404, "Board pack not found")
    so = row["section_order"]
    if so is not None and not isinstance(so, list):
        so = json.loads(so) if isinstance(so, str) else list(so)
    nar = row["narrative_json"]
    if nar is not None and isinstance(nar, str):
        nar = json.loads(nar) if nar else {}
    br = row.get("branding_json")
    if br is not None and isinstance(br, str):
        br = json.loads(br) if br else {}
    return {
        "pack_id": row["pack_id"],
        "label": row["label"],
        "run_id": row["run_id"],
        "budget_id": row["budget_id"],
        "section_order": so or DEFAULT_SECTION_ORDER,
        "status": row["status"],
        "narrative_json": nar or {},
        "error_message": row["error_message"],
        "branding_json": br if br is not None else {},
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


async def _fetch_budget_variance_summary(tenant_id: str, budget_id: str) -> str:
    """Fetch budget vs actual variance and return a short factual summary for the LLM. Returns empty string on error or no data."""
    materiality_pct = 5.0
    async with tenant_conn(tenant_id) as conn:
        row = await get_budget(conn, tenant_id, budget_id)
        if not row:
            return "Budget not found."
        vid = row.get("current_version_id")
        if not vid:
            return "Budget has no current version; variance N/A."
        budget_rows = await conn.fetch(
            """SELECT bli.account_ref, blia.period_ordinal, blia.amount AS budget_amount
               FROM budget_line_items bli
               JOIN budget_line_item_amounts blia ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
               WHERE bli.tenant_id = $1 AND bli.budget_id = $2 AND bli.version_id = $3""",
            tenant_id,
            budget_id,
            vid,
        )
        actual_rows = await conn.fetch(
            """SELECT period_ordinal, account_ref, SUM(amount) AS actual_amount
               FROM budget_actuals WHERE tenant_id = $1 AND budget_id = $2
               GROUP BY period_ordinal, account_ref""",
            tenant_id,
            budget_id,
        )
        budget_by_key: dict[tuple[str, int], float] = {}
        for r in budget_rows:
            budget_by_key[(r["account_ref"], r["period_ordinal"])] = float(r["budget_amount"])
        actual_by_key: dict[tuple[str, int], float] = {}
        for r in actual_rows:
            actual_by_key[(r["account_ref"], r["period_ordinal"])] = float(r["actual_amount"])
        if not budget_by_key and not actual_by_key:
            return "No budget amounts or actuals; variance N/A."
        all_keys = sorted(set(budget_by_key.keys()) | set(actual_by_key.keys()))
        material: list[str] = []
        for (acc, per) in all_keys:
            bud = budget_by_key.get((acc, per), 0.0)
            act = actual_by_key.get((acc, per), 0.0)
            var_abs = act - bud
            var_pct = (var_abs / bud * 100.0) if bud != 0 else (100.0 if var_abs != 0 else 0.0)
            if abs(var_pct) >= materiality_pct:
                material.append(f"  {acc} P{per}: budget={bud:.2f}, actual={act:.2f}, variance={var_abs:.2f} ({var_pct:+.1f}%)")
        if not material:
            return "No material variances (all within 5%)."
        return "Material variances (>=5%):\n" + "\n".join(material[:20])


def _assemble_facts_for_narrative(
    statements: dict[str, Any],
    kpis: list[dict[str, Any]],
    run_id: str,
    budget_summary: str | None,
) -> str:
    """Build a factual text blob for the LLM (executive summary + strategic commentary)."""
    parts = [f"Run ID: {run_id}\n"]
    is_list = statements.get("income_statement") or []
    bs_list = statements.get("balance_sheet") or []
    cf_list = statements.get("cash_flow") or []
    periods = statements.get("periods") or [f"P{i}" for i in range(max(len(is_list), len(bs_list), len(cf_list), 1))]
    parts.append("Periods: " + ", ".join(periods) + "\n")
    if is_list:
        parts.append("Income statement (last period): " + json.dumps(is_list[-1] if is_list else {}) + "\n")
    if bs_list:
        parts.append("Balance sheet (last period): " + json.dumps(bs_list[-1] if bs_list else {}) + "\n")
    if cf_list:
        parts.append("Cash flow (last period): " + json.dumps(cf_list[-1] if cf_list else {}) + "\n")
    if kpis:
        parts.append("KPIs (last period): " + json.dumps(kpis[-1] if kpis else {}) + "\n")
    if budget_summary:
        parts.append("Budget variance summary: " + budget_summary + "\n")
    return "\n".join(parts)


async def generate_board_pack_impl(
    tenant_id: str,
    pack_id: str,
    store: ArtifactStore,
    llm: LLMRouter,
) -> dict[str, Any]:
    """Internal: assemble data, call LLM, save narrative; returns dict with pack_id, status, narrative_json. Raises HTTPException on validation/not-found, LLMError on LLM failure."""
    async with tenant_conn(tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT pack_id, label, run_id, budget_id, status FROM board_packs WHERE tenant_id = $1 AND pack_id = $2""",
            tenant_id,
            pack_id,
        )
    if not row:
        raise HTTPException(404, "Board pack not found")
    if row["status"] not in ("draft", "error"):
        raise HTTPException(400, f"Pack status is '{row['status']}'; only draft or error can be regenerated")
    run_id = row["run_id"]
    if not run_id:
        raise HTTPException(400, "Board pack has no run_id; cannot assemble data")
    try:
        data = store.load(tenant_id, "run_results", f"{run_id}_statements")
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Run results not found for this run") from e
        raise
    statements = data.get("statements", {})
    kpis = data.get("kpis", [])
    budget_summary = await _fetch_budget_variance_summary(tenant_id, row["budget_id"]) if row["budget_id"] else None
    facts = _assemble_facts_for_narrative(statements, kpis, run_id, budget_summary)
    prompt = (
        "You are a financial analyst preparing a board pack. Using ONLY the following factual data, "
        "write a brief executive summary and strategic commentary. Be factual and sourced from the data; "
        "do not speculate or add unsourced claims.\n\nData:\n" + facts
    )
    async with tenant_conn(tenant_id) as conn:
        await conn.execute(
            """UPDATE board_packs SET status = 'generating', error_message = NULL WHERE tenant_id = $1 AND pack_id = $2""",
            tenant_id,
            pack_id,
        )
    try:
        resp = await llm.complete_with_routing(
            tenant_id=tenant_id,
            messages=[{"role": "user", "content": prompt}],
            response_schema=BOARD_PACK_NARRATIVE_SCHEMA,
            task_label="board_pack_narrative",
            max_tokens=4096,
            temperature=0.2,
        )
        narrative = resp.content or {}
        async with tenant_conn(tenant_id) as conn:
            await conn.execute(
                """UPDATE board_packs SET status = 'ready', narrative_json = $1::jsonb, error_message = NULL
                   WHERE tenant_id = $2 AND pack_id = $3""",
                json.dumps(narrative),
                tenant_id,
                pack_id,
            )
        return {"pack_id": pack_id, "status": "ready", "narrative_json": narrative}
    except LLMError as e:
        async with tenant_conn(tenant_id) as conn:
            await conn.execute(
                """UPDATE board_packs SET status = 'error', error_message = $1 WHERE tenant_id = $2 AND pack_id = $3""",
                str(e),
                tenant_id,
                pack_id,
            )
        raise HTTPException(502, f"LLM narrative failed: {e}") from e


@router.post("/{pack_id}/generate")
async def generate_board_pack(
    pack_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Assemble data from run (and optional budget), call LLM for narrative, save and set status=ready. VA-P7-07."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    return await generate_board_pack_impl(x_tenant_id, pack_id, store, llm)


class PatchBoardPackBody(BaseModel):
    label: str | None = Field(default=None, description="Update display label")
    section_order: list[str] | None = Field(default=None, description="Update section order")
    branding_json: dict[str, Any] | None = Field(default=None, description="Update branding (logo_url, primary_color, terms_footer)")


@router.patch("/{pack_id}")
async def patch_board_pack(
    pack_id: str,
    body: PatchBoardPackBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Update board pack label, section order, or branding (Phase 10 stub)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    updates: list[str] = []
    args: list[Any] = []
    pos = 1
    if body.label is not None:
        updates.append(f"label = ${pos}")
        args.append(body.label)
        pos += 1
    if body.section_order is not None:
        updates.append(f"section_order = ${pos}::jsonb")
        args.append(json.dumps(body.section_order))
        pos += 1
    if body.branding_json is not None:
        updates.append(f"branding_json = ${pos}::jsonb")
        args.append(json.dumps(body.branding_json))
        pos += 1
    if not updates:
        raise HTTPException(400, "No fields to update")
    args.extend([x_tenant_id, pack_id])
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            f"UPDATE board_packs SET {', '.join(updates)} WHERE tenant_id = ${pos} AND pack_id = ${pos + 1}",
            *args,
        )
    if result == "UPDATE 0":
        raise HTTPException(404, "Board pack not found")
    return {"pack_id": pack_id, "updated": True}


MAX_EXPORT_BYTES = 10 * 1024 * 1024  # 10MB VA-P7-08


# R11-05: Skip non-monetary keys so period_index, count, confidence_score, etc. are not scaled
_NON_MONETARY_KEYS = frozenset({
    "period_index", "period_ordinal", "period_number", "count", "sample_count",
    "n_periods", "num_periods", "confidence", "confidence_score",
    "variance_pct", "variance_percent", "utilisation_pct", "pct",
    "p25", "p75",
    "id", "version",
})


def _scale_numerics(obj: Any, rate: float, _key: str | None = None) -> Any:
    """Recursively multiply monetary numeric values by rate (VA-P8-01). Skips known non-monetary keys."""
    if _key and _key.lower() in _NON_MONETARY_KEYS:
        return obj
    if isinstance(obj, (int, float)):
        return obj * rate
    if isinstance(obj, dict):
        return {k: _scale_numerics(v, rate, _key=k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scale_numerics(v, rate, _key=_key) for v in obj]
    return obj


@router.get("/{pack_id}/export")
async def export_board_pack(
    pack_id: str,
    export_format: str = Query("html", alias="format", description="html, pdf, or pptx"),
    currency: str | None = Query(None, description="Optional: display amounts in this currency (VA-P8-01); uses tenant FX rates"),
    benchmark: bool = Query(False, description="Include industry benchmark section (VA-P8-09)"),
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> Response:
    """Export board pack as HTML, PDF, or PPTX (VA-P7-08). Optional currency (VA-P8-01), benchmark section (VA-P8-09)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if export_format not in ("html", "pdf", "pptx"):
        raise HTTPException(400, "format must be html, pdf, or pptx")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT pack_id, label, run_id, budget_id, section_order, status, narrative_json, branding_json
               FROM board_packs WHERE tenant_id = $1 AND pack_id = $2""",
            x_tenant_id,
            pack_id,
        )
    if not row:
        raise HTTPException(404, "Board pack not found")
    if row["status"] != "ready":
        raise HTTPException(400, "Pack must be in ready status to export; run generate first")
    so = row["section_order"]
    if so is not None and not isinstance(so, list):
        so = json.loads(so) if isinstance(so, str) else list(so)
    so = so or DEFAULT_SECTION_ORDER
    nar = row["narrative_json"] or {}
    if isinstance(nar, str):
        nar = json.loads(nar) if nar else {}
    br = row["branding_json"] or {}
    if isinstance(br, str):
        br = json.loads(br) if br else {}
    run_id = row["run_id"] or ""
    try:
        data = store.load(x_tenant_id, "run_results", f"{run_id}_statements")
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise HTTPException(404, "Run results not found for this pack") from e
        raise
    statements = data.get("statements", {})
    kpis = data.get("kpis", [])
    budget_summary: str | None = None
    if row["budget_id"]:
        budget_summary = await _fetch_budget_variance_summary(x_tenant_id, row["budget_id"])

    display_currency: str | None = None
    if currency:
        async with tenant_conn(x_tenant_id) as conn:
            settings_row = await conn.fetchrow(
                "SELECT base_currency FROM tenant_currency_settings WHERE tenant_id = $1",
                x_tenant_id,
            )
            base = (settings_row["base_currency"] if settings_row else "USD") or "USD"
        if base != currency:
            async with tenant_conn(x_tenant_id) as conn:
                rate_row = await conn.fetchrow(
                    """SELECT rate FROM fx_rates
                       WHERE tenant_id = $1 AND from_currency = $2 AND to_currency = $3
                       ORDER BY effective_date DESC LIMIT 1""",
                    x_tenant_id,
                    base,
                    currency,
                )
            if not rate_row:
                raise HTTPException(404, f"No FX rate for {base} -> {currency}; add rate in /api/v1/currency/rates")
            rate = float(rate_row["rate"])
            statements = _scale_numerics(copy.deepcopy(statements), rate)
            kpis = _scale_numerics(copy.deepcopy(kpis), rate)
        display_currency = currency

    benchmark_metrics: list[dict[str, Any]] = []
    so_with_bench = list(so) if so else list(DEFAULT_SECTION_ORDER)
    if benchmark:
        async with tenant_conn(x_tenant_id) as conn_b:
            opt = await conn_b.fetchrow(
                "SELECT industry_segment, size_segment FROM tenant_benchmark_opt_in WHERE tenant_id = $1",
                x_tenant_id,
            )
            seg = f"{opt['industry_segment']}|{opt['size_segment']}" if opt else "general|general"
            rows_b = await conn_b.fetch(
                "SELECT metric_name, median_value, p25_value, p75_value, sample_count FROM benchmark_aggregates WHERE segment_key = $1 ORDER BY metric_name LIMIT 20",
                seg,
            )
            benchmark_metrics = [
                {"metric_name": r["metric_name"], "median": float(r["median_value"]), "p25": float(r["p25_value"]) if r["p25_value"] is not None else None, "p75": float(r["p75_value"]) if r["p75_value"] is not None else None, "sample_count": r["sample_count"]}
                for r in rows_b
            ]
    if benchmark_metrics and "benchmark" not in so_with_bench:
        so_with_bench.append("benchmark")

    if export_format == "html":
        html = build_board_pack_html(
            label=row["label"],
            section_order=so_with_bench,
            narrative=nar,
            statements=statements,
            kpis=kpis,
            budget_summary=budget_summary,
            branding=br,
            run_id=run_id,
            display_currency=display_currency,
            benchmark_metrics=benchmark_metrics if benchmark_metrics else None,
        )
        if len(html.encode("utf-8")) > MAX_EXPORT_BYTES:
            raise HTTPException(413, "Export exceeds 10MB limit")
        return HTMLResponse(content=html, headers={"Content-Disposition": f'attachment; filename="{pack_id}.html"'})
    if export_format == "pdf":
        html = build_board_pack_html(
            label=row["label"],
            section_order=so_with_bench,
            narrative=nar,
            statements=statements,
            kpis=kpis,
            budget_summary=budget_summary,
            branding=br,
            run_id=run_id,
            display_currency=display_currency,
            benchmark_metrics=benchmark_metrics if benchmark_metrics else None,
        )
        try:
            pdf_bytes = html_to_pdf(html)
        except RuntimeError as e:
            raise HTTPException(501, str(e)) from e
        if len(pdf_bytes) > MAX_EXPORT_BYTES:
            raise HTTPException(413, "Export exceeds 10MB limit")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{pack_id}.pdf"'},
        )
    # pptx
    try:
        pptx_bytes = build_board_pack_pptx(
            label=row["label"],
            section_order=so_with_bench,
            narrative=nar,
            statements=statements,
            kpis=kpis,
            budget_summary=budget_summary,
            run_id=run_id,
            display_currency=display_currency,
            benchmark_metrics=benchmark_metrics if benchmark_metrics else None,
        )
    except RuntimeError as e:
        raise HTTPException(501, str(e)) from e
    if len(pptx_bytes) > MAX_EXPORT_BYTES:
        raise HTTPException(413, "Export exceeds 10MB limit")
    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{pack_id}.pptx"'},
    )


@router.delete("/{pack_id}")
async def delete_board_pack(
    pack_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Delete a board pack."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            "DELETE FROM board_packs WHERE tenant_id = $1 AND pack_id = $2",
            x_tenant_id,
            pack_id,
        )
    if result == "DELETE 0":
        raise HTTPException(404, "Board pack not found")
    return {"pack_id": pack_id, "deleted": True}
