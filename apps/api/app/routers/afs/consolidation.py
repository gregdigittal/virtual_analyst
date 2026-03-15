"""AFS consolidation endpoints — multi-entity consolidation."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from apps.api.app.db import tenant_conn
from apps.api.app.routers.afs._common import (
    ConsolidateBody,
    LinkOrgBody,
    _consolidation_id,
    _validate_engagement,
)

router = APIRouter()


@router.post("/engagements/{engagement_id}/consolidation/link", status_code=201)
async def link_org_structure(
    engagement_id: str,
    body: LinkOrgBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Link an engagement to an org-structure for multi-entity consolidation."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT * FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        # Validate org_id exists
        org = await conn.fetchrow(
            "SELECT org_id, group_name FROM org_structures WHERE tenant_id = $1 AND org_id = $2",
            x_tenant_id, body.org_id,
        )
        if not org:
            raise HTTPException(404, f"Org-structure {body.org_id} not found")

        # Check for existing link
        existing = await conn.fetchval(
            "SELECT consolidation_id FROM afs_consolidation_rules WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        if existing:
            raise HTTPException(409, "Engagement is already linked to an org-structure. Unlink first.")

        cid = _consolidation_id()
        row = await conn.fetchrow(
            """INSERT INTO afs_consolidation_rules
               (tenant_id, consolidation_id, engagement_id, org_id, reporting_currency,
                fx_avg_rates, fx_closing_rates, created_by)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8)
               RETURNING *""",
            x_tenant_id, cid, engagement_id, body.org_id, body.reporting_currency,
            json.dumps(body.fx_avg_rates),
            json.dumps(body.fx_closing_rates or {}),
            x_user_id or None,
        )
        return dict(row)


@router.get("/engagements/{engagement_id}/consolidation")
async def get_consolidation(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get consolidation config for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM afs_consolidation_rules WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        if not row:
            raise HTTPException(404, "No consolidation linked for this engagement")
        return dict(row)


@router.get("/engagements/{engagement_id}/consolidation/entities")
async def list_consolidation_entities(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List entities from the linked org-structure with their TB upload status."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        consol = await conn.fetchrow(
            "SELECT org_id FROM afs_consolidation_rules WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        if not consol:
            raise HTTPException(404, "No consolidation linked for this engagement")

        entities = await conn.fetch(
            """SELECT entity_id, name, entity_type, currency
               FROM org_entities
               WHERE tenant_id = $1 AND org_id = $2 AND status = 'active'
               ORDER BY is_root DESC, name""",
            x_tenant_id, consol["org_id"],
        )

        # Check which entities have trial balances uploaded for this engagement
        tb_entity_ids = await conn.fetch(
            """SELECT DISTINCT entity_id FROM afs_trial_balances
               WHERE tenant_id = $1 AND engagement_id = $2 AND entity_id IS NOT NULL""",
            x_tenant_id, engagement_id,
        )
        tb_set = {r["entity_id"] for r in tb_entity_ids}

        items = []
        for e in entities:
            items.append({
                **dict(e),
                "has_trial_balance": e["entity_id"] in tb_set,
            })

        return {"items": items}


@router.post("/engagements/{engagement_id}/consolidation/run")
async def run_consolidation(
    engagement_id: str,
    body: ConsolidateBody | None = None,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Run consolidation: aggregate entity trial balances with eliminations."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        consol = await conn.fetchrow(
            "SELECT * FROM afs_consolidation_rules WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        if not consol:
            raise HTTPException(404, "No consolidation linked for this engagement")

        org_id = consol["org_id"]
        reporting_ccy = consol["reporting_currency"]

        # Update FX rates if provided
        fx_avg = dict(consol["fx_avg_rates"] or {})
        fx_closing = dict(consol["fx_closing_rates"] or {})
        if body and body.fx_avg_rates:
            fx_avg.update(body.fx_avg_rates)
        if body and body.fx_closing_rates:
            fx_closing.update(body.fx_closing_rates)

        # Load entities
        entities = await conn.fetch(
            """SELECT entity_id, name, currency
               FROM org_entities
               WHERE tenant_id = $1 AND org_id = $2 AND status = 'active'""",
            x_tenant_id, org_id,
        )
        entity_map = {e["entity_id"]: dict(e) for e in entities}

        # Load all entity trial balances
        tbs = await conn.fetch(
            """SELECT entity_id, data_json FROM afs_trial_balances
               WHERE tenant_id = $1 AND engagement_id = $2 AND entity_id IS NOT NULL
               ORDER BY uploaded_at DESC""",
            x_tenant_id, engagement_id,
        )

        # Group by entity (take latest per entity)
        entity_tbs: dict[str, list] = {}
        for tb in tbs:
            eid = tb["entity_id"]
            if eid not in entity_tbs:
                data = tb["data_json"] if isinstance(tb["data_json"], list) else []
                entity_tbs[eid] = data

        if not entity_tbs:
            raise HTTPException(400, "No entity trial balances found. Upload trial balances with entity_id tags first.")

        # Build entity-TB map for tracking
        entity_tb_map = {eid: "loaded" for eid in entity_tbs}
        for eid in entity_map:
            if eid not in entity_tb_map:
                entity_tb_map[eid] = "missing"

        # Load intercompany links for elimination
        ic_links = await conn.fetch(
            """SELECT from_entity_id, to_entity_id, link_type, amount_or_rate, frequency
               FROM org_intercompany_links
               WHERE tenant_id = $1 AND org_id = $2""",
            x_tenant_id, org_id,
        )

        # Consolidate: sum accounts across entities with FX translation
        consolidated: dict[str, float] = {}
        for eid, accounts in entity_tbs.items():
            entity_ccy = entity_map.get(eid, {}).get("currency", reporting_ccy)
            fx_rate = 1.0
            if entity_ccy != reporting_ccy:
                pair_key = f"{entity_ccy}/{reporting_ccy}"
                fx_rate = fx_avg.get(pair_key, 1.0)

            for acct in accounts:
                name = acct.get("account_name", "Unknown")
                net = float(acct.get("net", 0)) * fx_rate
                consolidated[name] = consolidated.get(name, 0) + net

        # Compute elimination entries
        eliminations: list[dict] = []
        for link in ic_links:
            lt = link["link_type"]
            amount = float(link["amount_or_rate"] or 0)
            freq = link["frequency"] or "annual"

            # Annualize
            if freq == "monthly":
                amount *= 12
            elif freq == "quarterly":
                amount *= 4

            from_name = entity_map.get(link["from_entity_id"], {}).get("name", link["from_entity_id"])
            to_name = entity_map.get(link["to_entity_id"], {}).get("name", link["to_entity_id"])

            if lt in ("management_fee", "royalty", "trade"):
                eliminations.append({
                    "type": lt,
                    "from_entity": from_name,
                    "to_entity": to_name,
                    "revenue_eliminated": amount,
                    "expense_eliminated": amount,
                })
                # Remove from consolidated (simplified: reduce revenue and expense)
                consolidated[f"Intercompany {lt} revenue"] = consolidated.get(f"Intercompany {lt} revenue", 0) - amount
                consolidated[f"Intercompany {lt} expense"] = consolidated.get(f"Intercompany {lt} expense", 0) + amount
            elif lt == "loan":
                interest = amount  # amount_or_rate is interest rate for loans
                eliminations.append({
                    "type": "loan_interest",
                    "from_entity": from_name,
                    "to_entity": to_name,
                    "interest_eliminated": interest,
                })
            elif lt == "dividend":
                eliminations.append({
                    "type": "dividend",
                    "from_entity": from_name,
                    "to_entity": to_name,
                    "dividend_eliminated": amount,
                })

        # Build consolidated TB array
        consolidated_tb = [
            {"account_name": name, "net": round(net, 2)}
            for name, net in sorted(consolidated.items())
            if abs(net) > 0.005
        ]

        try:
            row = await conn.fetchrow(
                """UPDATE afs_consolidation_rules
                   SET consolidated_tb_json = $1::jsonb,
                       elimination_entries_json = $2::jsonb,
                       entity_tb_map = $3::jsonb,
                       fx_avg_rates = $4::jsonb,
                       fx_closing_rates = $5::jsonb,
                       status = 'consolidated',
                       consolidated_at = now()
                   WHERE tenant_id = $6 AND consolidation_id = $7
                   RETURNING *""",
                json.dumps(consolidated_tb),
                json.dumps(eliminations),
                json.dumps(entity_tb_map),
                json.dumps(fx_avg),
                json.dumps(fx_closing),
                x_tenant_id, consol["consolidation_id"],
            )
            return dict(row)
        except Exception as exc:
            await conn.execute(
                """UPDATE afs_consolidation_rules
                   SET status = 'error', error_message = $1
                   WHERE tenant_id = $2 AND consolidation_id = $3""",
                str(exc)[:2000], x_tenant_id, consol["consolidation_id"],
            )
            raise HTTPException(500, f"Consolidation failed: {exc}")
