# EASM Platform Sprint 1.5 - Comprehensive Security Audit Report

**Audit Date**: October 22, 2025
**Auditor**: Security Audit Team
**Platform Version**: Sprint 1.5 - Discovery Pipeline

---

## Executive Summary

### Overall Security Score: 5/10 (Moderate Risk)

The EASM platform Sprint 1.5 shows a foundation with security considerations, but requires significant hardening before production deployment. While the SecureToolExecutor demonstrates security-aware design, critical vulnerabilities exist in authentication, secrets management, and input validation.

### Risk Distribution:
- **Critical**: 3 vulnerabilities
- **High**: 5 vulnerabilities
- **Medium**: 7 vulnerabilities
- **Low**: 4 observations

---

## 1. CRITICAL VULNERABILITIES (Immediate Action Required)

### 1.1 No Authentication/Authorization Implementation
**OWASP A01:2021 - Broken Access Control**

**Finding**: The API currently has NO authentication or authorization mechanisms implemented.

```python
# app/main.py - Completely open endpoints
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # CRITICAL: Accepts all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Impact**:
- Complete unauthorized access to all platform functionality
- Data breach risk for all tenant data
- No user accountability or audit trails

**Recommendation**:
```python
# Implement JWT authentication immediately
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

security = HTTPBearer()

JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        tenant_id: int = payload.get("tenant_id")
        if tenant_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        return {"tenant_id": tenant_id, "user_id": payload.get("user_id")}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Apply to all endpoints
@app.get("/api/assets")
async def get_assets(current_user: dict = Depends(get_current_user)):
    # Access only tenant's data
    tenant_id = current_user["tenant_id"]
    # ... rest of implementation
```

### 1.2 Hardcoded Secrets and Weak Defaults
**OWASP A02:2021 - Cryptographic Failures**

**Finding**: Secrets are hardcoded or use weak defaults throughout the codebase.

```yaml
# docker-compose.yml
POSTGRES_PASSWORD: ${DB_PASSWORD:-easm_password}  # Weak default
MINIO_ROOT_USER: ${MINIO_USER:-minioadmin}       # Default credentials
MINIO_ROOT_PASSWORD: ${MINIO_PASSWORD:-minioadmin123}
JWT_SECRET_KEY: ${JWT_SECRET_KEY:-change-this-secret-key-in-production}
```

**Impact**:
- Credential compromise
- JWT token forgery
- Unauthorized database access

**Recommendation**:
```bash
# Create secure .env file with strong secrets
cat > .env.production << EOF
DB_PASSWORD=$(openssl rand -base64 32)
MINIO_USER=easm_minio_$(openssl rand -hex 8)
MINIO_PASSWORD=$(openssl rand -base64 32)
JWT_SECRET_KEY=$(openssl rand -base64 64)
EOF

# Update docker-compose.yml to require env vars
environment:
  POSTGRES_PASSWORD: ${DB_PASSWORD:?DB_PASSWORD is required}
  JWT_SECRET_KEY: ${JWT_SECRET_KEY:?JWT_SECRET_KEY is required}
```

### 1.3 Command Injection in discovery.py (run_uncover)
**OWASP A03:2021 - Injection**

**Finding**: Direct subprocess execution without SecureToolExecutor in run_uncover function.

```python
# app/tasks/discovery.py - Line 197-208
cmd = [
    'uncover',
    '-q', f'org:"{keyword}"',  # VULNERABLE: keyword not sanitized
    '-e', 'shodan,censys',
    '-silent',
    '-o', output_file
]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
```

**Impact**: Remote code execution through malicious keyword input

**Recommendation**:
```python
def run_uncover(tenant_id: int, keywords: list) -> list:
    """Run uncover with SecureToolExecutor for safety"""
    from app.utils.secure_executor import SecureToolExecutor

    results = []
    with SecureToolExecutor(tenant_id) as executor:
        for keyword in keywords:
            # Validate keyword
            if not re.match(r'^[a-zA-Z0-9\s\-_.]+$', keyword):
                logger.warning(f"Skipping invalid keyword: {keyword}")
                continue

            output_file = 'uncover_output.txt'

            returncode, stdout, stderr = executor.execute(
                'uncover',
                ['-q', f'org:{keyword}', '-e', 'shodan,censys',
                 '-silent', '-o', output_file],
                timeout=300
            )

            # Process results safely
            output_content = executor.read_output_file(output_file)
            results.extend(output_content.split('\n'))

    return list(set(results))
```

---

## 2. HIGH-RISK VULNERABILITIES

### 2.1 SQL Injection Risk in Asset Repository
**OWASP A03:2021 - Injection**

**Finding**: While SQLAlchemy provides some protection, the bulk_upsert uses raw SQL construction.

```python
# app/repositories/asset_repository.py - Line 119-130
stmt = insert(Asset).values(records)
stmt = stmt.on_conflict_do_update(
    index_elements=['tenant_id', 'identifier', 'type'],
    set_={
        'last_seen': stmt.excluded.last_seen,
        'raw_metadata': stmt.excluded.raw_metadata,  # JSON injection risk
    }
)
```

**Recommendation**:
```python
def bulk_upsert(self, tenant_id: int, assets_data: List[Dict]) -> Dict[str, int]:
    """Secure bulk upsert with validation"""
    # Validate all input data first
    for data in assets_data:
        # Validate identifier format
        if not self._validate_identifier(data['identifier']):
            raise ValueError(f"Invalid identifier: {data['identifier']}")

        # Validate and sanitize JSON metadata
        if 'raw_metadata' in data:
            try:
                # Parse and re-serialize to ensure valid JSON
                parsed = json.loads(data['raw_metadata']) if isinstance(data['raw_metadata'], str) else data['raw_metadata']
                data['raw_metadata'] = json.dumps(parsed)
            except json.JSONDecodeError:
                data['raw_metadata'] = '{}'

    # Continue with safe upsert...
```

### 2.2 Insufficient Multi-Tenant Isolation
**OWASP A01:2021 - Broken Access Control**

**Finding**: No enforcement of tenant boundaries at the repository level.

**Recommendation**:
```python
class AssetRepository:
    def __init__(self, db: Session, tenant_id: int):
        self.db = db
        self.tenant_id = tenant_id  # Enforce tenant context

    def get_by_id(self, asset_id: int) -> Optional[Asset]:
        """Get asset with tenant validation"""
        asset = self.db.query(Asset).filter_by(
            id=asset_id,
            tenant_id=self.tenant_id  # Always filter by tenant
        ).first()
        if not asset:
            raise PermissionError("Asset not found or access denied")
        return asset
```

### 2.3 Path Traversal in SecureToolExecutor
**OWASP A01:2021 - Broken Access Control**

**Finding**: Path validation can be bypassed with symlinks.

```python
# app/utils/secure_executor.py - Line 109-113
if safe_arg.startswith('/') or safe_arg.startswith('./'):
    if self.temp_dir and not Path(safe_arg).resolve().is_relative_to(Path(self.temp_dir)):
        logger.warning(f"Rejecting path outside temp dir: {safe_arg}")
        continue  # Only logs, doesn't raise exception
```

**Recommendation**:
```python
def sanitize_args(self, args: List[str]) -> List[str]:
    """Enhanced path traversal prevention"""
    sanitized = []
    for arg in args:
        safe_arg = str(arg).strip()

        # Block path traversal patterns
        if any(pattern in safe_arg for pattern in ['..', '~', '$', '`', ';', '&&', '||', '|', '>', '<']):
            raise ToolExecutionError(f"Dangerous pattern in argument: {safe_arg}")

        # Strict path validation
        if '/' in safe_arg:
            path = Path(safe_arg).resolve()
            temp_path = Path(self.temp_dir).resolve()

            # Check both path and realpath (follows symlinks)
            if not (path.is_relative_to(temp_path) and path.exists()):
                raise ToolExecutionError(f"Invalid path: {safe_arg}")

        sanitized.append(shlex.quote(safe_arg))

    return sanitized
```

### 2.4 Insecure Storage of API Keys
**OWASP A02:2021 - Cryptographic Failures**

**Finding**: API keys stored in plaintext in database.

```python
# app/models/database.py - Line 16
api_keys = Column(Text)  # JSON encrypted field for OSINT providers (NOT ENCRYPTED!)
```

**Recommendation**:
```python
from cryptography.fernet import Fernet
import os
import json

class EncryptedField:
    def __init__(self):
        key = os.getenv('ENCRYPTION_KEY')
        if not key:
            raise ValueError("ENCRYPTION_KEY environment variable required")
        self.cipher = Fernet(key.encode())

    def encrypt(self, data: dict) -> str:
        json_str = json.dumps(data)
        encrypted = self.cipher.encrypt(json_str.encode())
        return encrypted.decode()

    def decrypt(self, encrypted_data: str) -> dict:
        if not encrypted_data:
            return {}
        decrypted = self.cipher.decrypt(encrypted_data.encode())
        return json.loads(decrypted.decode())

# Use in model
@property
def decrypted_api_keys(self):
    encryptor = EncryptedField()
    return encryptor.decrypt(self.api_keys)

@decrypted_api_keys.setter
def decrypted_api_keys(self, value):
    encryptor = EncryptedField()
    self.api_keys = encryptor.encrypt(value)
```

### 2.5 Missing Rate Limiting
**OWASP A04:2021 - Insecure Design**

**Finding**: No rate limiting on API endpoints or Celery tasks.

**Recommendation**:
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100 per minute"]
)
app.state.limiter = limiter
app.add_exception_handler(429, _rate_limit_exceeded_handler)

@app.get("/api/discover")
@limiter.limit("5 per hour")  # Expensive operation
async def trigger_discovery(tenant_id: int):
    # ...
```

---

## 3. MEDIUM-RISK VULNERABILITIES

### 3.1 Excessive CORS Permissions
**OWASP A05:2021 - Security Misconfiguration**

```python
allow_origins=["*"]  # Too permissive
```

**Recommendation**:
```python
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '').split(',')
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["https://app.example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

### 3.2 Missing Security Headers
**OWASP A05:2021 - Security Misconfiguration**

**Recommendation**:
```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

### 3.3 Insufficient Input Validation
**OWASP A03:2021 - Injection**

**Recommendation**: Add Pydantic models for all inputs:
```python
from pydantic import BaseModel, validator, constr

class SeedInput(BaseModel):
    type: constr(regex='^(domain|asn|ip_range|keyword)$')
    value: constr(min_length=1, max_length=500)

    @validator('value')
    def validate_value(cls, v, values):
        seed_type = values.get('type')
        if seed_type == 'domain':
            if not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
                raise ValueError('Invalid domain format')
        elif seed_type == 'asn':
            if not re.match(r'^AS\d+$', v):
                raise ValueError('Invalid ASN format')
        return v
```

### 3.4 Weak Resource Limits
**Finding**: Resource limits may be insufficient for DoS prevention.

**Recommendation**:
```python
# Enhanced resource limits with per-tenant tracking
class SecureToolExecutor:
    DEFAULT_TIMEOUT = 300  # Reduce from 600
    DEFAULT_CPU_LIMIT = 60  # Reduce from 300
    DEFAULT_MEMORY_LIMIT = 512 * 1024 * 1024  # Reduce from 1GB

    @classmethod
    def check_tenant_quota(cls, tenant_id: int):
        """Check if tenant has exceeded quota"""
        # Implement quota checking
        pass
```

### 3.5 Container Security
**Finding**: Containers run as root user.

**Recommendation** - Update Dockerfiles:
```dockerfile
# Create non-root user
RUN useradd -m -u 1000 easm && \
    chown -R easm:easm /app

USER easm

# Drop capabilities
RUN setcap -r /usr/local/bin/python3.11 2>/dev/null || true
```

### 3.6 Logging Sensitive Data
**Finding**: Potential for logging sensitive information.

**Recommendation**:
```python
import logging
from typing import Any

class SecurityFilter(logging.Filter):
    """Filter sensitive data from logs"""
    SENSITIVE_PATTERNS = [
        'password', 'token', 'key', 'secret', 'api_key'
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        # Redact sensitive data
        if hasattr(record, 'args'):
            record.args = self._redact_sensitive(record.args)
        return True

    def _redact_sensitive(self, data: Any) -> Any:
        # Implementation to redact sensitive fields
        pass
```

### 3.7 Missing Dependency Scanning
**Finding**: No automated dependency vulnerability scanning.

**Recommendation**:
```yaml
# .github/workflows/security.yml
name: Security Scan
on: [push, pull_request]
jobs:
  dependency-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Safety check
        run: |
          pip install safety
          safety check -r requirements.txt
      - name: Run Bandit
        run: |
          pip install bandit
          bandit -r app/
```

---

## 4. LOW-RISK OBSERVATIONS

1. **Database connection pool settings** could be optimized for security
2. **Celery task timeouts** might be too generous (3600s)
3. **MinIO bucket naming** uses predictable pattern (tenant-{id})
4. **Docker network** uses default bridge driver

---

## 5. DEPENDENCY VULNERABILITIES

### Scan Results:
```bash
# Known vulnerabilities in requirements.txt:
- No critical vulnerabilities found in current versions
- Recommend updating to latest patch versions for all dependencies
```

**Recommendation**: Keep dependencies updated:
```txt
# Updated requirements.txt with latest secure versions
fastapi==0.110.0
uvicorn[standard]==0.29.0
pydantic==2.6.0
sqlalchemy==2.0.29
psycopg2-binary==2.9.9
celery==5.3.6
redis==5.0.3
minio==7.2.5
pyjwt==2.8.0
passlib[bcrypt]==1.7.4
httpx==0.27.0
requests==2.32.0
```

---

## 6. OWASP TOP 10 COMPLIANCE CHECK

| OWASP Category | Status | Issues Found |
|----------------|--------|--------------|
| A01:2021 - Broken Access Control | ❌ FAIL | No authentication, missing tenant isolation |
| A02:2021 - Cryptographic Failures | ❌ FAIL | Hardcoded secrets, unencrypted API keys |
| A03:2021 - Injection | ⚠️ PARTIAL | Command injection risk, needs input validation |
| A04:2021 - Insecure Design | ⚠️ PARTIAL | Missing rate limiting, threat modeling needed |
| A05:2021 - Security Misconfiguration | ❌ FAIL | Permissive CORS, missing security headers |
| A06:2021 - Vulnerable Components | ✅ PASS | Dependencies appear current |
| A07:2021 - Identity & Auth Failures | ❌ FAIL | No authentication implemented |
| A08:2021 - Software & Data Integrity | ⚠️ PARTIAL | No code signing, integrity checks |
| A09:2021 - Security Logging | ❌ FAIL | Insufficient security event logging |
| A10:2021 - SSRF | ✅ PASS | Tools use controlled inputs |

---

## 7. PRIORITIZED REMEDIATION PLAN

### Phase 1 - Critical (Week 1)
1. Implement JWT authentication and authorization
2. Fix command injection in run_uncover
3. Secure all secrets and environment variables
4. Add input validation for all user inputs

### Phase 2 - High Priority (Week 2)
1. Implement multi-tenant isolation at all levels
2. Encrypt sensitive database fields
3. Add rate limiting to all endpoints
4. Fix path traversal vulnerabilities

### Phase 3 - Medium Priority (Week 3-4)
1. Configure proper CORS settings
2. Add security headers
3. Implement comprehensive logging
4. Set up dependency scanning
5. Harden container security

### Phase 4 - Ongoing
1. Regular security testing
2. Dependency updates
3. Security training for developers
4. Incident response planning

---

## 8. SECURITY TESTING CHECKLIST

```python
# security_tests.py - Add to test suite
import pytest
from fastapi.testclient import TestClient

class TestSecurity:
    def test_authentication_required(self, client: TestClient):
        """Verify all endpoints require authentication"""
        response = client.get("/api/assets")
        assert response.status_code == 401

    def test_tenant_isolation(self, client: TestClient):
        """Verify tenants cannot access other tenant data"""
        # Test cross-tenant access attempts
        pass

    def test_injection_prevention(self, client: TestClient):
        """Test injection attack prevention"""
        malicious_inputs = [
            "'; DROP TABLE assets; --",
            "../../../etc/passwd",
            "$(cat /etc/passwd)",
            "<script>alert('XSS')</script>"
        ]
        for payload in malicious_inputs:
            response = client.post("/api/seeds", json={"value": payload})
            assert response.status_code == 400

    def test_rate_limiting(self, client: TestClient):
        """Verify rate limiting is enforced"""
        for _ in range(101):
            response = client.get("/api/health")
        assert response.status_code == 429
```

---

## 9. CONCLUSION

The EASM platform Sprint 1.5 demonstrates security awareness in its design, particularly with the SecureToolExecutor implementation. However, critical security gaps must be addressed before production deployment:

1. **Authentication is completely missing** - This is the highest priority
2. **Secrets management needs immediate attention** - No hardcoded values
3. **Input validation must be comprehensive** - Prevent injection attacks
4. **Multi-tenant isolation needs enforcement** - Prevent data leakage

### Next Steps:
1. Implement Phase 1 remediations immediately
2. Conduct penetration testing after Phase 2
3. Implement continuous security monitoring
4. Establish security review process for all code changes

### Positive Security Features:
- SecureToolExecutor shows good security design (needs minor improvements)
- Repository pattern provides good abstraction for security controls
- Docker containerization provides some isolation
- Use of PostgreSQL with proper indexes

With the recommended remediations implemented, the security score would improve from **5/10 to 8/10**, suitable for production deployment with appropriate monitoring.

---

## APPENDIX: SECURE CODE TEMPLATES

### A. Secure API Endpoint Template
```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.auth import get_current_user
from app.models import Asset, User
from app.validators import validate_tenant_access

router = APIRouter(prefix="/api/v1", tags=["assets"])

@router.get("/assets", response_model=List[Asset])
async def get_assets(
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get assets for authenticated tenant with pagination"""
    validate_tenant_access(current_user.tenant_id)

    # Audit log
    logger.info(f"User {current_user.id} accessed assets for tenant {current_user.tenant_id}")

    # Query with tenant isolation
    assets = db.query(Asset).filter_by(
        tenant_id=current_user.tenant_id
    ).limit(limit).offset(offset).all()

    return assets
```

### B. Secure Celery Task Template
```python
from celery import Task
from app.celery_app import celery
from app.auth import validate_task_token

class SecureTask(Task):
    """Base class for secure tasks with authentication"""

    def __call__(self, *args, **kwargs):
        # Validate task authorization
        task_token = kwargs.get('task_token')
        tenant_id = kwargs.get('tenant_id')

        if not validate_task_token(task_token, tenant_id):
            raise PermissionError("Invalid task authorization")

        # Execute with rate limiting
        if not self.check_rate_limit(tenant_id):
            raise Exception("Rate limit exceeded")

        return self.run(*args, **kwargs)

@celery.task(base=SecureTask, name='secure_discovery')
def run_secure_discovery(tenant_id: int, task_token: str):
    """Secure discovery task with authentication"""
    # Task implementation
    pass
```

### C. Security Configuration Template
```python
# config/security.py
from pydantic import BaseSettings
from typing import List

class SecuritySettings(BaseSettings):
    # Authentication
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # CORS
    allowed_origins: List[str] = []

    # Rate Limiting
    rate_limit_per_minute: int = 100
    rate_limit_per_hour: int = 1000

    # Encryption
    encryption_key: str

    # Security Headers
    enable_hsts: bool = True
    enable_csp: bool = True
    csp_policy: str = "default-src 'self'"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

security_settings = SecuritySettings()
```

---

**Report Generated**: 2025-10-22
**Next Review Date**: 2025-11-22
**Contact**: security-team@example.com