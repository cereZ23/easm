# EASM Platform - Customer Journey Guide

**How a Real Customer Uses the Platform: Day-by-Day Walkthrough**

---

## DAY 1: Onboarding & Initial Scan

### Step 1: Customer Signs Up

**Customer**: Acme Corp (security team)
**Goal**: Monitor their attack surface across 3 domains

```bash
# As the EASM platform admin, you add the new customer
cd /Users/cere/Downloads/easm

# Add customer tenant
docker-compose exec -T postgres psql -U easm -d easm << 'EOF'
INSERT INTO tenants (name, slug, created_at, updated_at)
VALUES ('Acme Corp', 'acme-corp', NOW(), NOW())
RETURNING id;
EOF
# Returns: id = 4
```

### Step 2: Customer Provides Their Domains

**Customer provides**:
- acme.com
- acme-cloud.com
- acmeapi.io

```bash
# Add their seed domains
docker-compose exec -T postgres psql -U easm -d easm << 'EOF'
INSERT INTO seeds (tenant_id, type, value, enabled, created_at, updated_at)
VALUES
  (4, 'domain', 'acme.com', true, NOW(), NOW()),
  (4, 'domain', 'acme-cloud.com', true, NOW(), NOW()),
  (4, 'domain', 'acmeapi.io', true, NOW(), NOW());
EOF
```

### Step 3: Trigger Initial Discovery Scan

```bash
# Trigger full reconnaissance
curl -X POST "http://localhost:8000/api/v1/tenants/4/scans/trigger" \
  -H "Content-Type: application/json" \
  -d '{
    "scan_type": "full_discovery",
    "priority": "high"
  }'
```

**What happens automatically**:
1. **Amass + Subfinder** run in parallel (30-45 min)
   - Discovers ~200-500 subdomains per root domain
2. **DNSx** validates all discovered domains (5-10 min)
   - Resolves A/AAAA/CNAME records
3. **HTTPx** probes all HTTP/HTTPS services (10-15 min)
   - Detects web servers, technologies, status codes
4. **Naabu** scans top 1000 ports (15-20 min)
   - Finds open ports across all assets
5. **TLSx** analyzes all HTTPS services (5-10 min)
   - Extracts certificate data, SANs, expiration dates

**Total time**: 1-2 hours for initial scan

### Step 4: Customer Receives Email Notification

```
Subject: Your EASM Scan is Complete

Hi Acme Corp Team,

Your initial attack surface scan has finished!

📊 Discovered Assets:
- 487 subdomains
- 143 live services
- 89 TLS certificates

🔍 Quick Findings:
- 2 high-risk ports exposed (SSH on legacy-vpn.acme.com)
- 3 certificates expiring in < 30 days
- 12 outdated web servers detected

View your full dashboard: https://easm.yourplatform.com/dashboard

Best regards,
EASM Platform Team
```

---

## DAY 2: Customer Explores Their Dashboard

### Customer Logs Into UI

**URL**: http://localhost:13000 (in production: https://easm.yourplatform.com)
**Login**: Their provided email/password

### Dashboard View (First Thing They See)

```
┌─────────────────────────────────────────────────────────────┐
│ EASM Platform        [Acme Corp ▼]     john@acme.com [👤]  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  📊 ATTACK SURFACE OVERVIEW                                 │
│                                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
│  │ 487          │ │ 143          │ │ 89           │       │
│  │ Assets       │ │ Services     │ │ Certificates │       │
│  │ ↑ 23 new     │ │ 109 HTTPS    │ │ ⚠️ 3 expiring│       │
│  └──────────────┘ └──────────────┘ └──────────────┘       │
│                                                              │
│  ┌──────────────────────────────────────────────┐          │
│  │ 🎯 FINDINGS BY SEVERITY                      │          │
│  │                                               │          │
│  │  Critical: 1   🔴                            │          │
│  │  High:     4   🟠                            │          │
│  │  Medium:   12  🟡                            │          │
│  │  Low:      8   🔵                            │          │
│  └──────────────────────────────────────────────┘          │
│                                                              │
│  📈 RISK DISTRIBUTION                                       │
│  Critical (71-100):  2 assets                               │
│  High (41-70):       15 assets                              │
│  Medium (21-40):     143 assets                             │
│  Low (0-20):         327 assets                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Customer Clicks: "Assets" Tab

See all discovered subdomains:

```
┌─────────────────────────────────────────────────────────────┐
│ ASSETS (487)                                    [Search...] │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Identifier                  Type      Risk Score  Last Seen │
│ ────────────────────────────────────────────────────────── │
│ legacy-vpn.acme.com        subdomain   85 🔴      2h ago   │
│ admin.acme-cloud.com       subdomain   72 🔴      2h ago   │
│ staging-api.acmeapi.io     subdomain   54 🟠      2h ago   │
│ www.acme.com               subdomain   18 🟢      2h ago   │
│ mail.acme.com              subdomain   12 🟢      2h ago   │
│ ...                                                          │
└─────────────────────────────────────────────────────────────┘
```

**Customer clicks on**: `legacy-vpn.acme.com` (highest risk)

### Asset Detail View

```
┌─────────────────────────────────────────────────────────────┐
│ legacy-vpn.acme.com                         Risk: 85/100 🔴 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 📋 OVERVIEW                                                 │
│ Type:        Subdomain                                      │
│ IP:          203.0.113.42                                   │
│ First Seen:  2024-10-26 14:23:15                           │
│ Last Seen:   2024-10-26 16:15:42                           │
│                                                              │
│ ⚠️ RISK BREAKDOWN                                           │
│ Findings:         +40  (1 critical SSH vuln)                │
│ Port Exposure:    +30  (SSH port 22 exposed)                │
│ Certificate:      +15  (expired cert)                       │
│ Service Security: +0                                        │
│ Asset Age:        +0                                        │
│                                                              │
│ 🔌 OPEN PORTS                                               │
│ Port 22  (SSH)      ⚠️ HIGH RISK                            │
│ Port 443 (HTTPS)    ✅ Normal                               │
│                                                              │
│ 🔐 CERTIFICATES                                             │
│ Subject CN:  *.acme.com                                     │
│ Issuer:      Let's Encrypt                                  │
│ Expiration:  EXPIRED 15 days ago 🔴                         │
│                                                              │
│ 🐛 FINDINGS (1 Critical)                                    │
│ [CRITICAL] SSH Service Exposed to Internet                  │
│   Template: exposed-panels/ssh-detect                       │
│   Evidence: SSH-2.0-OpenSSH_7.4                            │
│   Risk: Brute force attacks, unauthorized access            │
│                                                              │
│ 💡 RECOMMENDATIONS                                          │
│ 1. Immediately restrict SSH (port 22) to VPN/internal only │
│ 2. Renew expired TLS certificate                           │
│ 3. Update OpenSSH to version 9.x                           │
│                                                              │
│ [Export PDF Report] [Add to Watch List] [Suppress Finding] │
└─────────────────────────────────────────────────────────────┘
```

**Customer's Reaction**: 😱 "We didn't know this old VPN server was still exposed!"

---

## DAY 3: Customer Takes Action

### Workflow 1: Fix Critical Issue

**Customer (CISO)** forwards finding to DevOps team:

```
From: john@acme.com
To: devops@acme.com
Subject: URGENT: legacy-vpn.acme.com has SSH exposed

Team,

Our EASM scan found legacy-vpn.acme.com has:
- SSH (port 22) exposed to internet
- Expired certificate
- Outdated OpenSSH 7.4

Please:
1. Restrict SSH to VPN-only access
2. Renew cert
3. Update OpenSSH

Report: [attached PDF from EASM platform]
```

### Workflow 2: Export Reports for Management

Customer clicks "Export PDF Report" for executive summary:

```bash
# In production, this would be a UI button
# For now, customer can generate via API:

curl -X POST "http://localhost:8000/api/v1/tenants/4/reports/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "executive_summary",
    "format": "pdf"
  }' -o acme_attack_surface_report.pdf
```

**PDF Contains**:
- Executive Summary (1 page)
- Risk scorecard with trending
- Top 10 highest risk assets
- Certificate expiration timeline
- Recommendations prioritized by risk

### Workflow 3: Set Up Alerting

Customer navigates to Settings → Alerts (hypothetical UI):

```
┌─────────────────────────────────────────────────────────────┐
│ ALERT CONFIGURATION                                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ ✅ Email me when:                                           │
│    □ New subdomain discovered                               │
│    ☑ High-risk port exposed (22, 3389, 3306, etc.)        │
│    ☑ Certificate expiring in < 30 days                     │
│    ☑ Critical vulnerability found                          │
│                                                              │
│ 💬 Slack Integration:                                       │
│    Webhook: https://hooks.slack.com/...                     │
│    Channel: #security-alerts                                │
│    ☑ Enabled                                                │
│                                                              │
│ 📧 Recipients:                                              │
│    john@acme.com                                            │
│    security-team@acme.com                                   │
│    [Add recipient...]                                       │
│                                                              │
│ [Save Configuration]                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## DAY 7: Weekly Report

### Automated Weekly Email

Customer receives:

```
Subject: Weekly Attack Surface Report - Acme Corp

Hi John,

Here's your weekly attack surface summary:

📊 THIS WEEK'S CHANGES:
✅ Fixed: legacy-vpn.acme.com (SSH now restricted) - Risk: 85→15
⚠️  New: dev-api.acme.com discovered (exposed GraphQL playground)
📈 Total Assets: 487 → 492 (+5 new)

🔐 CERTIFICATE STATUS:
- 2 certificates expiring in < 30 days
- staging.acme-cloud.com expires Oct 30
- test-api.acmeapi.io expires Nov 2

🎯 ACTION ITEMS:
1. Review new dev-api.acme.com exposure
2. Renew 2 expiring certificates
3. Patch 3 outdated Nginx servers

Full report: https://easm.yourplatform.com/reports/weekly/2024-10-26

- EASM Platform Team
```

---

## DAY 30: Monthly Review Meeting

### Customer Prepares for Security Review

Customer generates comprehensive report:

```bash
# Via API or UI button
GET /api/v1/tenants/4/reports/monthly?month=2024-10
```

**Monthly Report Contains**:
- **Attack Surface Growth**: 487→503 assets (+3%)
- **Risk Trend**: Average risk score 18.5→14.2 (improved 23%)
- **Findings Resolved**: 23 of 25 critical findings fixed
- **New Discoveries**: 16 new subdomains from recent acquisition
- **Certificate Health**: 98% certs valid, 2 renewals needed
- **Compliance Posture**: 0 high-risk ports exposed (down from 2)

**Customer presents to Board**:
> "Since implementing continuous EASM monitoring:
> - Reduced attack surface risk by 23%
> - Discovered and secured 2 critical SSH exposures
> - Maintained 100% certificate uptime
> - Total time saved: ~40 hours/month vs manual recon"

---

## ONGOING: Continuous Monitoring

### What Runs Automatically (Customer Does Nothing)

**Every 30 Minutes**:
```
Critical Asset Watch:
- Checks DNS health for top 50 assets
- Detects if any critical assets go offline
- Alerts immediately via Slack/Email
```

**Every Day at 2 AM**:
```
Full Discovery Scan:
- Re-enumerate all subdomains (Amass + Subfinder)
- Detect new assets
- Update service information
- Flag any changes
```

**Every Sunday at 3 AM**:
```
Deep Scan:
- TLS certificate refresh
- Vulnerability scanning with Nuclei
- Risk score recalculation
- Weekly report generation
```

### Real-Time Alert Example

**3:42 PM - Slack Alert**:
```
🚨 NEW HIGH-RISK ASSET DETECTED

Asset: new-staging.acme.com
Risk Score: 68/100 (HIGH)
Discovered: 3 minutes ago

Issues:
- HTTP admin panel exposed
- No HTTPS available
- Default WordPress installation

View: https://easm.yourplatform.com/assets/1247

[@security-team please investigate]
```

---

## DAY 90: Customer Reviews ROI

### Time Saved Calculation

**Before EASM Platform**:
```
Manual reconnaissance: 8 hours/week
Certificate tracking: 2 hours/week
Vulnerability scanning: 4 hours/week
Report generation: 2 hours/week
─────────────────────────────────────
Total: 16 hours/week = 64 hours/month
Cost: ~$6,400/month (senior security eng @ $100/hr)
```

**With EASM Platform**:
```
Monthly cost: $1,499 (Professional tier)
Manual time: 2 hours/month (reviewing reports)
Cost: $200/month (eng time) + $1,499 = $1,699/month
─────────────────────────────────────
Savings: $4,701/month = $56,412/year
ROI: 277%
```

**Additional Benefits**:
- 30-50% better subdomain coverage (dual tools)
- Real-time alerts vs monthly manual scans
- Complete audit trail for compliance
- Automated reporting for management

---

## HOW CUSTOMER SCALES USAGE

### Month 6: Add More Domains

**Scenario**: Acme Corp acquires NewStartup.io

```bash
# Customer adds new domain via UI or API
POST /api/v1/tenants/4/seeds
{
  "type": "domain",
  "value": "newstartup.io"
}

# Platform automatically:
# - Discovers all newstartup.io subdomains
# - Scans services
# - Generates risk scores
# - Adds to monitoring schedule
```

### Month 12: Upgrade to Enterprise Tier

**Customer Growth**:
- Started: 3 root domains, 487 assets
- Now: 12 root domains, 2,143 assets

**Upgrade Benefits**:
- Unlimited domains/assets
- Custom scan frequencies (every 4 hours)
- Dedicated support
- On-premise deployment option
- API rate limit increased 10x
- White-label reporting

---

## CUSTOMER SUCCESS METRICS

### What Customer Tracks

**Dashboard KPIs** (always visible in UI):
```
┌─────────────────────────────────────────┐
│ SECURITY POSTURE SCORE: 8.7/10 ↑        │
├─────────────────────────────────────────┤
│ Assets Monitored:        2,143          │
│ Critical Findings:       0 ✅           │
│ High Findings:           2 ↓            │
│ Avg Risk Score:          12.3 ↓         │
│ Certificates Healthy:    98.5% ↑        │
│ Mean Time to Remediate:  4.2 days ↓     │
└─────────────────────────────────────────┘
```

**Trend Graphs** (last 90 days):
- Attack surface growth over time
- Risk score trending
- Finding resolution velocity
- Certificate health percentage

---

## SCALABILITY ISSUES (Current Implementation)

### Problem 1: Database Queries Get Slow

**When**: Customer has >10,000 assets

**Issue**:
```sql
-- This query gets slow with large datasets
SELECT * FROM assets WHERE tenant_id = 4 ORDER BY risk_score DESC;
-- Takes 8+ seconds with 50,000 assets
```

**Solution Needed**:
- Add database indexes
- Implement pagination
- Use materialized views for dashboards
- Cache frequently accessed data

### Problem 2: Scan Times Increase Linearly

**When**: Customer has >20 root domains

**Issue**:
```
1 domain = 1 hour scan time
20 domains = 20 hours scan time (not acceptable!)
```

**Solution Needed**:
- Horizontal scaling (multiple worker nodes)
- Distributed task queue
- Smart scheduling (prioritize critical assets)
- Incremental scans (only check changed assets)

### Problem 3: UI Loads Entire Dataset

**When**: Dashboard tries to load 10,000+ assets

**Issue**:
```javascript
// Frontend loads ALL assets at once
const assets = await api.getAssets(tenantId)
// 50,000 assets = 25MB JSON = browser crash
```

**Solution Needed**:
- Implement virtual scrolling
- Server-side pagination
- Lazy loading
- Data aggregation on backend

### Problem 4: No Auto-Scaling

**When**: 100 customers trigger scans simultaneously

**Issue**:
- Single Celery worker can't handle load
- Tasks queue up for hours
- Customer scans timeout

**Solution Needed**:
- Kubernetes auto-scaling
- Load balancing across workers
- Priority queues (paying customers first)
- Resource limits per tenant

---

## PRODUCTION-READY REQUIREMENTS

### Must Fix Before Selling:

1. **Infrastructure**
   - [ ] Kubernetes deployment manifests
   - [ ] Auto-scaling policies
   - [ ] Load balancer configuration
   - [ ] Multi-region support

2. **Database**
   - [ ] Add indexes for all queries
   - [ ] Implement connection pooling
   - [ ] Set up read replicas
   - [ ] Automated backups (hourly)

3. **Security**
   - [ ] SOC 2 Type II compliance
   - [ ] Penetration testing
   - [ ] Security audit
   - [ ] Bug bounty program

4. **Monitoring**
   - [ ] Prometheus metrics
   - [ ] Grafana dashboards
   - [ ] PagerDuty alerting
   - [ ] Log aggregation (ELK stack)

5. **Support**
   - [ ] Help desk software (Zendesk)
   - [ ] Knowledge base
   - [ ] SLA definitions
   - [ ] 24/7 on-call rotation

---

## CUSTOMER SELF-SERVICE (Required for Scale)

### Features Needed:

```
┌─────────────────────────────────────────────────────────────┐
│ SELF-SERVICE PORTAL                                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 🏢 Company Management                                       │
│    - Add/remove domains                                     │
│    - Manage users (invite team members)                     │
│    - Set scan schedules                                     │
│    - Configure notifications                                │
│                                                              │
│ 💳 Billing                                                  │
│    - View invoices                                          │
│    - Update payment method                                  │
│    - Upgrade/downgrade tier                                 │
│    - Usage analytics                                        │
│                                                              │
│ 📊 Reports                                                  │
│    - Generate custom reports                                │
│    - Schedule recurring reports                             │
│    - Export data (CSV, JSON, PDF)                           │
│                                                              │
│ ⚙️ Integrations                                             │
│    - Slack webhook setup                                    │
│    - JIRA integration                                       │
│    - API key management                                     │
│    - Webhook configuration                                  │
│                                                              │
│ 📚 Documentation                                            │
│    - API docs                                               │
│    - Video tutorials                                        │
│    - Best practices                                         │
│    - FAQ                                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## SUMMARY: Current vs Production-Ready

| Feature | Current State | Production Needed |
|---------|--------------|-------------------|
| **Multi-tenant** | ✅ Working | ✅ Ready |
| **Discovery Pipeline** | ✅ Working | ⚠️ Needs scaling |
| **UI Dashboard** | ✅ Basic | ⚠️ Needs UX polish |
| **API** | ✅ Working | ⚠️ Needs rate limiting |
| **Alerting** | ❌ Not implemented | 🔴 Critical |
| **Billing** | ❌ Not implemented | 🔴 Critical |
| **Auto-scaling** | ❌ Not implemented | 🔴 Critical |
| **Support Portal** | ❌ Not implemented | 🔴 Critical |
| **Documentation** | ⚠️ Partial | 🔴 Critical |
| **Monitoring** | ❌ Not implemented | 🔴 Critical |
| **Backups** | ❌ Not implemented | 🔴 Critical |
| **Security Audit** | ❌ Not done | 🔴 Critical |

**Bottom Line**: Technical foundation is solid, but need 3-6 months of product/infrastructure work before customer-ready.
