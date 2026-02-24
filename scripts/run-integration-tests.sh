#!/usr/bin/env bash
# N-01: Run integration tests against an isolated test database.
#
# Usage:
#   ./scripts/run-integration-tests.sh          # starts Postgres, runs tests, cleans up
#   ./scripts/run-integration-tests.sh --no-db   # skip Postgres lifecycle (use existing DB)
#
# Prerequisites: Docker (for Postgres) and psql (for migrations).
# The Supabase local Postgres on port 5432 is NOT affected.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.test.yml"
MIGRATIONS_DIR="$PROJECT_DIR/apps/api/app/db/migrations"

export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5433/finmodel_test}"
export INTEGRATION_TESTS=1
export ENVIRONMENT=test

MANAGE_DB=true
if [[ "${1:-}" == "--no-db" ]]; then
    MANAGE_DB=false
fi

cleanup() {
    if $MANAGE_DB; then
        echo "--- Stopping test database ---"
        docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Start test database
if $MANAGE_DB; then
    echo "--- Starting test database (port 5433) ---"
    docker compose -f "$COMPOSE_FILE" up -d --wait
fi

# Apply migrations via shared script
"$SCRIPT_DIR/apply-migrations.sh" "$MIGRATIONS_DIR"

echo "--- Running integration tests ---"
cd "$PROJECT_DIR"
python -m pytest tests/integration/ -v --tb=short

echo "--- Done ---"
