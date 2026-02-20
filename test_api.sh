#!/bin/bash

# Login and get token
LOGIN_RESP=$(curl -s -X POST http://localhost:18000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}')

TOKEN=$(echo "$LOGIN_RESP" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

echo "Token obtained: ${TOKEN:0:50}..."

# Test assets list
echo ""
echo "Testing assets list endpoint:"
curl -s -X GET "http://localhost:18000/api/v1/tenants/2/assets?page=1&page_size=5" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Test get first asset if available
ASSET_ID=$(curl -s -X GET "http://localhost:18000/api/v1/tenants/2/assets?page=1&page_size=1" \
  -H "Authorization: Bearer $TOKEN" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)

if [ -n "$ASSET_ID" ]; then
  echo ""
  echo "Testing asset detail endpoint for asset ID: $ASSET_ID"
  curl -s -X GET "http://localhost:18000/api/v1/tenants/2/assets/$ASSET_ID" \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
fi
