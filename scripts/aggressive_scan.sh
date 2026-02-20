#!/bin/bash
set -e

DOMAIN=${1:-tesla.com}
TENANT_ID=2
TIMESTAMP=$(date +%s)
WORKDIR="/tmp/easm_aggressive_${TIMESTAMP}"

mkdir -p "$WORKDIR"

echo ""
echo "🚀 AGGRESSIVE RECONNAISSANCE SCAN"
echo "   Domain: $DOMAIN"
echo "   Tenant: $TENANT_ID"
echo "   Working Dir: $WORKDIR"
echo "============================================================"
echo ""

# Run Subfinder with all sources
echo "🔍 [1/3] Running Subfinder (all sources)..."
docker-compose exec -T worker subfinder \
  -d "$DOMAIN" \
  -all \
  -recursive \
  -silent \
  -timeout 10 \
  > "$WORKDIR/subfinder.txt" 2>&1 &
SUBFINDER_PID=$!

# Run Amass ACTIVE enumeration (no -passive flag!)
echo "🔍 [2/3] Running Amass ACTIVE enumeration (this takes ~20 minutes)..."
docker-compose exec -T worker timeout 1800 amass enum \
  -d "$DOMAIN" \
  -brute \
  -min-for-recursive 2 \
  -timeout 30 \
  > "$WORKDIR/amass.txt" 2>&1 &
AMASS_PID=$!

echo ""
echo "⏳ Scans running in background..."
echo "   Subfinder PID: $SUBFINDER_PID"
echo "   Amass PID: $AMASS_PID"
echo ""

# Wait for Subfinder (should finish in ~2-3 minutes)
echo "⏳ Waiting for Subfinder to complete..."
wait $SUBFINDER_PID 2>/dev/null || true
SUBFINDER_COUNT=$(wc -l < "$WORKDIR/subfinder.txt" | tr -d ' ')
echo "✅ Subfinder complete: $SUBFINDER_COUNT subdomains"

# Wait for Amass (takes 20-30 minutes)
echo "⏳ Waiting for Amass to complete (this will take ~20 minutes)..."
echo "   Started at: $(date)"
wait $AMASS_PID 2>/dev/null || true
AMASS_COUNT=$(wc -l < "$WORKDIR/amass.txt" | tr -d ' ')
echo "✅ Amass complete: $AMASS_COUNT subdomains"
echo "   Finished at: $(date)"

# Merge and deduplicate
echo ""
echo "🔄 [3/3] Merging and deduplicating results..."
cat "$WORKDIR/subfinder.txt" "$WORKDIR/amass.txt" | \
  grep -E "^[a-zA-Z0-9.-]+\.$DOMAIN$|^$DOMAIN$" | \
  sort -u > "$WORKDIR/all_subdomains.txt" 2>/dev/null || true

echo "$DOMAIN" >> "$WORKDIR/all_subdomains.txt"
sort -u "$WORKDIR/all_subdomains.txt" -o "$WORKDIR/all_subdomains.txt"

TOTAL_COUNT=$(wc -l < "$WORKDIR/all_subdomains.txt" | tr -d ' ')
echo "✅ Total unique subdomains: $TOTAL_COUNT"

# Insert into database
echo ""
echo "💾 Inserting subdomains into database..."

# Insert root domain
docker-compose exec -T postgres psql -U easm -d easm <<EOSQL >/dev/null 2>&1
INSERT INTO assets (tenant_id, type, identifier, priority, is_active, first_seen, last_seen)
VALUES ($TENANT_ID, 'DOMAIN', '$DOMAIN', 'high', true, NOW(), NOW())
ON CONFLICT (tenant_id, identifier) DO UPDATE
SET last_seen = NOW(), is_active = true;
EOSQL

# Insert subdomains in batches
INSERTED=0
while IFS= read -r subdomain; do
    if [ "$subdomain" != "$DOMAIN" ] && [ -n "$subdomain" ]; then
        docker-compose exec -T postgres psql -U easm -d easm -c "
            INSERT INTO assets (tenant_id, type, identifier, priority, is_active, first_seen, last_seen)
            VALUES ($TENANT_ID, 'SUBDOMAIN', '$subdomain', 'medium', true, NOW(), NOW())
            ON CONFLICT (tenant_id, identifier) DO UPDATE
            SET last_seen = NOW(), is_active = true;
        " >/dev/null 2>&1 && ((INSERTED++))

        # Progress indicator every 50 subdomains
        if [ $((INSERTED % 50)) -eq 0 ]; then
            echo "   Inserted $INSERTED subdomains..."
        fi
    fi
done < "$WORKDIR/all_subdomains.txt"

echo "✅ Inserted $INSERTED subdomains into database"

# Verify in database
DB_COUNT=$(docker-compose exec -T postgres psql -U easm -d easm -t -c \
  "SELECT COUNT(*) FROM assets WHERE tenant_id = $TENANT_ID AND identifier LIKE '%$DOMAIN%'" | tr -d ' ')

echo ""
echo "============================================================"
echo "✅ AGGRESSIVE SCAN COMPLETE!"
echo ""
echo "   Subfinder found:    $SUBFINDER_COUNT"
echo "   Amass found:        $AMASS_COUNT"
echo "   Total unique:       $TOTAL_COUNT"
echo "   Inserted to DB:     $INSERTED"
echo "   Database total:     $DB_COUNT"
echo ""
echo "   Results saved to: $WORKDIR"
echo "   View in UI: http://localhost:13000"
echo "============================================================"
echo ""

# Save summary
cat > "$WORKDIR/summary.txt" <<SUMMARY
Aggressive Scan Summary
=======================
Domain: $DOMAIN
Started: $(date)
Duration: ~20-30 minutes

Results:
- Subfinder: $SUBFINDER_COUNT subdomains
- Amass: $AMASS_COUNT subdomains
- Total Unique: $TOTAL_COUNT subdomains
- Inserted: $INSERTED subdomains
- Database Total: $DB_COUNT assets

Working Directory: $WORKDIR
SUMMARY

echo "📝 Summary saved to: $WORKDIR/summary.txt"
