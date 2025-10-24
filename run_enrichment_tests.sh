#!/bin/bash

# Sprint 2 Enrichment Test Runner
# Executes comprehensive test suite for enrichment infrastructure

set -e  # Exit on error

echo "========================================"
echo "Sprint 2 Enrichment Test Suite"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Check if database is running
echo -e "${YELLOW}Checking database connection...${NC}"
docker-compose exec postgres pg_isready -U easm > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Database is not running!${NC}"
    echo "Start database with: docker-compose up -d postgres"
    exit 1
fi
echo -e "${GREEN}✓ Database is running${NC}"
echo ""

# Run enrichment task tests
echo "========================================"
echo "1. Testing Enrichment Tasks"
echo "========================================"
pytest tests/test_enrichment_tasks.py -v --tb=short --color=yes

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Enrichment task tests passed${NC}"
else
    echo -e "${RED}✗ Enrichment task tests failed${NC}"
    exit 1
fi
echo ""

# Run repository tests
echo "========================================"
echo "2. Testing Enrichment Repositories"
echo "========================================"
pytest tests/test_enrichment_repositories.py -v --tb=short --color=yes

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Repository tests passed${NC}"
else
    echo -e "${RED}✗ Repository tests failed${NC}"
    exit 1
fi
echo ""

# Run all enrichment tests with coverage
echo "========================================"
echo "3. Running Full Test Suite with Coverage"
echo "========================================"
pytest tests/test_enrichment_*.py \
    --cov=app.tasks.enrichment \
    --cov=app.repositories.service_repository \
    --cov=app.repositories.certificate_repository \
    --cov=app.repositories.endpoint_repository \
    --cov-report=term-missing \
    --cov-report=html:htmlcov/enrichment \
    -v

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed with coverage report${NC}"
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
echo ""

# Performance benchmarks
echo "========================================"
echo "4. Running Performance Benchmarks"
echo "========================================"
pytest tests/test_enrichment_repositories.py::TestServiceRepository::test_bulk_upsert_performance -v

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Performance benchmarks passed${NC}"
else
    echo -e "${YELLOW}⚠ Performance benchmarks failed (may need optimization)${NC}"
fi
echo ""

# Summary
echo "========================================"
echo "Test Suite Summary"
echo "========================================"
echo -e "${GREEN}✓ All enrichment tests passed${NC}"
echo ""
echo "Coverage report: htmlcov/enrichment/index.html"
echo ""
echo "Next steps:"
echo "1. Review coverage report: open htmlcov/enrichment/index.html"
echo "2. Run integration tests with real tools (HTTPx, Naabu, etc.)"
echo "3. Deploy to staging environment"
echo ""
echo "========================================"
