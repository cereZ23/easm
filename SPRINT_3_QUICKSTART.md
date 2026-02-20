# Sprint 3 - FastAPI REST API Quick Start Guide

This guide will help you get the EASM Platform API up and running in minutes.

---

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- MinIO (or AWS S3)

---

## Installation

### 1. Activate Virtual Environment

```bash
cd /Users/cere/Downloads/easm
source venv/bin/activate  # On macOS/Linux
# OR
.\venv\Scripts\activate   # On Windows
```

### 2. Install Dependencies

The new Sprint 3 dependency (slowapi for rate limiting) is already added to requirements.txt:

```bash
pip install -r requirements.txt
```

**New Package Added:**
- `slowapi==0.1.9` - Rate limiting for FastAPI

### 3. Configure Environment

If `.env` doesn't exist, copy from example:

```bash
cp .env.example .env
```

**Critical Settings to Update:**
```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=15432
POSTGRES_DB=easm
POSTGRES_USER=easm
POSTGRES_PASSWORD=easm_dev_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=16379

# JWT (generate strong keys for production!)
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
JWT_ALGORITHM=HS256  # Use RS256 for production

# CORS (update for your frontend)
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

---

## Database Setup

### Option 1: Using Docker Compose (Recommended)

```bash
# Start PostgreSQL, Redis, and MinIO
docker-compose up -d postgres redis minio
```

### Option 2: Local Installation

Make sure PostgreSQL and Redis are running:

```bash
# macOS
brew services start postgresql@14
brew services start redis

# Linux
sudo systemctl start postgresql
sudo systemctl start redis
```

### Run Migrations

```bash
# Apply database migrations
alembic upgrade head
```

---

## Create Admin User

```bash
python scripts/create_admin.py
```

Follow the interactive prompts to create your first admin user.

**Example:**
```
Email address: admin@example.com
Username: admin
Password: ********
Confirm password: ********
Full name (optional): Admin User
Tenant name (default: Default Tenant): ACME Corp
Tenant slug (default: default): acme-corp
```

---

## Start the API Server

### Development Mode (Recommended)

With auto-reload enabled:

```bash
./scripts/start_api.sh
```

Or manually:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

With multiple workers:

```bash
./scripts/start_api.sh production
```

Or manually:

```bash
uvicorn app.main:app --workers 4 --host 0.0.0.0 --port 8000
```

---

## Verify Installation

### 1. Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "services": {
    "database": {
      "status": "connected",
      "type": "postgresql"
    },
    "redis": {
      "status": "connected"
    },
    "minio": {
      "status": "connected",
      "endpoint": "localhost:19000"
    }
  }
}
```

### 2. Access API Documentation

Open in browser:
- **Swagger UI:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc
- **OpenAPI JSON:** http://localhost:8000/api/openapi.json

### 3. Test Authentication

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "your_password"
  }'
```

Expected response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": 1,
    "email": "admin@example.com",
    "username": "admin",
    "full_name": "Admin User",
    "is_active": true,
    "is_superuser": true
  }
}
```

### 4. Test Protected Endpoint

```bash
# Export token from login response
export TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Get current user
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### 5. Test Tenant Endpoint

```bash
# List tenants
curl http://localhost:8000/api/v1/tenants \
  -H "Authorization: Bearer $TOKEN"

# Get tenant dashboard
curl http://localhost:8000/api/v1/tenants/1/dashboard \
  -H "Authorization: Bearer $TOKEN"
```

---

## Common Issues & Solutions

### Issue: "Module not found: fastapi"

**Solution:**
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: "Cannot connect to database"

**Solution:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres
# OR
brew services list | grep postgresql

# Check connection settings in .env
# Make sure POSTGRES_HOST, POSTGRES_PORT, etc. are correct
```

### Issue: "Cannot connect to Redis"

**Solution:**
```bash
# Check Redis is running
docker-compose ps redis
# OR
brew services list | grep redis

# Test Redis connection
redis-cli -h localhost -p 16379 ping
```

### Issue: "Rate limit exceeded"

**Solution:**
```bash
# Rate limiting is enabled by default (100 req/min)
# Wait 60 seconds or disable in .env:
RATE_LIMIT_ENABLED=false
```

### Issue: "CORS error from frontend"

**Solution:**
```bash
# Update CORS_ORIGINS in .env to include your frontend URL
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://localhost:8080"]
```

---

## API Endpoint Overview

### Authentication (9 endpoints)
- POST `/api/v1/auth/login` - Login
- POST `/api/v1/auth/refresh` - Refresh token
- POST `/api/v1/auth/logout` - Logout
- GET `/api/v1/auth/me` - Get current user
- PATCH `/api/v1/auth/me` - Update profile
- POST `/api/v1/auth/change-password` - Change password
- POST `/api/v1/auth/users` - Create user (admin)
- GET `/api/v1/auth/users` - List users (admin)
- GET `/api/v1/auth/users/{id}` - Get user (admin)

### Tenants (5 endpoints)
- GET `/api/v1/tenants` - List tenants
- POST `/api/v1/tenants` - Create tenant (admin)
- GET `/api/v1/tenants/{id}` - Get tenant
- PATCH `/api/v1/tenants/{id}` - Update tenant
- GET `/api/v1/tenants/{id}/dashboard` - Dashboard

### Assets (4 endpoints)
- GET `/api/v1/tenants/{id}/assets` - List assets
- POST `/api/v1/tenants/{id}/assets` - Create asset
- GET `/api/v1/tenants/{id}/assets/{asset_id}` - Get asset
- DELETE `/api/v1/tenants/{id}/assets/{asset_id}` - Delete asset

### Services (2 endpoints)
- GET `/api/v1/tenants/{id}/services` - List services
- GET `/api/v1/tenants/{id}/services/{service_id}` - Get service

### Certificates (2 endpoints)
- GET `/api/v1/tenants/{id}/certificates` - List certificates
- GET `/api/v1/tenants/{id}/certificates/{cert_id}` - Get certificate

### Endpoints (2 endpoints)
- GET `/api/v1/tenants/{id}/endpoints` - List endpoints
- GET `/api/v1/tenants/{id}/endpoints/{endpoint_id}` - Get endpoint

### Findings (3 endpoints)
- GET `/api/v1/tenants/{id}/findings` - List findings
- POST `/api/v1/tenants/{id}/findings/{finding_id}/suppress` - Suppress
- PATCH `/api/v1/tenants/{id}/findings/{finding_id}` - Update

**Total: 27 endpoints**

---

## Next Steps

### 1. Explore API Documentation
Open http://localhost:8000/api/docs and try out the interactive API.

### 2. Create Some Test Data

```bash
# Create a test asset
curl -X POST http://localhost:8000/api/v1/tenants/1/assets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "domain",
    "identifier": "example.com",
    "priority": "high"
  }'
```

### 3. Run Discovery Pipeline

The API reads data from the discovery pipeline (Sprints 1 & 2):

```bash
# Trigger discovery via Celery (if running)
# This will populate assets, services, certificates, etc.
```

### 4. Integrate with Frontend

Use the API with your Vue.js frontend or any HTTP client:

```javascript
// Example: Fetch assets
const response = await fetch('http://localhost:8000/api/v1/tenants/1/assets', {
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});
const data = await response.json();
console.log(`Total assets: ${data.total}`);
```

---

## Development Tips

### Use API Documentation
The interactive Swagger UI at `/api/docs` is the fastest way to test endpoints.

### Enable Debug Mode
For detailed error messages:
```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

### Watch Logs
```bash
# In one terminal
./scripts/start_api.sh

# In another terminal
tail -f /var/log/easm/app.log  # If LOG_FILE is set
```

### Use HTTP Client Tools
- **curl** - Command line
- **httpie** - Human-friendly curl alternative
- **Postman** - GUI for API testing
- **Insomnia** - Alternative to Postman

---

## Production Deployment Checklist

Before deploying to production:

- [ ] Set strong `JWT_SECRET_KEY` (min 64 chars)
- [ ] Use `RS256` algorithm with key rotation
- [ ] Set `ENVIRONMENT=production`
- [ ] Configure `CORS_ORIGINS` to specific domains (no wildcard!)
- [ ] Enable HTTPS/TLS
- [ ] Set strong database passwords
- [ ] Enable Redis authentication (`REDIS_PASSWORD`)
- [ ] Configure rate limiting per user
- [ ] Enable Sentry error tracking
- [ ] Set up log aggregation (ELK, Datadog, etc.)
- [ ] Configure backup strategy
- [ ] Use environment variable for all secrets (no hardcoded values)
- [ ] Run behind reverse proxy (nginx, Traefik)
- [ ] Set up health check monitoring
- [ ] Configure auto-scaling (Kubernetes, ECS)

---

## Support & Documentation

- **API Docs:** http://localhost:8000/api/docs
- **Health Check:** http://localhost:8000/health
- **Comprehensive Guide:** `/Users/cere/Downloads/easm/API_DOCUMENTATION.md`
- **Sprint Summary:** `/Users/cere/Downloads/easm/SPRINT_3_SUMMARY.md`

---

**Happy building!** 🚀
