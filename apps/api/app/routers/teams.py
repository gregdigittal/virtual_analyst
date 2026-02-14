"""Team management API (VA-P6-02): CRUD teams, members, job functions; hierarchy validation."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn

router = APIRouter(prefix="/teams", tags=["teams"])

DEFAULT_JOB_FUNCTIONS = [
    ("jf_analyst", "Analyst"),
    ("jf_senior_analyst", "Senior Analyst"),
    ("jf_manager", "Manager"),
    ("jf_director", "Director"),
    ("jf_cfo", "CFO"),
]


class CreateTeamBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class UpdateTeamBody(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class AddMemberBody(BaseModel):
    user_id: str = Field(...)
    job_function_id: str = Field(...)
    reports_to: str | None = Field(default=None, description="user_id of manager; must be in same team")


class UpdateMemberBody(BaseModel):
    job_function_id: str | None = Field(default=None)
    reports_to: str | None = Field(default=None)


@router.get("")
async def list_teams(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List teams for the tenant."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT team_id, name, description, created_at, created_by
               FROM teams WHERE tenant_id = $1 ORDER BY name
               LIMIT $2 OFFSET $3""",
            x_tenant_id,
            limit,
            offset,
        )
    return {
        "teams": [
            {
                "team_id": r["team_id"],
                "name": r["name"],
                "description": r["description"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "created_by": r["created_by"],
            }
            for r in rows
        ],
    }


@router.post("", status_code=201)
async def create_team(
    body: CreateTeamBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a team."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    team_id = f"tm_{uuid.uuid4().hex[:14]}"
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO teams (tenant_id, team_id, name, description, created_by)
             VALUES ($1, $2, $3, $4, $5)""",
            x_tenant_id,
            team_id,
            body.name,
            body.description,
            x_user_id or None,
        )
    return {"team_id": team_id, "name": body.name, "description": body.description}


@router.get("/job-functions/list")
async def list_job_functions(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List job functions for the tenant. Ensures default set exists if none (e.g. new tenant)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT job_function_id, name, created_at FROM job_functions
               WHERE tenant_id = $1 ORDER BY name""",
            x_tenant_id,
        )
        if not rows:
            for jf_id, name in DEFAULT_JOB_FUNCTIONS:
                await conn.execute(
                    """INSERT INTO job_functions (tenant_id, job_function_id, name)
                     VALUES ($1, $2, $3) ON CONFLICT (tenant_id, job_function_id) DO NOTHING""",
                    x_tenant_id,
                    jf_id,
                    name,
                )
            rows = await conn.fetch(
                """SELECT job_function_id, name, created_at FROM job_functions
                   WHERE tenant_id = $1 ORDER BY name""",
                x_tenant_id,
            )
    return {
        "job_functions": [
            {
                "job_function_id": r["job_function_id"],
                "name": r["name"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }


@router.get("/{team_id}")
async def get_team(
    team_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get team and its members."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT team_id, name, description, created_at, created_by
               FROM teams WHERE tenant_id = $1 AND team_id = $2""",
            x_tenant_id,
            team_id,
        )
        if not row:
            raise HTTPException(404, "Team not found")
        members = await conn.fetch(
            """SELECT user_id, job_function_id, reports_to, created_at
               FROM team_members WHERE tenant_id = $1 AND team_id = $2
               ORDER BY created_at
               LIMIT 200""",
            x_tenant_id,
            team_id,
        )
    return {
        "team_id": row["team_id"],
        "name": row["name"],
        "description": row["description"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "created_by": row["created_by"],
        "members": [
            {
                "user_id": m["user_id"],
                "job_function_id": m["job_function_id"],
                "reports_to": m["reports_to"],
                "created_at": m["created_at"].isoformat() if m["created_at"] else None,
            }
            for m in members
        ],
    }


@router.patch("/{team_id}")
async def update_team(
    team_id: str,
    body: UpdateTeamBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Update team name/description."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    updates = []
    params: list[Any] = [x_tenant_id, team_id]
    idx = 3
    if body.name is not None:
        updates.append(f"name = ${idx}")
        params.append(body.name)
        idx += 1
    if body.description is not None:
        updates.append(f"description = ${idx}")
        params.append(body.description)
        idx += 1
    if not updates:
        raise HTTPException(400, "No fields to update; provide at least one of: name, description")
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            f"""UPDATE teams SET {", ".join(updates)} WHERE tenant_id = $1 AND team_id = $2""",
            *params,
        )
    return await get_team(team_id, x_tenant_id)


@router.delete("/{team_id}", status_code=204)
async def delete_team(
    team_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> None:
    """Delete team and all members."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            """DELETE FROM teams WHERE tenant_id = $1 AND team_id = $2""",
            x_tenant_id,
            team_id,
        )
    if result == "DELETE 0":
        raise HTTPException(404, "Team not found")


@router.get("/{team_id}/members")
async def list_members(
    team_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List members of a team."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        team = await conn.fetchrow(
            """SELECT 1 FROM teams WHERE tenant_id = $1 AND team_id = $2""",
            x_tenant_id,
            team_id,
        )
        if not team:
            raise HTTPException(404, "Team not found")
        rows = await conn.fetch(
            """SELECT user_id, job_function_id, reports_to, created_at
               FROM team_members WHERE tenant_id = $1 AND team_id = $2
               ORDER BY created_at
               LIMIT $3 OFFSET $4""",
            x_tenant_id,
            team_id,
            limit,
            offset,
        )
    return {
        "members": [
            {
                "user_id": r["user_id"],
                "job_function_id": r["job_function_id"],
                "reports_to": r["reports_to"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ],
    }


@router.post("/{team_id}/members", status_code=201)
async def add_member(
    team_id: str,
    body: AddMemberBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Add a member to the team. reports_to must be a user_id already in this team."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        team = await conn.fetchrow(
            """SELECT 1 FROM teams WHERE tenant_id = $1 AND team_id = $2""",
            x_tenant_id,
            team_id,
        )
        if not team:
            raise HTTPException(404, "Team not found")
        jf = await conn.fetchrow(
            """SELECT 1 FROM job_functions WHERE tenant_id = $1 AND job_function_id = $2""",
            x_tenant_id,
            body.job_function_id,
        )
        if not jf:
            raise HTTPException(400, "Unknown job_function_id for this tenant")
        if body.reports_to:
            if body.reports_to == body.user_id:
                raise HTTPException(400, "A member cannot report to themselves")
            manager = await conn.fetchrow(
                """SELECT 1 FROM team_members
                   WHERE tenant_id = $1 AND team_id = $2 AND user_id = $3""",
                x_tenant_id,
                team_id,
                body.reports_to,
            )
            if not manager:
                raise HTTPException(
                    400,
                    "reports_to must be a user_id of an existing member in the same team",
                )
        await conn.execute(
            """INSERT INTO team_members (tenant_id, team_id, user_id, job_function_id, reports_to)
             VALUES ($1, $2, $3, $4, $5)
             ON CONFLICT (tenant_id, team_id, user_id) DO UPDATE SET
               job_function_id = EXCLUDED.job_function_id,
               reports_to = EXCLUDED.reports_to""",
            x_tenant_id,
            team_id,
            body.user_id,
            body.job_function_id,
            body.reports_to,
        )
    return {
        "team_id": team_id,
        "user_id": body.user_id,
        "job_function_id": body.job_function_id,
        "reports_to": body.reports_to,
    }


@router.patch("/{team_id}/members/{user_id}")
async def update_member(
    team_id: str,
    user_id: str,
    body: UpdateMemberBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Update member job function or reports_to. reports_to must be in same team."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT 1 FROM team_members WHERE tenant_id = $1 AND team_id = $2 AND user_id = $3""",
            x_tenant_id,
            team_id,
            user_id,
        )
        if not row:
            raise HTTPException(404, "Member not found")
        if body.job_function_id is not None:
            jf = await conn.fetchrow(
                """SELECT 1 FROM job_functions WHERE tenant_id = $1 AND job_function_id = $2""",
                x_tenant_id,
                body.job_function_id,
            )
            if not jf:
                raise HTTPException(400, "Unknown job_function_id for this tenant")
        if body.reports_to is not None:
            if body.reports_to and body.reports_to == user_id:
                raise HTTPException(400, "A member cannot report to themselves")
            if body.reports_to:
                manager = await conn.fetchrow(
                    """SELECT 1 FROM team_members
                       WHERE tenant_id = $1 AND team_id = $2 AND user_id = $3""",
                    x_tenant_id,
                    team_id,
                    body.reports_to,
                )
                if not manager:
                    raise HTTPException(
                        400,
                        "reports_to must be a user_id of an existing member in the same team",
                    )
        updates = []
        params: list[Any] = [x_tenant_id, team_id, user_id]
        idx = 4
        if body.job_function_id is not None:
            updates.append(f"job_function_id = ${idx}")
            params.append(body.job_function_id)
            idx += 1
        if body.reports_to is not None:
            updates.append(f"reports_to = ${idx}")
            params.append(body.reports_to)
            idx += 1
        if updates:
            await conn.execute(
                f"""UPDATE team_members SET {", ".join(updates)}
                    WHERE tenant_id = $1 AND team_id = $2 AND user_id = $3""",
                *params,
            )
    return await list_members(team_id, x_tenant_id)


@router.delete("/{team_id}/members/{user_id}", status_code=204)
async def remove_member(
    team_id: str,
    user_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> None:
    """Remove a member from the team."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            """DELETE FROM team_members
               WHERE tenant_id = $1 AND team_id = $2 AND user_id = $3""",
            x_tenant_id,
            team_id,
            user_id,
        )
    if result == "DELETE 0":
        raise HTTPException(404, "Member not found")
