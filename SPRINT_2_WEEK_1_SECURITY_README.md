# Sprint 2 Week 1 - Security Documentation Guide
## Complete Security Requirements for New Tool Integration

**Sprint**: Sprint 2 Week 1
**Security Focus**: HTTPx, Naabu, TLSx, Katana Integration
**Current Score**: 9.0/10
**Target Score**: 9.5/10
**Timeline**: 5 days

---

## Documentation Overview

This security review has produced comprehensive documentation to guide the secure integration of 4 new enrichment tools. All documents are actionable, implementation-ready, and aligned with OWASP Top 10 2021.

### Document Structure

```
/Users/cere/Downloads/easm/
├── SPRINT_2_WEEK_1_NEW_TOOLS_SECURITY_REQUIREMENTS.md    (90 KB)
│   └── Comprehensive security requirements
│       ├── Tool-specific requirements for all 4 tools
│       ├── Input validation rules
│       ├── Output sanitization rules
│       ├── Network security controls
│       ├── Resource limits
│       ├── Data redaction rules
│       ├── Threat model
│       ├── Security testing requirements
│       ├── Compliance requirements
│       ├── Implementation guidance
│       └── Security checklist updates
│
├── SPRINT_2_WEEK_1_SECURITY_IMPLEMENTATION_CHECKLIST.md  (17 KB)
│   └── Day-by-day implementation guide
│       ├── Daily tasks (5 days)
│       ├── Verification commands
│       ├── Critical security tests
│       ├── Common issues & solutions
│       ├── Code review checklist
│       └── Final validation steps
│
├── SPRINT_2_WEEK_1_SECURITY_SUMMARY.md                   (39 KB)
│   └── Visual overview and threat model
│       ├── Security architecture layers
│       ├── Attack scenario diagrams
│       ├── Threat matrix
│       ├── Blocked resources
│       ├── Security control matrix
│       ├── Risk assessment
│       ├── Compliance scorecard
│       └── Performance impact analysis
│
└── scripts/security_pentest.sh                            (18 KB)
    └── Penetration testing script
        ├── 27 automated security tests
        ├── SSRF prevention tests
        ├── Input validation tests
        ├── Rate limiting tests
        └── Pass/fail reporting
```

---

## Quick Start Guide

### For Security Auditors

**Start here**: Read this README first, then:

1. **Read**: `SPRINT_2_WEEK_1_SECURITY_SUMMARY.md`
   - Visual overview of security architecture
   - Threat model with attack scenarios
   - Risk assessment matrix
   - **Time**: 20 minutes

2. **Review**: `SPRINT_2_WEEK_1_NEW_TOOLS_SECURITY_REQUIREMENTS.md`
   - Detailed requirements for all 4 tools
   - OWASP Top 10 compliance
   - Implementation specifications
   - **Time**: 60 minutes

3. **Approve**: Sign off on requirements if acceptable

### For Developers

**Start here**: Read this README first, then:

1. **Read**: `SPRINT_2_WEEK_1_SECURITY_IMPLEMENTATION_CHECKLIST.md`
   - Day-by-day implementation plan
   - Code examples and patterns
   - Verification commands
   - **Time**: 15 minutes

2. **Reference**: `SPRINT_2_WEEK_1_NEW_TOOLS_SECURITY_REQUIREMENTS.md`
   - Detailed specs for each component
   - Copy-paste ready code examples
   - Use as reference during implementation
   - **Time**: As needed during implementation

3. **Implement**: Follow the 5-day plan
   - Day 1: Input validators
   - Day 2: Output sanitizers
   - Day 3: Rate limiting & redaction
   - Day 4: Configuration & consent
   - Day 5: Integration & testing

4. **Test**: Run `scripts/security_pentest.sh`
   - Automated penetration testing
   - Must pass 100% before deployment

### For QA / Security Testing

**Start here**: Read this README first, then:

1. **Review**: `SPRINT_2_WEEK_1_SECURITY_SUMMARY.md`
   - Understand threat model
   - Review attack scenarios
   - **Time**: 20 minutes

2. **Test**: Run `scripts/security_pentest.sh`
   - 27 automated security tests
   - SSRF, injection, rate limiting
   - **Time**: 5 minutes

3. **Manual Test**: Follow penetration test scenarios in requirements doc
   - Section 8.3: Penetration Testing Scenarios
   - **Time**: 30 minutes

4. **Report**: Document any failures and work with developers to fix

---

## Document Summaries

### 1. Security Requirements Document (90 KB)

**File**: `SPRINT_2_WEEK_1_NEW_TOOLS_SECURITY_REQUIREMENTS.md`

**Purpose**: Comprehensive, authoritative security requirements for all 4 tools

**Contents**:
- **Section 1**: Tool-specific requirements (HTTPx, Naabu, TLSx, Katana)
- **Section 2**: Input validation requirements
- **Section 3**: Output sanitization requirements
- **Section 4**: Network security controls
- **Section 5**: Resource limits and rate limiting
- **Section 6**: Data redaction rules
- **Section 7**: Threat model analysis (15 threats)
- **Section 8**: Security testing requirements
- **Section 9**: Compliance and legal considerations
- **Section 10**: Implementation guidance
- **Section 11**: Security checklist updates

**Key Features**:
- 75+ security requirements (SR-*)
- Copy-paste ready code examples
- OWASP Top 10 2021 compliance
- PCI-DSS, GDPR, HIPAA considerations
- Threat scenarios with mitigations
- Complete test coverage requirements

**Use Cases**:
- Reference during implementation
- Code review checklist
- Security audit evidence
- Compliance documentation

---

### 2. Implementation Checklist (17 KB)

**File**: `SPRINT_2_WEEK_1_SECURITY_IMPLEMENTATION_CHECKLIST.md`

**Purpose**: Day-by-day implementation guide with verification steps

**Contents**:
- **Day 1**: Input validators (8 hours)
  - ToolInputValidator class
  - NetworkSecurityValidator class
  - Unit tests (90% coverage)

- **Day 2**: Output sanitizers (8 hours)
  - 4 tool-specific sanitizers
  - Private key detection (critical)
  - Unit tests

- **Day 3**: Rate limiting & redaction (8 hours)
  - ToolRateLimiter with Redis
  - DataRedactor with 50+ patterns
  - Unit tests

- **Day 4**: Configuration & consent (8 hours)
  - Config updates
  - Database migrations
  - Port scan consent system

- **Day 5**: Integration & testing (8 hours)
  - Task integration
  - Integration tests
  - Security checklist
  - Penetration tests

**Key Features**:
- Hour-by-hour task breakdown
- Success criteria for each day
- Verification commands to run after each task
- Common issues and solutions
- Code review checklist
- Final validation steps

**Use Cases**:
- Daily standup agenda
- Progress tracking
- Implementation guide
- Troubleshooting reference

---

### 3. Security Summary (39 KB)

**File**: `SPRINT_2_WEEK_1_SECURITY_SUMMARY.md`

**Purpose**: Visual overview with architecture diagrams and threat model

**Contents**:
- **Architecture Layers**: 10-layer security diagram
- **Attack Scenarios**: 5 detailed scenarios with defense layers
  1. SSRF to AWS metadata → Blocked at input validation
  2. Port scan of internal DB → Blocked at domain validation
  3. Private key leakage → Redacted with alerts
  4. Infinite crawl DoS → Prevented by limits
  5. Credential leakage in URLs → Redacted before storage

- **Security Control Matrix**: Controls per tool
- **Blocked Resources**: IPs, ports, URL schemes
- **Threat Matrix**: 15 threats with risk levels
- **Compliance Scorecard**: OWASP, PCI-DSS, GDPR, HIPAA
- **Performance Impact**: <5% overhead
- **Security Metrics**: 9.0 → 9.5/10 progression

**Key Features**:
- ASCII diagrams showing attack flows
- Visual threat model
- Risk assessment matrix
- Compliance mapping
- Progress tracker

**Use Cases**:
- Security presentations
- Stakeholder communication
- Architecture documentation
- Threat model workshop

---

### 4. Penetration Testing Script (18 KB)

**File**: `scripts/security_pentest.sh`

**Purpose**: Automated penetration testing for all 4 tools

**Test Coverage**:
- **HTTPx** (9 tests): SSRF, schemes, command injection
- **Naabu** (7 tests): Internal networks, dangerous ports, limits
- **TLSx** (4 tests): HTTPS requirement, metadata, internal IPs
- **Katana** (5 tests): Schemes, networks, depth/page limits
- **Rate Limiting** (1 test): Enforcement verification
- **Tenant Isolation** (1 test): Cross-tenant access

**Total**: 27 automated security tests

**Usage**:
```bash
# Set up environment
export API_BASE=http://localhost:8000/api/v1
export TOKEN=$(curl -X POST $API_BASE/auth/login \
  -d '{"username":"test","password":"test"}' | jq -r '.access_token')

# Run tests
./scripts/security_pentest.sh

# Expected output:
# ✓ ALL TESTS PASSED - SECURITY REQUIREMENTS MET
# Pass Rate: 100%
# Security score: 9.5/10 maintained
```

**Features**:
- Color-coded output (pass/fail)
- Detailed failure messages
- Progress tracking
- Exit code 0 (pass) or 1 (fail)
- CI/CD integration ready

---

## Implementation Workflow

### Phase 1: Planning (Day 0)

```
┌─────────────────────────────────────────┐
│ 1. Review all security documentation    │
│    - Security Summary (visual overview) │
│    - Requirements (detailed specs)      │
│    - Checklist (daily tasks)            │
│                                         │
│ 2. Team meeting                         │
│    - Discuss threat model               │
│    - Review architecture                │
│    - Assign tasks                       │
│                                         │
│ 3. Environment setup                    │
│    - Development environment            │
│    - Testing environment                │
│    - CI/CD pipeline                     │
└─────────────────────────────────────────┘
```

### Phase 2: Implementation (Days 1-5)

```
Day 1: Input Validators
├─ Morning: Create ToolInputValidator
├─ Morning: Create NetworkSecurityValidator
├─ Afternoon: Write unit tests
└─ Verify: pytest tests/security/test_tool_validators.py

Day 2: Output Sanitizers
├─ Morning: Create tool-specific sanitizers
├─ Afternoon: Implement private key detection
├─ Afternoon: Write unit tests
└─ Verify: pytest tests/security/test_output_sanitizers.py

Day 3: Rate Limiting & Redaction
├─ Morning: Create ToolRateLimiter
├─ Afternoon: Create DataRedactor
├─ Evening: Write unit tests
└─ Verify: pytest tests/security/test_rate_limiter.py

Day 4: Configuration & Consent
├─ Morning: Update config.py
├─ Morning: Create database migrations
├─ Afternoon: Implement PortScanConsent
└─ Verify: alembic upgrade head

Day 5: Integration & Testing
├─ Morning: Integrate with tasks
├─ Afternoon: Integration tests
├─ Evening: Penetration tests
└─ Verify: ./scripts/security_pentest.sh
```

### Phase 3: Validation (Day 6)

```
┌─────────────────────────────────────────┐
│ 1. Run all tests                        │
│    ✓ pytest tests/ -v --cov            │
│    ✓ python scripts/security_checklist.py │
│    ✓ ./scripts/security_pentest.sh     │
│                                         │
│ 2. Code review                          │
│    ✓ Security review by senior dev     │
│    ✓ Check against requirements doc    │
│                                         │
│ 3. Security sign-off                   │
│    ✓ Security team approval             │
│    ✓ Score verification: 9.5/10        │
└─────────────────────────────────────────┘
```

---

## Critical Security Requirements Summary

### Must-Have Security Controls

```
┌─────────────────────────────────────────────────────────┐
│ CRITICAL (Must implement before deployment)             │
├─────────────────────────────────────────────────────────┤
│ 1. ✅ Input Validation                                  │
│    - Domain/URL validation                             │
│    - SSRF prevention (169.254.169.254, RFC1918)        │
│    - Command injection prevention                      │
│                                                         │
│ 2. ✅ Output Sanitization                              │
│    - Private key detection and redaction (TLSx)        │
│    - Credential detection and redaction                │
│    - HTML/JS sanitization                              │
│                                                         │
│ 3. ✅ Network Security                                 │
│    - Block metadata endpoints                          │
│    - Block internal networks                           │
│    - Block dangerous ports                             │
│                                                         │
│ 4. ✅ Rate Limiting                                    │
│    - Per-tenant limits                                 │
│    - Concurrent execution limits                       │
│    - Global platform limits                            │
│                                                         │
│ 5. ✅ Audit Logging                                    │
│    - All tool executions                               │
│    - Port scan consent                                 │
│    - Security incidents                                │
└─────────────────────────────────────────────────────────┘
```

### Testing Requirements

```
┌─────────────────────────────────────────────────────────┐
│ REQUIRED (All must pass before deployment)              │
├─────────────────────────────────────────────────────────┤
│ ✅ Unit Tests:           90%+ coverage                  │
│ ✅ Integration Tests:    100% of security controls      │
│ ✅ Penetration Tests:    27/27 pass (100%)              │
│ ✅ Security Checklist:   100% pass                      │
│ ✅ Security Score:       ≥ 9.5/10                       │
│ ✅ OWASP ZAP:            0 high/medium issues           │
│ ✅ Bandit:               0 high/medium issues           │
│ ✅ Safety:               0 known vulnerabilities        │
└─────────────────────────────────────────────────────────┘
```

---

## Verification Commands

### Quick Health Check

```bash
# 1. Check if all files are created
ls -lh app/utils/tool_validators.py
ls -lh app/utils/network_security.py
ls -lh app/utils/output_sanitizers.py
ls -lh app/utils/rate_limiter.py
ls -lh app/utils/data_redaction.py

# 2. Run security checklist
python scripts/security_checklist.py

# 3. Run penetration tests
./scripts/security_pentest.sh

# 4. Check test coverage
pytest tests/security/ -v --cov=app/utils --cov-report=term-missing

# 5. Security score
python scripts/security_checklist.py | grep "SECURITY SCORE"
# Expected: 9.5/10.0 or higher
```

### Critical Security Tests (Must Pass)

```bash
# Test 1: Block AWS metadata
curl -X POST http://localhost:8000/api/v1/tools/httpx \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"url": "http://169.254.169.254/latest/meta-data/"}' \
  -w "\nStatus: %{http_code}\n"
# Expected: 400 Bad Request

# Test 2: Block internal network
curl -X POST http://localhost:8000/api/v1/tools/naabu \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"target": "192.168.1.1", "ports": "22"}' \
  -w "\nStatus: %{http_code}\n"
# Expected: 400 Bad Request

# Test 3: Private key redaction (unit test)
python -c "
from app.utils.output_sanitizers import TLSxOutputSanitizer
output = {'private_key': '-----BEGIN PRIVATE KEY-----\nSECRET\n-----END PRIVATE KEY-----'}
sanitized = TLSxOutputSanitizer().sanitize(output)
assert '[REDACTED' in str(sanitized), 'Private key not redacted!'
print('✅ Private key redaction working')
"
```

---

## Common Questions

### Q: How do I know if I've implemented everything correctly?

**A**: Run the security checklist:
```bash
python scripts/security_checklist.py
```
Expected output:
- All checks pass (100%)
- Security score: 9.5/10 or higher
- "✓ READY FOR DEPLOYMENT" message

### Q: What if a security test fails?

**A**:
1. Review the failure message
2. Check the relevant section in the requirements document
3. Review the code example for that requirement
4. Fix the issue
5. Re-run the test
6. If still failing, check "Common Issues & Solutions" in the checklist

### Q: How long will this implementation take?

**A**:
- **Total time**: 5 days (40 hours)
- **Daily time**: 8 hours per day
- **Can be parallelized**: 2-3 developers working simultaneously
- **Critical path**: Days 1-2 must complete before Days 3-5

### Q: What's the minimum I need to implement?

**A**: All critical requirements marked with "CRITICAL" priority:
- Input validators for all 4 tools
- NetworkSecurityValidator
- Output sanitizers (especially TLSx private key redaction)
- Rate limiter
- Basic audit logging

Skipping any critical requirement will fail security tests.

### Q: Can I deploy before reaching 9.5/10?

**A**: No. The 9.5/10 security score is a hard requirement. Deploying below this score introduces unacceptable security risks, particularly:
- SSRF vulnerabilities
- Private key exposure
- Credential leakage
- DoS vulnerabilities

### Q: How do I handle failures in production?

**A**: Refer to the incident response plan in the requirements document (Section 9). Key points:
- All security incidents logged to security_incidents table
- Security team alerted via SIEM/Slack
- Audit logs provide forensic evidence
- Rate limiting prevents abuse escalation

---

## Success Criteria

### Pre-Deployment Checklist

```
┌─────────────────────────────────────────────────────────┐
│ DEPLOYMENT READINESS CHECKLIST                          │
├─────────────────────────────────────────────────────────┤
│ Implementation                                          │
│ ☐ All input validators implemented                      │
│ ☐ All output sanitizers implemented                     │
│ ☐ Rate limiter implemented                              │
│ ☐ Data redactor implemented                             │
│ ☐ Configuration updated                                 │
│ ☐ Database migrations applied                           │
│ ☐ Port scan consent system working                      │
│                                                         │
│ Testing                                                 │
│ ☐ Unit tests: 90%+ coverage                            │
│ ☐ Integration tests: All pass                          │
│ ☐ Penetration tests: 27/27 pass                        │
│ ☐ Security checklist: 100% pass                        │
│ ☐ OWASP ZAP: Clean                                      │
│ ☐ Bandit: Clean                                         │
│ ☐ Safety: Clean                                         │
│                                                         │
│ Documentation                                           │
│ ☐ API documentation updated                             │
│ ☐ Security documentation updated                        │
│ ☐ Incident response plan reviewed                       │
│                                                         │
│ Approval                                                │
│ ☐ Code review: Approved                                 │
│ ☐ Security review: Approved                             │
│ ☐ Security score: ≥ 9.5/10                              │
│ ☐ Stakeholder sign-off                                  │
└─────────────────────────────────────────────────────────┘
```

---

## Support and Escalation

### During Implementation

**Questions about requirements**:
- Reference: `SPRINT_2_WEEK_1_NEW_TOOLS_SECURITY_REQUIREMENTS.md`
- Sections: 1-6 for specific controls, Section 10 for implementation guidance

**Questions about implementation**:
- Reference: `SPRINT_2_WEEK_1_SECURITY_IMPLEMENTATION_CHECKLIST.md`
- Daily tasks with code examples
- Common issues and solutions section

**Security concerns or questions**:
- Escalate to security lead
- Email: security@example.com
- Slack: #security-sprint-2

### During Testing

**Test failures**:
- Review failure message
- Check requirements document for correct behavior
- Review implementation checklist for common issues
- If unresolved, escalate to security team

**Security incidents**:
- DO NOT commit vulnerable code
- DO NOT discuss in public channels
- Escalate immediately to security team

---

## Next Steps

1. **Read this README completely** (10 minutes)

2. **Choose your path**:
   - Security Auditor → Read Security Summary first
   - Developer → Read Implementation Checklist first
   - QA/Testing → Run penetration tests

3. **Start implementation** (5 days)
   - Follow day-by-day checklist
   - Run tests continuously
   - Mark items as complete

4. **Validate** (Day 6)
   - Run all tests
   - Security checklist
   - Penetration tests
   - Code review

5. **Deploy** (Day 7)
   - After all validations pass
   - With security sign-off
   - Monitor for 24 hours

---

## Document Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-23 | Security Team | Initial comprehensive documentation |

---

## Approval Signatures

**Security Lead**: _________________________ Date: _________

**Engineering Lead**: _________________________ Date: _________

**Product Owner**: _________________________ Date: _________

---

**For questions or clarifications, contact the security team.**

**DO NOT deploy without security sign-off.**
