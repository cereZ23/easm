# EASM Platform - Company Onboarding Guide
**How to Add New Companies Without a UI**

---

## 🚀 Quick Start: Add a Company in 3 Steps

```bash
# Step 1: Create the tenant/company
# Step 2: Add seed domains
# Step 3: Trigger discovery scan
```

---

## Method 1: Using PostgreSQL CLI (Fastest)

### Step 1: Create a New Tenant/Company

```bash
docker-compose exec -T postgres psql -U easm -d easm << 'EOF'
-- Insert new company
INSERT INTO tenants (name, slug, created_at, updated_at)
VALUES ('Acme Corporation', 'acme-corp', NOW(), NOW())
RETURNING id, name, slug;
EOF
```

**Example Output:**
```
 id |      name        |    slug
----+------------------+-----------
  2 | Acme Corporation | acme-corp
```

**Note the `id` - you'll need it for the next steps!**

---

### Step 2: Add Seed Domains

```bash
# Replace TENANT_ID with the ID from Step 1
TENANT_ID=2

docker-compose exec -T postgres psql -U easm -d easm << EOF
-- Add root domains for scanning
INSERT INTO seeds (tenant_id, type, value, enabled, created_at, updated_at)
VALUES
  ($TENANT_ID, 'domain', 'acme.com', true, NOW(), NOW()),
  ($TENANT_ID, 'domain', 'acmecorp.com', true, NOW(), NOW()),
  ($TENANT_ID, 'domain', 'acme.io', true, NOW(), NOW());

-- Verify seeds were added
SELECT id, type, value, enabled FROM seeds WHERE tenant_id = $TENANT_ID;
EOF
```

---

### Step 3: Trigger Discovery Scan

```bash
# Option A: Trigger via Celery task
docker-compose exec -T worker python3 << EOF
from app.celery_app import celery
from app.tasks.discovery import run_tenant_discovery

# Trigger discovery for tenant ID 2
result = run_tenant_discovery.delay(2)
print(f"✅ Discovery task queued: {result.id}")
EOF
```

**OR**

```bash
# Option B: Run discovery directly
docker-compose exec -T worker python3 << 'EOF'
import sys
sys.path.insert(0, '/app')

from app.database import SessionLocal
from app.tasks.discovery import collect_seeds, run_parallel_enumeration
from app.tasks.enrichment import run_enrichment_pipeline

db = SessionLocal()
tenant_id = 2  # Replace with your tenant ID

print(f"🔍 Starting discovery for tenant {tenant_id}...")

# Step 1: Collect seeds
seed_data = collect_seeds(tenant_id)
print(f"📋 Seeds collected: {seed_data}")

# Step 2: Run enumeration
print(f"🌐 Running Amass + Subfinder...")
result = run_parallel_enumeration(seed_data, tenant_id)
print(f"✅ Found {len(result.get('subdomains', []))} subdomains")

db.close()
EOF
```

---

## Method 2: Using the REST API

### Step 1: Get API Token (if authentication is enabled)

```bash
# Login and get JWT token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your-password"
  }' | jq -r '.access_token')

echo "Token: $TOKEN"
```

---

### Step 2: Create Tenant via API

```bash
# Create new tenant
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "Acme Corporation",
    "slug": "acme-corp",
    "contact_email": "security@acme.com"
  }' | jq
```

**Example Response:**
```json
{
  "id": 2,
  "name": "Acme Corporation",
  "slug": "acme-corp",
  "contact_email": "security@acme.com",
  "created_at": "2025-10-26T18:00:00Z"
}
```

---

### Step 3: Add Seeds via API

```bash
# Add seed domains
TENANT_ID=2

curl -X POST http://localhost:8000/api/v1/tenants/$TENANT_ID/seeds \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "seeds": [
      {"type": "domain", "value": "acme.com"},
      {"type": "domain", "value": "acmecorp.com"},
      {"type": "domain", "value": "acme.io"}
    ]
  }' | jq
```

---

### Step 4: Trigger Scan via API

```bash
# Trigger discovery scan
curl -X POST http://localhost:8000/api/v1/tenants/$TENANT_ID/scans/discovery \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq
```

---

## Method 3: Using Python Script (Recommended for Bulk)

### Create a Company Onboarding Script

```bash
cat > /tmp/onboard_company.py << 'SCRIPT_EOF'
#!/usr/bin/env python3
"""
Quick company onboarding script for EASM platform
Usage: python3 onboard_company.py "Company Name" domain1.com domain2.com
"""
import sys
import psycopg2
from datetime import datetime

if len(sys.argv) < 3:
    print("Usage: python3 onboard_company.py 'Company Name' domain1.com [domain2.com ...]")
    print("Example: python3 onboard_company.py 'Acme Corp' acme.com acmecorp.com")
    sys.exit(1)

company_name = sys.argv[1]
domains = sys.argv[2:]

# Sanitize company name for slug
slug = company_name.lower().replace(' ', '-').replace('&', 'and')
slug = ''.join(c for c in slug if c.isalnum() or c == '-')

print(f"🏢 Onboarding: {company_name}")
print(f"📛 Slug: {slug}")
print(f"🌐 Domains: {', '.join(domains)}")
print()

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="easm",
    user="easm",
    password="ubAuUoBiFC661Ox0CtRIbMI5z"
)
cur = conn.cursor()

try:
    # Check if tenant already exists
    cur.execute("SELECT id, name FROM tenants WHERE slug = %s", (slug,))
    existing = cur.fetchone()

    if existing:
        tenant_id = existing[0]
        print(f"⚠️  Tenant already exists: {existing[1]} (ID: {tenant_id})")

        # Ask to continue
        response = input("Continue and add domains to existing tenant? (y/n): ")
        if response.lower() != 'y':
            print("❌ Cancelled")
            sys.exit(0)
    else:
        # Create tenant
        cur.execute("""
            INSERT INTO tenants (name, slug, created_at, updated_at)
            VALUES (%s, %s, NOW(), NOW())
            RETURNING id
        """, (company_name, slug))

        tenant_id = cur.fetchone()[0]
        conn.commit()
        print(f"✅ Created tenant: {company_name} (ID: {tenant_id})")

    # Add seed domains
    print(f"\n📋 Adding {len(domains)} seed domains...")

    for domain in domains:
        domain = domain.strip().lower()

        # Check if seed already exists
        cur.execute("""
            SELECT id FROM seeds
            WHERE tenant_id = %s AND type = 'domain' AND value = %s
        """, (tenant_id, domain))

        if cur.fetchone():
            print(f"   ⏭️  Skipped (already exists): {domain}")
        else:
            cur.execute("""
                INSERT INTO seeds (tenant_id, type, value, enabled, created_at, updated_at)
                VALUES (%s, 'domain', %s, true, NOW(), NOW())
            """, (tenant_id, domain))
            print(f"   ✅ Added: {domain}")

    conn.commit()

    # Show summary
    print()
    print("=" * 60)
    print("✅ ONBOARDING COMPLETE")
    print("=" * 60)
    print(f"Tenant ID: {tenant_id}")
    print(f"Company: {company_name}")
    print(f"Slug: {slug}")
    print(f"Domains: {len(domains)}")
    print()
    print("🚀 Next Steps:")
    print(f"   1. Trigger discovery: docker-compose exec -T worker python3 -c \"from app.tasks.discovery import run_tenant_discovery; run_tenant_discovery.delay({tenant_id})\"")
    print(f"   2. Check status: docker-compose exec -T postgres psql -U easm -d easm -c \"SELECT COUNT(*) FROM assets WHERE tenant_id = {tenant_id}\"")
    print(f"   3. View results: docker-compose exec -T postgres psql -U easm -d easm -c \"SELECT identifier FROM assets WHERE tenant_id = {tenant_id} LIMIT 10\"")
    print()

except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    sys.exit(1)
finally:
    cur.close()
    conn.close()
SCRIPT_EOF

chmod +x /tmp/onboard_company.py
```

### Use the Script

```bash
# Copy script into worker container
cat /tmp/onboard_company.py | docker-compose exec -T worker bash -c "cat > /tmp/onboard_company.py"

# Run it
docker-compose exec -T worker python3 /tmp/onboard_company.py "Tesla Inc" tesla.com teslamotors.com
```

**Example Output:**
```
🏢 Onboarding: Tesla Inc
📛 Slug: tesla-inc
🌐 Domains: tesla.com, teslamotors.com

✅ Created tenant: Tesla Inc (ID: 3)

📋 Adding 2 seed domains...
   ✅ Added: tesla.com
   ✅ Added: teslamotors.com

============================================================
✅ ONBOARDING COMPLETE
============================================================
Tenant ID: 3
Company: Tesla Inc
Slug: tesla-inc
Domains: 2

🚀 Next Steps:
   1. Trigger discovery
   2. Check status
   3. View results
```

---

## Method 4: Bulk CSV Import

### Create CSV File

```bash
cat > /tmp/companies.csv << 'EOF'
company_name,domain1,domain2,domain3
"Acme Corporation",acme.com,acmecorp.com,acme.io
"Tesla Inc",tesla.com,teslamotors.com,
"SpaceX",spacex.com,,
"Example Corp",example.com,example.org,example.net
EOF
```

### Import Script

```bash
cat > /tmp/bulk_import.py << 'SCRIPT_EOF'
#!/usr/bin/env python3
"""Bulk import companies from CSV"""
import csv
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="easm",
    user="easm",
    password="ubAuUoBiFC661Ox0CtRIbMI5z"
)
cur = conn.cursor()

with open('/tmp/companies.csv', 'r') as f:
    reader = csv.DictReader(f)

    for row in reader:
        company_name = row['company_name']
        slug = company_name.lower().replace(' ', '-').replace('&', 'and')
        slug = ''.join(c for c in slug if c.isalnum() or c == '-')

        # Collect all domains
        domains = [
            row.get('domain1', '').strip(),
            row.get('domain2', '').strip(),
            row.get('domain3', '').strip(),
        ]
        domains = [d for d in domains if d]  # Remove empty

        if not domains:
            print(f"⏭️  Skipped {company_name}: No domains")
            continue

        # Create tenant
        cur.execute("""
            INSERT INTO tenants (name, slug, created_at, updated_at)
            VALUES (%s, %s, NOW(), NOW())
            ON CONFLICT (slug) DO UPDATE SET updated_at = NOW()
            RETURNING id
        """, (company_name, slug))

        tenant_id = cur.fetchone()[0]

        # Add domains
        for domain in domains:
            cur.execute("""
                INSERT INTO seeds (tenant_id, type, value, enabled, created_at, updated_at)
                VALUES (%s, 'domain', %s, true, NOW(), NOW())
                ON CONFLICT DO NOTHING
            """, (tenant_id, domain))

        conn.commit()
        print(f"✅ {company_name} ({len(domains)} domains)")

cur.close()
conn.close()
print("\n✅ Bulk import complete!")
SCRIPT_EOF

# Run import
cat /tmp/companies.csv | docker-compose exec -T worker bash -c "cat > /tmp/companies.csv"
cat /tmp/bulk_import.py | docker-compose exec -T worker bash -c "cat > /tmp/bulk_import.py"
docker-compose exec -T worker python3 /tmp/bulk_import.py
```

---

## Verify Company Was Added

```bash
# List all companies
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT
  t.id,
  t.name,
  t.slug,
  COUNT(s.id) as seed_count,
  COUNT(a.id) as asset_count
FROM tenants t
LEFT JOIN seeds s ON t.id = s.tenant_id
LEFT JOIN assets a ON t.id = a.tenant_id
GROUP BY t.id, t.name, t.slug
ORDER BY t.created_at DESC;
"
```

---

## Trigger Full Scanning Pipeline

```bash
# Replace with your tenant ID
TENANT_ID=2

echo "🚀 Starting full reconnaissance pipeline for tenant $TENANT_ID..."

# Step 1: Discovery (Amass + Subfinder)
docker-compose exec -T worker python3 << EOF
from app.tasks.discovery import run_tenant_discovery
result = run_tenant_discovery($TENANT_ID)
print(f"✅ Discovery: {result}")
EOF

# Wait for discovery to complete (check progress)
sleep 30

# Step 2: Enrichment (HTTPx + Naabu + TLSx)
docker-compose exec -T worker python3 << EOF
from app.tasks.enrichment import run_enrichment_pipeline
from app.database import SessionLocal

db = SessionLocal()
asset_ids = db.execute("SELECT id FROM assets WHERE tenant_id = $TENANT_ID").fetchall()
asset_ids = [a[0] for a in asset_ids]

result = run_enrichment_pipeline.delay($TENANT_ID, asset_ids)
print(f"✅ Enrichment queued: {result.id}")
db.close()
EOF

# Step 3: Risk Scoring
docker-compose exec -T worker python3 << EOF
from app.tasks.scanning import calculate_comprehensive_risk_scores
result = calculate_comprehensive_risk_scores.delay($TENANT_ID)
print(f"✅ Risk scoring queued: {result.id}")
EOF
```

---

## Monitor Scanning Progress

```bash
TENANT_ID=2

# Watch asset discovery in real-time
watch -n 5 "docker-compose exec -T postgres psql -U easm -d easm -c \"
  SELECT
    'Assets' as metric, COUNT(*)::text as count FROM assets WHERE tenant_id = $TENANT_ID
  UNION ALL
  SELECT 'Services', COUNT(*)::text FROM services s
    JOIN assets a ON s.asset_id = a.id WHERE a.tenant_id = $TENANT_ID
  UNION ALL
  SELECT 'Certificates', COUNT(*)::text FROM certificates c
    JOIN assets a ON c.asset_id = a.id WHERE a.tenant_id = $TENANT_ID
\""
```

---

## Check Scan Results

```bash
TENANT_ID=2

# Full summary
docker-compose exec -T postgres psql -U easm -d easm << EOF
-- Company Overview
SELECT
  t.name as company,
  COUNT(DISTINCT a.id) as total_assets,
  COUNT(DISTINCT s.id) as services,
  COUNT(DISTINCT c.id) as certificates,
  ROUND(AVG(a.risk_score), 2) as avg_risk_score
FROM tenants t
LEFT JOIN assets a ON t.id = a.tenant_id AND a.is_active = true
LEFT JOIN services s ON a.id = s.asset_id
LEFT JOIN certificates c ON a.id = c.asset_id
WHERE t.id = $TENANT_ID
GROUP BY t.id, t.name;

-- Top 10 discovered subdomains
SELECT identifier, risk_score, last_seen::date
FROM assets
WHERE tenant_id = $TENANT_ID AND is_active = true
ORDER BY first_seen DESC
LIMIT 10;
EOF
```

---

## Export Results to CSV

```bash
TENANT_ID=2
COMPANY_NAME="acme-corp"

# Export all assets
docker-compose exec -T postgres psql -U easm -d easm -c "
COPY (
  SELECT
    a.identifier,
    a.type,
    a.risk_score,
    a.first_seen::date,
    a.last_seen::date,
    COUNT(DISTINCT s.id) as services_count,
    COUNT(DISTINCT c.id) as certificates_count
  FROM assets a
  LEFT JOIN services s ON a.id = s.asset_id
  LEFT JOIN certificates c ON a.id = c.asset_id
  WHERE a.tenant_id = $TENANT_ID AND a.is_active = true
  GROUP BY a.id, a.identifier, a.type, a.risk_score, a.first_seen, a.last_seen
  ORDER BY a.risk_score DESC NULLS LAST
) TO STDOUT WITH CSV HEADER
" > /tmp/${COMPANY_NAME}_assets.csv

echo "✅ Exported to /tmp/${COMPANY_NAME}_assets.csv"
```

---

## Complete Example: Add Company End-to-End

```bash
#!/bin/bash
# Complete company onboarding workflow

COMPANY_NAME="Example Corporation"
SLUG="example-corp"
DOMAINS=("example.com" "example.org" "example.net")

echo "🏢 Onboarding: $COMPANY_NAME"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Create tenant
echo "Step 1/5: Creating tenant..."
TENANT_ID=$(docker-compose exec -T postgres psql -U easm -d easm -t -c "
  INSERT INTO tenants (name, slug, created_at, updated_at)
  VALUES ('$COMPANY_NAME', '$SLUG', NOW(), NOW())
  RETURNING id
" | tr -d ' ')

echo "✅ Tenant created with ID: $TENANT_ID"

# 2. Add seeds
echo "Step 2/5: Adding ${#DOMAINS[@]} seed domains..."
for domain in "${DOMAINS[@]}"; do
  docker-compose exec -T postgres psql -U easm -d easm -c "
    INSERT INTO seeds (tenant_id, type, value, enabled, created_at, updated_at)
    VALUES ($TENANT_ID, 'domain', '$domain', true, NOW(), NOW())
  " > /dev/null
  echo "   ✅ $domain"
done

# 3. Trigger discovery
echo "Step 3/5: Starting discovery scan..."
docker-compose exec -T worker python3 -c "
from app.tasks.discovery import run_tenant_discovery
run_tenant_discovery.delay($TENANT_ID)
print('✅ Discovery queued')
"

# 4. Wait and check progress
echo "Step 4/5: Waiting for initial results (60 seconds)..."
sleep 60

# 5. Show results
echo "Step 5/5: Results summary..."
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT
  '📊 Total Assets' as metric,
  COUNT(*)::text as value
FROM assets WHERE tenant_id = $TENANT_ID
UNION ALL
SELECT
  '🌐 Subdomains',
  COUNT(*)::text
FROM assets WHERE tenant_id = $TENANT_ID AND type = 'subdomain'
"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Onboarding complete!"
echo "   Tenant ID: $TENANT_ID"
echo "   Company: $COMPANY_NAME"
echo ""
echo "🔍 View results:"
echo "   docker-compose exec -T postgres psql -U easm -d easm -c \"SELECT * FROM assets WHERE tenant_id = $TENANT_ID LIMIT 10\""
```

---

## Quick Reference Commands

```bash
# List all companies
docker-compose exec -T postgres psql -U easm -d easm -c "SELECT id, name, slug FROM tenants;"

# Add single domain to existing tenant
docker-compose exec -T postgres psql -U easm -d easm -c "
  INSERT INTO seeds (tenant_id, type, value, enabled, created_at, updated_at)
  VALUES (2, 'domain', 'newdomain.com', true, NOW(), NOW());
"

# Trigger scan for specific tenant
docker-compose exec -T worker python3 -c "from app.tasks.discovery import run_tenant_discovery; run_tenant_discovery.delay(2)"

# Check scan status
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT tenant_id, COUNT(*) as assets
  FROM assets
  GROUP BY tenant_id;
"

# Delete tenant (CAREFUL!)
docker-compose exec -T postgres psql -U easm -d easm -c "DELETE FROM tenants WHERE id = 2;"
```

---

## 🎯 Best Practices

1. **Always use unique slugs** - Prevents conflicts
2. **Validate domains** - Ensure they're owned by the client
3. **Start small** - Add 1-2 root domains first, expand later
4. **Monitor progress** - Check asset count after 5-10 minutes
5. **Schedule scans** - Use Celery Beat for recurring scans
6. **Export regularly** - Keep CSV backups of discoveries

---

## Troubleshooting

**Q: Tenant created but no assets found?**
```bash
# Check if seeds exist
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT * FROM seeds WHERE tenant_id = 2;
"

# Check Celery worker logs
docker-compose logs worker | tail -50
```

**Q: Discovery running forever?**
```bash
# Check Celery active tasks
docker-compose exec -T worker celery -A app.celery_app inspect active
```

**Q: How to re-run scan?**
```bash
# Just trigger discovery again - it will update existing assets
docker-compose exec -T worker python3 -c "from app.tasks.discovery import run_tenant_discovery; run_tenant_discovery.delay(2)"
```

---

**You're ready to onboard companies! Choose the method that works best for you:**
- **Quick & Simple**: PostgreSQL CLI (Method 1)
- **Production Ready**: Python Script (Method 3)
- **Bulk Import**: CSV Import (Method 4)
