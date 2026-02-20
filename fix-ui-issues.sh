#!/bin/bash

# EASM UI Quick Fix Script
# This script performs common fixes for UI issues

set -e

echo "================================================"
echo "EASM UI Quick Fix Script"
echo "================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -d "frontend" ]; then
    echo -e "${RED}Error: frontend directory not found${NC}"
    echo "Please run this script from the easm root directory"
    exit 1
fi

echo -e "${YELLOW}Step 1: Checking Docker containers${NC}"
docker ps --filter "name=easm" --format "table {{.Names}}\t{{.Status}}"
echo ""

echo -e "${YELLOW}Step 2: Checking API health${NC}"
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:18000/ || echo "000")
if [ "$API_STATUS" = "200" ]; then
    echo -e "${GREEN}✓ API is responding (HTTP 200)${NC}"
else
    echo -e "${RED}✗ API is not responding (HTTP $API_STATUS)${NC}"
    echo "  Try: docker restart easm-api"
fi
echo ""

echo -e "${YELLOW}Step 3: Checking UI accessibility${NC}"
UI_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:13000/ || echo "000")
if [ "$UI_STATUS" = "200" ]; then
    echo -e "${GREEN}✓ UI is serving content (HTTP 200)${NC}"
else
    echo -e "${RED}✗ UI is not accessible (HTTP $UI_STATUS)${NC}"
    echo "  Try: docker restart easm-ui"
fi
echo ""

echo -e "${YELLOW}Step 4: Testing authentication${NC}"
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:18000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}' \
  | jq -r '.access_token' 2>/dev/null || echo "ERROR")

if [ "$LOGIN_RESPONSE" != "ERROR" ] && [ "$LOGIN_RESPONSE" != "null" ] && [ -n "$LOGIN_RESPONSE" ]; then
    echo -e "${GREEN}✓ Authentication working${NC}"
    echo "  Token: ${LOGIN_RESPONSE:0:50}..."

    # Test /me endpoint
    echo ""
    echo -e "${YELLOW}Step 5: Testing /me endpoint${NC}"
    ME_RESPONSE=$(curl -s -H "Authorization: Bearer $LOGIN_RESPONSE" \
      http://localhost:18000/api/v1/auth/me \
      | jq -r '.email' 2>/dev/null || echo "ERROR")

    if [ "$ME_RESPONSE" != "ERROR" ] && [ "$ME_RESPONSE" != "null" ]; then
        echo -e "${GREEN}✓ /me endpoint working${NC}"
        echo "  User: $ME_RESPONSE"
    else
        echo -e "${RED}✗ /me endpoint failed${NC}"
    fi
else
    echo -e "${RED}✗ Authentication failed${NC}"
    echo "  Check API logs: docker logs easm-api --tail 50"
fi
echo ""

echo -e "${YELLOW}Step 6: Checking UI container logs${NC}"
echo "Last 20 lines of UI logs:"
docker logs easm-ui --tail 20 2>&1 | grep -v "hmr update" | tail -10
echo ""

echo -e "${YELLOW}Step 7: Common fixes${NC}"
echo ""
echo "Option 1: Restart UI container"
echo "  docker restart easm-ui"
echo ""
echo "Option 2: Rebuild UI container"
echo "  docker-compose build ui && docker-compose up -d ui"
echo ""
echo "Option 3: Full system restart"
echo "  docker-compose restart"
echo ""
echo "Option 4: Clear browser cache"
echo "  1. Open http://localhost:13000"
echo "  2. Press Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)"
echo "  3. Or open in incognito/private window"
echo ""

echo "================================================"
echo "Summary"
echo "================================================"
echo ""

# Summary
if [ "$API_STATUS" = "200" ] && [ "$UI_STATUS" = "200" ] && [ "$LOGIN_RESPONSE" != "ERROR" ]; then
    echo -e "${GREEN}✓ All systems operational${NC}"
    echo ""
    echo "If UI still appears broken, check:"
    echo "1. Browser console (F12) for JavaScript errors"
    echo "2. Network tab for failed API requests"
    echo "3. Try different browser"
    echo "4. Clear browser cache and localStorage"
    echo ""
    echo "Test URLs:"
    echo "  - Login: http://localhost:13000/login"
    echo "  - Dashboard: http://localhost:13000/"
    echo "  - API Docs: http://localhost:18000/api/docs"
else
    echo -e "${RED}✗ Issues detected${NC}"
    echo ""
    echo "Run these commands to fix:"
    echo "  docker restart easm-api easm-ui"
    echo "  docker logs easm-api --tail 50"
    echo "  docker logs easm-ui --tail 50"
fi

echo ""
echo "For detailed diagnosis, see: UI_COMPREHENSIVE_DIAGNOSIS.md"
echo "For browser testing, run test script at: test-ui-comprehensive.js"
echo ""
