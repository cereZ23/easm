# EASM Platform - UI Usage Guide

**Complete Guide to Using the Web Interface**

---

## Quick Access

**URL**: http://localhost:13000

**Default Credentials**:
- Email: `admin@example.com`
- Password: See "First Time Login" section below

---

## First Time Login

### Option 1: Reset Admin Password (Recommended)

```bash
# Navigate to project directory
cd /Users/cere/Downloads/easm

# Reset admin password to "admin123" (change after first login!)
docker-compose exec -T postgres psql -U easm -d easm -c "
UPDATE users
SET hashed_password = '\$2b\$12\$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyKcpZL0m0K6'
WHERE username = 'admin';
"

# Now login with:
# Email: admin@example.com
# Password: admin123
```

### Option 2: Create New User via Database

```bash
# Create a new user with your email
docker-compose exec -T postgres psql -U easm -d easm -c "
INSERT INTO users (username, email, hashed_password, is_active, created_at, updated_at)
VALUES (
  'your-username',
  'you@company.com',
  '\$2b\$12\$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyKcpZL0m0K6',  -- password: admin123
  true,
  NOW(),
  NOW()
);
"

# Login with your email and password: admin123
```

---

## UI Overview

The EASM Platform UI is a modern Vue.js dashboard with:

- **Dark Mode Support**: Toggle in navigation bar
- **Multi-Tenant**: Switch between organizations
- **Real-time Data**: Live updates from reconnaissance
- **Charts & Visualizations**: Risk distribution, severity charts
- **Responsive Design**: Works on desktop, tablet, mobile

---

## Main Navigation

After logging in, you'll see the main navigation:

```
┌─────────────────────────────────────────────────┐
│ EASM Platform      [Tenant Selector]  [Profile] │
├─────────────────────────────────────────────────┤
│ • Dashboard                                      │
│ • Assets                                         │
│ • Services                                       │
│ • Certificates                                   │
│ • Findings                                       │
└─────────────────────────────────────────────────┘
```

---

## Page-by-Page Guide

### 1. Dashboard (Home Page)

**URL**: http://localhost:13000/

**What You'll See**:
- **4 Stats Cards** (top):
  - Total Assets (471 for Tesla demo)
  - Services (115 live services)
  - Certificates (107 monitored)
  - Open Findings (severity breakdown)

- **Charts**:
  - Finding Severity Distribution (Doughnut chart)
  - Asset Risk Distribution (Bar chart)

- **Recent Activity**: Latest discoveries and changes
- **Assets by Type**: Breakdown (subdomains, IPs, etc.)

**Use Cases**:
- Quick health check of attack surface
- Identify critical/high-risk findings at a glance
- See recent changes to infrastructure

---

### 2. Assets Page

**URL**: http://localhost:13000/assets

**Features**:
- **Search**: Filter by identifier (domain, subdomain)
- **Type Filter**: subdomain, domain, ip, url, service
- **Risk Score Sorting**: Sort by risk (0-100)
- **Pagination**: Browse large asset inventories

**Table Columns**:
- Identifier (clickable)
- Type
- Risk Score (color-coded: green/yellow/orange/red)
- First Seen
- Last Seen
- Status (Active/Inactive)

**How to Use**:
1. Click "Assets" in navigation
2. Use search box to find specific domains
3. Click on any asset to see full details
4. Filter by type or risk level
5. Export to CSV for reports

---

### 3. Asset Detail Page

**URL**: http://localhost:13000/assets/[ID]

**Sections**:
- **Overview**: Asset metadata, risk score breakdown
- **Associated Services**: All HTTP/HTTPS endpoints
- **Certificates**: TLS certificates for this asset
- **Findings**: Vulnerabilities discovered
- **Timeline**: Discovery and change history

**Risk Score Breakdown**:
```
Total Risk: 42.5 / 100 (HIGH)

Components:
  - Findings Score: 25.0 (2 high, 3 medium vulnerabilities)
  - Certificate Score: 12.0 (1 expiring cert)
  - Port Exposure: 0.0 (no high-risk ports)
  - Service Security: 5.5 (1 login page exposed)
  - Asset Age: 0.0 (discovered 30 days ago)
```

**Actions**:
- Trigger manual scan
- Add to monitoring watchlist
- Export asset report
- View full timeline

---

### 4. Services Page

**URL**: http://localhost:13000/services

**What You'll See**:
- All discovered HTTP/HTTPS services
- Port scanning results
- Technology detection (from HTTPx)

**Table Columns**:
- Asset (domain)
- Protocol (http/https)
- Port (80, 443, 8080, etc.)
- Status Code (200, 301, 403, etc.)
- Title (from HTTP response)
- Technologies (detected frameworks)
- Server (web server software)
- Last Seen

**Filters**:
- Protocol (HTTP only, HTTPS only)
- Port (specific ports)
- Status code ranges
- Technology stack

**Use Cases**:
- Find all WordPress sites: Filter by "Technologies: WordPress"
- Find admin panels: Search title for "admin", "login", "console"
- Identify outdated software: Filter by server version
- Find HTTP services needing TLS: Filter "Protocol: http"

---

### 5. Certificates Page

**URL**: http://localhost:13000/certificates

**Features**:
- TLS certificate monitoring
- Expiration tracking
- Certificate mismatch detection

**Table Columns**:
- Asset (domain)
- Subject CN (certificate common name)
- Issuer (CA)
- Valid From
- Valid Until
- Days Until Expiry (color-coded)
- Is Wildcard
- Status (Valid/Expired/Expiring)

**Alerts**:
- **Red Badge**: Expired certificates
- **Orange Badge**: Expiring within 30 days
- **Yellow Badge**: CN mismatch with domain

**Filters**:
- Expiring Soon (< 90 days, < 30 days)
- Expired Only
- Wildcard Certificates
- Certificate Issuer

**Use Cases**:
- Track certificate renewals
- Find expired certificates before they cause outages
- Identify certificate mismatches (security issue)
- Audit certificate authorities in use

---

### 6. Findings Page

**URL**: http://localhost:13000/findings

**What You'll See**:
- Nuclei vulnerability scan results
- Severity-based filtering
- Status tracking (open/fixed/suppressed)

**Table Columns**:
- Name (vulnerability/misconfiguration)
- Asset (affected domain)
- Severity (Critical, High, Medium, Low, Info)
- Template ID (Nuclei template)
- CVSS Score
- Status
- First Seen
- Last Seen

**Filters**:
- **Severity**: Critical, High, Medium, Low, Info
- **Status**: Open, Fixed, Suppressed, False Positive
- **Template Category**: CVE, Misconfiguration, Exposed Panel, Default Credentials
- **Date Range**: Discovered in last 24h, 7d, 30d

**Actions per Finding**:
- View full details (click row)
- Mark as fixed
- Suppress (false positive)
- Export to PDF
- Create JIRA ticket (if integrated)

---

### 7. Finding Detail Page

**URL**: http://localhost:13000/findings/[ID]

**Sections**:

**Overview**:
- Finding name and description
- Severity badge
- CVSS score and vector
- CWE reference
- CVE IDs (if applicable)

**Evidence**:
```
Request:
GET /admin/login HTTP/1.1
Host: example.tesla.com

Response:
HTTP/1.1 200 OK
<html><title>Admin Login</title>...
```

**Affected Asset**:
- Direct link to asset detail
- Asset risk score
- Related findings on same asset

**Remediation**:
- Recommended fix
- References (CVE, CWE, vendor advisories)
- Priority based on risk score

**Timeline**:
- First discovered
- Last confirmed present
- Status changes (open → fixed → reopened)

---

## How to Add a Company via UI

Currently, tenant/company creation is done via backend (see COMPANY_ONBOARDING_GUIDE.md).

**Quick Workaround**:

1. **Add Company via Database**:
```bash
docker-compose exec -T postgres psql -U easm -d easm << 'EOF'
INSERT INTO tenants (name, slug, created_at, updated_at)
VALUES ('Acme Corp', 'acme-corp', NOW(), NOW())
RETURNING id;
EOF
```

2. **Add Seed Domains**:
```bash
docker-compose exec -T postgres psql -U easm -d easm << 'EOF'
INSERT INTO seeds (tenant_id, type, value, enabled, created_at, updated_at)
VALUES
  (2, 'domain', 'acme.com', true, NOW(), NOW()),
  (2, 'domain', 'acme-cloud.com', true, NOW(), NOW());
EOF
```

3. **Refresh UI** - New tenant will appear in tenant selector dropdown

---

## How to Trigger Scans via UI

### Method 1: Via API Documentation (Swagger UI)

1. Open API docs: http://localhost:8000/docs
2. Find endpoint: `POST /api/v1/tenants/{tenant_id}/scans/trigger`
3. Click "Try it out"
4. Enter tenant ID (get from tenant selector or database)
5. Select scan type:
   - `full_discovery`: Complete subdomain enumeration
   - `enrichment`: HTTPx + Naabu + TLSx on existing assets
   - `vulnerability`: Nuclei scan on web services
6. Click "Execute"

### Method 2: Via Terminal

```bash
# Get tenant ID
TENANT_ID=$(docker-compose exec -T postgres psql -U easm -d easm -tc "SELECT id FROM tenants WHERE slug='demo-org';" | xargs)

# Trigger full discovery scan
curl -X POST "http://localhost:8000/api/v1/tenants/${TENANT_ID}/scans/trigger" \
  -H "Content-Type: application/json" \
  -d '{
    "scan_type": "full_discovery",
    "priority": "normal"
  }'

# Trigger enrichment only
curl -X POST "http://localhost:8000/api/v1/tenants/${TENANT_ID}/scans/trigger" \
  -H "Content-Type: application/json" \
  -d '{
    "scan_type": "enrichment",
    "priority": "high"
  }'

# Trigger vulnerability scan
curl -X POST "http://localhost:8000/api/v1/tenants/${TENANT_ID}/scans/trigger" \
  -H "Content-Type: application/json" \
  -d '{
    "scan_type": "vulnerability",
    "priority": "normal",
    "severity_filter": "critical,high"
  }'
```

### Method 3: Scheduled Automatic Scans

The platform already runs scans automatically:

- **Daily Full Discovery**: 2:00 AM (complete subdomain enumeration)
- **Critical Asset Watch**: Every 30 minutes (DNS health checks)
- **Weekly Deep Scan**: Sundays 3:00 AM (TLS + vulnerability scanning)

To view schedule:
```bash
docker-compose exec -T worker celery -A app.celery_app inspect scheduled
```

---

## Monitoring Scan Progress

### Via UI (Coming Soon)
A "Scans" page will show active and completed scans.

### Via Terminal
```bash
# Show active Celery tasks
docker-compose exec -T worker celery -A app.celery_app inspect active

# Show worker status
docker-compose exec -T worker celery -A app.celery_app status

# View worker logs in real-time
docker-compose logs -f worker
```

### Via Database
```bash
# Show recent events
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT
  kind,
  COUNT(*) as count,
  MAX(created_at) as last_occurrence
FROM events
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY kind
ORDER BY count DESC
LIMIT 10;
"
```

---

## Common Workflows

### Workflow 1: Onboard New Company and Scan

```bash
# 1. Create tenant
docker-compose exec -T postgres psql -U easm -d easm << 'EOF'
INSERT INTO tenants (name, slug, created_at, updated_at)
VALUES ('NewCorp', 'newcorp', NOW(), NOW())
RETURNING id;
EOF

# 2. Add seed domains (use ID from step 1)
docker-compose exec -T postgres psql -U easm -d easm << 'EOF'
INSERT INTO seeds (tenant_id, type, value, enabled, created_at, updated_at)
VALUES (3, 'domain', 'newcorp.com', true, NOW(), NOW());
EOF

# 3. Trigger discovery scan
curl -X POST "http://localhost:8000/api/v1/tenants/3/scans/trigger" \
  -H "Content-Type: application/json" \
  -d '{"scan_type": "full_discovery"}'

# 4. Wait 15-30 minutes, then check UI
# Navigate to: http://localhost:13000
# Select tenant: NewCorp
# View Dashboard to see discovered assets
```

### Workflow 2: Investigate High-Risk Asset

1. **Dashboard**: Notice "42 High-Risk Assets" on dashboard
2. **Assets Page**: Click "Assets" → Sort by "Risk Score" descending
3. **Asset Detail**: Click highest-risk asset
4. **Review Components**:
   - Check "Findings" section for vulnerabilities
   - Check "Certificates" for expiration
   - Check "Services" for exposed admin panels
5. **Findings Detail**: Click critical finding for remediation steps
6. **Export Report**: Click "Export PDF" for security team

### Workflow 3: Certificate Expiration Monitoring

1. **Certificates Page**: Navigate to Certificates
2. **Filter**: Click "Expiring Soon (< 30 days)"
3. **Export**: Download CSV of expiring certificates
4. **Alert**: Forward CSV to DevOps team for renewal
5. **Track**: Re-check in 1 week to verify renewals

### Workflow 4: Find All WordPress Sites

1. **Services Page**: Navigate to Services
2. **Search**: Type "wordpress" in search box
3. **Review**: See all WordPress installations
4. **Findings**: Click each asset to check for WordPress vulnerabilities
5. **Remediation**: Group by version, prioritize outdated versions

---

## Keyboard Shortcuts

- `Ctrl + K` (or `Cmd + K` on Mac): Quick search (if implemented)
- `Esc`: Close modals/dialogs
- `Tab`: Navigate between form fields
- Click logo: Return to Dashboard

---

## Dark Mode

Toggle dark mode via:
- User profile menu (top-right)
- Settings page (if available)
- System preference (auto-detect)

Dark mode uses:
- Dark background: `#1a1a1a`
- Dark secondary: `#2d2d2d`
- Primary accent: Blue/Cyan
- Severity colors preserved for accessibility

---

## Troubleshooting

### Problem: UI doesn't load (blank page)

**Solution**:
```bash
# Restart UI container
docker-compose restart ui

# Check UI logs
docker-compose logs ui

# Verify container is running
docker-compose ps | grep ui
```

### Problem: "Login failed" error

**Solution**:
```bash
# Reset admin password
docker-compose exec -T postgres psql -U easm -d easm -c "
UPDATE users
SET hashed_password = '\$2b\$12\$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyKcpZL0m0K6'
WHERE username = 'admin';
"

# Use credentials:
# Email: admin@example.com
# Password: admin123
```

### Problem: "No tenant available" error

**Solution**:
```bash
# Check if tenants exist
docker-compose exec -T postgres psql -U easm -d easm -c "SELECT * FROM tenants;"

# Create demo tenant if missing
docker-compose exec -T postgres psql -U easm -d easm -c "
INSERT INTO tenants (name, slug, created_at, updated_at)
VALUES ('Demo Organization', 'demo-org', NOW(), NOW());
"

# Refresh UI
```

### Problem: Data not showing (empty dashboard)

**Solution**:
```bash
# Check if assets exist
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT COUNT(*) as total_assets FROM assets WHERE is_active = true;
"

# If zero, run discovery scan
curl -X POST "http://localhost:8000/api/v1/tenants/1/scans/trigger" \
  -H "Content-Type: application/json" \
  -d '{"scan_type": "full_discovery"}'

# Wait 15-30 minutes, then refresh UI
```

### Problem: UI is slow/unresponsive

**Solution**:
```bash
# Check resource usage
docker stats --no-stream | grep easm

# Restart all services
docker-compose restart

# Clear browser cache
# Chrome: Ctrl+Shift+Delete → Clear cache
# Firefox: Ctrl+Shift+Delete → Clear cache
```

---

## API Integration

The UI uses these backend APIs. You can use them directly:

**Base URL**: http://localhost:8000

**Key Endpoints**:
- `GET /api/v1/tenants` - List all tenants
- `GET /api/v1/tenants/{id}/dashboard` - Dashboard stats
- `GET /api/v1/tenants/{id}/assets` - List assets
- `GET /api/v1/tenants/{id}/services` - List services
- `GET /api/v1/tenants/{id}/certificates` - List certificates
- `GET /api/v1/tenants/{id}/findings` - List findings
- `POST /api/v1/tenants/{id}/scans/trigger` - Trigger scan

**Full API Docs**: http://localhost:8000/docs

---

## Mobile Access

The UI is responsive and works on mobile devices:

1. Ensure your mobile device is on the same network
2. Find your computer's local IP: `ifconfig | grep "inet "`
3. Access from mobile: http://[YOUR_IP]:13000
4. Login with same credentials

---

## Export & Reporting

### Export Options (Currently via API)

**Export Assets to CSV**:
```bash
curl "http://localhost:8000/api/v1/tenants/1/assets?format=csv" > assets.csv
```

**Export Findings to JSON**:
```bash
curl "http://localhost:8000/api/v1/tenants/1/findings?severity=critical&status=open" > critical_findings.json
```

**Generate PDF Report** (if implemented):
```bash
curl -X POST "http://localhost:8000/api/v1/tenants/1/reports/generate" \
  -H "Content-Type: application/json" \
  -d '{"report_type": "executive_summary"}' \
  -o report.pdf
```

---

## Security Best Practices

1. **Change Default Password**: Immediately after first login
2. **Use Strong Passwords**: Minimum 12 characters, mixed case, numbers, symbols
3. **Access Control**: Only expose UI port (13000) on trusted networks
4. **Regular Updates**: Keep Docker images updated
5. **Audit Logs**: Review user actions regularly
6. **Multi-Factor Auth**: Enable if available (future feature)

---

## Performance Tips

1. **Use Filters**: Don't load all 10,000 assets at once - use search/filters
2. **Pagination**: Keep page size reasonable (50-100 items)
3. **Dashboard Refresh**: Auto-refresh every 30s (configurable)
4. **Browser Choice**: Chrome/Edge recommended for best performance
5. **Close Unused Tabs**: Each tab maintains WebSocket connection

---

## Support & Feedback

**Report Issues**:
- UI bugs: Check browser console (F12 → Console tab)
- Backend errors: Check `docker-compose logs api`
- Worker issues: Check `docker-compose logs worker`

**Feature Requests**:
Create an issue on GitHub or contact the development team.

---

## Quick Reference Card

```
┌────────────────────────────────────────────────┐
│ EASM Platform - Quick Reference                │
├────────────────────────────────────────────────┤
│ UI URL:        http://localhost:13000          │
│ API Docs:      http://localhost:8000/docs      │
│ Default User:  admin@example.com               │
│ Default Pass:  admin123 (after reset)          │
├────────────────────────────────────────────────┤
│ MAIN SECTIONS                                  │
│ • Dashboard    - Overview & charts             │
│ • Assets       - 471 discovered assets         │
│ • Services     - 115 live services             │
│ • Certificates - 107 TLS certs monitored       │
│ • Findings     - Vulnerabilities & issues      │
├────────────────────────────────────────────────┤
│ QUICK ACTIONS                                  │
│ 1. View high-risk assets:                      │
│    Assets → Sort by Risk Score                 │
│                                                │
│ 2. Find expiring certs:                        │
│    Certificates → Filter: Expiring Soon        │
│                                                │
│ 3. Review critical findings:                   │
│    Findings → Filter: Severity=Critical        │
│                                                │
│ 4. Trigger new scan:                           │
│    API Docs → POST /scans/trigger              │
└────────────────────────────────────────────────┘
```

Print this card and keep it nearby when using the platform!

---

**You now have everything you need to use the EASM Platform UI effectively. Happy hunting! 🔍**
