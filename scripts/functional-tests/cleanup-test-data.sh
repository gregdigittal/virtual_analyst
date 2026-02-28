#!/usr/bin/env bash
# cleanup-test-data.sh — Remove test fixtures (reverse order to avoid FK violations)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
API_URL="${API_URL:-http://localhost:8000/api/v1}"
FIXTURES_FILE="$PROJECT_DIR/apps/web/e2e/functional/fixtures/test-constants.ts"

echo "Cleaning up test data..."

# Read IDs from fixtures file
read_id() {
    grep "$1" "$FIXTURES_FILE" | sed "s/.*'\(.*\)'.*/\1/" | head -1
}

BOARD_PACK_ID=$(read_id "boardPackId")
BUDGET_ID=$(read_id "budgetId")
RUN_ID=$(read_id "runId")
DRAFT_ID=$(read_id "draftId")
BASELINE_ID=$(read_id "baselineId")

api() {
    local method="$1" path="$2"
    shift 2
    curl -s -X "$method" "${API_URL}${path}" \
        -H "Content-Type: application/json" \
        -H "X-Tenant-ID: test-tenant-001" \
        -H "X-Dev-User: functional-test@va.dev" \
        "$@"
}

# Delete in reverse dependency order
[ -n "$BOARD_PACK_ID" ] && api DELETE "/board-packs/${BOARD_PACK_ID}" && echo "  → Deleted board pack"
[ -n "$BUDGET_ID" ] && api DELETE "/budgets/${BUDGET_ID}" && echo "  → Deleted budget"
[ -n "$RUN_ID" ] && api DELETE "/runs/${RUN_ID}" && echo "  → Deleted run"
[ -n "$DRAFT_ID" ] && api DELETE "/drafts/${DRAFT_ID}" && echo "  → Deleted draft"
[ -n "$BASELINE_ID" ] && api DELETE "/baselines/${BASELINE_ID}" && echo "  → Deleted baseline"

# Clean up generated test files
echo "  → Removing generated spec files"
rm -f "$PROJECT_DIR/apps/web/e2e/functional/"*.spec.ts

echo ""
echo "✓ Cleanup complete."
