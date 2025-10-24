# Sprint 2 Week 1 - Security Implementation Checklist
## Quick Reference for New Tool Integration

**Based on**: SPRINT_2_WEEK_1_NEW_TOOLS_SECURITY_REQUIREMENTS.md
**Target Score**: 9.5/10
**Timeline**: 5 days

---

## Daily Implementation Plan

### Day 1: Critical Validators (8 hours)

#### Morning (4 hours)
- [ ] Create `/Users/cere/Downloads/easm/app/utils/tool_validators.py`
  - [ ] Implement `ToolInputValidator` class
  - [ ] Implement `validate_httpx_input()` - URL validation, length check
  - [ ] Implement `validate_naabu_input()` - target validation, port parsing, blocked ports
  - [ ] Implement `validate_tlsx_input()` - HTTPS validation
  - [ ] Implement `validate_katana_input()` - depth/page limits
  - [ ] Implement `_parse_port_range()` helper

#### Afternoon (4 hours)
- [ ] Create `/Users/cere/Downloads/easm/app/utils/network_security.py`
  - [ ] Implement `NetworkSecurityValidator` class
  - [ ] Define `BLOCKED_NETWORKS` list (RFC1918, loopback, etc.)
  - [ ] Define `BLOCKED_HOSTS` list (cloud metadata)
  - [ ] Implement `is_safe_target()` - DNS resolution and IP validation
  - [ ] Implement `validate_redirect()` - redirect chain protection

#### Unit Tests (Evening)
- [ ] Create `/Users/cere/Downloads/easm/tests/security/test_tool_validators.py`
  - [ ] Test HTTPx validator (SSRF, file://, internal IPs)
  - [ ] Test Naabu validator (internal IPs, dangerous ports, port limits)
  - [ ] Test TLSx validator (HTTPS requirement, metadata blocks)
  - [ ] Test Katana validator (depth limits, URL validation)
  - [ ] Test NetworkSecurityValidator (all blocked ranges)

**Day 1 Success Criteria**:
- ✅ All validators implemented
- ✅ All validators prevent SSRF to 169.254.169.254
- ✅ Unit tests: 90%+ coverage
- ✅ pytest passes all validator tests

---

### Day 2: Output Sanitizers (8 hours)

#### Morning (4 hours)
- [ ] Create `/Users/cere/Downloads/easm/app/utils/output_sanitizers.py`
  - [ ] Implement `HTTPxOutputSanitizer` class
    - [ ] `SENSITIVE_HEADERS` constant
    - [ ] `sanitize()` method - redact headers, truncate body, strip JS
  - [ ] Implement `NaabuOutputSanitizer` class
    - [ ] Port limit enforcement
    - [ ] Banner truncation
  - [ ] Implement `TLSxOutputSanitizer` class
    - [ ] `PRIVATE_KEY_PATTERNS` regex list
    - [ ] `_redact_recursive()` method
    - [ ] `_alert_security_team()` method
    - [ ] Email redaction

#### Afternoon (4 hours)
- [ ] Continue output_sanitizers.py
  - [ ] Implement `KatanaOutputSanitizer` class
    - [ ] `CREDENTIAL_PATTERNS` regex list
    - [ ] `_sanitize_url()` method
    - [ ] `_sanitize_form()` method
    - [ ] URL truncation
  - [ ] Install bleach library: `pip install bleach`
  - [ ] Add bleach to requirements.txt

#### Unit Tests
- [ ] Create `/Users/cere/Downloads/easm/tests/security/test_output_sanitizers.py`
  - [ ] Test HTTPx redacts Authorization headers
  - [ ] Test HTTPx truncates large bodies
  - [ ] Test TLSx detects and redacts private keys
  - [ ] Test TLSx alerts on private key detection
  - [ ] Test Katana redacts password= in URLs
  - [ ] Test Katana redacts api_key= in URLs

**Day 2 Success Criteria**:
- ✅ All sanitizers implemented
- ✅ Private key detection works (TLSx critical test)
- ✅ Credential patterns detected in URLs
- ✅ Unit tests: 90%+ coverage
- ✅ No sensitive data leaks in test outputs

---

### Day 3: Rate Limiting & Redaction (8 hours)

#### Morning (4 hours)
- [ ] Create `/Users/cere/Downloads/easm/app/utils/rate_limiter.py`
  - [ ] Implement `ToolRateLimiter` class
  - [ ] Implement `check_rate_limit()` - per-minute limits
  - [ ] Implement `check_concurrent_limit()` - concurrent execution
  - [ ] Implement `acquire_slot()` - slot management
  - [ ] Implement `release_slot()` - cleanup
  - [ ] Redis integration for distributed limiting

#### Afternoon (4 hours)
- [ ] Create `/Users/cere/Downloads/easm/app/utils/data_redaction.py`
  - [ ] Implement `DataRedactor` class
  - [ ] Define `CREDENTIAL_PATTERNS` dict (API keys, passwords, tokens)
  - [ ] Define `EMAIL_PATTERN`, `CC_PATTERN`, `INTERNAL_IP_PATTERNS`
  - [ ] Implement `redact_credentials()` method
  - [ ] Implement `redact_email()` method
  - [ ] Implement `redact_internal_ips()` method
  - [ ] Implement `redact_credit_cards()` method
  - [ ] Implement `redact_sessions()` method
  - [ ] Implement `redact_all()` method with statistics

#### Unit Tests
- [ ] Create `/Users/cere/Downloads/easm/tests/security/test_rate_limiter.py`
  - [ ] Test per-minute rate limiting
  - [ ] Test concurrent limit enforcement
  - [ ] Test slot acquisition and release
  - [ ] Test Redis integration
- [ ] Create `/Users/cere/Downloads/easm/tests/security/test_data_redaction.py`
  - [ ] Test credential pattern detection (API keys, passwords)
  - [ ] Test email redaction
  - [ ] Test internal IP redaction
  - [ ] Test JWT token redaction
  - [ ] Test AWS key detection

**Day 3 Success Criteria**:
- ✅ Rate limiting enforced
- ✅ Concurrent limits work
- ✅ All credential patterns detected
- ✅ Unit tests: 90%+ coverage

---

### Day 4: Configuration & Consent (8 hours)

#### Morning (4 hours)
- [ ] Update `/Users/cere/Downloads/easm/app/config.py`
  - [ ] Add HTTPx settings (max_response_size, max_redirects, rate_limit)
  - [ ] Add Naabu settings (max_ports, max_pps, require_consent)
  - [ ] Add TLSx settings (connection_timeout, max_attempts)
  - [ ] Add Katana settings (max_depth, max_pages, respect_robots_txt)
  - [ ] Add security settings (block_internal_networks, redact_credentials)
  - [ ] Add tool-specific rate limits

- [ ] Create `/Users/cere/Downloads/easm/config/tool_limits.yaml`
  - [ ] Define resource limits per tool (CPU, memory, timeout)
  - [ ] Define rate limits per tool
  - [ ] Define blocked resources

#### Afternoon (4 hours)
- [ ] Create `/Users/cere/Downloads/easm/app/models/consent.py`
  - [ ] Implement `PortScanConsentRecord` model
  - [ ] Implement `ToolAuditLog` model
  - [ ] Implement `SecurityIncident` model

- [ ] Create database migration
  ```bash
  cd /Users/cere/Downloads/easm
  alembic revision -m "Add tool security tables"
  ```
  - [ ] Add port_scan_consent table
  - [ ] Add tool_audit_log table
  - [ ] Add security_incidents table

- [ ] Create `/Users/cere/Downloads/easm/app/utils/consent.py`
  - [ ] Implement `PortScanConsent` class
  - [ ] Define `CONSENT_TEXT` constant
  - [ ] Implement `require_consent()` method
  - [ ] Implement `record_consent()` method
  - [ ] Implement consent expiry check (1 year)

#### Tests
- [ ] Create `/Users/cere/Downloads/easm/tests/security/test_consent.py`
  - [ ] Test consent requirement
  - [ ] Test consent expiry (1 year)
  - [ ] Test consent recording

**Day 4 Success Criteria**:
- ✅ Configuration updated
- ✅ Database migrations created and tested
- ✅ Port scan consent system working
- ✅ Settings validation passes

---

### Day 5: Integration & Testing (8 hours)

#### Morning (4 hours)
- [ ] Update `/Users/cere/Downloads/easm/app/tasks/tool_tasks.py`
  - [ ] Create `run_httpx_task()` with full security integration
  - [ ] Create `run_naabu_task()` with consent check
  - [ ] Create `run_tlsx_task()` with sanitization
  - [ ] Create `run_katana_task()` with robots.txt check

- [ ] Each task must include:
  - [ ] Input validation (ToolInputValidator)
  - [ ] Network security check (NetworkSecurityValidator)
  - [ ] Rate limit check (ToolRateLimiter)
  - [ ] Slot acquisition
  - [ ] Tool execution (SecureToolExecutor)
  - [ ] Output sanitization
  - [ ] Audit logging
  - [ ] Error handling
  - [ ] Slot release (finally block)

#### Afternoon (4 hours)
- [ ] Integration tests
  - [ ] Create `/Users/cere/Downloads/easm/tests/integration/test_tool_security_integration.py`
  - [ ] Test HTTPx blocks SSRF to metadata endpoint
  - [ ] Test Naabu blocks internal network scan
  - [ ] Test Katana respects depth limit
  - [ ] Test rate limiting enforcement
  - [ ] Test output sanitization in response
  - [ ] Test consent requirement for Naabu

- [ ] Update security checklist
  - [ ] Update `/Users/cere/Downloads/easm/scripts/security_checklist.py`
  - [ ] Add `check_tool_validators()`
  - [ ] Add `check_output_sanitizers()`
  - [ ] Add `check_network_security_validator()`
  - [ ] Add `check_rate_limiting_implementation()`
  - [ ] Add `check_data_redaction()`
  - [ ] Add `check_port_scan_consent()`
  - [ ] Add `check_audit_logging_for_tools()`

#### Run All Tests
```bash
# Unit tests
pytest tests/security/ -v --cov=app/utils --cov-report=html

# Integration tests
pytest tests/integration/test_tool_security_integration.py -v

# Security checklist
python scripts/security_checklist.py

# Expected: Score 9.5/10
```

**Day 5 Success Criteria**:
- ✅ All tasks integrated with security controls
- ✅ All integration tests pass
- ✅ Security checklist: 100% pass
- ✅ Test coverage: 90%+
- ✅ Security score: 9.5/10

---

## Verification Commands

### Test Input Validation
```python
# In Python shell
from app.utils.tool_validators import ToolInputValidator

# Test SSRF prevention
is_valid, error = ToolInputValidator.validate_httpx_input(
    "http://169.254.169.254/latest/meta-data/"
)
assert not is_valid, "Should block metadata endpoint"

# Test internal IP prevention
is_valid, error = ToolInputValidator.validate_naabu_input(
    "192.168.1.1", "22,445,3389"
)
assert not is_valid, "Should block internal IP and dangerous ports"
```

### Test Output Sanitization
```python
from app.utils.output_sanitizers import TLSxOutputSanitizer

output = {
    'private_key': '-----BEGIN PRIVATE KEY-----\nSECRET\n-----END PRIVATE KEY-----'
}

sanitized = TLSxOutputSanitizer().sanitize(output)
assert sanitized['private_key'] == '[REDACTED-PRIVATE-KEY]'
```

### Test Rate Limiting
```python
from app.utils.rate_limiter import ToolRateLimiter
import redis

redis_client = redis.Redis(host='localhost', port=16379, db=0)
limiter = ToolRateLimiter(redis_client)

# Should allow first 10
for i in range(10):
    allowed, _ = limiter.check_rate_limit(tenant_id=1, tool='httpx', limit_per_minute=10)
    assert allowed

# Should block 11th
allowed, error = limiter.check_rate_limit(tenant_id=1, tool='httpx', limit_per_minute=10)
assert not allowed
```

### Run Security Checklist
```bash
cd /Users/cere/Downloads/easm
python scripts/security_checklist.py

# Expected output:
# ========================================
# SECURITY SCORE: 9.5/10.0
# ========================================
# ✓ READY FOR DEPLOYMENT
```

---

## Critical Security Tests

### SSRF Prevention Tests (MUST PASS)

```bash
# Test 1: AWS Metadata
curl -X POST http://localhost:8000/api/v1/tools/httpx \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"url": "http://169.254.169.254/latest/meta-data/"}' \
  -w "Status: %{http_code}\n"
# Expected: 400

# Test 2: GCP Metadata
curl -X POST http://localhost:8000/api/v1/tools/httpx \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"url": "http://metadata.google.internal/"}' \
  -w "Status: %{http_code}\n"
# Expected: 400

# Test 3: Internal Network
curl -X POST http://localhost:8000/api/v1/tools/naabu \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"target": "192.168.1.1", "ports": "22"}' \
  -w "Status: %{http_code}\n"
# Expected: 400

# Test 4: Loopback
curl -X POST http://localhost:8000/api/v1/tools/httpx \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"url": "http://127.0.0.1:8080/"}' \
  -w "Status: %{http_code}\n"
# Expected: 400
```

### Private Key Protection Tests (MUST PASS)

```python
# Test TLSx sanitizer
from app.utils.output_sanitizers import TLSxOutputSanitizer

test_output = {
    'certificate': 'CERT_DATA',
    'private_key': '-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----'
}

sanitized = TLSxOutputSanitizer().sanitize(test_output)

# MUST be redacted
assert '[REDACTED-PRIVATE-KEY]' in str(sanitized)
assert 'BEGIN RSA PRIVATE KEY' not in str(sanitized)
assert 'MIIEpAIBAAKCAQEA' not in str(sanitized)
```

### Rate Limiting Tests (MUST PASS)

```bash
# Make 15 rapid requests
for i in {1..15}; do
  curl -X POST http://localhost:8000/api/v1/tools/httpx \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"url\": \"https://example$i.com\"}" \
    -w "Request $i: %{http_code}\n" \
    -s -o /dev/null
done

# Expected: First 10 succeed (200/202), rest fail (429)
```

---

## Common Issues & Solutions

### Issue 1: Import Errors
**Problem**: `ImportError: cannot import name 'ToolInputValidator'`
**Solution**:
```bash
# Ensure files are created in correct location
ls app/utils/tool_validators.py
# Add to app/utils/__init__.py if needed
```

### Issue 2: Redis Connection Error
**Problem**: `redis.exceptions.ConnectionError`
**Solution**:
```bash
# Start Redis
docker-compose up -d redis
# Or check Redis is running
docker ps | grep redis
```

### Issue 3: Database Migration Error
**Problem**: `alembic.util.exc.CommandError`
**Solution**:
```bash
# Initialize Alembic if not done
alembic init alembic
# Run migrations
alembic upgrade head
```

### Issue 4: Test Failures
**Problem**: Unit tests fail with validation errors
**Solution**:
```bash
# Run with verbose output
pytest tests/security/test_tool_validators.py -v -s
# Check specific test
pytest tests/security/test_tool_validators.py::TestHTTPxValidator::test_blocks_metadata_endpoint -v
```

### Issue 5: Security Checklist Fails
**Problem**: Security score below 9.0
**Solution**:
```bash
# Run checklist with verbose output
python scripts/security_checklist.py

# Check which tests failed
# Common failures:
# - Missing validators: Create tool_validators.py
# - Missing sanitizers: Create output_sanitizers.py
# - Missing rate limiter: Create rate_limiter.py
```

---

## Code Review Checklist

Before submitting PR, verify:

**Input Validation**:
- [ ] All 4 tool validators implemented
- [ ] NetworkSecurityValidator blocks all RFC1918 networks
- [ ] Cloud metadata endpoints blocked (169.254.169.254, metadata.google.internal)
- [ ] URL schemes limited to http/https
- [ ] Port validation blocks dangerous ports (22, 445, 3389, 5432, 3306)

**Output Sanitization**:
- [ ] HTTPx redacts sensitive headers (Authorization, Cookie)
- [ ] TLSx detects and redacts private keys (CRITICAL)
- [ ] TLSx alerts security team on private key detection
- [ ] Katana redacts credentials in URLs (password=, api_key=)
- [ ] All outputs truncated to size limits

**Rate Limiting**:
- [ ] Per-minute rate limits enforced
- [ ] Concurrent execution limits enforced
- [ ] Slots properly acquired and released
- [ ] Redis integration working

**Security Controls**:
- [ ] SecureToolExecutor used for all tool execution
- [ ] Audit logging for sensitive operations
- [ ] Error handling doesn't leak information
- [ ] Timeouts configured for all operations

**Testing**:
- [ ] Unit tests: 90%+ coverage
- [ ] All SSRF prevention tests pass
- [ ] Private key protection test passes
- [ ] Rate limiting tests pass
- [ ] Integration tests pass

**Documentation**:
- [ ] Docstrings for all public methods
- [ ] Security considerations documented
- [ ] Configuration options documented
- [ ] API endpoints documented

---

## Final Validation

### Before Deployment

```bash
# 1. Run all tests
pytest tests/ -v --cov=app --cov-report=html

# 2. Run security checklist
python scripts/security_checklist.py

# 3. Run Bandit (Python security linter)
pip install bandit
bandit -r app/ -ll

# 4. Run Safety (dependency scanner)
pip install safety
safety check --file requirements.txt

# 5. Manual penetration tests
bash scripts/security_pentest.sh

# 6. Check security score
python scripts/security_checklist.py | grep "SECURITY SCORE"
# Expected: 9.5/10.0 or higher
```

### Deployment Approval Criteria

- [ ] All unit tests pass (100%)
- [ ] All integration tests pass (100%)
- [ ] Security checklist: 100% pass
- [ ] Security score: ≥ 9.5/10
- [ ] Test coverage: ≥ 90%
- [ ] Bandit: No high/medium issues
- [ ] Safety: No known vulnerabilities
- [ ] Manual penetration tests: All pass
- [ ] Code review: Approved
- [ ] Documentation: Complete

---

## Quick Reference - Security Patterns

### Pattern 1: Validate Input
```python
from app.utils.tool_validators import ToolInputValidator

is_valid, error = ToolInputValidator.validate_httpx_input(url)
if not is_valid:
    raise ToolExecutionError(f"Invalid input: {error}")
```

### Pattern 2: Check Network Safety
```python
from app.utils.network_security import NetworkSecurityValidator

is_safe, error = NetworkSecurityValidator.is_safe_target(hostname)
if not is_safe:
    raise ToolExecutionError(f"Blocked target: {error}")
```

### Pattern 3: Enforce Rate Limit
```python
from app.utils.rate_limiter import ToolRateLimiter

rate_limiter = ToolRateLimiter(redis_client)
allowed, error = rate_limiter.check_rate_limit(tenant_id, tool, limit=10)
if not allowed:
    raise RateLimitError(error)
```

### Pattern 4: Sanitize Output
```python
from app.utils.output_sanitizers import HTTPxOutputSanitizer

sanitizer = HTTPxOutputSanitizer()
sanitized = sanitizer.sanitize(raw_output)
# Store sanitized, not raw_output
```

### Pattern 5: Redact Sensitive Data
```python
from app.utils.data_redaction import DataRedactor

redacted, stats = DataRedactor.redact_all(text)
logger.info(f"Redacted {stats['credentials']} credentials")
```

---

## Success Metrics

**Day 1**:
- ✅ 20 validator tests pass
- ✅ SSRF prevention verified

**Day 2**:
- ✅ 15 sanitizer tests pass
- ✅ Private key redaction verified

**Day 3**:
- ✅ Rate limiting working
- ✅ 50+ redaction patterns detected

**Day 4**:
- ✅ Database migrations applied
- ✅ Port scan consent system working

**Day 5**:
- ✅ Security score: 9.5/10
- ✅ All integration tests pass
- ✅ Ready for deployment

---

**Keep this checklist open during implementation!**
**Mark items as you complete them.**
**Run tests continuously, not just at the end.**
