# Sprint 5: Complete Reconnaissance Pipeline

**Goal**: Integrate all ProjectDiscovery tools, automate scanning workflows, and build intelligent alerting

**Duration**: Est. 2-3 days
**Current Status**: Planning Phase
**Priority**: HIGH - Core EASM functionality

---

## 📋 Sprint Backlog

### Phase 1: Tool Integration (Day 1)

#### 1.1 Naabu Port Scanning
**Priority**: HIGH
**Est Time**: 3 hours

**Tasks**:
- [ ] Create Naabu wrapper script for batch port scanning
- [ ] Parse Naabu JSON output (ports, services, banners)
- [ ] Update services table with port scan results
- [ ] Add port scanning API endpoint: `POST /tenants/{id}/scans/ports`
- [ ] Test on Tesla assets (463 hosts, top 1000 ports)

**Deliverable**: Port scan data for all Tesla assets visible in UI

---

#### 1.2 TLSX Certificate Intelligence
**Priority**: HIGH
**Est Time**: 2 hours

**Tasks**:
- [ ] Create TLSX wrapper script for certificate extraction
- [ ] Parse TLSX JSON output (CN, SANs, expiry, issuer, cipher suites)
- [ ] Create `certificates` table insertion logic
- [ ] Add certificate scanning API endpoint: `POST /tenants/{id}/scans/certificates`
- [ ] Build certificate expiry alerting logic (< 30 days)
- [ ] Test on 107 Tesla HTTPS services

**Deliverable**: Certificate data with expiry warnings in UI

---

#### 1.3 Katana Web Crawling
**Priority**: MEDIUM
**Est Time**: 3 hours

**Tasks**:
- [ ] Create Katana wrapper for crawling accessible services
- [ ] Parse Katana JSON output (endpoints, parameters, forms)
- [ ] Create `endpoints` table for discovered paths
- [ ] Add crawling API endpoint: `POST /tenants/{id}/scans/crawl`
- [ ] Implement depth and scope limiting
- [ ] Test on 30 accessible Tesla services (200 OK)

**Deliverable**: Discovered endpoints and API routes in UI

---

#### 1.4 Nuclei Vulnerability Scanning
**Priority**: HIGH
**Est Time**: 4 hours

**Tasks**:
- [ ] Create Nuclei wrapper with severity filtering (critical/high only)
- [ ] Implement template selection (CVEs, exposed-panels, misconfigs)
- [ ] Parse Nuclei JSON output (CVE, CVSS, evidence, matched-at)
- [ ] Update `findings` table with vulnerability data
- [ ] Add vulnerability scanning API endpoint: `POST /tenants/{id}/scans/vulnerabilities`
- [ ] Implement rate limiting (300 req/min)
- [ ] Test on accessible Tesla services with CVE templates

**Deliverable**: Real vulnerability findings with CVSS scores in UI

---

### Phase 2: Task Orchestration (Day 2)

#### 2.1 Celery Task System
**Priority**: HIGH
**Est Time**: 4 hours

**Tasks**:
- [ ] Define Celery tasks for each tool (amass_task, subfinder_task, httpx_task, naabu_task, etc.)
- [ ] Create task chains for full pipeline:
  ```python
  # Discovery chain - Amass + Subfinder in parallel, then merge
  group(
      amass_task.si(domain),
      subfinder_task.si(domain)
  ) | merge_subdomains_task.s() | dnsx_task.s() | httpx_task.s() | naabu_task.s()

  # Enrichment chain
  chain(
      tlsx_task.si(https_services),
      katana_task.s(accessible_services),
      nuclei_task.s(all_services)
  )
  ```
- [ ] Implement task status tracking in database
- [ ] Add task progress API: `GET /tenants/{id}/scans/{scan_id}/status`
- [ ] Build task retry logic with exponential backoff
- [ ] Add task result storage (raw JSON to MinIO)

**Deliverable**: Async scan execution with progress tracking

---

#### 2.2 Scheduled Scans (Celery Beat)
**Priority**: MEDIUM
**Est Time**: 3 hours

**Tasks**:
- [ ] Configure Celery Beat scheduler
- [ ] Create scan schedule models (frequency, targets, enabled/disabled)
- [ ] Implement schedule types:
  - Daily full discovery (all tools)
  - Hourly quick check (httpx + nuclei on critical assets)
  - Weekly deep scan (full port scan + comprehensive nuclei)
- [ ] Add schedule management API: `POST /tenants/{id}/schedules`
- [ ] Build schedule UI in frontend (enable/disable, configure frequency)

**Deliverable**: Automated continuous reconnaissance

---

### Phase 3: Intelligence & Alerting (Day 2-3)

#### 3.1 Risk Scoring Engine
**Priority**: HIGH
**Est Time**: 4 hours

**Tasks**:
- [ ] Define risk scoring algorithm:
  ```python
  risk_score = (
      max_finding_severity_weight +    # 0-40 points
      open_high_risk_ports * 5 +        # 0-30 points
      expired_cert_weight +              # 0-15 points
      is_new_asset * 10 +                # 0-10 points
      exposed_admin_panel * 5            # 0-5 points
  ) * internet_exposure_multiplier
  ```
- [ ] Implement scoring calculation on asset save
- [ ] Create risk trend tracking (score over time)
- [ ] Add risk thresholds (critical: 80+, high: 60-79, medium: 40-59, low: <40)
- [ ] Update dashboard with risk distribution chart
- [ ] Add risk-based sorting and filtering in UI

**Deliverable**: Intelligent asset prioritization based on risk

---

#### 3.2 Notify Integration (Alerts)
**Priority**: MEDIUM
**Est Time**: 3 hours

**Tasks**:
- [ ] Install and configure ProjectDiscovery Notify
- [ ] Create alert policies per tenant:
  - New critical/high findings
  - New assets discovered
  - Certificates expiring in < 30 days
  - Risk score exceeds threshold
  - Scan failures
- [ ] Implement Slack webhook integration
- [ ] Implement email notification (SMTP)
- [ ] Add webhook integration for custom alerting
- [ ] Create alert management API: `POST /tenants/{id}/alerts/policies`
- [ ] Build alert history view in UI

**Deliverable**: Real-time alerts on critical changes

---

## 🗂️ Database Schema Additions

### New Tables:

```sql
-- Enhanced certificates table
CREATE TABLE certificates (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id),
    common_name VARCHAR(255),
    san_domains JSON,  -- Subject Alternative Names
    issuer VARCHAR(255),
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    is_expired BOOLEAN,
    days_until_expiry INTEGER,
    cipher_suite VARCHAR(255),
    tls_version VARCHAR(50),
    fingerprint_sha256 VARCHAR(64),
    first_seen TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW()
);

-- Endpoints discovered by crawling
CREATE TABLE endpoints (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id),
    url VARCHAR(2048) NOT NULL,
    method VARCHAR(10),  -- GET, POST, etc.
    parameters JSON,     -- Query/body parameters
    has_authentication BOOLEAN,
    response_code INTEGER,
    discovered_by VARCHAR(50),  -- katana, manual
    first_seen TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW(),
    UNIQUE(asset_id, url, method)
);

-- Scan jobs tracking
CREATE TABLE scan_jobs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    scan_type VARCHAR(50),  -- full, quick, ports, vulnerabilities
    status VARCHAR(20),      -- pending, running, completed, failed
    celery_task_id VARCHAR(255),
    target_count INTEGER,
    completed_count INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    results_url VARCHAR(500)  -- MinIO URL to raw results
);

-- Scan schedules
CREATE TABLE scan_schedules (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    name VARCHAR(255),
    scan_type VARCHAR(50),
    cron_expression VARCHAR(100),  -- e.g., "0 2 * * *"
    is_enabled BOOLEAN DEFAULT true,
    targets JSON,  -- Asset IDs or domain list
    created_at TIMESTAMP DEFAULT NOW(),
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP
);

-- Alert policies
CREATE TABLE alert_policies (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER REFERENCES tenants(id),
    name VARCHAR(255),
    event_type VARCHAR(50),  -- new_finding, new_asset, cert_expiry
    severity_threshold VARCHAR(20),  -- critical, high, medium
    notification_channels JSON,  -- [{"type": "slack", "webhook": "..."}]
    is_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🔄 Pipeline Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Celery Beat                          │
│                 (Scheduled Triggers)                     │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│                  Discovery Pipeline                      │
│  Amass + Subfinder → DNSX → HTTPX → Naabu → [Assets]   │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│                 Enrichment Pipeline                      │
│     TLSX → [Certificates] → Katana → [Endpoints]        │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│               Vulnerability Pipeline                     │
│   Nuclei (filtered templates) → [Findings + Risk Score] │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│                  Risk Scoring Engine                     │
│   Calculate risk → Update assets → Trigger alerts       │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│                  Notify (Alerting)                       │
│         Slack / Email / Webhook notifications           │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 Success Metrics

**After Sprint 5 Completion**:
- ✅ All ProjectDiscovery tools integrated and operational
- ✅ Full scan pipeline executes end-to-end automatically
- ✅ Risk scores calculated for all assets
- ✅ Scheduled scans running on cadence
- ✅ Real-time alerts for critical findings
- ✅ Complete Tesla attack surface mapped with:
  - 463 subdomains
  - All open ports discovered
  - Certificate inventory with expiry tracking
  - Discovered endpoints and API routes
  - Actual CVE vulnerabilities identified

---

## 🚀 Implementation Order

**Day 1 Morning**: Naabu + TLSX integration (quick wins)
**Day 1 Afternoon**: Katana + Nuclei integration
**Day 2 Morning**: Celery task orchestration
**Day 2 Afternoon**: Scheduled scans + risk scoring
**Day 3 Morning**: Notify integration + alerting
**Day 3 Afternoon**: Testing + documentation

---

## 🧪 Testing Plan

For each tool integration:
1. Run tool manually on 5-10 Tesla assets
2. Verify data insertion into database
3. Check data display in UI
4. Test error handling (timeouts, empty results)
5. Verify background task execution

For full pipeline:
1. Trigger full scan on tesla.com
2. Monitor Celery task progress
3. Verify all data flows through pipeline
4. Check risk scores calculated correctly
5. Verify alerts triggered for critical findings

---

**Ready to start Sprint 5?**

Let's begin with **Phase 1.2: TLSX Certificate Intelligence** - it's the quickest win and will give us immediate value by finding expiring certificates!
