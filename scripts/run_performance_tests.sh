#!/bin/bash
#
# Run comprehensive performance tests for EASM enrichment pipeline
# This script executes performance benchmarks and generates optimization reports
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}EASM Enrichment Performance Test Suite${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if virtual environment is activated
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate || {
        echo -e "${RED}Failed to activate virtual environment${NC}"
        exit 1
    }
fi

# Install required packages for benchmarking
echo -e "${YELLOW}Installing benchmark dependencies...${NC}"
pip install -q pytest-benchmark numpy

# Create results directory
RESULTS_DIR="test_results/performance"
mkdir -p "$RESULTS_DIR"

# Start Docker services if not running
echo -e "${YELLOW}Checking Docker services...${NC}"
if ! docker ps | grep -q easm-postgres; then
    echo -e "${YELLOW}Starting Docker services...${NC}"
    docker-compose up -d postgres redis
    echo "Waiting for services to be ready..."
    sleep 10
fi

# Run different performance test suites
echo -e "${GREEN}Running performance tests...${NC}"

# 1. Tool Execution Performance
echo -e "\n${YELLOW}1. Testing Tool Execution Performance...${NC}"
pytest tests/performance/test_enrichment_performance.py::TestToolExecutionPerformance \
    -v \
    --benchmark-only \
    --benchmark-json="$RESULTS_DIR/tools_benchmark.json" \
    --benchmark-histogram="$RESULTS_DIR/tools_histogram" \
    2>&1 | tee "$RESULTS_DIR/tools_output.log"

# 2. Database Performance
echo -e "\n${YELLOW}2. Testing Database Performance...${NC}"
pytest tests/performance/test_enrichment_performance.py::TestDatabasePerformance \
    -v \
    --benchmark-only \
    --benchmark-json="$RESULTS_DIR/db_benchmark.json" \
    --benchmark-histogram="$RESULTS_DIR/db_histogram" \
    2>&1 | tee "$RESULTS_DIR/db_output.log"

# 3. Concurrent Execution
echo -e "\n${YELLOW}3. Testing Concurrent Execution...${NC}"
pytest tests/performance/test_enrichment_performance.py::TestConcurrentExecution \
    -v \
    --benchmark-only \
    --benchmark-json="$RESULTS_DIR/concurrent_benchmark.json" \
    2>&1 | tee "$RESULTS_DIR/concurrent_output.log"

# 4. Stress Testing (optional, takes longer)
if [[ "$1" == "--stress" ]]; then
    echo -e "\n${YELLOW}4. Running Stress Tests...${NC}"
    pytest tests/performance/test_enrichment_performance.py::TestStressTesting \
        -v \
        -s \
        2>&1 | tee "$RESULTS_DIR/stress_output.log"
else
    echo -e "\n${YELLOW}4. Skipping stress tests (use --stress to enable)${NC}"
fi

# Generate performance report
echo -e "\n${YELLOW}Generating Performance Report...${NC}"
python -c "
from tests.performance.test_enrichment_performance import generate_performance_report
report = generate_performance_report('$RESULTS_DIR/performance_report.md')
print('Report generated successfully')
"

# Summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Performance Test Summary${NC}"
echo -e "${GREEN}========================================${NC}"

# Check for performance regressions
echo -e "\n${YELLOW}Analyzing results for regressions...${NC}"

# Parse JSON results and check against baselines
python -c "
import json
import os
from pathlib import Path

results_dir = Path('$RESULTS_DIR')
regression_found = False

# Define performance baselines (in seconds)
BASELINES = {
    'test_httpx_performance_small': 1.0,
    'test_httpx_performance_medium': 3.0,
    'test_httpx_performance_large': 6.0,
    'test_bulk_insert_small': 0.5,
    'test_bulk_insert_medium': 2.0,
    'test_bulk_insert_large': 15.0,
    'test_parallel_tool_execution_5': 2.0,
    'test_parallel_tool_execution_10': 3.0,
}

# Check each benchmark file
for json_file in results_dir.glob('*_benchmark.json'):
    try:
        with open(json_file) as f:
            data = json.load(f)

        for benchmark in data.get('benchmarks', []):
            name = benchmark['name']
            mean = benchmark['stats']['mean']

            if name in BASELINES:
                baseline = BASELINES[name]
                if mean > baseline * 1.2:  # 20% regression threshold
                    print(f'  ⚠️  REGRESSION: {name} - {mean:.3f}s (baseline: {baseline}s)')
                    regression_found = True
                else:
                    print(f'  ✓  {name}: {mean:.3f}s (baseline: {baseline}s)')
    except Exception as e:
        print(f'  Error parsing {json_file.name}: {e}')

if regression_found:
    print('\\n⚠️  Performance regressions detected!')
    exit(1)
else:
    print('\\n✅  All performance benchmarks passed!')
"

# Display key metrics
echo -e "\n${YELLOW}Key Performance Metrics:${NC}"
echo "----------------------------------------"

# Extract and display key metrics
grep -E "(URLs/second|records/second|parallel|memory|throughput)" "$RESULTS_DIR"/*.log | \
    sed 's/.*\///' | \
    sed 's/.log:/: /' | \
    head -20

# Location of results
echo -e "\n${GREEN}Results saved to: $RESULTS_DIR${NC}"
echo -e "  - Benchmark JSONs: $RESULTS_DIR/*.json"
echo -e "  - Histograms: $RESULTS_DIR/*_histogram.svg"
echo -e "  - Performance Report: $RESULTS_DIR/performance_report.md"
echo -e "  - Test Logs: $RESULTS_DIR/*.log"

# Cleanup test database
echo -e "\n${YELLOW}Cleaning up test database...${NC}"
docker exec easm-postgres psql -U easm -c "DROP DATABASE IF EXISTS easm_perf_test;" 2>/dev/null || true

echo -e "\n${GREEN}Performance testing complete!${NC}"

# Exit with appropriate code
if [[ -f "$RESULTS_DIR/performance_report.md" ]]; then
    echo -e "\n${GREEN}✅ Performance tests completed successfully${NC}"
    exit 0
else
    echo -e "\n${RED}❌ Performance tests failed${NC}"
    exit 1
fi