#!/usr/bin/env bash
# run-all.sh — Master runner for TDD Red-Green functional test suite
#
# Usage:
#   ./scripts/functional-tests/run-all.sh              # Run all 6 phases
#   ./scripts/functional-tests/run-all.sh --phase 3    # Run only phase 3
#   ./scripts/functional-tests/run-all.sh --no-seed    # Skip seeding (data already exists)
#   ./scripts/functional-tests/run-all.sh --no-cleanup  # Skip cleanup (keep test data)
#
# Prerequisites:
#   - Dev server running at localhost:3000 (Next.js) and localhost:8000 (FastAPI)
#   - Claude Code CLI installed and authenticated
#   - Node.js and npx available
#   - Database with migrations applied
#
# TDD Philosophy:
#   Each test encodes a claim from docs/user-manual/ (the specification).
#   RED = app diverges from the manual. GREEN = app conforms.
#   Run this suite to answer: "Does the app do what the manual says?"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/lib/test-helpers.sh"

PHASE_FILTER=""
SEED=true
CLEANUP=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --phase) PHASE_FILTER="$2"; shift 2 ;;
        --no-seed) SEED=false; shift ;;
        --no-cleanup) CLEANUP=false; shift ;;
        --help|-h)
            echo "Usage: $0 [--phase N] [--no-seed] [--no-cleanup]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  Virtual Analyst — TDD Red-Green Functional Test Suite  ║${NC}"
echo -e "${BOLD}║  Specification: docs/user-manual/ (26 chapters)         ║${NC}"
echo -e "${BOLD}║  Method: claude -p → Playwright → RED/GREEN             ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Preflight checks
echo "Preflight checks..."

if ! command -v claude &>/dev/null; then
    echo -e "${RED_CLR}✗ Claude Code CLI not found. Install: https://docs.anthropic.com/claude-code${NC}"
    exit 1
fi
echo -e "  ${GREEN_CLR}✓ Claude Code CLI available${NC}"

if ! curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${RED_CLR}✗ Web server not responding at localhost:3000${NC}"
    exit 1
fi
echo -e "  ${GREEN_CLR}✓ Web server running at localhost:3000${NC}"

if ! curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo -e "${YELLOW_CLR}⚠ API server may not be running at localhost:8000 (non-critical for UI tests)${NC}"
fi

# Ensure Playwright is ready
cd "$PROJECT_DIR/apps/web"
if ! npx playwright --version &>/dev/null 2>&1; then
    echo "Installing Playwright..."
    npx playwright install chromium
fi
echo -e "  ${GREEN_CLR}✓ Playwright available${NC}"
cd "$PROJECT_DIR"

# Create results directory
mkdir -p "$SCRIPT_DIR/results"

# Seed test data
if $SEED; then
    echo ""
    echo -e "${CYAN_CLR}Seeding test data...${NC}"
    bash "$SCRIPT_DIR/seed-test-data.sh" || {
        echo -e "${YELLOW_CLR}⚠ Seed script had errors (continuing anyway)${NC}"
    }
fi

echo ""
echo -e "${CYAN_CLR}Starting test execution...${NC}"
START_TIME=$(date +%s)

# Run phases
run_phase() {
    local phase_num="$1"
    if [[ -n "$PHASE_FILTER" && "$PHASE_FILTER" != "$phase_num" ]]; then
        return
    fi
    local phase_script="$SCRIPT_DIR/phase-${phase_num}-"*.sh
    for script in $phase_script; do
        if [[ -f "$script" ]]; then
            source "$script"
        fi
    done
}

run_phase 1
run_phase 2
run_phase 3
run_phase 4
run_phase 5
run_phase 6

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo ""
echo -e "${CYAN_CLR}Total execution time: ${MINUTES}m ${SECONDS}s${NC}"

# Cleanup
if $CLEANUP; then
    echo ""
    echo -e "${CYAN_CLR}Cleaning up test data...${NC}"
    bash "$SCRIPT_DIR/cleanup-test-data.sh" 2>/dev/null || true
fi

# Print final summary
print_summary
