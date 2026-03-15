"""AFS Roll-Forward — copy sections and comparatives from a prior engagement."""

from __future__ import annotations

import json
import uuid

import asyncpg


def _section_id() -> str:
    return f"asc_{uuid.uuid4().hex[:14]}"


def _tb_id() -> str:
    return f"atb_{uuid.uuid4().hex[:14]}"


async def rollforward_sections(
    conn,
    tenant_id: str,
    source_engagement_id: str,
    target_engagement_id: str,
    *,
    created_by: str | None = None,
) -> dict:
    """
    Copy all sections from source engagement into target engagement.
    - Sets status='draft' on all copied sections
    - Sets rolled_forward_from to the source section_id
    - Preserves section_type, title, content_json, section_number
    - Generates new section_ids
    - Uses ON CONFLICT DO NOTHING to be idempotent on section_number
    Returns { sections_copied: int, sections: [...] }
    """
    source_rows = await conn.fetch(
        """SELECT section_id, section_type, section_number, title, content_json
           FROM afs_sections
           WHERE tenant_id = $1 AND engagement_id = $2
           ORDER BY section_number""",
        tenant_id, source_engagement_id,
    )

    copied = []
    for row in source_rows:
        new_id = _section_id()
        try:
            await conn.execute(
                """INSERT INTO afs_sections
                   (tenant_id, section_id, engagement_id, section_type, section_number,
                    title, content_json, status, version, rolled_forward_from, needs_review, created_by)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, 'draft', 1, $8, true, $9)
                   ON CONFLICT (tenant_id, engagement_id, section_number) DO NOTHING""",
                tenant_id, new_id, target_engagement_id,
                row["section_type"], row["section_number"],
                row["title"], row["content_json"],
                row["section_id"],  # rolled_forward_from = source section_id
                created_by,
            )
            copied.append({
                "section_id": new_id,
                "title": row["title"],
                "section_type": row["section_type"],
                "rolled_forward_from": row["section_id"],
            })
        except asyncpg.exceptions.UniqueViolationError:
            # ON CONFLICT: section_number already exists in target engagement
            pass

    return {"sections_copied": len(copied), "sections": copied}


async def rollforward_comparatives(
    conn,
    tenant_id: str,
    source_engagement_id: str,
    target_engagement_id: str,
) -> dict:
    """
    Copy trial balance data from source engagement as comparative reference.
    Inserts a new TB row with source='va_baseline' and a marker in mapped_accounts_json.
    Returns { comparatives_copied: bool, trial_balance_id: str | None }
    """
    # Get the primary (first) trial balance from source
    source_tb = await conn.fetchrow(
        """SELECT data_json, mapped_accounts_json, entity_id
           FROM afs_trial_balances
           WHERE tenant_id = $1 AND engagement_id = $2
           ORDER BY uploaded_at ASC
           LIMIT 1""",
        tenant_id, source_engagement_id,
    )

    if not source_tb:
        return {"comparatives_copied": False, "trial_balance_id": None}

    new_tb_id = _tb_id()

    # Preserve the source mapping and add the _comparative_source marker.
    # This allows downstream consumers to render comparative columns using the
    # prior year's account mapping while still identifying the source engagement.
    raw_mapping = source_tb["mapped_accounts_json"]
    if raw_mapping:
        prior_mapping: dict = json.loads(raw_mapping) if isinstance(raw_mapping, str) else dict(raw_mapping)
    else:
        prior_mapping = {}
    prior_mapping["_comparative_source"] = source_engagement_id
    comparative_meta = json.dumps(prior_mapping)

    await conn.execute(
        """INSERT INTO afs_trial_balances
           (tenant_id, trial_balance_id, engagement_id, entity_id, source,
            data_json, mapped_accounts_json, is_partial)
           VALUES ($1, $2, $3, $4, 'va_baseline', $5, $6, false)
           ON CONFLICT DO NOTHING""",
        tenant_id, new_tb_id, target_engagement_id,
        source_tb["entity_id"],
        source_tb["data_json"],
        comparative_meta,
    )

    return {"comparatives_copied": True, "trial_balance_id": new_tb_id}
