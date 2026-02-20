# Sprint 3 Docker Integration Guide

**Status:** ✅ Sprint 3 API runs in Docker

---

## Overview

All Sprint 3 components (FastAPI API, Nuclei scanner, security features, tests) are designed to run in Docker containers for consistency and production-readiness.

---

## Docker Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose Stack                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │PostgreSQL│  │  Redis   │  │  MinIO   │  │   API    │    │
│  │          │  │          │  │          │  │(FastAPI) │    │
│  │  :5432   │  │  :6379   │  │  :9000   │  │  :8000   │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │              │             │           │
│       └─────────────┴──────────────┴─────────────┘           │
│                         │                                    │
│                    easm-network                              │
│                         │                                    │
│  ┌──────────┐  ┌──────────┐                                 │
│  │  Worker  │  │   Beat   │                                 │
│  │ (Celery) │  │(Scheduler)│                                │
│  │+ PD Tools│  │          │                                 │
│  └──────────┘  └──────────┘                                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘

Exposed Ports:
- 18000 → API (FastAPI)
- 15432 → PostgreSQL
- 16379 → Redis
- 9000  → MinIO API
- 9001  → MinIO Console
```

---

## Docker Services

### 1. **API Service** (NEW in Sprint 3)

**Container:** `easm-api`
**Dockerfile:** `Dockerfile.api`
**Port:** 18000 (external) → 8000 (internal)

**Purpose:**
- FastAPI REST API
- JWT authentication (RS256)
- Multi-tenant endpoints
- Rate limiting
- OpenAPI documentation

**Health Check:**
```bash
curl http://localhost:18000/health
```

**Logs:**
```bash
docker-compose logs -f api
```

### 2. **Worker Service** (Sprint 2 - Enhanced in Sprint 3)

**Container:** `easm-worker`
**Dockerfile:** `Dockerfile.worker`

**Purpose:**
- Celery task workers
- ProjectDiscovery tools (Subfinder, HTTPx, Naabu, TLSx, Katana, **Nuclei**)
- Enrichment pipeline
- **Nuclei vulnerability scanning** (Sprint 3)

**Nuclei Version:**
```bash
docker-compose exec worker nuclei -version
```

### 3. **Beat Service** (Scheduler)

**Container:** `easm-beat`
**Purpose:** Celery Beat scheduler for periodic tasks

### 4. **Supporting Services**

- **PostgreSQL** - Database (port 15432)
- **Redis** - Cache & queue (port 16379)
- **MinIO** - Object storage (port 9000)

---

## Quick Start

### 1. Start All Services

```bash
# Start everything (API + Worker + Database)
docker-compose up -d

# Check status
docker-compose ps

# Expected output:
# easm-api       running   0.0.0.0:18000->8000/tcp
# easm-worker    running
# easm-beat      running
# easm-postgres  running   0.0.0.0:15432->5432/tcp
# easm-redis     running   0.0.0.0:16379->6379/tcp
# easm-minio     running   0.0.0.0:9000-9001->9000-9001/tcp
```

### 2. Verify API is Running

```bash
# Health check
curl http://localhost:18000/health

# Expected: {"status":"healthy","database":"connected","redis":"connected"}

# Swagger UI
open http://localhost:18000/api/docs
```

### 3. Create Admin User

```bash
# Interactive user creation
docker-compose exec api python scripts/create_admin.py

# Or manually:
docker-compose exec api python3 -c "
from app.database import SessionLocal
from app.models.database import User, Tenant
from app.security.jwt_auth import get_password_hash

db = SessionLocal()

tenant = Tenant(name='Demo Tenant', slug='demo', contact_email='admin@example.com')
db.add(tenant)
db.commit()

user = User(
    email='admin@example.com',
    hashed_password=get_password_hash('ChangeMe123!'),
    full_name='Admin User',
    role='admin',
    tenant_id=tenant.id,
    is_active=True
)
db.add(user)
db.commit()

print(f'✓ Created admin user: {user.email}')
db.close()
"
```

### 4. Test Authentication

```bash
# Login
curl -X POST http://localhost:18000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"ChangeMe123!"}'

# Response:
# {
#   "access_token": "eyJhbGc...",
#   "refresh_token": "eyJhbGc...",
#   "token_type": "bearer"
# }

# Test authenticated endpoint
curl http://localhost:18000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

---

## Running Tests in Docker

### Option 1: Run Unit Tests Inside Container

```bash
# Run all Sprint 3 tests
docker-compose exec api pytest tests/test_api_*.py tests/test_nuclei_integration.py -v

# Run specific test file
docker-compose exec api pytest tests/test_api_auth.py -v

# With coverage
docker-compose exec api pytest tests/ --cov=app.api --cov=app.security --cov-report=html
```

### Option 2: Automated Integration Test Script

```bash
# Run comprehensive Docker integration tests
./scripts/test_api_docker.sh

# Tests:
# ✓ Health check
# ✓ OpenAPI documentation
# ✓ Database connection
# ✓ Authentication flow
# ✓ Tenant endpoints
# ✓ Rate limiting
# ✓ CORS headers
# ✓ Security headers
```

---

## Development Workflow

### Live Code Reloading

The API container mounts `./app` as a volume, so code changes are immediately reflected:

```yaml
volumes:
  - ./app:/app/app  # Live reload enabled
```

**Workflow:**
1. Edit code locally in `app/`
2. Changes are automatically detected by uvicorn `--reload`
3. API restarts in container
4. Test changes immediately at `http://localhost:18000`

### Viewing Logs

```bash
# API logs
docker-compose logs -f api

# Worker logs (Nuclei scans, enrichment tasks)
docker-compose logs -f worker

# All logs
docker-compose logs -f
```

### Rebuilding Containers

```bash
# Rebuild API after dependency changes
docker-compose build api

# Rebuild worker after tool updates
docker-compose build worker

# Rebuild everything
docker-compose build
```

---

## Nuclei Scanning in Docker

### Verify Nuclei Installation

```bash
# Check Nuclei version in worker container
docker-compose exec worker nuclei -version

# Expected: Nuclei Engine Version: v3.4.10
```

### Update Nuclei Templates

```bash
# Update templates in worker container
docker-compose exec worker nuclei -update-templates

# Templates stored at: /root/.config/nuclei/
```

### Test Nuclei Scan

```bash
# Run test scan against safe target
docker-compose exec worker nuclei -u https://example.com \
  -t cves/ -severity critical,high \
  -json -silent

# Run from Python
docker-compose exec worker python3 -c "
from app.services.scanning.nuclei_service import NucleiService
import asyncio

async def test_scan():
    service = NucleiService()
    results = await service.scan_urls(
        urls=['https://example.com'],
        severity=['critical', 'high']
    )
    print(f'Found {len(results)} findings')

asyncio.run(test_scan())
"
```

---

## Environment Variables

Configure via `.env` file or docker-compose environment section:

```bash
# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=easm
POSTGRES_USER=easm
POSTGRES_PASSWORD=secure_password_here

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123

# JWT
JWT_SECRET_KEY=change-this-in-production
JWT_ALGORITHM=RS256

# API
CORS_ORIGINS=["http://localhost:5173"]
ENVIRONMENT=development
```

---

## Troubleshooting

### API Won't Start

```bash
# Check logs
docker-compose logs api

# Common issues:
# 1. Database not ready → Wait for postgres health check
# 2. Port conflict → Change 18000 to another port
# 3. Missing dependencies → Rebuild: docker-compose build api
```

### Database Connection Error

```bash
# Test database connectivity
docker-compose exec api python3 -c "
from app.database import engine
try:
    engine.connect()
    print('✓ Database connected')
except Exception as e:
    print(f'✗ Database error: {e}')
"
```

### Nuclei Not Found in Worker

```bash
# Verify PATH
docker-compose exec worker which nuclei

# Should return: /usr/local/pd-tools/nuclei

# Reinstall if missing
docker-compose build worker --no-cache
```

### Rate Limiting Not Working

```bash
# Check Redis connection
docker-compose exec api python3 -c "
import redis
r = redis.Redis(host='redis', port=6379)
r.ping()
print('✓ Redis connected')
"
```

---

## Production Deployment

### 1. Update docker-compose.yml for Production

```yaml
api:
  build:
    context: .
    dockerfile: Dockerfile.api
  restart: unless-stopped
  environment:
    ENVIRONMENT: production
    JWT_ALGORITHM: RS256
  # Remove volume mount for security
  # volumes:
  #   - ./app:/app/app  # Comment out in production
```

### 2. Use Docker Secrets for Sensitive Data

```yaml
secrets:
  postgres_password:
    external: true
  jwt_private_key:
    external: true
```

### 3. Enable TLS/SSL

Use a reverse proxy (nginx, Traefik, Caddy) in front of the API:

```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl
```

### 4. Production Checklist

- [ ] Change all default passwords
- [ ] Generate production RSA keys
- [ ] Set `ENVIRONMENT=production`
- [ ] Remove volume mounts (disable live reload)
- [ ] Configure TLS/SSL reverse proxy
- [ ] Set up log aggregation (ELK, Loki)
- [ ] Configure Prometheus metrics
- [ ] Set up automated backups (PostgreSQL, MinIO)
- [ ] Enable Docker restart policies
- [ ] Use Docker secrets for credentials
- [ ] Limit container resources (CPU, memory)

---

## API Endpoints (Docker)

All endpoints accessible at `http://localhost:18000/api/v1/`

### Authentication
- POST `/auth/login` - Login and get JWT
- POST `/auth/refresh` - Refresh access token
- GET `/auth/me` - Get current user
- POST `/auth/logout` - Logout and revoke token

### Tenants
- GET `/tenants` - List tenants (admin)
- POST `/tenants` - Create tenant (admin)
- GET `/tenants/{id}` - Get tenant details
- GET `/tenants/{id}/dashboard` - Dashboard stats

### Assets
- GET `/tenants/{t}/assets` - List assets (with filters)
- POST `/tenants/{t}/assets` - Create asset
- GET `/tenants/{t}/assets/{id}` - Asset details
- DELETE `/tenants/{t}/assets/{id}` - Delete asset

### Findings (Nuclei)
- GET `/tenants/{t}/findings` - List findings (with filters)
- POST `/tenants/{t}/findings/{id}/suppress` - Suppress finding
- PATCH `/tenants/{t}/findings/{id}` - Update finding status

---

## Monitoring

### Health Checks

```bash
# API health
curl http://localhost:18000/health

# Database health
docker-compose exec postgres pg_isready -U easm

# Redis health
docker-compose exec redis redis-cli ping
```

### Resource Usage

```bash
# Container stats
docker stats

# Disk usage
docker system df
```

---

## Summary

✅ **Sprint 3 API runs fully in Docker**
✅ **All services containerized** (API, Worker, Database, Cache, Storage)
✅ **Development workflow optimized** (live reload, easy testing)
✅ **Production-ready** (health checks, restart policies, secrets)
✅ **Nuclei integration working** in worker container
✅ **Comprehensive testing** via `test_api_docker.sh`

**Next:** Sprint 4 - Vue.js UI will connect to API at `http://localhost:18000`
