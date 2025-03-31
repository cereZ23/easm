# EASM Platform - External Attack Surface Management

Multi-tenant EASM platform built around ProjectDiscovery tools for continuous security reconnaissance.

## Sprint 1 Status: Core Infrastructure & Discovery Pipeline ✅

### Completed Features

- ✅ Docker Compose environment (PostgreSQL, Redis, MinIO, API, Worker, Beat)
- ✅ Complete database schema with multi-tenant isolation
- ✅ Celery task queue with scheduler (Beat)
- ✅ Discovery pipeline: Uncover → Subfinder + Amass (parallel) → DNSX
- ✅ MinIO storage for raw tool outputs
- ✅ Asset persistence with event tracking
- ✅ Database migrations (Alembic)

## Quick Start

### Prerequisites

- Docker & Docker Compose
- 8GB+ RAM recommended
- Ports 5432, 6379, 8000, 9000, 9001 available

### Installation

1. **Clone and setup**
   ```bash
   cd easm
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Start services**
   ```bash
   docker-compose up -d
   ```

3. **Check status**
   ```bash
   docker-compose ps
   docker-compose logs -f
   ```

4. **Access services**
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - MinIO Console: http://localhost:9001 (minioadmin/minioadmin123)

### Running Discovery

The discovery pipeline runs automatically via Celery Beat:
- **Daily full discovery**: 2 AM UTC
- **Critical asset watch**: Every 30 minutes

To manually trigger discovery for a tenant:

```bash
# Enter worker container
docker-compose exec worker bash

# Run Python shell
python

# Trigger discovery
from app.tasks.discovery import run_full_discovery
run_full_discovery.apply_async()
```

### Database Access

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U easm -d easm

# Check tenants
SELECT * FROM tenants;

# Check assets
SELECT id, type, identifier, risk_score FROM assets LIMIT 10;

# Check recent events
SELECT * FROM events ORDER BY created_at DESC LIMIT 10;
```

### Adding Seeds

Seeds are the starting points for discovery (domains, ASNs, keywords).

```bash
# Enter PostgreSQL
docker-compose exec postgres psql -U easm -d easm

# Add domain seed
INSERT INTO seeds (tenant_id, type, value, enabled, created_at)
VALUES (1, 'domain', 'yourdomain.com', true, NOW());

# Add keyword for OSINT (requires API keys in .env)
INSERT INTO seeds (tenant_id, type, value, enabled, created_at)
VALUES (1, 'keyword', 'Your Company Name', true, NOW());
```

### Monitoring Tasks

```bash
# View Celery workers
docker-compose exec worker celery -A app.celery_app inspect active

# View scheduled tasks
docker-compose exec beat celery -A app.celery_app inspect scheduled

# View task results
docker-compose exec worker celery -A app.celery_app result <task-id>
```

### MinIO Storage

Raw tool outputs are stored in MinIO:

1. Open MinIO Console: http://localhost:9001
2. Login: minioadmin / minioadmin123
3. Browse buckets: `tenant-1`, `tenant-2`, etc.
4. View raw outputs: `subfinder/`, `dnsx/`, `httpx/`, etc.

## Architecture

```
Seeds (domains, ASNs, keywords)
    ↓
Uncover (OSINT discovery)
    ↓
Subfinder + Amass (parallel subdomain enumeration)
    ↓
Merge & Deduplicate (30-50% more coverage)
    ↓
DNSX (DNS resolution)
    ↓
Database (assets, events)
    ↓
MinIO (raw outputs)
```

## Testing

```bash
# Run tests
docker-compose exec worker pytest

# Run specific test
docker-compose exec worker pytest tests/test_discovery.py

# Run with coverage
docker-compose exec worker pytest --cov=app tests/
```

## Development

### Project Structure

```
easm/
├── app/
│   ├── models/         # Database models
│   ├── tasks/          # Celery tasks
│   ├── routers/        # API routers (Sprint 2)
│   ├── utils/          # Utilities
│   ├── main.py         # FastAPI app
│   ├── database.py     # DB connection
│   └── celery_app.py   # Celery config
├── alembic/            # Database migrations
├── tests/              # Unit tests
├── docker-compose.yml  # Services orchestration
├── Dockerfile.api      # API container
├── Dockerfile.worker   # Worker container
└── requirements.txt    # Python dependencies
```

### Making Database Changes

```bash
# Create new migration
docker-compose exec api alembic revision --autogenerate -m "description"

# Apply migration
docker-compose exec api alembic upgrade head

# Rollback
docker-compose exec api alembic downgrade -1
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f worker
docker-compose logs -f api
docker-compose logs -f beat

# Last 100 lines
docker-compose logs --tail=100 worker
```

## Troubleshooting

### Worker not picking up tasks

```bash
# Restart worker
docker-compose restart worker

# Check Redis connection
docker-compose exec worker python -c "import redis; r=redis.from_url('redis://redis:6379/0'); print(r.ping())"
```

### Database connection issues

```bash
# Check PostgreSQL status
docker-compose exec postgres pg_isready

# Restart database
docker-compose restart postgres

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
```

### MinIO not accessible

```bash
# Restart MinIO
docker-compose restart minio

# Check MinIO logs
docker-compose logs minio
```

### ProjectDiscovery tools not found

```bash
# Enter worker container
docker-compose exec worker bash

# Check tool versions
subfinder -version
dnsx -version
httpx -version
nuclei -version

# Rebuild worker if needed
docker-compose build --no-cache worker
```

## Multi-Tenant Usage

Each tenant is completely isolated:

1. **Database**: All queries filtered by `tenant_id`
2. **Storage**: Separate MinIO buckets (`tenant-1`, `tenant-2`)
3. **API Keys**: Per-tenant OSINT provider keys
4. **Schedules**: Independent scan schedules per tenant

### Creating a New Tenant

```sql
INSERT INTO tenants (name, slug, contact_policy, created_at, updated_at)
VALUES ('Acme Corp', 'acme', 'security@acme.com', NOW(), NOW());
```

## Next Steps (Sprint 2)

- [ ] HTTP enrichment (httpx)
- [ ] Port scanning (naabu)
- [ ] TLS intelligence (tlsx)
- [ ] Web crawling (katana)
- [ ] FastAPI authentication (JWT)
- [ ] Multi-tenant API endpoints
- [ ] Asset and service REST APIs

## Documentation

- [CLAUDE.md](CLAUDE.md) - AI assistant guidance
- [SPRINTS.md](SPRINTS.md) - Detailed sprint plans
- [easm.md](easm.md) - Original architecture design (Italian)

## License

Proprietary - Internal Use Only

## Support

For issues and questions, create an issue in the repository.
