# Security Quick Reference - Sprint 2

## Critical Security Patterns

### 1. Always Validate Domain Inputs

```python
from app.utils.validators import DomainValidator

# Before using ANY domain from user input
domain = request.domain
is_valid, error = DomainValidator.validate_domain(domain)
if not is_valid:
    raise HTTPException(status_code=400, detail=f"Invalid domain: {error}")

# Now safe to use domain
```

### 2. Always Validate URLs

```python
from app.utils.validators import URLValidator

url = request.url
is_valid, error = URLValidator.validate_url(url)
if not is_valid:
    raise HTTPException(status_code=400, detail=f"Invalid URL: {error}")
```

### 3. Always Use SecureToolExecutor

```python
from app.utils.secure_executor import SecureToolExecutor

with SecureToolExecutor(tenant_id=tenant_id) as executor:
    # Validator is built-in, but you can add extra validation
    returncode, stdout, stderr = executor.execute(
        tool='subfinder',
        args=['-d', domain, '-silent'],
        timeout=300
    )
```

### 4. Always Protect API Endpoints

```python
from fastapi import Depends
from app.security.jwt_auth import get_current_user, require_role

@router.get("/api/v1/assets")
async def get_assets(
    current_user: dict = Depends(get_current_user)  # Require authentication
):
    tenant_id = current_user['tenant_id']
    # Only return this tenant's assets
    return get_assets_for_tenant(tenant_id)

@router.post("/api/v1/admin/settings")
async def admin_settings(
    current_user: dict = Depends(require_role("admin"))  # Require admin role
):
    # Admin-only operation
    pass
```

### 5. Always Filter by Tenant

```python
from app.security.multitenancy import TenantIsolation

# In database queries
def get_assets(tenant_id: int):
    # ALWAYS filter by tenant_id
    return db.query(Asset).filter(
        Asset.tenant_id == tenant_id,
        Asset.is_active == True
    ).all()

# Verify tenant access
TenantIsolation.verify_tenant_access(
    user_tenant_id=current_user['tenant_id'],
    resource_tenant_id=asset.tenant_id
)
```

### 6. Never Log Sensitive Data

```python
from app.utils.validators import InputSanitizer

# Before logging user input
user_input = request.data
safe_input = InputSanitizer.sanitize_for_logging(user_input)
logger.info(f"Processing input: {safe_input}")

# Never log tokens, passwords, API keys
logger.info(f"User logged in: {username}")  # Good
logger.info(f"User logged in with password: {password}")  # BAD!
```

### 7. Sanitize File Operations

```python
from app.utils.validators import InputSanitizer

# Before creating files from user input
filename = request.filename
safe_filename = InputSanitizer.sanitize_filename(filename)

# Use within SecureToolExecutor context
with SecureToolExecutor(tenant_id) as executor:
    file_path = executor.create_input_file(safe_filename, content)
```

---

## Common Security Mistakes to Avoid

### ❌ DON'T: Trust User Input
```python
# BAD - Command injection vulnerability
domain = request.domain
os.system(f"subfinder -d {domain}")
```

### ✅ DO: Validate and Use SecureToolExecutor
```python
# GOOD - Validated and sandboxed
from app.utils.validators import DomainValidator
from app.utils.secure_executor import SecureToolExecutor

is_valid, error = DomainValidator.validate_domain(request.domain)
if not is_valid:
    raise HTTPException(400, detail=error)

with SecureToolExecutor(tenant_id) as executor:
    executor.execute('subfinder', ['-d', request.domain])
```

---

### ❌ DON'T: Allow Cross-Tenant Access
```python
# BAD - Returns any asset by ID (cross-tenant access!)
@router.get("/assets/{asset_id}")
def get_asset(asset_id: int):
    return db.query(Asset).filter(Asset.id == asset_id).first()
```

### ✅ DO: Always Filter by Tenant
```python
# GOOD - Only returns asset if it belongs to user's tenant
@router.get("/assets/{asset_id}")
def get_asset(
    asset_id: int,
    current_user: dict = Depends(get_current_user)
):
    asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.tenant_id == current_user['tenant_id']  # Critical!
    ).first()

    if not asset:
        raise HTTPException(404, detail="Asset not found")

    return asset
```

---

### ❌ DON'T: Hardcode Secrets
```python
# BAD - Hardcoded credentials
API_KEY = "sk-1234567890abcdef"
DATABASE_PASSWORD = "mysecretpassword"
```

### ✅ DO: Use SecretManager
```python
# GOOD - Secrets from environment/vault
from app.utils.secrets import SecretManager

secret_manager = SecretManager()
api_key = secret_manager.get_secret('API_KEY')
db_password = secret_manager.get_secret('DATABASE_PASSWORD')
```

---

### ❌ DON'T: Use Raw SQL with String Interpolation
```python
# BAD - SQL injection vulnerability
query = f"SELECT * FROM assets WHERE name = '{user_input}'"
db.execute(query)
```

### ✅ DO: Use ORM or Parameterized Queries
```python
# GOOD - Using SQLAlchemy ORM
assets = db.query(Asset).filter(Asset.name == user_input).all()

# Also GOOD - Parameterized query if you must use raw SQL
db.execute(
    "SELECT * FROM assets WHERE name = :name",
    {"name": user_input}
)
```

---

### ❌ DON'T: Return Sensitive Data in Errors
```python
# BAD - Leaks database structure
except Exception as e:
    return {"error": str(e)}  # Might contain SQL, file paths, etc.
```

### ✅ DO: Return Generic Errors, Log Details
```python
# GOOD - Generic error to user, details in logs
except Exception as e:
    logger.error(f"Database error: {e}", exc_info=True)
    raise HTTPException(500, detail="Internal server error")
```

---

### ❌ DON'T: Allow Unlimited Resource Usage
```python
# BAD - No timeout, could run forever
subprocess.run(['naabu', '-host', domain])
```

### ✅ DO: Use SecureToolExecutor with Timeouts
```python
# GOOD - Enforces timeout and resource limits
with SecureToolExecutor(tenant_id) as executor:
    executor.execute('naabu', ['-host', domain], timeout=300)
```

---

## Security Checklist for Code Reviews

When reviewing code, check for:

- [ ] All user inputs are validated (domains, URLs, filenames)
- [ ] All API endpoints have authentication
- [ ] All database queries filter by tenant_id
- [ ] No hardcoded secrets or credentials
- [ ] No raw SQL with string interpolation
- [ ] SecureToolExecutor used for external tools
- [ ] Timeouts set for all operations
- [ ] Sensitive data not logged
- [ ] Error messages don't leak information
- [ ] File operations use sanitized names
- [ ] CORS configured correctly (no wildcards)
- [ ] Rate limiting configured for endpoints
- [ ] Security headers present on responses

---

## Testing Security Features

### Run Security Tests
```bash
# All security tests
pytest tests/test_security_comprehensive.py -v

# Specific test class
pytest tests/test_security_comprehensive.py::TestDomainValidation -v

# Run security checklist
python scripts/security_checklist.py
```

### Manual Security Testing
```bash
# Test command injection
curl -X POST http://localhost:8000/api/v1/discovery/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"domain": "example.com; whoami"}'
# Should return 400 Bad Request

# Test SSRF
curl -X POST http://localhost:8000/api/v1/tools/httpx \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "http://169.254.169.254/latest/meta-data/"}'
# Should return 400 Bad Request

# Test cross-tenant access
curl -X GET http://localhost:8000/api/v1/tenants/999/assets \
  -H "Authorization: Bearer $TOKEN_TENANT_1"
# Should return 403 Forbidden

# Test rate limiting
for i in {1..150}; do
  curl http://localhost:8000/api/v1/assets -H "Authorization: Bearer $TOKEN"
done
# Should return 429 Too Many Requests after ~100 requests
```

---

## Security Incident Response

### If You Discover a Security Vulnerability

1. **DO NOT** commit or push the vulnerable code
2. **DO NOT** discuss in public channels
3. **DO** notify the security lead immediately
4. **DO** create a private security advisory if on GitHub

### Security Contact
- Security Lead: [contact@example.com]
- Emergency: [emergency-security@example.com]
- Slack: #security-incidents (private channel)

---

## Quick Commands

### Generate Binary Checksums
```bash
bash scripts/generate_checksums.sh
```

### Run Security Checklist
```bash
python scripts/security_checklist.py
```

### Check for Hardcoded Secrets
```bash
# Using grep
grep -r "password\s*=\s*['\"]" app/ --include="*.py"

# Using git-secrets (if installed)
git secrets --scan
```

### Check Dependencies for Vulnerabilities
```bash
# Install safety
pip install safety

# Scan dependencies
safety check --file requirements.txt
```

### Validate JWT Token
```python
from app.security.jwt_auth import jwt_manager

token = "your.jwt.token"
payload = jwt_manager.verify_token(token)
print(payload)
```

---

## Security Resources

### OWASP Resources
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- OWASP Cheat Sheets: https://cheatsheetseries.owasp.org/
- OWASP ZAP (scanner): https://www.zaproxy.org/

### Python Security
- Bandit (linter): https://bandit.readthedocs.io/
- Safety (dependency checker): https://pyup.io/safety/
- OWASP Python Security: https://github.com/OWASP/Python-Security

### Internal Documentation
- Full requirements: `SPRINT_2_SECURITY_REQUIREMENTS.md`
- Implementation summary: `SPRINT_2_SECURITY_IMPLEMENTATION_SUMMARY.md`
- Deployment checklist: `DEPLOYMENT_CHECKLIST.md`

---

## Environment Variables Required

```bash
# Required in production
export SECRET_KEY="generate-with-secrets.token_urlsafe(64)"
export JWT_SECRET_KEY="generate-with-secrets.token_urlsafe(64)"
export POSTGRES_PASSWORD="strong-random-password"
export MINIO_SECRET_KEY="strong-random-key"
export ENVIRONMENT="production"

# Optional secret backend
export SECRET_BACKEND="env"  # or "file", "vault", "azure", "aws"

# Optional security configuration
export RATE_LIMIT_ENABLED="true"
export RATE_LIMIT_REQUESTS_PER_MINUTE="100"
```

---

**Keep this reference handy while coding!**
**When in doubt, validate first, execute second.**