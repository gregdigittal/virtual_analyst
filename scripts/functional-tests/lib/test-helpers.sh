#!/usr/bin/env bash
# test-helpers.sh — Shared functions for the TDD Red-Green functional test runner

RED_CLR='\033[0;31m'
GREEN_CLR='\033[0;32m'
YELLOW_CLR='\033[1;33m'
CYAN_CLR='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

# Include guard: prevent counter reset when re-sourced by phase scripts
# inside run-all.sh orchestration
if [ -z "${_TEST_HELPERS_LOADED:-}" ]; then
    _TEST_HELPERS_LOADED=1
    PASS_COUNT=0
    FAIL_COUNT=0
    SKIP_COUNT=0
    declare -a RESULTS=()
fi

# Configurable URLs (override via env vars for production)
BASE_URL="${BASE_URL:-http://localhost:3000}"
API_URL="${API_URL:-http://localhost:8000/api/v1}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

log_phase() {
    echo ""
    echo -e "${CYAN_CLR}${BOLD}════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN_CLR}${BOLD}  $1${NC}"
    echo -e "${CYAN_CLR}${BOLD}════════════════════════════════════════════════════${NC}"
    echo ""
}

log_phase_complete() {
    echo ""
    echo -e "${CYAN_CLR}  ✓ $1 complete (GREEN: $PASS_COUNT | RED: $FAIL_COUNT | SKIP: $SKIP_COUNT)${NC}"
    echo ""
}

run_tdd_test() {
    local test_name="$1"
    local spec="$2"

    echo -e "${YELLOW_CLR}  ▶ TDD test: ${test_name}${NC}"

    local prompt="You are executing a TDD RED-GREEN functional test for Virtual Analyst.

${spec}

TEST CONSTRAINTS:
- Base URL: ${BASE_URL}
- Test user email: functional-test@va.dev
- Test user password: TestPass123!
- Write the test in TypeScript using @playwright/test
- Save to: apps/web/e2e/functional/${test_name}.spec.ts
- Use page.waitForSelector() or expect(locator).toBeVisible() for async content
- Assert on visible UI text and elements, not CSS classes or implementation details
- Each test must be independently runnable (login fresh if needed)
- Do not modify application source code
- If you need seeded data IDs, import from apps/web/e2e/functional/fixtures/test-constants.ts
- Run with: cd apps/web && npx playwright test e2e/functional/${test_name}.spec.ts --project=chromium
- Report the result on the LAST LINE in this EXACT format:
  RESULT: GREEN — ${test_name} — PASS
  or
  RESULT: RED — ${test_name} — FAIL — <one-line reason>"

    local output
    output=$(cd "$PROJECT_DIR" && claude -p "$prompt" 2>&1) || true

    # Save full output
    echo "$output" > "$SCRIPT_DIR/results/${test_name}.log"

    # Parse RESULT line
    local result_line
    result_line=$(echo "$output" | grep "^RESULT:" | tail -1)

    if echo "$result_line" | grep -q "GREEN"; then
        echo -e "    ${GREEN_CLR}✓ GREEN — ${test_name} — PASS${NC}"
        PASS_COUNT=$((PASS_COUNT + 1))
        RESULTS+=("GREEN|${test_name}")
    elif echo "$result_line" | grep -q "RED"; then
        local reason
        reason=$(echo "$result_line" | sed 's/.*FAIL — //')
        echo -e "    ${RED_CLR}✗ RED — ${test_name} — FAIL — ${reason}${NC}"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        RESULTS+=("RED|${test_name}|${reason}")
    else
        echo -e "    ${YELLOW_CLR}? SKIP — ${test_name} — No RESULT line in output${NC}"
        SKIP_COUNT=$((SKIP_COUNT + 1))
        RESULTS+=("SKIP|${test_name}|No RESULT line")
    fi
}

print_summary() {
    local total=$((PASS_COUNT + FAIL_COUNT + SKIP_COUNT))
    echo ""
    echo -e "${BOLD}════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  FUNCTIONAL TEST SUMMARY${NC}"
    echo -e "${BOLD}════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${GREEN_CLR}GREEN (pass): ${PASS_COUNT}${NC}"
    echo -e "  ${RED_CLR}RED (fail):   ${FAIL_COUNT}${NC}"
    echo -e "  ${YELLOW_CLR}SKIP:         ${SKIP_COUNT}${NC}"
    echo -e "  Total:        ${total}"
    echo ""

    if [ ${FAIL_COUNT} -gt 0 ]; then
        echo -e "${RED_CLR}${BOLD}  Specification violations:${NC}"
        for result in "${RESULTS[@]}"; do
            if [[ "$result" == RED* ]]; then
                local name reason
                name=$(echo "$result" | cut -d'|' -f2)
                reason=$(echo "$result" | cut -d'|' -f3)
                echo -e "    ${RED_CLR}✗ ${name}: ${reason}${NC}"
            fi
        done
        echo ""
        exit 1
    else
        echo -e "${GREEN_CLR}${BOLD}  All tests match specification ✓${NC}"
        exit 0
    fi
}
