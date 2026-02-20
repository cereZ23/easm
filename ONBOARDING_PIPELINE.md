# Complete Onboarding Pipeline

**What Happens When You Onboard a Customer**

---

## Full Pipeline Overview

When you onboard a customer through the UI, the system triggers a **complete 4-stage pipeline**:

```
STAGE 1: Discovery (30-60 min)
  ├─ Amass: Subdomain enumeration from 55+ sources
  ├─ Subfinder: Fast passive subdomain enumeration
  └─ DNSx: DNS resolution and validation

STAGE 2: Enrichment (20-40 min)
  ├─ HTTPx: Web service fingerprinting & technology detection
  ├─ Naabu: Port scanning (top 1000 ports)
  ├─ TLSx: Certificate analysis and expiration tracking
  └─ Katana: Web crawling and endpoint discovery

STAGE 3: Vulnerability Scanning (30-60 min)
  └─ Nuclei: 6000+ templates scanning for CVEs, misconfigurations, exposed panels

STAGE 4: Risk Analysis (5 min)
  └─ Risk Scoring: Multi-factor risk calculation (0-100 scale)

TOTAL TIME: 1.5 - 3 hours
```

---

## Stage-by-Stage Breakdown

### STAGE 1: Discovery 🔍

**What it does:**
- Enumerates all subdomains for each root domain
- Validates DNS records
- Creates asset records in database

**Tools Used:**
```bash
# Amass - Deep OSINT enumeration
amass enum -passive -d lessismore.fun -o amass.txt

# Subfinder - Fast passive enumeration
subfinder -d lessismore.fun -all -recursive -o subfinder.txt

# DNSx - Resolve and validate
cat merged.txt | dnsx -a -aaaa -cname -resp -json -o resolved.json
```

**Typical Results:**
- 50-500 subdomains discovered per root domain
- 70-90% resolution rate
- Example for lessismore.fun:
  ```
  www.lessismore.fun
  api.lessismore.fun
  staging.lessismore.fun
  blog.lessismore.fun
  cdn.lessismore.fun
  mail.lessismore.fun
  ... (40+ more)
  ```

**Database Impact:**
- Creates ~50-500 `assets` records (type: subdomain)
- Creates `events` for new asset discoveries
- Updates `last_seen` timestamps

---

### STAGE 2: Enrichment 🔬

**What it does:**
- Probes all discovered assets for live services
- Scans ports to find exposed services
- Analyzes TLS certificates
- Crawls web applications to find endpoints

**Tools Used:**

#### HTTPx - Web Service Discovery
```bash
cat assets.txt | httpx -mc 200,301,302,403,401,500 \
  -server -tech-detect -title -follow-redirects \
  -json -o httpx.json
```

**Discovers:**
- Live HTTP/HTTPS services
- Web server software (nginx, Apache, etc.)
- Technologies (React, WordPress, etc.)
- Status codes and redirects
- Page titles

#### Naabu - Port Scanning
```bash
naabu -list assets.txt -top-ports 1000 \
  -rate 8000 -json -o naabu.json
```

**Discovers:**
- Open ports (22=SSH, 3306=MySQL, etc.)
- High-risk exposed services
- Database ports
- Admin panels on non-standard ports

#### TLSx - Certificate Analysis
```bash
tlsx -list assets.txt -cn -sans -issuer -exp -alpn \
  -ja3 -json -o tlsx.json
```

**Discovers:**
- Certificate details and issuers
- SANs (Subject Alternative Names)
- Expiration dates
- Wildcard certificates
- Certificate mismatches

#### Katana - Web Crawling
```bash
cat web_urls.txt | katana -js-crawl -known-files all \
  -depth 3 -json -o katana.json
```

**Discovers:**
- API endpoints
- Hidden admin pages
- JavaScript files
- Forms and parameters
- GraphQL/REST endpoints

**Typical Results:**
- 100-200 live services discovered
- 20-50 open ports found
- 50-100 TLS certificates analyzed
- 500-2000 web endpoints discovered

**Database Impact:**
- Creates ~100-200 `services` records
- Creates ~50-100 `certificates` records
- Creates ~500-2000 `endpoints` records
- Creates `events` for new services/certs

---

### STAGE 3: Nuclei Vulnerability Scanning 🐛

**What it does:**
- Scans all web services for known vulnerabilities
- Detects CVEs, misconfigurations, exposed panels
- Identifies security issues

**Tool Used:**
```bash
nuclei -list urls.txt \
  -t cves/ -t exposed-panels/ -t misconfiguration/ -t vulnerabilities/ \
  -severity critical,high,medium,low \
  -rl 300 -bs 50 -c 50 \
  -json -o nuclei.json
```

**Templates Included:**
- **CVEs**: 3000+ known vulnerability checks
- **Exposed Panels**: Admin panels, dashboards, consoles
- **Misconfigurations**: Security headers, CORS, CSP
- **Default Credentials**: Common default passwords
- **Technologies**: WordPress, Joomla, Drupal vulns
- **APIs**: GraphQL introspection, Swagger exposure

**Severity Breakdown:**
- **Critical**: Remote code execution, SQL injection
- **High**: Authentication bypass, sensitive data exposure
- **Medium**: XSS, CSRF, information disclosure
- **Low**: Minor misconfigurations, deprecated software

**Typical Results for lessismore.fun:**
```
Critical: 0-2 findings
High:     2-5 findings
Medium:   5-15 findings
Low:      10-30 findings
Info:     20-50 findings

Common findings:
- Missing security headers (HSTS, X-Frame-Options)
- Outdated software versions
- Exposed Git repositories
- Information disclosure
- Weak TLS ciphers
```

**Database Impact:**
- Creates ~30-100 `findings` records
- Links findings to assets
- Creates `events` for new vulnerabilities
- Updates finding status (open, fixed, suppressed)

---

### STAGE 4: Risk Scoring 📊

**What it does:**
- Calculates comprehensive risk score (0-100) for each asset
- Considers multiple risk factors
- Prioritizes assets for remediation

**Risk Score Formula:**
```
Total Risk Score =
  Findings Score (max 50 pts) +
  Certificate Score (max 30 pts) +
  Port Exposure Score (max 40 pts) +
  Service Security Score (max 25 pts) +
  Asset Age Bonus (10 pts)

Max Score: 100 (normalized)
```

**Risk Score Breakdown:**

#### 1. Findings Score (50 pts max)
```
Critical finding: +15 pts each
High finding:     +10 pts each
Medium finding:   +5 pts each
Low finding:      +2 pts each
Info finding:     +0.5 pts each
```

#### 2. Certificate Score (30 pts max)
```
Expired cert:        +15 pts
Expiring < 30 days:  +12 pts
CN mismatch:         +12 pts
Self-signed:         +8 pts
Weak cipher:         +5 pts
```

#### 3. Port Exposure (40 pts max)
```
SSH (22):            +8 pts
Telnet (23):         +10 pts
RDP (3389):          +9 pts
MySQL (3306):        +7 pts
PostgreSQL (5432):   +7 pts
MongoDB (27017):     +8 pts
Redis (6379):        +7 pts
Elasticsearch (9200): +7 pts
```

#### 4. Service Security (25 pts max)
```
HTTP login page:     +15 pts
Admin panel exposed: +10 pts
No HTTPS redirect:   +5 pts
Directory listing:   +8 pts
Debug mode enabled:  +10 pts
```

#### 5. Asset Age Bonus (10 pts)
```
New asset (< 7 days): +10 pts (needs immediate review)
```

**Risk Levels:**
```
0-20:   LOW       (green)   - Normal monitoring
21-40:  MEDIUM    (yellow)  - Review recommended
41-70:  HIGH      (orange)  - Action required
71-100: CRITICAL  (red)     - Immediate action
```

**Example Risk Calculation for staging.lessismore.fun:**
```
Asset: staging.lessismore.fun
Risk Score: 68/100 (HIGH)

Breakdown:
  Findings:         25 pts (1 high, 3 medium findings)
  Certificate:      12 pts (CN mismatch)
  Port Exposure:    0 pts  (no high-risk ports)
  Service Security: 15 pts (HTTP login page exposed)
  Asset Age:        10 pts (discovered 2 days ago)
  Base Score:       62 pts

  Risk Modifiers:
  + Login page without HTTPS: +6 pts

  Final Score: 68/100 → HIGH RISK
```

**Database Impact:**
- Updates `risk_score` field on all `assets`
- Creates trending data for risk score changes
- Triggers alerts for high/critical risk assets

---

## Timeline: Real Example (lessismore.fun)

```
[14:23:15] Onboarding started
[14:23:16] ✅ Tenant "Less Is More" created (ID: 3)
[14:23:16] ✅ User admin@lessismore.fun created
[14:23:16] ✅ Domain lessismore.fun added
[14:23:17] 🚀 Pipeline triggered

STAGE 1: Discovery
[14:23:20] Starting Amass enumeration...
[14:23:20] Starting Subfinder enumeration (parallel)...
[14:48:35] Amass complete: 38 subdomains found
[14:45:12] Subfinder complete: 47 subdomains found
[14:50:02] Merged results: 62 unique subdomains
[14:52:15] DNSx resolution: 47 subdomains resolved
[14:53:01] Discovery complete: 47 assets created

STAGE 2: Enrichment
[14:53:05] Starting HTTPx probe...
[14:58:23] HTTPx complete: 15 live services found
[14:53:05] Starting Naabu scan (parallel)...
[15:08:45] Naabu complete: 8 open ports found
[14:53:05] Starting TLSx analysis (parallel)...
[14:58:01] TLSx complete: 12 certificates analyzed
[15:08:50] Starting Katana crawl...
[15:23:17] Katana complete: 143 endpoints discovered
[15:24:02] Enrichment complete

STAGE 3: Nuclei Scanning
[15:24:10] Starting Nuclei scan on 15 URLs...
[15:24:10] Using templates: cves, exposed-panels, misconfiguration
[15:58:42] Nuclei complete: 23 findings
  - Critical: 0
  - High: 1 (outdated nginx)
  - Medium: 3
  - Low: 4
  - Info: 15
[15:59:01] Vulnerabilities saved

STAGE 4: Risk Scoring
[15:59:05] Calculating risk scores for 47 assets...
[15:59:32] Risk scoring complete
  - Critical (71-100): 0 assets
  - High (41-70):      1 asset (staging.lessismore.fun)
  - Medium (21-40):    5 assets
  - Low (0-20):        41 assets
  - Average risk:      12.3/100
[15:59:35] ✅ Pipeline complete

Total Duration: 1 hour 36 minutes
```

---

## What the Customer Sees

### Immediately After Onboarding:
```
Dashboard shows:
  🔄 Scan in progress
  ⏳ Estimated completion: 1-2 hours

  Current progress:
  ✅ Subfinder enumeration complete
  🔄 Amass enumeration running... (45%)
  ⏸️ DNS resolution (waiting)
  ⏸️ Service discovery (waiting)
  ...
```

### After Stage 1 (Discovery):
```
Dashboard updates:
  📊 47 assets discovered
  🔄 Enrichment in progress
  ⏳ Estimated completion: 1 hour
```

### After Stage 2 (Enrichment):
```
Dashboard updates:
  📊 47 assets | 15 services | 12 certificates
  🔄 Vulnerability scanning in progress
  ⏳ Estimated completion: 30 minutes
```

### After Complete Pipeline:
```
Full Dashboard:
  ┌─────────────────────────────────────────┐
  │ 47 Assets      15 Services   12 Certs  │
  │ 23 Findings    Average Risk: 12.3/100   │
  └─────────────────────────────────────────┘

  Risk Distribution:
  Critical: 0
  High:     1  ← staging.lessismore.fun
  Medium:   5
  Low:      41

  Top Findings:
  [HIGH] Outdated Nginx - staging.lessismore.fun
  [MEDIUM] Missing HSTS - api.lessismore.fun
  [MEDIUM] Weak TLS Cipher - www.lessismore.fun

  Recent Activity:
  • New subdomain discovered: blog.lessismore.fun
  • Certificate expiring soon: staging.lessismore.fun (28 days)
  • Service detected: PostgreSQL on db.lessismore.fun:5432
```

---

## Pipeline Monitoring

### View Pipeline Progress

```bash
# Check active tasks
docker-compose exec -T worker celery -A app.celery_app inspect active

# View worker logs
docker-compose logs -f worker

# Check specific tenant progress
docker-compose logs worker | grep "tenant_id: 3"
```

### Database Queries

```bash
# Check discovery progress
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT COUNT(*) as total_assets FROM assets WHERE tenant_id = 3;
"

# Check enrichment progress
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT COUNT(*) as total_services FROM services
JOIN assets ON services.asset_id = assets.id
WHERE assets.tenant_id = 3;
"

# Check vulnerability scan results
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT severity, COUNT(*) as count FROM findings
JOIN assets ON findings.asset_id = assets.id
WHERE assets.tenant_id = 3
GROUP BY severity;
"

# Check risk scores
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT
  CASE
    WHEN risk_score >= 71 THEN 'Critical'
    WHEN risk_score >= 41 THEN 'High'
    WHEN risk_score >= 21 THEN 'Medium'
    ELSE 'Low'
  END as risk_level,
  COUNT(*) as count
FROM assets
WHERE tenant_id = 3
GROUP BY risk_level;
"
```

---

## Summary

✅ **Complete onboarding pipeline now includes:**
1. ✅ Discovery (Amass + Subfinder + DNSx)
2. ✅ Enrichment (HTTPx + Naabu + TLSx + Katana)
3. ✅ **Nuclei vulnerability scanning** ← FIXED!
4. ✅ Risk score calculation

**Total Coverage:**
- Subdomain discovery
- Live service detection
- Port scanning
- Certificate monitoring
- Endpoint discovery
- **Vulnerability detection** ← NOW INCLUDED!
- Risk prioritization

**Customer gets complete security visibility** from day one! 🚀
