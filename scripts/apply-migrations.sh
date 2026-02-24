#!/usr/bin/env bash
# Apply all numbered migrations in order against DATABASE_URL.
# Usage: ./scripts/apply-migrations.sh [migrations-dir]
#
# Defaults to apps/api/app/db/migrations relative to the project root.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MIGRATIONS_DIR="${1:-$PROJECT_DIR/apps/api/app/db/migrations}"
DB_URL="${DATABASE_URL:?DATABASE_URL must be set}"

echo "--- Applying migrations from $MIGRATIONS_DIR ---"

# Core schema first
psql "$DB_URL" -f "$MIGRATIONS_DIR/0001_init.sql" -q
psql "$DB_URL" -f "$MIGRATIONS_DIR/0002_functions_and_rls.sql" -q

# All remaining numbered migrations (0003+) in sorted order
for f in "$MIGRATIONS_DIR"/[0-9][0-9][0-9][0-9]_*.sql; do
    num="$(basename "$f" | cut -d_ -f1)"
    if [ "$num" -le 2 ]; then continue; fi
    psql "$DB_URL" -f "$f" -q
done

echo "--- Migrations applied ---"
