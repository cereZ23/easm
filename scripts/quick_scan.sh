#!/bin/bash
set -e

DOMAIN=${1:-tesla.com}
TENANT_ID=2
TIMESTAMP=$(date +%s)

echo ""
echo "🚀 Starting reconnaissance scan for: $DOMAIN"
echo "   Tenant ID: $TENANT_ID"
echo "============================================================"

# Create work directory
WORKDIR="/tmp/easm_scan_${TIMESTAMP}"
mkdir -p "$WORKDIR"

# Run Subfinder
echo ""
echo "🔍 Running Subfinder..."
docker-compose exec -T worker subfinder -d "$DOMAIN" -silent > "$WORKDIR/subfinder.txt" 2>&1 &
SUBFINDER_PID=$!

# Run Amass (passive mode, timeout 2 minutes)
echo "🔍 Running Amass (passive)..."
timeout 120 docker-compose exec -T worker amass enum -passive -d "$DOMAIN" -timeout 2 > "$WORKDIR/amass.txt" 2>&1 || true

# Wait for subfinder
wait $SUBFINDER_PID 2>/dev/null || true

# Combine and deduplicate
cat "$WORKDIR/subfinder.txt" "$WORKDIR/amass.txt" | sort -u | grep -E "^[a-zA-Z0-9.-]+\.$DOMAIN$|^$DOMAIN$" > "$WORKDIR/all_subdomains.txt" 2>/dev/null || true
echo "$DOMAIN" >> "$WORKDIR/all_subdomains.txt"
sort -u "$WORKDIR/all_subdomains.txt" -o "$WORKDIR/all_subdomains.txt"

SUBDOMAIN_COUNT=$(wc -l < "$WORKDIR/all_subdomains.txt" | tr -d ' ')
echo "✅ Total unique subdomains found: $SUBDOMAIN_COUNT"

# Limit to first 20 for quick test
head -20 "$WORKDIR/all_subdomains.txt" > "$WORKDIR/targets.txt"
TARGET_COUNT=$(wc -l < "$WORKDIR/targets.txt" | tr -d ' ')

# Copy to worker container
docker cp "$WORKDIR/targets.txt" easm-worker:/tmp/targets.txt

# Run HTTPX
echo ""
echo "🌐 Running HTTPX on $TARGET_COUNT targets..."
docker-compose exec -T worker httpx -l /tmp/targets.txt -silent -json -title -tech-detect -status-code -web-server -timeout 10 -retries 1 > "$WORKDIR/httpx.json" 2>&1 || true

HTTP_COUNT=$(cat "$WORKDIR/httpx.json" | wc -l | tr -d ' ')
echo "✅ HTTPX probed $HTTP_COUNT web services"

# Insert into database
echo ""
echo "💾 Inserting data into database..."

# Insert root domain
docker-compose exec -T postgres psql -U easm -d easm <<EOF
-- Insert root domain
INSERT INTO assets (tenant_id, type, identifier, priority, is_active, first_seen, last_seen)
VALUES ($TENANT_ID, 'DOMAIN', '$DOMAIN', 'high', true, NOW(), NOW())
ON CONFLICT (tenant_id, identifier) DO UPDATE
SET last_seen = NOW(), is_active = true;
EOF

# Insert subdomains
while IFS= read -r subdomain; do
    if [ "$subdomain" != "$DOMAIN" ]; then
        docker-compose exec -T postgres psql -U easm -d easm -c "
            INSERT INTO assets (tenant_id, type, identifier, priority, is_active, first_seen, last_seen)
            VALUES ($TENANT_ID, 'SUBDOMAIN', '$subdomain', 'medium', true, NOW(), NOW())
            ON CONFLICT (tenant_id, identifier) DO UPDATE
            SET last_seen = NOW(), is_active = true;
        " 2>/dev/null || true
    fi
done < "$WORKDIR/all_subdomains.txt"

echo "✅ Inserted subdomains"

# Parse and insert HTTP data
if [ -s "$WORKDIR/httpx.json" ]; then
    cat "$WORKDIR/httpx.json" | jq -r '. | @json' 2>/dev/null | while read -r line; do
        HOST=$(echo "$line" | jq -r '.host // .url' | sed 's|https\?://||' | cut -d'/' -f1 | cut -d':' -f1)
        PORT=$(echo "$line" | jq -r '.port // (if .url | contains("https") then 443 else 80 end)')
        TITLE=$(echo "$line" | jq -r '.title // ""' | sed "s/'/''/g")
        STATUS=$(echo "$line" | jq -r '.status_code // 0')
        WEBSERVER=$(echo "$line" | jq -r '.webserver // ""' | sed "s/'/''/g")
        HAS_TLS=$(echo "$line" | jq -r 'if .url | contains("https") then true else false end')

        docker-compose exec -T postgres psql -U easm -d easm <<EOSQL 2>/dev/null || true
DO \$\$
DECLARE
    v_asset_id INT;
BEGIN
    SELECT id INTO v_asset_id FROM assets WHERE tenant_id = $TENANT_ID AND identifier = '$HOST';

    IF v_asset_id IS NOT NULL THEN
        INSERT INTO services (asset_id, port, protocol, product, http_title, http_status, web_server, has_tls, first_seen, last_seen)
        VALUES (v_asset_id, $PORT, 'tcp', 'http', '$TITLE', $STATUS, '$WEBSERVER', $HAS_TLS, NOW(), NOW())
        ON CONFLICT DO NOTHING;
    END IF;
END \$\$;
EOSQL
    done

    echo "✅ Inserted HTTP services"
fi

echo ""
echo "============================================================"
echo "✅ Scan complete! Check the UI at http://localhost:13000"
echo "   - Total subdomains discovered: $SUBDOMAIN_COUNT"
echo "   - Web services probed: $HTTP_COUNT"
echo "   - Data in database for tenant: $TENANT_ID"
echo "============================================================"
echo ""

# Cleanup
rm -rf "$WORKDIR"
