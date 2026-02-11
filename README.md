# Virtual Analyst

Deterministic financial modeling platform with an LLM-assisted Draft layer.

## Quick Start (Phase 0)

1. Copy environment file:
   - `cp .env.example .env`
2. Start local services:
   - `docker-compose up -d`
3. Create a virtual environment and install dependencies:
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -e ".[dev]"`

## Hosting Targets

- Backend: Render (Python service)
- Frontend: Vercel (Next.js)
- Testing: Hosted endpoints only (`tests/e2e`)
  - Vercel build config: `vercel.json` (monorepo root)

Hosted tests require GitHub secrets:
- `HOSTED_API_URL`
- `HOSTED_WEB_URL` (optional)

## Repository Layout

- `apps/` — API, web, and worker services
- `shared/` — shared engine and utilities
- `tests/` — unit, integration, e2e, security, load
- `docs/` — project documentation
- `scripts/` — automation scripts

## Specs

The full specification pack lives in `finmodel spec pack v7/`. Start with:
- `finmodel spec pack v7/docs/specs/BUILD_PLAN.md`
- `finmodel spec pack v7/docs/specs/BACKLOG.md`
- `finmodel spec pack v7/docs/specs/CURSOR_MASTER_PROMPT.md`
