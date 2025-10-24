# EASM Platform - Sprint 2 Enrichment Tools Integration Design

## Executive Summary

This design document provides a production-ready architecture for integrating HTTPx, Naabu, TLSx, and Katana into the EASM platform's enrichment pipeline. The design leverages existing patterns from Sprint 1.7 (Subfinder/Amass) and extends the discovery pipeline with a parallel enrichment phase.

**Security Score Target**: 9.0/10 → 9.5/10

**Implementation Timeline**: 5 days (Sprint 2 Days 2-6)

---

## Architecture Overview

### Task Flow Diagram

```
DISCOVERY PHASE                    ENRICHMENT PHASE                    SCANNING PHASE
─────────────────                  ──────────────────                  ──────────────

collect_seeds                      run_enrichment_pipeline             run_nuclei
      │                                    │                                 │
      v                                    │                                 v
run_parallel_enumeration                  │                          [vulnerability
  (Subfinder + Amass)                     │                            scanning]
      │                                    │
      v                                    │
run_dnsx                                  │
      │                                    │
      v                                    │
process_discovery_results ────────────────┤
(creates/updates Assets)                  │
                                          v
                                   ┌──────────────────┐
                                   │ Group: Parallel  │
                                   │ HTTPx + Naabu +  │
                                   │ TLSx (parallel)  │
                                   └──────────────────┘
                                          │
                                          v
                                   process_enrichment_results
                                   (update Services, Certificates)
                                          │
                                          v
                                   run_katana
                                   (uses HTTPx results - only live HTTP)
                                          │
                                          v
                                   process_katana_results
                                   (create Endpoints)
```

### Execution Strategy

**Phase Separation:**
- Discovery phase discovers assets (domains, subdomains, IPs)
- Enrichment phase enriches known assets with service data
- Scanning phase performs vulnerability assessment

**Parallel Execution**: HTTPx, Naabu, TLSx run concurrently (independent operations)
**Sequential Katana**: Runs after HTTPx (depends on live HTTP URLs)

---

## Database Schema

### New Tables

1. **certificates** - TLS/SSL certificate data from TLSx
2. **endpoints** - HTTP endpoints discovered by Katana

### Enhanced Tables

1. **services** - Add HTTP/TLS enrichment fields
2. **assets** - Add enrichment tracking fields

### Complete Schema

See full database schema in backend-architect agent output above.

---

## Implementation Files

### New Files to Create

1. `app/models/enrichment.py` - Certificate, Endpoint models
2. `app/tasks/enrichment.py` - HTTPx, Naabu, TLSx, Katana tasks
3. `app/repositories/service_repository.py` - Service CRUD with bulk UPSERT
4. `app/repositories/certificate_repository.py` - Certificate CRUD
5. `app/repositories/endpoint_repository.py` - Endpoint CRUD
6. `app/routers/enrichment.py` - API endpoints for enrichment
7. `alembic/versions/004_add_enrichment_models.py` - Database migration
8. `tests/test_enrichment.py` - Comprehensive test suite

### Files to Modify

1. `app/config.py` - Add enrichment configuration
2. `app/models/database.py` - Enhance Service, Asset models
3. `app/tasks/discovery.py` - Add enrichment trigger
4. `app/celery_app.py` - Add beat schedules

---

## Security Requirements Summary

### Critical Security Controls

**From security-auditor agent:**

1. **Input Validation**
   - URLValidator for all URLs
   - DomainValidator for all domains
   - Port range validation (1-65535, block sensitive)
   - Depth/page limits for Katana

2. **SSRF Prevention**
   - Block RFC1918 networks (10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12)
   - Block cloud metadata (169.254.169.254, metadata.google.internal)
   - Block loopback (127.0.0.0/8)
   - Validate redirect chains

3. **Output Sanitization**
   - **CRITICAL**: Redact private keys (TLSx)
   - Redact sensitive headers (Authorization, Cookie)
   - Sanitize HTML/JS (XSS prevention)
   - Redact credentials in URLs

4. **Rate Limiting**
   - Per-tenant limits (10 req/min per tool)
   - Concurrent limits (3 per tenant per tool)
   - Global platform limits

5. **Resource Limits**
   - HTTPx: 5min timeout, 1MB response limit
   - Naabu: 20min timeout, 1000 ports max
   - TLSx: 10min timeout
   - Katana: 30min timeout, max depth 3, max pages 1000

---

## Implementation Priority

### Day 2: HTTPx (Web Technology Fingerprinting)
**Priority**: HIGH
**Dependencies**: None
**Effort**: 8 hours

**Tasks**:
1. Create `app/models/enrichment.py` (basic structure)
2. Enhance `app/models/database.py` (Service model)
3. Create `app/tasks/enrichment.py` with `run_httpx()`
4. Create `app/repositories/service_repository.py`
5. Update `app/config.py` with HTTPx settings
6. Write tests for HTTPx
7. Test end-to-end

### Day 3: Naabu (Port Scanning)
**Priority**: HIGH
**Dependencies**: None (parallel with HTTPx)
**Effort**: 6 hours

**Tasks**:
1. Add `run_naabu()` to `app/tasks/enrichment.py`
2. Add port scanning configuration
3. Implement user consent system
4. Write tests for Naabu
5. Test end-to-end

### Day 4: TLSx (Certificate Analysis)
**Priority**: HIGH
**Dependencies**: None
**Effort**: 6 hours

**Tasks**:
1. Create Certificate model in `app/models/enrichment.py`
2. Create `app/repositories/certificate_repository.py`
3. Add `run_tlsx()` to `app/tasks/enrichment.py`
4. **CRITICAL**: Implement private key detection/redaction
5. Write tests for TLSx
6. Test end-to-end

### Day 5: Katana (Web Crawling)
**Priority**: MEDIUM
**Dependencies**: HTTPx (needs live URL list)
**Effort**: 6 hours

**Tasks**:
1. Create Endpoint model in `app/models/enrichment.py`
2. Create `app/repositories/endpoint_repository.py`
3. Add `run_katana()` to `app/tasks/enrichment.py`
4. Implement robots.txt compliance
5. Write tests for Katana
6. Test end-to-end

### Day 6: Integration & Testing
**Priority**: CRITICAL
**Dependencies**: All tools
**Effort**: 8 hours

**Tasks**:
1. Create `run_enrichment_pipeline()` orchestrator
2. Add enrichment trigger to discovery.py
3. Create database migration
4. Run comprehensive tests
5. Run security pentests
6. Update Docker configuration
7. Deploy to staging

---

## Configuration

Add to `app/config.py`:

```python
# Enrichment Configuration
enrichment_enabled: bool = True
enrichment_auto_trigger: bool = True
enrichment_ttl_days: int = 7
enrichment_batch_size: int = 100

# HTTPx
httpx_timeout: int = 900
httpx_rate_limit: int = 50
httpx_response_size_limit: int = 1048576

# Naabu
naabu_timeout: int = 1200
naabu_default_ports: str = "top-1000"
naabu_blocked_ports: list = [22, 445, 3389, 3306, 5432]

# TLSx
tlsx_timeout: int = 600
tlsx_expiry_warning_days: int = 30

# Katana
katana_timeout: int = 1800
katana_max_depth: int = 3
katana_max_pages: int = 1000
katana_respect_robots: bool = True
```

---

## Success Criteria

**Functional**:
- ✅ All 4 tools integrated
- ✅ Parallel execution working
- ✅ Database models created
- ✅ Bulk UPSERT performance <100ms for 100 records
- ✅ End-to-end pipeline tested

**Security**:
- ✅ All inputs validated
- ✅ SSRF prevention tested (27 tests passing)
- ✅ Private key redaction working
- ✅ Rate limiting enforced
- ✅ Security score ≥ 9.5/10

**Performance**:
- ✅ 10,000 assets enriched in <30 minutes
- ✅ No database locks
- ✅ Memory usage <2GB per worker

---

For full implementation details, see the complete agent outputs above.
