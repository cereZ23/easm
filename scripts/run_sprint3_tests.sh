#!/bin/bash
#
# Run Sprint 3 Test Suite
# Tests for FastAPI endpoints and Nuclei integration
#
# Usage:
#   ./scripts/run_sprint3_tests.sh [OPTIONS]
#
# Options:
#   --api-only        Run only API endpoint tests
#   --integration     Run only integration tests
#   --performance     Run only performance tests
#   --security        Run only security tests
#   --coverage        Generate coverage report
#   --verbose         Verbose output
#   --fast           Skip slow tests
#

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
RUN_API=true
RUN_INTEGRATION=true
RUN_PERFORMANCE=false
RUN_SECURITY=true
GENERATE_COVERAGE=false
VERBOSE=""
SKIP_SLOW=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --api-only)
            RUN_API=true
            RUN_INTEGRATION=false
            RUN_PERFORMANCE=false
            RUN_SECURITY=false
            shift
            ;;
        --integration)
            RUN_API=false
            RUN_INTEGRATION=true
            RUN_PERFORMANCE=false
            RUN_SECURITY=false
            shift
            ;;
        --performance)
            RUN_API=false
            RUN_INTEGRATION=false
            RUN_PERFORMANCE=true
            RUN_SECURITY=false
            shift
            ;;
        --security)
            RUN_API=false
            RUN_INTEGRATION=false
            RUN_PERFORMANCE=false
            RUN_SECURITY=true
            shift
            ;;
        --coverage)
            GENERATE_COVERAGE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE="-v"
            shift
            ;;
        --fast)
            SKIP_SLOW="-m 'not slow'"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}=== Sprint 3 Test Suite ===${NC}"
echo ""

# Check dependencies
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest not found. Please install: pip install pytest${NC}"
    exit 1
fi

# Build test command
TEST_PATHS=""
MARKERS=""

if [ "$RUN_API" = true ]; then
    TEST_PATHS="$TEST_PATHS tests/api/"
fi

if [ "$RUN_INTEGRATION" = true ]; then
    TEST_PATHS="$TEST_PATHS tests/integration/test_nuclei_integration.py tests/integration/test_api_workflows.py"
fi

if [ "$RUN_PERFORMANCE" = true ]; then
    MARKERS="-m performance"
    TEST_PATHS="tests/api/test_api_performance.py $TEST_PATHS"
fi

if [ "$RUN_SECURITY" = true ] && [ "$RUN_API" = false ]; then
    MARKERS="-m security"
    TEST_PATHS="tests/api/test_api_security.py $TEST_PATHS"
fi

# Coverage options
COV_OPTS=""
if [ "$GENERATE_COVERAGE" = true ]; then
    COV_OPTS="--cov=app/api --cov=app/services/scanning --cov=app/repositories/finding_repository --cov-report=html --cov-report=term --cov-report=json"
fi

# Run tests
echo -e "${YELLOW}Running tests...${NC}"
echo ""

pytest $TEST_PATHS $MARKERS $VERBOSE $SKIP_SLOW $COV_OPTS

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${RED}✗ Some tests failed${NC}"
fi

# Coverage summary
if [ "$GENERATE_COVERAGE" = true ]; then
    echo ""
    echo -e "${BLUE}Coverage report generated:${NC}"
    echo "  HTML: htmlcov/index.html"
    echo "  JSON: coverage.json"
fi

echo ""
echo -e "${BLUE}Test Summary:${NC}"
pytest $TEST_PATHS $MARKERS --collect-only -q 2>/dev/null | tail -n 1 || true

exit $EXIT_CODE
