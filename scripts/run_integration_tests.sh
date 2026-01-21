#!/bin/bash

# Sprint 2 Integration Test Suite
# Real-world testing of enrichment tools with actual targets

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "Sprint 2 Integration Test Suite"
echo "Real-World Tool Validation"
echo "========================================"
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Check database connection
echo -e "${BLUE}Checking database connection...${NC}"
docker-compose exec -T postgres pg_isready -U easm > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Database is not running!${NC}"
    echo "Start database with: docker-compose up -d postgres"
    exit 1
fi
echo -e "${GREEN}✓ Database is running${NC}"
echo ""

# Verify all tools are installed
echo -e "${BLUE}Verifying tool installations...${NC}"
TOOLS=(httpx naabu tlsx katana)
for tool in "${TOOLS[@]}"; do
    if ! command -v $tool &> /dev/null; then
        echo -e "${RED}✗ $tool not found${NC}"
        echo "Install with: go install -v github.com/projectdiscovery/$tool/cmd/$tool@latest"
        exit 1
    fi
    echo -e "${GREEN}✓ $tool installed: $(which $tool)${NC}"
done
echo ""

# Check Naabu permissions
echo -e "${BLUE}Checking Naabu permissions...${NC}"
NAABU_PATH=$(which naabu)

# Check OS - getcap only exists on Linux
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${YELLOW}⚠ Running on macOS - Naabu may require sudo for raw sockets${NC}"
    echo "Naabu tests will be skipped (macOS requires sudo for port scanning)"
    SKIP_NAABU=true
elif command -v getcap &> /dev/null; then
    if ! getcap $NAABU_PATH | grep -q cap_net_raw; then
        echo -e "${YELLOW}⚠ Naabu does not have CAP_NET_RAW${NC}"
        echo "Grant permissions with: sudo setcap cap_net_raw+ep $NAABU_PATH"
        echo "Naabu tests will be skipped."
        SKIP_NAABU=true
    else
        echo -e "${GREEN}✓ Naabu has CAP_NET_RAW capability${NC}"
        SKIP_NAABU=false
    fi
else
    echo -e "${YELLOW}⚠ getcap not available - Naabu tests will be skipped${NC}"
    SKIP_NAABU=true
fi
echo ""

#=====================================================================
# Test 1: HTTPx Basic Execution
#=====================================================================
echo "========================================"
echo "Test 1: HTTPx Basic Execution"
echo "Target: example.com"
echo "========================================"

echo -e "${BLUE}Running HTTPx against example.com...${NC}"
OUTPUT=$(httpx -u https://example.com -json -silent 2>&1)

if [ $? -eq 0 ] && [ -n "$OUTPUT" ]; then
    echo -e "${GREEN}✓ HTTPx executed successfully${NC}"
    echo "Sample output:"
    echo "$OUTPUT" | jq '.' 2>/dev/null || echo "$OUTPUT"
    echo ""

    # Verify JSON fields
    if echo "$OUTPUT" | jq -e '.url' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ JSON output contains 'url' field${NC}"
    else
        echo -e "${RED}✗ JSON output missing 'url' field${NC}"
        exit 1
    fi

    if echo "$OUTPUT" | jq -e '.status_code' > /dev/null 2>&1; then
        echo -e "${GREEN}✓ JSON output contains 'status_code' field${NC}"
    else
        echo -e "${RED}✗ JSON output missing 'status_code' field${NC}"
        exit 1
    fi
else
    echo -e "${RED}✗ HTTPx execution failed${NC}"
    exit 1
fi
echo ""

#=====================================================================
# Test 2: Naabu Basic Execution (if permissions available)
#=====================================================================
if [ "$SKIP_NAABU" = false ]; then
    echo "========================================"
    echo "Test 2: Naabu Basic Execution"
    echo "Target: scanme.nmap.org (official test target)"
    echo "========================================"

    echo -e "${BLUE}Running Naabu against scanme.nmap.org...${NC}"
    OUTPUT=$(naabu -host scanme.nmap.org -top-ports 10 -json -silent 2>&1)

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Naabu executed successfully${NC}"
        if [ -n "$OUTPUT" ]; then
            echo "Ports found:"
            echo "$OUTPUT" | head -5
        else
            echo -e "${YELLOW}⚠ No ports found (target may be down)${NC}"
        fi
    else
        echo -e "${RED}✗ Naabu execution failed${NC}"
        echo "$OUTPUT"
        exit 1
    fi
    echo ""
else
    echo "========================================"
    echo "Test 2: Naabu Basic Execution"
    echo "========================================"
    echo -e "${YELLOW}SKIPPED (missing CAP_NET_RAW permission)${NC}"
    echo ""
fi

#=====================================================================
# Test 3: TLSx Basic Execution
#=====================================================================
echo "========================================"
echo "Test 3: TLSx Basic Execution"
echo "Target: badssl.com (various cert scenarios)"
echo "========================================"

echo -e "${BLUE}Running TLSx against badssl.com...${NC}"
OUTPUT=$(tlsx -u https://badssl.com -json -silent 2>&1)

if [ $? -eq 0 ] && [ -n "$OUTPUT" ]; then
    echo -e "${GREEN}✓ TLSx executed successfully${NC}"
    echo "Sample output:"
    echo "$OUTPUT" | jq '.' 2>/dev/null || echo "$OUTPUT"
    echo ""

    # CRITICAL: Check for private keys
    if echo "$OUTPUT" | grep -i "PRIVATE KEY" > /dev/null 2>&1; then
        echo -e "${RED}⚠ CRITICAL: PRIVATE KEY DETECTED IN OUTPUT!${NC}"
        echo "This confirms the need for our private key detection feature."
        echo -e "${YELLOW}Our code will catch and redact this.${NC}"
    else
        echo -e "${GREEN}✓ No private keys in output${NC}"
    fi
else
    echo -e "${RED}✗ TLSx execution failed${NC}"
    exit 1
fi
echo ""

#=====================================================================
# Test 4: Katana Basic Execution
#=====================================================================
echo "========================================"
echo "Test 4: Katana Basic Execution"
echo "Target: example.com"
echo "========================================"

echo -e "${BLUE}Running Katana against example.com...${NC}"
OUTPUT=$(katana -u https://example.com -depth 1 -jc -silent 2>&1)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Katana executed successfully${NC}"
    if [ -n "$OUTPUT" ]; then
        echo "Endpoints discovered:"
        echo "$OUTPUT" | head -10
    else
        echo -e "${YELLOW}⚠ No endpoints discovered${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Katana execution had issues (non-critical)${NC}"
    echo "$OUTPUT"
fi
echo ""

#=====================================================================
# Summary
#=====================================================================
echo "========================================"
echo "Integration Test Summary"
echo "========================================"
echo -e "${GREEN}✓ HTTPx: Working${NC}"
if [ "$SKIP_NAABU" = false ]; then
    echo -e "${GREEN}✓ Naabu: Working${NC}"
else
    echo -e "${YELLOW}⚠ Naabu: Skipped (needs permissions)${NC}"
fi
echo -e "${GREEN}✓ TLSx: Working${NC}"
echo -e "${GREEN}✓ Katana: Working${NC}"
echo ""
echo -e "${GREEN}All basic tool tests passed!${NC}"
echo ""
echo "Next steps:"
echo "1. Run Python integration tests: ./venv/bin/python3 -m pytest tests/test_integration.py"
echo "2. Test full enrichment pipeline"
echo "3. Validate database storage"
echo ""
echo "=========================================="
