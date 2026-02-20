# UI Onboarding Walkthrough for lessismore.fun

**How to Onboard a New Customer Using the UI**

---

## CURRENT LIMITATION

⚠️ **The UI doesn't have a self-service onboarding page yet.** This is one of the gaps we need to build for production.

For now, you need to:
1. Add customer via database (one-time setup)
2. Customer uses UI to view their data

---

## STEP-BY-STEP: Onboard lessismore.fun

### Step 1: Add Customer to Database (Admin Task - 2 minutes)

Open terminal and run:

```bash
cd /Users/cere/Downloads/easm

# Create tenant and add domain
docker-compose exec -T postgres psql -U easm -d easm << 'EOF'
-- Create tenant
INSERT INTO tenants (name, slug, created_at, updated_at)
VALUES ('Less Is More', 'lessismore', NOW(), NOW())
RETURNING id;

-- Add seed domain (use tenant ID from above, likely 3 or 4)
INSERT INTO seeds (tenant_id, type, value, enabled, created_at, updated_at)
VALUES (3, 'domain', 'lessismore.fun', true, NOW(), NOW());

-- Show what we created
SELECT t.id, t.name, t.slug, s.value as domain
FROM tenants t
LEFT JOIN seeds s ON t.id = s.tenant_id
WHERE t.slug = 'lessismore';
EOF
```

### Step 2: Trigger Initial Scan via API

```bash
# Get the tenant ID (from step 1)
TENANT_ID=3

# Trigger discovery scan
curl -X POST "http://localhost:8000/api/v1/tenants/${TENANT_ID}/scans/trigger" \
  -H "Content-Type: application/json" \
  -d '{
    "scan_type": "full_discovery",
    "priority": "high"
  }'
```

**This starts**:
- Amass + Subfinder subdomain enumeration (~30-45 min)
- DNSx resolution validation (~5 min)
- HTTPx service discovery (~10 min)
- Naabu port scanning (~15 min)
- TLSx certificate analysis (~5 min)

**Total time**: 1-2 hours

---

## Step 3: Customer Accesses UI

While scan is running, customer can log in and watch progress.

### Open UI in Browser

```
URL: http://localhost:13000
```

### Login Page

```
┌─────────────────────────────────────────────────┐
│                                                  │
│            🔒 EASM Platform                     │
│     External Attack Surface Management          │
│                                                  │
│  ┌────────────────────────────────────────┐    │
│  │ Email                                   │    │
│  │ ┌────────────────────────────────────┐ │    │
│  │ │ admin@example.com                  │ │    │
│  │ └────────────────────────────────────┘ │    │
│  │                                         │    │
│  │ Password                                │    │
│  │ ┌────────────────────────────────────┐ │    │
│  │ │ ••••••••••                         │ │    │
│  │ └────────────────────────────────────┘ │    │
│  │                                         │    │
│  │        [ Sign In ]                      │    │
│  └────────────────────────────────────────┘    │
│                                                  │
└─────────────────────────────────────────────────┘

Credentials:
Email:    admin@example.com
Password: admin123
```

---

## Step 4: View Dashboard (After Login)

### Tenant Selector

After login, you'll see a tenant selector dropdown:

```
┌─────────────────────────────────────────────────┐
│ EASM Platform  [Select Tenant ▼]  admin@... 👤 │
│                                                  │
│  Available Tenants:                             │
│  • Demo Organization (demo-org)                 │
│  • Less Is More (lessismore)      ← NEW!        │
│                                                  │
└─────────────────────────────────────────────────┘
```

Click "Less Is More" to switch to their data.

### Initial Dashboard (Scan in Progress)

```
┌─────────────────────────────────────────────────┐
│ EASM Platform        [Less Is More ▼]  admin 👤│
├─────────────────────────────────────────────────┤
│                                                  │
│  🔄 SCAN IN PROGRESS                            │
│                                                  │
│  Discovering attack surface for lessismore.fun  │
│                                                  │
│  ⏳ Estimated completion: 45 minutes             │
│                                                  │
│  Progress:                                       │
│  ✅ Subfinder enumeration complete               │
│  🔄 Amass enumeration running... (45%)           │
│  ⏸️ DNS resolution (waiting)                     │
│  ⏸️ Service discovery (waiting)                  │
│  ⏸️ Port scanning (waiting)                      │
│                                                  │
│  Current Results:                                │
│  • 12 subdomains discovered so far              │
│  • Scan started: 5 minutes ago                  │
│                                                  │
│  [Refresh Status]  [Cancel Scan]                │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## Step 5: View Results (After Scan Completes)

### Full Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│ EASM Platform        [Less Is More ▼]     admin@example 👤 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  📊 ATTACK SURFACE OVERVIEW                                 │
│                                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ 47           │ │ 15           │ │ 12           │       │
│  │ Assets       │ │ Services     │ │ Certificates │       │
│  │ lessismore   │ │ 13 HTTPS     │ │ ✅ All valid │       │
│  └──────────────┘ └──────────────┘ └──────────────┘       │
│                                                              │
│  🎯 FINDINGS BY SEVERITY                                    │
│  Critical: 0   ✅                                           │
│  High:     1   🟠  (Outdated Nginx)                        │
│  Medium:   3   🟡                                           │
│  Low:      2   🔵                                           │
│                                                              │
│  📈 RISK SCORE: 18.5/100 (LOW) ✅                           │
│                                                              │
│  🔥 Top Risk Assets:                                        │
│  1. staging.lessismore.fun     - 42/100 (Medium)           │
│  2. api.lessismore.fun         - 28/100 (Medium)           │
│  3. www.lessismore.fun         - 12/100 (Low)              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 6: Explore Assets

Click "Assets" in navigation:

```
┌─────────────────────────────────────────────────────────────┐
│ ASSETS (47)                                    [Search...🔍] │
├─────────────────────────────────────────────────────────────┤
│ Filters: [All Types ▼] [All Risk Levels ▼] [Active Only ☑]│
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Identifier                  Type      Risk    Last Seen     │
│ ─────────────────────────────────────────────────────────── │
│ staging.lessismore.fun     subdomain  42 🟡  2 hours ago   │
│ api.lessismore.fun         subdomain  28 🟡  2 hours ago   │
│ www.lessismore.fun         subdomain  12 🟢  2 hours ago   │
│ blog.lessismore.fun        subdomain  10 🟢  2 hours ago   │
│ cdn.lessismore.fun         subdomain  8  🟢  2 hours ago   │
│ mail.lessismore.fun        subdomain  5  🟢  2 hours ago   │
│ docs.lessismore.fun        subdomain  5  🟢  2 hours ago   │
│ ... (40 more)                                                │
│                                                              │
│ [< Prev]  Page 1 of 2  [Next >]                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Click on Highest Risk Asset

Click "staging.lessismore.fun":

```
┌─────────────────────────────────────────────────────────────┐
│ staging.lessismore.fun              Risk: 42/100 🟡 MEDIUM  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 📋 OVERVIEW                                                 │
│ Type:        Subdomain                                      │
│ IP:          104.21.45.123                                  │
│ First Seen:  2024-10-26 18:23:15                           │
│ Last Seen:   2024-10-26 20:15:42                           │
│                                                              │
│ 🎯 RISK BREAKDOWN                                           │
│ Findings:         +25  (1 high: outdated Nginx)             │
│ Port Exposure:    +0   (no high-risk ports)                 │
│ Certificate:      +12  (CN mismatch)                        │
│ Service Security: +5   (HTTP redirect missing)             │
│ Asset Age:        +0                                        │
│                                                              │
│ 🔌 SERVICES                                                 │
│ https://staging.lessismore.fun                              │
│   Status: 200 OK                                            │
│   Server: nginx/1.18.0                                      │
│   Tech:   React, Cloudflare                                 │
│                                                              │
│ 🔐 CERTIFICATE                                              │
│ Subject CN:  *.lessismore.fun                               │
│ Issuer:      Cloudflare                                     │
│ Valid Until: 2025-02-15 (111 days) ✅                       │
│ ⚠️ Warning:  CN is wildcard but covers this subdomain       │
│                                                              │
│ 🐛 FINDINGS (1 High, 1 Medium)                              │
│ [HIGH] Outdated Nginx Version                               │
│   Current: nginx/1.18.0                                     │
│   Latest:  nginx/1.24.0                                     │
│   Risk:    Known CVEs in old version                        │
│                                                              │
│ [MEDIUM] Missing HSTS Header                                │
│   Header: Strict-Transport-Security not set                 │
│   Risk:   Protocol downgrade attacks possible               │
│                                                              │
│ 💡 RECOMMENDED ACTIONS                                      │
│ 1. Upgrade Nginx to 1.24.0+ (fixes 3 CVEs)                 │
│ 2. Add HSTS header with max-age=31536000                    │
│                                                              │
│ [Export PDF] [Add to Watch List] [Mark as Fixed]           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 7: View All Services

Click "Services" tab:

```
┌─────────────────────────────────────────────────────────────┐
│ SERVICES (15)                              [Search...🔍]     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ URL                              Status  Server    Tech     │
│ ─────────────────────────────────────────────────────────── │
│ https://www.lessismore.fun       200     nginx     React    │
│ https://api.lessismore.fun       200     nginx     Node.js  │
│ https://staging.lessismore.fun   200     nginx     React    │
│ https://blog.lessismore.fun      200     Apache    WordPress│
│ https://docs.lessismore.fun      200     nginx     GitBook  │
│ http://cdn.lessismore.fun        301     Cloudflare -       │
│ ... (9 more)                                                 │
│                                                              │
│ Filters: [HTTPS Only ▼] [Status Code ▼] [Technology ▼]    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 8: Monitor Certificates

Click "Certificates" tab:

```
┌─────────────────────────────────────────────────────────────┐
│ CERTIFICATES (12)                          [Search...🔍]     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Asset                    CN              Expiry    Status   │
│ ─────────────────────────────────────────────────────────── │
│ www.lessismore.fun      lessismore.fun   111 days  ✅       │
│ api.lessismore.fun      *.lessismore.fun 111 days  ✅       │
│ staging.lessismore.fun  *.lessismore.fun 111 days  ✅       │
│ blog.lessismore.fun     lessismore.fun   111 days  ✅       │
│ ... (8 more)                                                 │
│                                                              │
│ All certificates valid! No action needed. ✅                │
│                                                              │
│ Filters: [Expiring Soon] [Expired] [Wildcard Only]         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 9: Review Findings

Click "Findings" tab:

```
┌─────────────────────────────────────────────────────────────┐
│ FINDINGS (6)                               [Search...🔍]     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Name                     Asset              Severity  Status│
│ ─────────────────────────────────────────────────────────── │
│ Outdated Nginx          staging.less...     HIGH      Open  │
│ Missing HSTS            staging.less...     MEDIUM    Open  │
│ X-Frame-Options Missing api.lessismore...   MEDIUM    Open  │
│ WordPress 6.2.0         blog.less...        MEDIUM    Open  │
│ Weak SSL Cipher         www.less...         LOW       Open  │
│ ... (1 more)                                                 │
│                                                              │
│ Filters: [Critical+High] [Open Only ☑] [Template ▼]       │
│                                                              │
│ [Export All] [Bulk Actions ▼]                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## WHAT'S MISSING: Self-Service Onboarding UI

### What We NEED to Build (Not Available Yet)

```
┌─────────────────────────────────────────────────────────────┐
│ EASM Platform - New Customer Onboarding                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Step 1: Company Information                                 │
│ ┌────────────────────────────────────────────────┐         │
│ │ Company Name: [Less Is More              ]    │         │
│ │ Website:      [https://lessismore.fun     ]    │         │
│ │ Industry:     [Technology ▼]                   │         │
│ │ Size:         [11-50 employees ▼]              │         │
│ └────────────────────────────────────────────────┘         │
│                                                              │
│ Step 2: Domains to Monitor                                  │
│ ┌────────────────────────────────────────────────┐         │
│ │ Domain 1: [lessismore.fun        ] [Remove]    │         │
│ │ Domain 2: [                      ] [Add More]  │         │
│ └────────────────────────────────────────────────┘         │
│                                                              │
│ Step 3: Scan Configuration                                  │
│ ┌────────────────────────────────────────────────┐         │
│ │ ☑ Daily full scans (2 AM)                      │         │
│ │ ☑ Critical asset monitoring (every 30 min)     │         │
│ │ ☑ Weekly vulnerability scanning                │         │
│ └────────────────────────────────────────────────┘         │
│                                                              │
│ Step 4: Alert Configuration                                 │
│ ┌────────────────────────────────────────────────┐         │
│ │ Email: [admin@lessismore.fun     ]            │         │
│ │ Slack: [https://hooks.slack...    ] (Optional)│         │
│ │                                                 │         │
│ │ Alert me on:                                    │         │
│ │ ☑ New subdomain discovered                     │         │
│ │ ☑ High-risk port exposed                       │         │
│ │ ☑ Certificate expiring soon                    │         │
│ │ ☑ Critical vulnerability found                 │         │
│ └────────────────────────────────────────────────┘         │
│                                                              │
│ [Cancel]                      [Start First Scan →]         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

This page doesn't exist yet! You need to build it for self-service onboarding.

---

## CURRENT WORKAROUND: Manual Onboarding

### For Now, Use This Process:

1. **Admin adds customer** (database command - 30 seconds)
2. **Admin triggers scan** (API call - 10 seconds)
3. **Customer logs into UI** (existing - works!)
4. **Customer views results** (existing - works!)

### Quick Onboarding Script

Save this as `onboard_customer.sh`:

```bash
#!/bin/bash
# Quick customer onboarding script

COMPANY_NAME="$1"
DOMAIN="$2"

if [ -z "$COMPANY_NAME" ] || [ -z "$DOMAIN" ]; then
    echo "Usage: ./onboard_customer.sh 'Company Name' domain.com"
    exit 1
fi

SLUG=$(echo "$COMPANY_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')

echo "🏢 Onboarding: $COMPANY_NAME"
echo "🌐 Domain: $DOMAIN"
echo "🔖 Slug: $SLUG"
echo ""

# Create tenant and seed
docker-compose exec -T postgres psql -U easm -d easm << EOF
BEGIN;

-- Create tenant
INSERT INTO tenants (name, slug, created_at, updated_at)
VALUES ('$COMPANY_NAME', '$SLUG', NOW(), NOW())
RETURNING id;

-- Add domain (using last inserted tenant_id)
INSERT INTO seeds (tenant_id, type, value, enabled, created_at, updated_at)
VALUES (currval('tenants_id_seq'), 'domain', '$DOMAIN', true, NOW(), NOW());

COMMIT;

-- Show results
SELECT t.id, t.name, t.slug, s.value as domain
FROM tenants t
JOIN seeds s ON t.id = s.tenant_id
WHERE t.slug = '$SLUG';
EOF

# Get tenant ID
TENANT_ID=$(docker-compose exec -T postgres psql -U easm -d easm -tc "SELECT id FROM tenants WHERE slug='$SLUG'" | xargs)

echo ""
echo "✅ Customer created! Tenant ID: $TENANT_ID"
echo ""
echo "🚀 Triggering initial scan..."

# Trigger scan
curl -s -X POST "http://localhost:8000/api/v1/tenants/${TENANT_ID}/scans/trigger" \
  -H "Content-Type: application/json" \
  -d '{"scan_type": "full_discovery", "priority": "high"}' | jq

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Onboarding Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Customer can now:"
echo "  1. Login at: http://localhost:13000"
echo "  2. Select tenant: $COMPANY_NAME"
echo "  3. View results in ~1-2 hours"
echo ""
echo "Next steps:"
echo "  - Create user account for customer"
echo "  - Send welcome email"
echo "  - Schedule onboarding call"
echo ""
```

Make it executable:
```bash
chmod +x onboard_customer.sh
```

Use it:
```bash
./onboard_customer.sh "Less Is More" "lessismore.fun"
```

---

## SUMMARY

### ✅ What Works Now (UI Features):
- Login/authentication
- Tenant selector dropdown
- Dashboard with stats and charts
- Assets list and detail views
- Services list
- Certificates list
- Findings list
- Search and filtering
- PDF export (via API)

### ❌ What's Missing (Need to Build):
- Self-service signup page
- Domain management UI (add/remove domains)
- Scan trigger button in UI
- Alert configuration page
- User management (invite team members)
- Billing/subscription management
- Settings page
- Help/documentation in UI

### Current Process:
1. **You (admin)** add customer via script: `./onboard_customer.sh "Less Is More" "lessismore.fun"`
2. **Customer** logs into UI and views their data
3. **Customer** can browse all discovered assets, services, certificates, findings

**Time to onboard**: ~2 minutes manual work + 1-2 hour scan

---

Ready to onboard lessismore.fun? Just run:

```bash
./onboard_customer.sh "Less Is More" "lessismore.fun"
```

Then the customer can log in at http://localhost:13000 and see their data!
