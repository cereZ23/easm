# Sprint 2 - TODO & Memo

**Created**: October 22, 2025
**Based on**: Sprint 1 completion analysis
**Status**: Planning Phase

---

## 📋 Overview

This document consolidates all actionable items, recommendations, and considerations from Sprint 1 documentation to guide Sprint 2 development.

---

## 🎯 Sprint 2 Goals (from SPRINTS.md)

### Primary Objective
**Enrichment Pipeline & Multi-Tenant API (Weeks 4-6)**

Implement enrichment tools (httpx, naabu, tlsx, katana), build FastAPI backend with JWT authentication, and create multi-tenant API endpoints.

---

## ⚡ HIGH PRIORITY ITEMS

### 1. Monitoring Integration (CRITICAL)
**Source**: SPRINT_1_DEPLOYMENT_REPORT.md, SECURITY_VERIFICATION_REPORT.md

**Tasks**:
- [ ] Set up Sentry for error tracking
  - Configure DSN in environment
  - Set `SENTRY_DSN` and `SENTRY_ENVIRONMENT`
  - Already configured in `app/config.py:145-147`
  - Test error reporting

- [ ] Implement Prometheus metrics
  - Add prometheus-client library
  - Create `/metrics` endpoint
  - Instrument critical operations
  - Set up Grafana dashboards

- [ ] Configure log aggregation
  - Choose: ELK Stack or Grafana Loki
  - Centralize logs from all services
  - Set up log retention policies
  - Configure alerting rules

**Why Critical**: Production deployment needs observability for incident response

---

### 2. Test Coverage Improvement (CRITICAL)
**Source**: FINAL_TEST_REPORT.md, SPRINT_1_DEPLOYMENT_REPORT.md

**Current State**: 62.6% (97/155 tests passing)

**Tasks**:
- [ ] Fix failing integration tests (35 failed, 23 errors)
  - **Integration tests**: 3/21 passing (14.3%)
  - **Performance tests**: 0/23 passing (0%)

- [ ] Target 80%+ test coverage
  - Add edge case tests
  - Improve security test coverage (currently 70.2%)
  - Add more repository operation tests

- [ ] Fix PostgreSQL-specific tests
  - Performance tests currently use SQLite
  - Need actual PostgreSQL for realistic metrics
  - Set up test database in CI/CD

**Files to Review**:
- `tests/test_integration_discovery.py` - Many failures
- `tests/test_performance.py` - All errors (need PostgreSQL)
- `tests/test_security.py` - Some failures to fix

---

### 3. PostgreSQL Connection Pool Tuning (HIGH)
**Source**: SPRINT_1_DEPLOYMENT_REPORT.md, DATABASE_OPTIMIZATION_REPORT.md

**Current Configuration**:
```python
postgres_pool_size: int = 20
postgres_max_overflow: int = 40
postgres_pool_pre_ping: bool = True
postgres_pool_recycle: int = 3600
```

**Tasks**:
- [ ] Load testing to determine optimal pool size
  - Test with 100, 500, 1000 concurrent connections
  - Monitor connection usage patterns
  - Identify bottlenecks

- [ ] Connection pool monitoring
  - Track pool exhaustion events
  - Monitor connection wait times
  - Set up alerts for pool issues

- [ ] Optimize based on metrics
  - Adjust pool_size based on worker count
  - Tune max_overflow for burst traffic
  - Consider connection pooler (PgBouncer)

**Recommended Tools**:
- Locust for load testing
- pg_stat_activity for monitoring
- Connection pool metrics in Prometheus

---

## 🔧 MEDIUM PRIORITY ITEMS

### 4. Full API Implementation
**Source**: SPRINTS.md Sprint 2, SPRINT_1_DEPLOYMENT_REPORT.md

**Tasks**:
- [ ] Implement REST API endpoints
  - Assets CRUD: `/api/v1/assets/`
  - Services CRUD: `/api/v1/services/`
  - Findings CRUD: `/api/v1/findings/`
  - Events listing: `/api/v1/events/`
  - Seeds management: `/api/v1/seeds/`

- [ ] JWT Authentication
  - User registration/login
  - Token refresh mechanism
  - Token revocation
  - Password reset flow

- [ ] Multi-tenant API
  - Tenant-scoped endpoints
  - Tenant isolation verification
  - API key management per tenant
  - Rate limiting per tenant

- [ ] API Documentation
  - OpenAPI/Swagger integration
  - Auto-generated docs at `/docs`
  - API versioning strategy
  - Example requests/responses

**Reference**: `SPRINTS.md` lines 200-500 for detailed API specifications

---

### 5. Enrichment Pipeline Implementation
**Source**: SPRINTS.md Sprint 2

**Tools to Implement**:

- [ ] **HTTPx** - HTTP probing and tech detection
  - File: `app/tasks/enrichment.py`
  - Features: title extraction, server detection, tech stack
  - Store results in Service model

- [ ] **Naabu** - Port scanning
  - Full port scan vs top 1000 ports
  - Service version detection
  - Integration with Service model

- [ ] **TLSx** - SSL/TLS analysis
  - Certificate information
  - SSL/TLS version detection
  - Vulnerability checking

- [ ] **Katana** - Web crawling
  - Endpoint discovery
  - JavaScript file analysis
  - URL extraction

**Important**: All new tools MUST use `SecureToolExecutor` (see Sprint 1 migration)

**Example Pattern**:
```python
from app.utils.secure_executor import SecureToolExecutor

@celery.task(name='app.tasks.enrichment.run_httpx')
def run_httpx(tenant_id: int, asset_ids: list = None):
    with SecureToolExecutor(tenant_id) as executor:
        input_file = executor.create_input_file('hosts.txt', hosts_content)
        output_file = 'httpx_results.json'

        returncode, stdout, stderr = executor.execute(
            'httpx',
            ['-l', input_file, '-json', '-o', output_file],
            timeout=1800
        )

        results = executor.read_output_file(output_file)
        # Process results...
```

---

### 6. Security Enhancements (MEDIUM)
**Source**: SECURITY_VERIFICATION_REPORT.md

**Recommended Improvements**:

- [ ] **Input Validation** (MEDIUM Priority)
  - Add explicit length limits:
    ```python
    MAX_KEYWORD_LENGTH = 100
    MAX_DOMAIN_LENGTH = 253  # RFC 1035
    MAX_IDENTIFIER_LENGTH = 255
    ```
  - Stricter regex for keywords:
    ```python
    if not re.match(r'^[a-zA-Z0-9\s\-_]+$', keyword):
        logger.warning(f"Invalid keyword format: {keyword}")
        continue
    ```

- [ ] **Null Byte Protection** (LOW Priority)
  - Add to dangerous characters:
    ```python
    dangerous_chars = [';', '&', '|', '$', '`', '\n', '\r', '\x00']
    ```

- [ ] **Rate Limiting** (MEDIUM Priority)
  - Implement with slowapi:
    ```python
    from slowapi import Limiter, _rate_limit_exceeded_handler
    limiter = Limiter(key_func=get_remote_address)
    ```
  - Already configured in `config.py:133-135`
  - Need actual middleware implementation

- [ ] **Dependency Security** (MEDIUM Priority)
  - Review `python-jose==3.3.0` for CVEs
  - Consider migrating to PyJWT directly
  - Check `requests==2.31.0` for updates
  - Set up automated dependency scanning:
    ```bash
    pip install safety
    safety check --json
    ```

---

## 📊 OPTIMIZATION OPPORTUNITIES

### 7. Database Query Optimizations
**Source**: DATABASE_OPTIMIZATION_REPORT.md

**Already Completed** ✅:
- Bulk upsert with native PostgreSQL UPSERT
- Strategic indexes via migration 003
- N+1 query elimination

**Remaining Opportunities**:
- [ ] Add database query logging for slow queries
  - Track queries > 100ms
  - Identify new N+1 patterns
  - Monitor index usage

- [ ] Implement query result caching
  - Redis cache for frequently accessed data
  - Cache invalidation strategy
  - TTL configuration

- [ ] Optimize critical queries
  - Review `get_critical_assets` performance under load
  - Optimize pagination queries
  - Consider materialized views for reports

---

### 8. Docker & Infrastructure Improvements
**Source**: DEPLOYMENT_CHECKLIST.md, SPRINT_1_DEPLOYMENT_REPORT.md

**Post-Deployment Tasks**:
- [ ] SSL/TLS certificates
  - Let's Encrypt integration
  - Certificate auto-renewal
  - HTTPS redirect

- [ ] Load balancer configuration
  - Use `/health` endpoint for checks
  - Sticky sessions if needed
  - SSL termination

- [ ] Backup strategy
  - PostgreSQL automated backups
  - MinIO bucket replication
  - Backup retention policy
  - Disaster recovery testing

- [ ] Disaster recovery plan
  - Document recovery procedures
  - Test recovery from backups
  - RTO/RPO definitions

---

## 🧪 TESTING STRATEGY

### 9. Integration Test Fixes
**Source**: FINAL_TEST_REPORT.md

**Failing Test Files**:

1. **test_integration_discovery.py** (3/21 passing)
   - `test_collect_seeds_integration` - ERROR
   - `test_dnsx_integration` - FAILED
   - `test_process_discovery_results_integration` - ERROR
   - `test_full_pipeline_chain` - ERROR
   - Most errors related to database connections

   **Action**: Fix database setup in integration tests

2. **test_performance.py** (0/23 passing)
   - All tests have ERRORs
   - Root cause: Using SQLite instead of PostgreSQL
   - Performance tests need actual PostgreSQL

   **Action**: Set up PostgreSQL test database

3. **test_security.py** (33/47 passing)
   - `test_shell_metacharacters_escaped` - FAILED
   - `test_path_traversal_via_filename` - FAILED
   - `test_symlink_attacks_prevented` - FAILED
   - SQL injection tests - ERRORS

   **Action**: Review and fix security test assumptions

4. **test_repositories.py** (29/33 passing)
   - `test_bulk_upsert_creates_records` - FAILED
   - `test_asset_queries_include_tenant_filter` - FAILED

   **Action**: Fix bulk upsert and tenant isolation tests

---

## 📖 DOCUMENTATION NEEDS

### 10. Documentation to Create/Update

- [ ] **API Documentation**
  - OpenAPI/Swagger specification
  - Authentication guide
  - Multi-tenant usage examples
  - Rate limiting documentation

- [ ] **Deployment Guide**
  - Production deployment checklist
  - Environment variable reference
  - Scaling guidelines
  - Monitoring setup

- [ ] **Operations Runbook**
  - Common troubleshooting scenarios
  - Database maintenance procedures
  - Backup/restore procedures
  - Incident response playbook

- [ ] **Developer Guide**
  - Architecture overview
  - Adding new enrichment tools
  - Testing guidelines
  - Contributing guide

---

## 🔍 TECHNICAL DEBT & CLEANUP

### 11. Code Quality Improvements
**Source**: Code review from Sprint 1

**Identified Issues**:

- [ ] **Test Fixtures** (LOW Priority)
  - Some tests failing due to fixture conflicts
  - Review `conftest.py` for proper scoping
  - Fix session vs function scope issues

- [ ] **Error Handling** (MEDIUM Priority)
  - Standardize error responses
  - Consistent exception handling
  - Better error messages for API

- [ ] **Code Documentation** (LOW Priority)
  - Add docstrings to all public functions
  - Document complex algorithms
  - Add type hints consistently

---

## 📦 DEPENDENCIES & UPGRADES

### 12. Dependency Management
**Source**: SECURITY_VERIFICATION_REPORT.md, requirements.txt

**Review for Upgrades**:
- [ ] `python-jose==3.3.0` → Consider PyJWT directly
- [ ] `requests==2.31.0` → Check for security updates
- [ ] `pyyaml==6.0.1` → Ensure using safe_load()
- [ ] All dependencies - Run `pip list --outdated`

**New Dependencies Needed**:
- [ ] `prometheus-client` - Metrics
- [ ] `slowapi` - Rate limiting
- [ ] `sentry-sdk` - Already in requirements ✅
- [ ] `safety` - Dependency scanning (dev)

---

## 🎭 SPRINT 2 SPECIFIC TASKS (from SPRINTS.md)

### Phase 1: Enrichment Pipeline (Weeks 4-5)

- [ ] Implement HTTPx enrichment task
- [ ] Implement Naabu port scanning
- [ ] Implement TLSx SSL analysis
- [ ] Implement Katana web crawling
- [ ] Create enrichment orchestration
- [ ] Add enrichment results to Service model
- [ ] Test enrichment pipeline end-to-end

### Phase 2: API Development (Weeks 5-6)

- [ ] Design API structure and endpoints
- [ ] Implement JWT authentication
- [ ] Create user management endpoints
- [ ] Implement asset management API
- [ ] Implement findings management API
- [ ] Add API documentation (Swagger)
- [ ] Implement rate limiting
- [ ] Add API versioning
- [ ] Write API tests

### Phase 3: Multi-Tenancy (Week 6)

- [ ] Implement tenant-scoped API endpoints
- [ ] Add API key management per tenant
- [ ] Implement tenant isolation in API
- [ ] Add tenant usage metrics
- [ ] Test cross-tenant isolation
- [ ] Document multi-tenant API usage

---

## 🚨 CRITICAL REMINDERS

### Security Requirements (MUST DO)

1. ✅ **All enrichment tools MUST use SecureToolExecutor**
   - Pattern established in Sprint 1
   - No direct subprocess.run() calls
   - Always use context manager for cleanup

2. ✅ **All API endpoints MUST enforce tenant isolation**
   - Filter all queries by tenant_id
   - Validate tenant access in middleware
   - Test for cross-tenant access

3. ✅ **All user inputs MUST be validated**
   - Length limits
   - Character whitelist
   - SQL injection prevention
   - Command injection prevention

4. ✅ **Rate limiting MUST be implemented**
   - Already configured in config.py
   - Need middleware implementation
   - Per-tenant limits

---

## 📝 DOCUMENTATION REFERENCES

**Key Files to Reference**:

1. **SPRINTS.md** - Sprint 2 detailed implementation plan
2. **SPRINT_1_DEPLOYMENT_REPORT.md** - Sprint 2 next steps (lines 510-540)
3. **SECURITY_VERIFICATION_REPORT.md** - Security recommendations
4. **DATABASE_OPTIMIZATION_REPORT.md** - Query optimization patterns
5. **FINAL_TEST_REPORT.md** - Test failures to fix
6. **DEPLOYMENT_CHECKLIST.md** - Production deployment tasks

**Code Examples**:
- `app/tasks/discovery.py` - SecureToolExecutor pattern
- `app/repositories/asset_repository.py` - Bulk operations pattern
- `app/config.py` - Configuration validation pattern
- `app/main.py` - Health check pattern

---

## ✅ SUCCESS CRITERIA FOR SPRINT 2

### Functional Requirements
- [ ] All 4 enrichment tools working (httpx, naabu, tlsx, katana)
- [ ] Complete API with authentication
- [ ] Multi-tenant API working
- [ ] All Sprint 2 features tested

### Quality Requirements
- [ ] Test coverage ≥ 80%
- [ ] All integration tests passing
- [ ] No critical security issues
- [ ] API documentation complete

### Performance Requirements
- [ ] API response time < 100ms (p95)
- [ ] Enrichment pipeline completes in < 30min for 1000 assets
- [ ] Database queries optimized
- [ ] Rate limiting working

### Infrastructure Requirements
- [ ] Monitoring fully operational
- [ ] Logging aggregation working
- [ ] Alerts configured
- [ ] Backup/restore tested

---

## 🎯 SPRINT 2 KICKOFF CHECKLIST

**Before starting Sprint 2**:

- [ ] Review SPRINTS.md Sprint 2 section in detail
- [ ] Set up monitoring infrastructure first
- [ ] Create Sprint 2 git branch
- [ ] Set up project management board with tasks
- [ ] Assign priorities to all tasks
- [ ] Schedule regular check-ins
- [ ] Review this TODO document with team

**First Week Focus**:
1. Monitoring setup (Sentry, Prometheus, Logging)
2. Test suite fixes (get to 80% passing)
3. HTTPx enrichment implementation
4. Start API design document

---

## 📞 CONTACTS & RESOURCES

**Documentation**:
- Sprint Plans: `SPRINTS.md`
- Security: `SECURITY_VERIFICATION_REPORT.md`
- Performance: `DATABASE_OPTIMIZATION_REPORT.md`
- Deployment: `SPRINT_1_DEPLOYMENT_REPORT.md`

**Repositories**:
- Main: (current repository)
- ProjectDiscovery Tools: https://github.com/projectdiscovery

**Monitoring**:
- Sentry: (to be configured)
- Prometheus: (to be configured)
- Grafana: (to be configured)

---

**Last Updated**: October 22, 2025
**Status**: Ready for Sprint 2 Planning
**Next Review**: Start of Sprint 2

---

## 🏁 CONCLUSION

Sprint 2 builds on the solid foundation of Sprint 1. Focus areas:

1. **Week 4**: Monitoring + HTTPx + Naabu + Test fixes
2. **Week 5**: TLSx + Katana + API foundation + JWT auth
3. **Week 6**: Multi-tenant API + API testing + Documentation

**Critical Success Factors**:
- Monitoring MUST be set up first
- All tools MUST use SecureToolExecutor
- Tests MUST reach 80% coverage
- Security MUST be maintained

**Expected Outcome**: Production-ready enrichment pipeline with fully functional multi-tenant API.
