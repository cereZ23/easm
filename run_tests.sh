#!/bin/bash

# EASM Platform Test Runner
# Comprehensive test execution script with various options

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
COVERAGE=false
PARALLEL=false
VERBOSE=false
REPORT=false
CATEGORY="all"
PROFILE=false

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if services are running
check_services() {
    print_status "Checking if required services are running..."

    # Check PostgreSQL
    if ! nc -z localhost 5432 2>/dev/null; then
        print_warning "PostgreSQL not detected on localhost:5432"
        print_warning "Integration tests may fail. Start with: docker-compose up -d postgres"
    else
        print_status "PostgreSQL detected"
    fi

    # Check Redis
    if ! nc -z localhost 6379 2>/dev/null; then
        print_warning "Redis not detected on localhost:6379"
    else
        print_status "Redis detected"
    fi

    # Check MinIO
    if ! nc -z localhost 9000 2>/dev/null; then
        print_warning "MinIO not detected on localhost:9000"
    else
        print_status "MinIO detected"
    fi
}

# Function to display help
show_help() {
    cat << EOF
EASM Platform Test Runner

Usage: ./run_tests.sh [OPTIONS]

OPTIONS:
    -h, --help              Show this help message
    -c, --coverage          Run with coverage report
    -p, --parallel          Run tests in parallel
    -v, --verbose           Verbose output
    -r, --report            Generate HTML coverage report
    --profile               Run with profiling

CATEGORIES:
    --unit                  Run only unit tests
    --integration           Run only integration tests
    --security              Run only security tests
    --performance           Run only performance tests
    --all                   Run all tests (default)

EXAMPLES:
    # Run all tests with coverage
    ./run_tests.sh --coverage

    # Run unit tests in parallel
    ./run_tests.sh --unit --parallel

    # Run security tests with verbose output
    ./run_tests.sh --security --verbose

    # Run all tests with coverage and HTML report
    ./run_tests.sh --coverage --report

    # Run performance tests with profiling
    ./run_tests.sh --performance --profile

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -p|--parallel)
            PARALLEL=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -r|--report)
            REPORT=true
            COVERAGE=true  # Report requires coverage
            shift
            ;;
        --profile)
            PROFILE=true
            shift
            ;;
        --unit)
            CATEGORY="unit"
            shift
            ;;
        --integration)
            CATEGORY="integration"
            shift
            ;;
        --security)
            CATEGORY="security"
            shift
            ;;
        --performance)
            CATEGORY="performance"
            shift
            ;;
        --all)
            CATEGORY="all"
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Banner
echo "========================================"
echo "  EASM Platform Test Suite"
echo "========================================"
echo ""

# Check services
check_services
echo ""

# Build pytest command
PYTEST_CMD="pytest"

# Add test files based on category
case $CATEGORY in
    unit)
        print_status "Running UNIT tests..."
        PYTEST_CMD="$PYTEST_CMD tests/test_secure_executor.py tests/test_repositories.py tests/test_models.py tests/test_discovery.py"
        ;;
    integration)
        print_status "Running INTEGRATION tests..."
        PYTEST_CMD="$PYTEST_CMD tests/test_integration_discovery.py"
        ;;
    security)
        print_status "Running SECURITY tests..."
        PYTEST_CMD="$PYTEST_CMD tests/test_security.py"
        ;;
    performance)
        print_status "Running PERFORMANCE tests..."
        PYTEST_CMD="$PYTEST_CMD tests/test_performance.py --durations=10"
        ;;
    all)
        print_status "Running ALL tests..."
        PYTEST_CMD="$PYTEST_CMD tests/"
        ;;
esac

# Add verbose flag
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -vv"
else
    PYTEST_CMD="$PYTEST_CMD -v"
fi

# Add parallel execution
if [ "$PARALLEL" = true ]; then
    print_status "Enabling parallel execution..."
    PYTEST_CMD="$PYTEST_CMD -n auto"
fi

# Add coverage
if [ "$COVERAGE" = true ]; then
    print_status "Enabling coverage tracking..."
    PYTEST_CMD="$PYTEST_CMD --cov=app --cov-report=term"

    if [ "$REPORT" = true ]; then
        PYTEST_CMD="$PYTEST_CMD --cov-report=html"
    fi
fi

# Add profiling
if [ "$PROFILE" = true ]; then
    print_status "Enabling profiling..."
    PYTEST_CMD="$PYTEST_CMD --profile"
fi

# Display command
echo ""
print_status "Executing: $PYTEST_CMD"
echo ""

# Run tests
if $PYTEST_CMD; then
    echo ""
    print_status "✓ All tests passed!"

    # Show coverage summary if enabled
    if [ "$COVERAGE" = true ]; then
        echo ""
        print_status "Coverage Summary:"
        coverage report --skip-empty

        if [ "$REPORT" = true ]; then
            print_status "HTML coverage report generated: htmlcov/index.html"
            print_status "Open with: open htmlcov/index.html"
        fi
    fi

    echo ""
    echo "========================================"
    echo -e "${GREEN}  TEST SUITE: PASSED${NC}"
    echo "========================================"
    exit 0
else
    echo ""
    print_error "✗ Some tests failed!"
    echo ""
    echo "========================================"
    echo -e "${RED}  TEST SUITE: FAILED${NC}"
    echo "========================================"
    exit 1
fi
