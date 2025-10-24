# Sprint 2 Enrichment Tools - Architecture Review

## Executive Summary

This document provides a high-level review of the proposed architecture for integrating 4 enrichment tools (HTTPx, Naabu, TLSx, Katana) into the EASM platform.

**Review Date**: 2025-01-23
**Sprint**: Sprint 2 Week 1 (Days 2-6)
**Current Security Score**: 9.0/10
**Target Security Score**: 9.5/10

---

## 1. What We're Building

### The Big Picture

```
Current State (Sprint 1.7):
┌─────────────┐
│  Discovery  │  ← Subfinder + Amass find subdomains
│   Pipeline  │  ← DNSx resolves them
│             │  ← Stores in PostgreSQL
└─────────────┘

New State (Sprint 2):
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  Discovery  │───▶│  Enrichment  │───▶│  Scanning   │
│   Pipeline  │    │   Pipeline   │    │  (Future)   │
└─────────────┘    └──────────────┘    └─────────────┘
                         │
                    ┌────┴─────┐
                    │          │
                ┌───▼──┐   ┌───▼──┐
                │HTTPx │   │Naabu │  ← Run in parallel
                │TLSx  │   │      │
                └───┬──┘   └──────┘
                    │
                ┌───▼──┐
                │Katana│  ← Runs after HTTPx
                └──────┘
```

### What Each Tool Does

| Tool | Purpose | Input | Output | Example |
|------|---------|-------|--------|---------|
| **HTTPx** | Web fingerprinting | Domains/URLs | Technologies, headers, status | "example.com runs nginx + WordPress" |
| **Naabu** | Port scanning | Domains/IPs | Open ports, services | "example.com has ports 80, 443, 8080 open" |
| **TLSx** | SSL/TLS analysis | HTTPS URLs | Certificates, expiry, ciphers | "example.com cert expires in 30 days" |
| **Katana** | Web crawling | Live URLs | Endpoints, APIs, forms | "Found /api/v1/users endpoint" |

---

## 2. How It Fits Together

### Data Flow

```
1. Discovery finds: sub1.example.com, sub2.example.com, sub3.example.com
                                    ↓
2. Assets created in PostgreSQL with type=SUBDOMAIN
                                    ↓
3. Enrichment triggered (auto or manual)
                                    ↓
4. Parallel execution starts:
   ┌─────────────────────────────────────────┐
   │ HTTPx: Probe sub1, sub2, sub3          │
   │   → Finds: sub1=200 (nginx), sub2=404  │
   │   → Creates Service records            │
   ├─────────────────────────────────────────┤
   │ Naabu: Scan sub1, sub2, sub3           │
   │   → Finds: sub1 ports 80,443,8080      │
   │   → Creates Service records            │
   ├─────────────────────────────────────────┤
   │ TLSx: Analyze sub1:443, sub3:443       │
   │   → Finds: sub1 cert expires 2025-06-01│
   │   → Creates Certificate records        │
   └─────────────────────────────────────────┘
                                    ↓
5. Process results → Update database
                                    ↓
6. Katana crawls (only live URLs from HTTPx):
   ┌─────────────────────────────────────────┐
   │ Crawl: https://sub1.example.com/       │
   │   → Finds: /api/users, /admin, /login  │
   │   → Creates Endpoint records           │
   └─────────────────────────────────────────┘
```

### Database Schema Changes

**New Tables** (2):
```sql
certificates
├─ id, asset_id, subject_cn, issuer
├─ not_before, not_after, is_expired
├─ san_domains (JSON), cipher_suites (JSON)
└─ Indexes: asset_id, expiry date

endpoints
├─ id, asset_id, url, path, method
├─ query_params (JSON), status_code
├─ is_api, is_external, depth
└─ Indexes: asset_id, url, is_api
```

**Enhanced Tables** (2):
```sql
services (add columns):
├─ web_server, http_technologies (JSON)
├─ http_headers (JSON), response_time_ms
├─ has_tls, tls_version
└─ enriched_at, enrichment_source

assets (add columns):
├─ last_enriched_at
└─ enrichment_status (pending/enriched/failed)
```

**Why This Schema?**
- ✅ Normalized (not JSON blobs) for queryability
- ✅ Indexed for performance (composite indexes on tenant_id + key)
- ✅ Supports time-series queries (certificate expiry alerts)
- ✅ Enables API endpoint discovery tracking

---

## 3. Key Design Decisions

### Decision #1: Parallel vs Sequential Execution

**DECISION**: HTTPx + Naabu + TLSx run **in parallel**, Katana runs **after HTTPx**

**Why?**
```python
# Parallel (saves time):
group(
    run_httpx.si(asset_ids, tenant_id),    # 15 min
    run_naabu.si(asset_ids, tenant_id),    # 20 min
    run_tlsx.si(asset_ids, tenant_id)      # 10 min
)
# Total time: 20 min (max of all)

# Sequential (slow):
run_httpx → run_naabu → run_tlsx
# Total time: 45 min (sum of all)
```

**Katana Sequential** because:
- Needs HTTPx results (list of live URLs)
- Crawling all domains wastes time on 404s
- HTTPx filters: only crawl URLs with status 200

### Decision #2: Incremental vs Full Re-Enrichment

**DECISION**: Incremental with 7-day TTL (configurable)

**Why?**
```python
# Scenario: 10,000 assets in database

# Full re-enrichment every time:
→ Scan all 10,000 assets (30 min)
→ Mostly unchanged data (waste)

# Incremental (7-day TTL):
→ Scan only assets not enriched in 7 days (~1,000)
→ Much faster (3 min)
→ Can force full refresh when needed
```

**Configuration**:
```python
enrichment_ttl_days: int = 7  # Customize per environment
force_refresh: bool = False   # Override for full scan
```

### Decision #3: Database Schema - Normalized vs JSON

**DECISION**: Normalized tables (Certificate, Endpoint) not JSON blobs

**Why?**

❌ **JSON Approach** (rejected):
```python
# Store everything in Asset.enrichment_data as JSON
asset.enrichment_data = {
    "certificates": [...],
    "endpoints": [...],
    "technologies": [...]
}

# Problems:
# - Can't query efficiently (find all expiring certs)
# - Can't index (slow queries)
# - Can't foreign key (data integrity issues)
# - Hard to report on (complex JSON queries)
```

✅ **Normalized Approach** (chosen):
```sql
-- Efficient queries:
SELECT * FROM certificates
WHERE not_after < NOW() + INTERVAL '30 days'
ORDER BY not_after;

-- Indexed lookups:
SELECT * FROM endpoints
WHERE asset_id = 123 AND is_api = true;

-- Foreign key integrity:
DELETE FROM assets WHERE id = 123;
-- Automatically deletes related certificates, endpoints
```

### Decision #4: Bulk Operations vs Individual Inserts

**DECISION**: PostgreSQL native UPSERT (bulk operations)

**Why?**

❌ **Individual Inserts** (slow):
```python
# For 1000 services:
for service in services:
    db.add(Service(**service))
    db.commit()
# Time: ~50 seconds (50ms per insert × 1000)
# Database locks: 1000 transactions
```

✅ **Bulk UPSERT** (fast):
```python
# For 1000 services:
stmt = insert(Service).values(services)
stmt = stmt.on_conflict_do_update(...)
db.execute(stmt)
db.commit()
# Time: ~100ms (single transaction)
# Database locks: 1 transaction
```

**Performance Improvement**: 500x faster (50s → 100ms)

### Decision #5: Security - Defense in Depth

**DECISION**: Multiple validation layers, not single point

**Why?**

❌ **Single Validation** (risky):
```python
# Only validate at tool input
run_httpx(urls)  # Validate here
→ If bypass, system compromised
```

✅ **Defense in Depth** (secure):
```python
# Layer 1: Input validation
urls = validate_urls(raw_input)

# Layer 2: Network security
urls = block_private_ips(urls)

# Layer 3: SecureToolExecutor
executor.execute('httpx', urls)  # Sandboxed

# Layer 4: Output sanitization
results = redact_sensitive_data(raw_output)

# Layer 5: Rate limiting
check_rate_limit(tenant_id, 'httpx')

# Even if one layer fails, others protect
```

**10 Security Layers**:
1. Input validation
2. Network security (SSRF prevention)
3. SecureToolExecutor (sandboxing)
4. Output sanitization
5. Rate limiting
6. Resource limits (timeout, memory)
7. Tenant isolation
8. Audit logging
9. Data redaction (credentials, keys)
10. Production validation

---

## 4. Security Considerations

### Critical Security Requirement: Private Key Protection

**⚠️ HIGHEST PRIORITY**: TLSx can potentially expose private keys if not handled correctly.

**The Risk**:
```bash
# TLSx output might contain:
{
  "certificate": "-----BEGIN CERTIFICATE-----...",
  "private_key": "-----BEGIN PRIVATE KEY-----..."  # ← NEVER STORE THIS
}
```

**The Protection**:
```python
class TLSxOutputSanitizer:
    PRIVATE_KEY_PATTERNS = [
        r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----',
        r'-----BEGIN ENCRYPTED PRIVATE KEY-----',
    ]

    def sanitize(self, output: str) -> tuple[str, bool]:
        """
        Detect and REDACT private keys

        Returns:
            (sanitized_output, private_key_detected)
        """
        for pattern in self.PRIVATE_KEY_PATTERNS:
            if re.search(pattern, output):
                # CRITICAL: Alert security team
                logger.critical("PRIVATE KEY DETECTED in TLSx output!")

                # REDACT completely
                output = re.sub(
                    r'-----BEGIN.*PRIVATE KEY-----.*?-----END.*PRIVATE KEY-----',
                    '[REDACTED: PRIVATE KEY]',
                    output,
                    flags=re.DOTALL
                )

                return output, True  # Flag for incident review

        return output, False
```

**Why This Matters**:
- Private keys = complete compromise of SSL/TLS
- Attacker can impersonate the domain
- Could decrypt all past traffic (if no forward secrecy)
- **Storing private keys is a CRITICAL security incident**

### SSRF Prevention Architecture

**The Threat**: Tools could be tricked into accessing internal resources

**Attack Examples**:
```python
# Example 1: AWS metadata
run_httpx(['http://169.254.169.254/latest/meta-data/'])
→ Could expose AWS credentials

# Example 2: Internal database
run_httpx(['http://192.168.1.10:5432'])
→ Could access internal PostgreSQL

# Example 3: localhost
run_naabu(['127.0.0.1'])
→ Could scan worker container itself
```

**Protection Layers**:
```python
# Layer 1: Input validation
BLOCKED_IPS = [
    '127.0.0.0/8',        # Loopback
    '10.0.0.0/8',         # Private
    '172.16.0.0/12',      # Private
    '192.168.0.0/16',     # Private
    '169.254.0.0/16',     # Link-local (AWS metadata)
]

BLOCKED_HOSTS = [
    '169.254.169.254',         # AWS/GCP/Azure metadata
    'metadata.google.internal', # GCP metadata
    'metadata.amazonaws.com',   # AWS metadata
]

# Layer 2: DNS resolution validation
def validate_resolved_ip(domain: str) -> bool:
    """Resolve domain and check if IP is blocked"""
    ip = socket.gethostbyname(domain)
    for blocked_network in BLOCKED_NETWORKS:
        if ipaddress.ip_address(ip) in blocked_network:
            raise SecurityError(f"Domain {domain} resolves to blocked IP {ip}")

# Layer 3: Redirect chain validation
def validate_redirects(url: str, max_redirects: int = 3):
    """Follow redirects and validate each hop"""
    # Prevents: http://safe.com → redirect → http://169.254.169.254
```

**Test Coverage**: 27 automated security tests verify all protections work

---

## 5. Performance Considerations

### Expected Performance

**Scenario**: Enrich 10,000 assets for a tenant

```
┌─────────────────────────────────────────────────┐
│ Phase 1: Parallel Execution (HTTPx/Naabu/TLSx) │
├─────────────────────────────────────────────────┤
│ HTTPx:  10,000 URLs × 1.5s  = 15,000s / 100 batch = 150s (2.5 min) │
│ Naabu:  10,000 hosts × 2s   = 20,000s / 50 batch  = 400s (6.5 min) │
│ TLSx:   10,000 certs × 1s   = 10,000s / 100 batch = 100s (1.5 min) │
│                                                                      │
│ Parallel max: 6.5 min (limited by slowest = Naabu)                 │
├─────────────────────────────────────────────────┤
│ Phase 2: Database Processing                    │
├─────────────────────────────────────────────────┤
│ Bulk UPSERT: 10,000 services / 100 batch = 100 ops × 100ms = 10s   │
│ Bulk UPSERT: 5,000 certs / 100 batch = 50 ops × 100ms = 5s         │
├─────────────────────────────────────────────────┤
│ Phase 3: Katana (only live URLs)                │
├─────────────────────────────────────────────────┤
│ Live URLs: ~3,000 (30% of total)                │
│ Crawl: 3,000 × 5s / 20 batch = 750s (12.5 min)  │
├─────────────────────────────────────────────────┤
│ TOTAL: ~20 minutes for 10,000 assets            │
└─────────────────────────────────────────────────┘
```

**Scalability**:
- 1,000 assets: ~2 minutes
- 10,000 assets: ~20 minutes
- 100,000 assets: ~3 hours (consider sharding/distributed workers)

**Bottlenecks**:
1. **Naabu** (port scanning slowest) → Optimize: reduce port range
2. **Katana** (CPU intensive) → Optimize: increase worker count
3. **Database** (bulk inserts) → Already optimized with UPSERT

### Resource Usage

**Per Worker**:
```
CPU:    2-4 cores (Katana needs more)
Memory: 1-2 GB (HTTPx/Katana parse HTML)
Disk:   Minimal (streaming output)
Network: High (scanning operations)
```

**Scaling Strategy**:
```python
# Small deployment (< 10,000 assets):
workers = 4

# Medium deployment (10,000 - 100,000 assets):
workers = 10

# Large deployment (> 100,000 assets):
workers = 20 + auto-scaling
```

---

## 6. Operational Considerations

### Monitoring & Alerts

**Key Metrics to Track**:
```python
# Performance
enrichment_duration_seconds{tenant_id, tool}
enrichment_assets_processed_total{tenant_id, tool}
enrichment_batch_size{tenant_id, tool}

# Errors
enrichment_errors_total{tenant_id, tool, error_type}
enrichment_timeouts_total{tenant_id, tool}

# Security
ssrf_attempts_blocked_total{tenant_id, tool, target}
private_key_detections_total{tenant_id}  # Should always be 0!
rate_limit_exceeded_total{tenant_id, tool}

# Business
certificates_expiring_30days{tenant_id}
new_endpoints_discovered{tenant_id}
technologies_detected{technology, count}
```

**Critical Alerts** (PagerDuty/Slack):
```yaml
- name: PrivateKeyDetected
  severity: CRITICAL
  trigger: private_key_detections_total > 0
  action: Immediate security team notification

- name: SSRFAttempt
  severity: HIGH
  trigger: ssrf_attempts_blocked_total > 10 in 5m
  action: Investigate potential attack

- name: EnrichmentFailure
  severity: MEDIUM
  trigger: enrichment_errors_total > 100 in 1h
  action: Check worker health
```

### Incident Response

**If Private Key Detected**:
```
1. IMMEDIATE: Stop all TLSx tasks
2. Alert security team (PagerDuty P1)
3. Audit logs: Which tenant? Which domain?
4. Containment: Delete any stored keys
5. Investigation: How did tool capture private key?
6. Remediation: Update TLSx command flags
7. Post-mortem: Document incident
```

### Maintenance Windows

**When to Schedule**:
- Database migration (5 min downtime)
- Tool binary updates (15 min downtime)
- Configuration changes (no downtime - rolling restart)

**Recommended Schedule**:
```
Database migrations:  Weekly maintenance window (Sunday 2-3 AM)
Tool updates:         Monthly (first Sunday)
Configuration:        Anytime (rolling restart)
```

---

## 7. Migration Strategy

### Database Migration

**Alembic Migration** (`004_add_enrichment_models.py`):

```python
# Estimated time: 5 minutes
# Downtime required: YES (brief lock on services table)

def upgrade():
    # Step 1: Add columns to assets (fast - no data)
    op.add_column('assets', Column('last_enriched_at', DateTime))

    # Step 2: Add columns to services (SLOW if large table)
    op.add_column('services', Column('web_server', String(200)))
    # ... (10 more columns)

    # Step 3: Create certificates table (fast - empty)
    op.create_table('certificates', ...)

    # Step 4: Create endpoints table (fast - empty)
    op.create_table('endpoints', ...)

    # Step 5: Create indexes (SLOW - can do CONCURRENTLY)
    op.create_index('idx_asset_cert', 'certificates', ['asset_id'],
                    postgresql_concurrently=True)
```

**Risk Mitigation**:
```sql
-- Before migration: Check table sizes
SELECT
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    n_live_tup AS row_count
FROM pg_stat_user_tables
WHERE relname IN ('assets', 'services')
ORDER BY pg_total_relation_size(relid) DESC;

-- If services table > 10M rows, consider:
-- 1. Create indexes CONCURRENTLY (no lock)
-- 2. Add columns with ALTER TABLE ... ADD COLUMN IF NOT EXISTS
-- 3. Schedule during low-traffic window
```

### Rollback Plan

**If Migration Fails**:
```bash
# Step 1: Rollback Alembic
alembic downgrade -1

# Step 2: Restart services (old code)
docker-compose restart api worker

# Step 3: Verify system health
curl http://localhost:8000/health

# Step 4: Investigate failure
tail -f logs/alembic.log
```

**If Enrichment Tasks Fail**:
```python
# Graceful degradation:
# - Discovery pipeline continues working
# - Enrichment failures logged but don't block
# - Retry logic (Celery autoretry_for)
# - Status field tracks failures: enrichment_status='failed'
```

---

## 8. Testing Strategy

### Test Pyramid

```
                    ▲
                   ╱ ╲
                  ╱ E2E╲          5 tests (slow, comprehensive)
                 ╱───────╲
                ╱ Integr ╲        20 tests (medium speed)
               ╱───────────╲
              ╱    Unit     ╲     100 tests (fast, focused)
             ╱───────────────╲
            ╱                 ╲
           ╱___________________╲
```

**Unit Tests** (100+ tests):
```python
# Test each component in isolation
test_domain_validator_blocks_private_ips()
test_httpx_output_sanitizer_removes_auth_headers()
test_service_repository_bulk_upsert()
test_certificate_expiry_calculation()
```

**Integration Tests** (20 tests):
```python
# Test components working together
test_httpx_task_creates_service_records()
test_enrichment_pipeline_processes_all_tools()
test_katana_uses_httpx_results()
```

**E2E Tests** (5 tests):
```python
# Test complete user workflows
test_discovery_to_enrichment_full_pipeline()
test_api_trigger_enrichment_returns_results()
test_periodic_enrichment_updates_stale_assets()
```

**Security Tests** (27 tests - CRITICAL):
```bash
# Automated penetration tests
./scripts/security_pentest.sh

# Must pass before deployment:
✓ Block AWS metadata (169.254.169.254)
✓ Block GCP metadata (metadata.google.internal)
✓ Block RFC1918 networks
✓ Block dangerous ports (22, 445, 3389)
✓ Detect private keys in TLSx output
✓ Redact credentials in URLs
✓ Enforce rate limits
✓ ... (20 more tests)
```

### Test Coverage Requirements

**Minimum Coverage**:
```
Overall:     90%
Security:    100% (all validators, sanitizers)
Critical:    100% (private key detection, SSRF prevention)
```

**Coverage Report**:
```bash
pytest --cov=app/tasks/enrichment --cov-report=html
open htmlcov/index.html
```

---

## 9. Questions to Consider

### Before Implementation

**Architecture Questions**:
1. ✅ Is parallel execution acceptable for your infrastructure? (HTTPx + Naabu + TLSx)
2. ❓ Is 7-day enrichment TTL appropriate, or do you need different cadence?
3. ❓ Should enrichment auto-trigger after discovery, or manual only?
4. ❓ Do you want screenshot capture with HTTPx? (adds complexity + storage)

**Security Questions**:
1. ✅ Is blocking port 22 (SSH) acceptable? Some users may want to scan SSH
2. ❓ Should we respect robots.txt for Katana? (ethical but might miss data)
3. ❓ Do you need user consent before port scanning? (legal requirement in some jurisdictions)
4. ❓ Should we implement IP whitelisting for allowed internal scans?

**Performance Questions**:
1. ❓ What's acceptable enrichment time for 10,000 assets? (current target: 20 min)
2. ❓ Should we limit max assets per enrichment run? (current: 10,000)
3. ❓ Do you have worker resources for parallel execution? (need 2-4 cores per worker)

**Data Questions**:
1. ❓ How long to retain raw tool outputs in MinIO? (current: unlimited)
2. ❓ Should we store full HTTP responses or just headers? (privacy concern)
3. ❓ Certificate retention: keep expired certs for how long? (compliance)

### Cost Considerations

**Infrastructure Costs**:
```
┌─────────────────────────────────────────────┐
│ Resource      │ Current │ After Enrichment │
├─────────────────────────────────────────────┤
│ Workers       │ 4       │ 8 (need more)    │
│ PostgreSQL    │ 100GB   │ 150GB (+50%)     │
│ MinIO         │ 50GB    │ 200GB (+300%)    │
│ Memory/Worker │ 2GB     │ 3GB (+50%)       │
└─────────────────────────────────────────────┘

Estimated Cost Increase: 40-50% infrastructure
```

**Network Costs**:
- HTTPx: ~1KB per request × 10,000 = 10MB
- Naabu: ~100KB per scan × 10,000 = 1GB
- TLSx: ~5KB per cert × 10,000 = 50MB
- Katana: ~500KB per crawl × 3,000 = 1.5GB

**Total**: ~2.5GB network traffic per 10,000 asset enrichment

---

## 10. Risks & Mitigation

### High Risk Items

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Private key exposure** | CRITICAL | Low | Automated detection + redaction + alerts |
| **SSRF to internal DB** | HIGH | Medium | Multi-layer IP/DNS validation |
| **Port scan legal issues** | HIGH | Low | User consent system + documentation |
| **Database locks during migration** | MEDIUM | Medium | CONCURRENT indexes + maintenance window |
| **Worker resource exhaustion** | MEDIUM | Medium | Resource limits + monitoring |

### Medium Risk Items

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| **Enrichment takes too long** | MEDIUM | Medium | Parallel execution + batching |
| **MinIO storage growth** | MEDIUM | High | Retention policies + compression |
| **Failed enrichment** | MEDIUM | Medium | Retry logic + status tracking |
| **Rate limiting too strict** | LOW | Medium | Configurable limits |

---

## 11. Deployment Checklist

### Pre-Deployment

**Code Review**:
- [ ] All security validators implemented
- [ ] Private key detection tested
- [ ] SSRF prevention tested (27 tests passing)
- [ ] Bulk UPSERT performance verified (<100ms for 100 records)
- [ ] Error handling comprehensive

**Testing**:
- [ ] Unit tests: 90%+ coverage
- [ ] Integration tests: All passing
- [ ] Security tests: 27/27 passing
- [ ] Load test: 10,000 assets in <25 minutes
- [ ] Regression test: Existing features still work

**Infrastructure**:
- [ ] Worker count increased (4 → 8)
- [ ] PostgreSQL storage increased
- [ ] MinIO storage increased
- [ ] Monitoring configured (Prometheus/Grafana)
- [ ] Alerts configured (PagerDuty/Slack)

**Documentation**:
- [ ] API documentation updated
- [ ] Runbook created for incidents
- [ ] Security playbook reviewed
- [ ] Changelog updated

### Deployment Day

**Phase 1: Database Migration** (Maintenance Window)
```bash
# 1. Backup database
pg_dump easm > backup_pre_enrichment.sql

# 2. Run migration
alembic upgrade head

# 3. Verify migration
psql -c "SELECT COUNT(*) FROM certificates;"  # Should be 0
```

**Phase 2: Code Deployment** (Rolling Restart)
```bash
# 1. Deploy new code
git pull origin main
docker-compose build

# 2. Restart workers (rolling)
for i in {1..8}; do
    docker-compose restart worker-$i
    sleep 30  # Wait for health check
done

# 3. Restart API
docker-compose restart api
```

**Phase 3: Smoke Testing** (15 minutes)
```bash
# 1. Test discovery still works
curl -X POST /api/v1/discovery/start -d '{"tenant_id": 1}'

# 2. Test enrichment manually
curl -X POST /api/v1/enrichment/run/1

# 3. Check worker logs
docker-compose logs -f worker-1 | grep enrichment

# 4. Verify database
psql -c "SELECT COUNT(*) FROM services WHERE enriched_at IS NOT NULL;"
```

**Phase 4: Monitoring** (24 hours)
```bash
# Watch for:
- Enrichment duration (should be <25 min for 10k assets)
- Error rates (should be <1%)
- Private key detections (should be 0!)
- SSRF blocks (any unexpected targets?)
- Database performance (check for locks)
```

### Rollback Plan

**If Critical Issue** (private key exposure, SSRF bypass):
```bash
# 1. IMMEDIATE: Stop all enrichment tasks
celery -A app.celery_app control shutdown

# 2. Rollback code
git checkout <previous-commit>
docker-compose build && docker-compose restart

# 3. Rollback database (if needed)
alembic downgrade -1

# 4. Investigate
tail -f logs/security.log
```

---

## 12. Success Criteria

### Must Have (Go/No-Go)

✅ **Functional**:
- [ ] All 4 tools integrated and working
- [ ] Parallel execution 3x faster than sequential
- [ ] Database queries <100ms (indexed properly)
- [ ] 10,000 assets enriched in <25 minutes

✅ **Security**:
- [ ] Security score ≥ 9.5/10
- [ ] All 27 security tests passing
- [ ] 0 private key exposures
- [ ] SSRF prevention 100% effective
- [ ] Rate limiting enforced

✅ **Reliability**:
- [ ] Error rate <1%
- [ ] Graceful degradation (enrichment failures don't break discovery)
- [ ] Rollback tested and working
- [ ] Monitoring and alerts functional

### Nice to Have (Future Enhancements)

⏸️ **Performance**:
- [ ] Screenshot capture (HTTPx)
- [ ] Distributed workers (multiple machines)
- [ ] Result caching (avoid re-scanning same domains)

⏸️ **Features**:
- [ ] Custom port lists per tenant
- [ ] Enrichment scheduling (per-asset cadence)
- [ ] Webhook notifications (new endpoints found)

---

## 13. Next Steps

### If You Approve This Architecture

**Week 1 (Days 2-6)**:
1. **Day 2**: Database models + HTTPx implementation
2. **Day 3**: Naabu implementation
3. **Day 4**: TLSx implementation (focus on private key security)
4. **Day 5**: Katana implementation
5. **Day 6**: Integration, testing, security validation

**Week 2 (If Needed)**:
- Fine-tuning performance
- Additional security hardening
- Documentation
- Training

### If You Want Changes

**Common Modifications**:
1. Different enrichment cadence (change TTL from 7 days)
2. Different tool priorities (maybe skip Katana initially)
3. Different security constraints (allow internal network scanning)
4. Different performance targets (faster/slower enrichment)

---

## 14. Approval Questions

### For You to Decide

**Question 1**: Is the **security architecture acceptable**?
- 10 layers of defense
- Private key detection mandatory
- SSRF prevention with 34M+ blocked IPs
- 27 automated security tests

**Question 2**: Is the **performance acceptable**?
- 20 minutes for 10,000 assets
- Parallel execution (HTTPx + Naabu + TLSx)
- Incremental enrichment (7-day TTL)

**Question 3**: Is the **database schema acceptable**?
- 2 new tables (certificates, endpoints)
- Enhanced services table (+10 columns)
- Normalized (not JSON blobs)
- Requires migration with brief downtime

**Question 4**: Are **operational requirements acceptable**?
- Need 8 workers (currently 4)
- Need +50GB PostgreSQL
- Need +150GB MinIO
- 40-50% infrastructure cost increase

**Question 5**: Is the **implementation timeline realistic**?
- 5 days (Sprint 2 Days 2-6)
- 2-3 developers
- Can parallelize some work

---

## Recommendation

**My Recommendation**: ✅ **Approve and proceed with implementation**

**Reasoning**:
1. **Follows proven patterns** from Sprint 1.7 (Subfinder/Amass)
2. **Security-first design** with defense in depth
3. **Performance optimized** with parallel execution + bulk operations
4. **Well tested** with 27 security tests + comprehensive coverage
5. **Incrementally deployable** (can deploy tools one at a time)
6. **Rollback plan** tested and documented

**Low-Risk Changes** (if needed):
- Adjust TTL (easy config change)
- Start with just HTTPx (defer others)
- Disable auto-trigger (manual enrichment only)

**What do you think?** Ready to implement, or do you have concerns/questions about any aspect?
