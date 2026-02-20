# EASM Platform REST API

> Sprint 3 Complete - Production-Ready FastAPI Implementation

**Version:** 3.0.0
**Status:** ✅ COMPLETE
**Sprint:** 3 of 6

---

## Overview

The EASM (External Attack Surface Management) Platform provides a comprehensive REST API for managing continuous reconnaissance, vulnerability scanning, and attack surface monitoring. Built with FastAPI, it offers high performance, automatic documentation, and production-grade security.

### Key Features

- 🔐 **JWT Authentication** - RS256/HS256 with token rotation
- 🏢 **Multi-tenancy** - Complete tenant isolation with RBAC
- 🚀 **High Performance** - Async endpoints, connection pooling
- 📊 **Auto Documentation** - OpenAPI/Swagger with interactive testing
- 🛡️ **Security First** - Rate limiting, CORS, input validation
- 🔍 **Advanced Filtering** - Delta queries, pagination, search
- 📈 **Monitoring Ready** - Health checks, metrics, logging

---

## Quick Links

| Resource | URL | Description |
|----------|-----|-------------|
| 📚 API Docs | http://localhost:8000/api/docs | Interactive Swagger UI |
| 📖 ReDoc | http://localhost:8000/api/redoc | Clean documentation |
| 💚 Health Check | http://localhost:8000/health | Service status |
| 📊 Stats | http://localhost:8000/api/v1/stats | API statistics |

---

## Quick Start

### 1. Install & Configure

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies (includes new slowapi for rate limiting)
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

### 2. Start Services

```bash
# Start PostgreSQL, Redis, MinIO (via Docker)
docker-compose up -d postgres redis minio

# Run database migrations
alembic upgrade head
```

### 3. Create Admin User

```bash
# Interactive script to create first admin user
python scripts/create_admin.py
```

### 4. Start API Server

```bash
# Development mode (auto-reload)
./scripts/start_api.sh

# Production mode (4 workers)
./scripts/start_api.sh production
```

### 5. Test Authentication

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"your_password"}'

# Access protected endpoint
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

**Done!** 🎉 API is running at http://localhost:8000

---

## API Endpoints (27 total)

### Authentication (9 endpoints)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/auth/login` | Login with credentials | No |
| POST | `/api/v1/auth/refresh` | Refresh access token | No |
| POST | `/api/v1/auth/logout` | Logout (revoke tokens) | Yes |
| GET | `/api/v1/auth/me` | Get current user | Yes |
| PATCH | `/api/v1/auth/me` | Update profile | Yes |
| POST | `/api/v1/auth/change-password` | Change password | Yes |
| POST | `/api/v1/auth/users` | Create user | Admin |
| GET | `/api/v1/auth/users` | List users | Admin |
| GET | `/api/v1/auth/users/{id}` | Get user details | Admin |

### Tenants (5 endpoints)

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/api/v1/tenants` | List accessible tenants | User |
| POST | `/api/v1/tenants` | Create tenant | Admin |
| GET | `/api/v1/tenants/{id}` | Get tenant | Member |
| PATCH | `/api/v1/tenants/{id}` | Update tenant | Admin |
| GET | `/api/v1/tenants/{id}/dashboard` | Dashboard stats | Member |

### Assets (4 endpoints)

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/api/v1/tenants/{id}/assets` | List with filters | Read |
| POST | `/api/v1/tenants/{id}/assets` | Create asset | Write |
| GET | `/api/v1/tenants/{id}/assets/{aid}` | Get details | Read |
| DELETE | `/api/v1/tenants/{id}/assets/{aid}` | Soft delete | Write |

**Query Filters:**
- `type` - domain, subdomain, ip, url, service
- `changed_since` - ISO 8601 timestamp (delta query)
- `risk_score` - Minimum score (0-100)
- `search` - Search identifier
- `page`, `page_size` - Pagination

### Services (2 endpoints)

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/api/v1/tenants/{id}/services` | List services | Read |
| GET | `/api/v1/tenants/{id}/services/{sid}` | Get service | Read |

**Query Filters:**
- `port` - Filter by port (443, 80, etc.)
- `product` - Filter by product (nginx, Apache)
- `has_tls` - TLS enabled (true/false)

### Certificates (2 endpoints)

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/api/v1/tenants/{id}/certificates` | List certificates | Read |
| GET | `/api/v1/tenants/{id}/certificates/{cid}` | Get certificate | Read |

**Query Filters:**
- `expiring_in` - Days until expiry (e.g., 30)
- `wildcard` - Wildcard certs (true/false)
- `is_expired` - Expired certs (true/false)

### Endpoints (2 endpoints)

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/api/v1/tenants/{id}/endpoints` | List endpoints | Read |
| GET | `/api/v1/tenants/{id}/endpoints/{eid}` | Get endpoint | Read |

**Query Filters:**
- `is_api` - API endpoints (true/false)
- `endpoint_type` - api, form, file, etc.
- `method` - GET, POST, PUT, DELETE

### Findings (3 endpoints)

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/api/v1/tenants/{id}/findings` | List findings | Read |
| POST | `/api/v1/tenants/{id}/findings/{fid}/suppress` | Suppress | Write |
| PATCH | `/api/v1/tenants/{id}/findings/{fid}` | Update status | Write |

**Query Filters:**
- `severity` - critical,high,medium,low,info
- `status` - open, suppressed, fixed
- `template_id` - Nuclei template ID
- `cve_id` - CVE identifier

---

## Authentication

### JWT Token Flow

```
1. POST /auth/login (email, password)
   ↓
2. Receive access_token (30 min) + refresh_token (7 days)
   ↓
3. Use access_token in Authorization header
   ↓
4. When expired, POST /auth/refresh to get new tokens
```

### Token Format

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Token Payload

```json
{
  "sub": "user_id",
  "tenant_id": 1,
  "roles": ["user", "admin"],
  "exp": 1698234567,
  "iat": 1698232767,
  "type": "access",
  "jti": "unique_token_id"
}
```

---

## Multi-tenancy & RBAC

### Tenant Isolation

All resource endpoints are scoped to tenants:
```
/api/v1/tenants/{tenant_id}/assets
/api/v1/tenants/{tenant_id}/services
/api/v1/tenants/{tenant_id}/findings
```

Users can only access tenants they belong to (via TenantMembership).

### Roles & Permissions

| Role | Permissions | Description |
|------|-------------|-------------|
| **viewer** | read | Read-only access |
| **member** | read, write | Can modify resources |
| **admin** | read, write, admin | Full tenant control |

**Superusers** have access to all tenants and admin functions.

---

## Security Features

### JWT Authentication
- RS256 (asymmetric) recommended for production
- HS256 (symmetric) for development
- Token rotation on refresh
- Token revocation via Redis
- Secure password hashing (bcrypt)

### Rate Limiting
- 100 requests/minute per IP (default)
- Configurable per user/role
- Redis-backed state
- 429 response with retry headers

### CORS
- Configurable allowed origins
- No wildcard in production
- Credentials support
- Custom headers allowed

### Input Validation
- Pydantic v2 schemas
- Email validation
- URL validation
- Type checking
- Min/max length enforcement

### SQL Injection Prevention
- SQLAlchemy ORM (parameterized queries)
- No raw SQL in endpoints
- Input sanitization

---

## Error Handling

All errors follow consistent format:

```json
{
  "error": "ErrorClassName",
  "detail": "Human-readable message",
  "status_code": 400
}
```

### HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | Successful request |
| 201 | Created | Resource created |
| 400 | Bad Request | Invalid input |
| 401 | Unauthorized | Missing/invalid token |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 422 | Validation Error | Schema validation failed |
| 429 | Rate Limited | Too many requests |
| 500 | Server Error | Internal error |

---

## Pagination

All list endpoints support pagination:

```
GET /api/v1/tenants/1/assets?page=2&page_size=100
```

**Parameters:**
- `page` - Page number (default: 1)
- `page_size` - Items per page (default: 50, max: 1000)

**Response:**
```json
{
  "items": [...],
  "total": 1250,
  "page": 2,
  "page_size": 100,
  "pages": 13
}
```

---

## Advanced Features

### Delta Queries

Track changes over time:

```bash
# Get assets changed since October 20, 2025
GET /api/v1/tenants/1/assets?changed_since=2025-10-20T00:00:00Z
```

### Complex Filtering

Combine multiple filters:

```bash
# High-risk subdomains with recent changes
GET /api/v1/tenants/1/assets?type=subdomain&risk_score=70&changed_since=2025-10-20T00:00:00Z
```

### Search

Full-text search in identifiers:

```bash
# Find all assets matching "api"
GET /api/v1/tenants/1/assets?search=api
```

### Dashboard Stats

Comprehensive dashboard data:

```bash
GET /api/v1/tenants/1/dashboard
```

Returns:
- Total assets by type
- Finding counts by severity
- Expiring certificates
- Recent activity
- Risk distribution

---

## Development

### Project Structure

```
easm/
├── app/
│   ├── api/
│   │   ├── dependencies.py      # Auth, DB, pagination
│   │   ├── routers/             # Endpoint handlers (7 files)
│   │   └── schemas/             # Pydantic models (8 files)
│   ├── main.py                  # FastAPI app
│   ├── config.py                # Settings
│   ├── database.py              # DB connection
│   ├── security/
│   │   └── jwt_auth.py          # JWT manager
│   └── models/                  # SQLAlchemy models
├── scripts/
│   ├── start_api.sh             # Startup script
│   └── create_admin.py          # Admin creation
├── requirements.txt             # Dependencies
├── .env                         # Configuration
└── API_DOCUMENTATION.md         # Full API reference
```

### Configuration

Key environment variables:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=15432

# Redis
REDIS_HOST=localhost
REDIS_PORT=16379

# JWT
JWT_SECRET_KEY=<strong-random-key>
JWT_ALGORITHM=HS256  # or RS256

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=100
```

### Adding New Endpoints

1. Create schema in `app/api/schemas/`
2. Add route in `app/api/routers/`
3. Register router in `app/main.py`
4. Add dependency for auth/permissions
5. Document with docstrings

Example:

```python
from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_user, verify_tenant_access
from app.api.schemas.custom import CustomResponse

router = APIRouter(prefix="/api/v1/custom", tags=["Custom"])

@router.get("/{tenant_id}/items", response_model=list[CustomResponse])
def list_items(
    tenant_id: int,
    membership = Depends(verify_tenant_access),
    db: Session = Depends(get_db)
):
    """
    List custom items for tenant

    Requires read permission.
    """
    # Your logic here
    pass
```

---

## Testing

### Interactive Testing (Swagger UI)

1. Open http://localhost:8000/api/docs
2. Click "Authorize" button
3. Login via `/auth/login` endpoint
4. Copy `access_token` from response
5. Paste into authorization dialog
6. Try endpoints with "Try it out"

### Command Line (curl)

```bash
# Set token variable
export TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# List assets
curl http://localhost:8000/api/v1/tenants/1/assets \
  -H "Authorization: Bearer $TOKEN"

# Create asset
curl -X POST http://localhost:8000/api/v1/tenants/1/assets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"type":"domain","identifier":"example.com"}'
```

### Python Client

```python
import requests

# Login
resp = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"email": "admin@example.com", "password": "admin123"}
)
token = resp.json()["access_token"]

# Authenticated request
headers = {"Authorization": f"Bearer {token}"}
resp = requests.get(
    "http://localhost:8000/api/v1/tenants/1/assets",
    headers=headers
)
assets = resp.json()
```

---

## Performance

### Database
- Connection pooling (20 connections, 40 overflow)
- Pool pre-ping (stale detection)
- Connection recycling (1 hour)
- Query optimization with indexes

### Caching
- Redis for JWT tokens
- Token revocation state
- Rate limiting state

### Response Optimization
- GZip compression (> 1KB)
- Pagination (max 1000 items)
- Lazy loading (ORM)
- Process time tracking

---

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

Returns status of:
- PostgreSQL (connection test)
- Redis (ping)
- MinIO (bucket list)

Returns 503 if any service is down.

### Metrics

Process time header on all responses:
```
X-Process-Time: 123.45
```

### Logging

Structured logging for all requests:
```
INFO: GET /api/v1/tenants/1/assets - Client: 192.168.1.100
INFO: GET /api/v1/tenants/1/assets - Status: 200
```

---

## Production Deployment

### Pre-deployment Checklist

- [ ] Generate strong JWT_SECRET_KEY (64+ chars)
- [ ] Use RS256 algorithm
- [ ] Set ENVIRONMENT=production
- [ ] Update CORS_ORIGINS (no wildcard!)
- [ ] Enable HTTPS/TLS
- [ ] Strong database password (16+ chars)
- [ ] Enable Redis authentication
- [ ] Configure rate limiting
- [ ] Set up Sentry error tracking
- [ ] Configure log aggregation
- [ ] Set up backups
- [ ] Use secrets management (Vault, AWS Secrets)

### Docker Deployment

```bash
# Build image
docker build -t easm-api:3.0.0 .

# Run container
docker run -d \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e JWT_SECRET_KEY=$JWT_SECRET_KEY \
  --name easm-api \
  easm-api:3.0.0
```

### Kubernetes

See `k8s/` directory for manifests.

---

## Integration

### Frontend (Vue.js)

```javascript
// api.js
const API_BASE = 'http://localhost:8000/api/v1';
const token = localStorage.getItem('access_token');

export async function getAssets(tenantId, filters = {}) {
  const params = new URLSearchParams(filters);
  const resp = await fetch(
    `${API_BASE}/tenants/${tenantId}/assets?${params}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    }
  );
  return resp.json();
}
```

### External Services

```python
# Webhook integration
import hmac
import hashlib

def verify_webhook(payload, signature, secret):
    """Verify webhook signature"""
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

---

## Documentation

| Document | Description |
|----------|-------------|
| `API_DOCUMENTATION.md` | Complete API reference |
| `SPRINT_3_SUMMARY.md` | Sprint completion summary |
| `SPRINT_3_QUICKSTART.md` | Quick start guide |
| `API_README.md` | This file |
| `/api/docs` | Interactive Swagger UI |
| `/api/redoc` | Clean documentation |

---

## Support

- **Issues:** Report bugs or request features
- **Documentation:** Full API reference in `API_DOCUMENTATION.md`
- **Health:** Monitor at `/health` endpoint
- **Logs:** Check application logs for errors

---

## License

Proprietary - EASM Platform

---

## Credits

**Sprint 3 - FastAPI REST API Architecture**
- Completed: 2025-10-25
- Status: Production-ready
- Endpoints: 27
- Lines of Code: ~2,500
- Test Coverage: Pending (Sprint 4)

Built with ❤️ using FastAPI, SQLAlchemy, and Pydantic.

---

**Version:** 3.0.0
**Last Updated:** 2025-10-25
**Sprint:** 3 of 6 - COMPLETE ✅
