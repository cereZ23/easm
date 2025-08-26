# Sprint 2 Quick Reference Guide

**Sprint Duration**: 21 days (October 24 - November 13, 2025)
**Status**: Ready to Start

---

## QUICK PRIORITIES

### Day 1: CRITICAL SECURITY FIXES 🚨

**MUST DO FIRST - NO EXCEPTIONS**

1. **Verify SecureToolExecutor Constants** ✅ (already fixed)
2. **Verify CORS Configuration** ✅ (already fixed)
3. **Fix .env Security Issue** ⚠️
   ```bash
   # Add .env to .gitignore
   echo ".env" >> .gitignore

   # Remove from git if committed
   git rm --cached .env
   git commit -m "Security: Remove .env from version control"

   # Generate new secrets
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   ```

4. **Add Security Headers**
   - X-Content-Type-Options: nosniff
   - X-Frame-Options: DENY
   - X-XSS-Protection: 1; mode=block
   - Strict-Transport-Security: max-age=31536000
   - Content-Security-Policy: default-src 'self'

---

## WEEKLY OVERVIEW

### WEEK 1: Security + HTTPx + Naabu
- **Day 1**: Critical security fixes
- **Days 2-3**: HTTPx implementation
- **Days 4-5**: Naabu implementation
- **Days 6-7**: Database updates + testing

**Deliverables:**
- All security issues resolved
- HTTPx enrichment working
- Naabu port scanning working
- Service repository implemented

---

### WEEK 2: TLSx + Katana + API Foundation
- **Days 8-9**: TLSx implementation
- **Days 10-11**: Katana implementation
- **Days 12-14**: JWT auth + API foundation

**Deliverables:**
- TLSx certificate analysis working
- Katana web crawling working
- Authentication system complete
- Basic API endpoints operational

---

### WEEK 3: Complete API + Production Ready
- **Days 15-16**: Complete CRUD endpoints
- **Days 17-18**: Monitoring + observability
- **Days 19-20**: Testing + documentation
- **Day 21**: Final deployment prep

**Deliverables:**
- All API endpoints complete
- Sentry + Prometheus integrated
- Test coverage ≥ 80%
- Production deployment ready

---

## FILES TO CREATE

### New Python Files

```
app/
├── tasks/
│   └── enrichment.py (NEW - HTTPx, Naabu, TLSx, Katana)
├── repositories/
│   └── service_repository.py (NEW)
├── routers/
│   ├── auth.py (NEW - JWT authentication)
│   ├── assets.py (NEW - Asset endpoints)
│   ├── services.py (NEW - Service endpoints)
│   └── seeds.py (NEW - Seed management)
├── utils/
│   └── metrics.py (NEW - Prometheus metrics)
└── middleware/
    └── security_headers.py (NEW)
```

### New Test Files

```
tests/
├── test_enrichment.py (NEW)
├── test_api_integration.py (NEW)
├── test_authentication.py (NEW)
└── test_api_endpoints.py (NEW)
```

### New Documentation

```
docs/
├── api/
│   ├── authentication.md
│   ├── assets.md
│   └── enrichment.md
└── architecture/
    └── sprint-2-architecture.md
```

---

## KEY DECISIONS

### Tool Execution
- **Pattern**: Use SecureToolExecutor for ALL tools
- **Isolation**: Tenant-specific temp directories
- **Timeouts**: Configurable per tool
- **Resource Limits**: CPU, memory, file size enforced

### API Design
- **Versioning**: URL-based (`/api/v1/...`)
- **Authentication**: JWT with refresh tokens
- **Authorization**: Role-based (Admin, Member, Viewer)
- **Pagination**: Cursor-based for large datasets
- **Rate Limiting**: 100 req/min per IP

### Database Strategy
- **Bulk Operations**: Use PostgreSQL ON CONFLICT DO UPDATE
- **Indexes**: Created in migration 004
- **Caching**: Redis for frequently accessed data
- **Connection Pool**: 20 connections, 40 overflow

### Testing Strategy
- **Unit Tests**: 80% coverage minimum
- **Integration Tests**: All API endpoints
- **Security Tests**: OWASP Top 10
- **Performance Tests**: p95 < 100ms

---

## CRITICAL PATHS

### Dependencies

```
Day 1: Security Fixes
  ↓
Days 2-5: Enrichment Tools (HTTPx, Naabu)
  ↓
Days 8-11: Enrichment Tools (TLSx, Katana)
  ↓
Days 12-14: API Foundation
  ↓
Days 15-18: Complete API + Monitoring
  ↓
Days 19-21: Testing + Production Prep
```

### Parallel Work Streams

**Stream 1: Enrichment Tools** (Days 2-11)
- HTTPx → Naabu → TLSx → Katana

**Stream 2: API Development** (Days 12-18)
- Auth → Assets → Services → Seeds

**Stream 3: Infrastructure** (Days 17-20)
- Monitoring → Logging → Metrics

---

## SUCCESS CRITERIA CHECKLIST

### Functional Requirements
- [ ] HTTPx enrichment operational
- [ ] Naabu port scanning operational
- [ ] TLSx SSL analysis operational
- [ ] Katana web crawling operational
- [ ] JWT authentication working
- [ ] All CRUD endpoints implemented
- [ ] Multi-tenant isolation verified

### Quality Requirements
- [ ] Test coverage ≥ 80%
- [ ] All integration tests passing
- [ ] No critical security issues
- [ ] API documentation complete
- [ ] Code review approved

### Performance Requirements
- [ ] API response time < 100ms (p95)
- [ ] Enrichment pipeline < 30min (1000 assets)
- [ ] Database queries optimized
- [ ] Rate limiting enforced

### Infrastructure Requirements
- [ ] Sentry monitoring active
- [ ] Prometheus metrics working
- [ ] Logging aggregation setup
- [ ] Health checks passing

---

## COMMON COMMANDS

### Development

```bash
# Start environment
docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head

# Create new migration
docker-compose exec api alembic revision -m "description"

# Run tests
docker-compose exec api pytest

# Run tests with coverage
docker-compose exec api pytest --cov=app --cov-report=html

# View logs
docker-compose logs -f api
docker-compose logs -f worker

# Access database
docker-compose exec postgres psql -U easm -d easm

# Access Redis
docker-compose exec redis redis-cli
```

### Testing

```bash
# Run specific test file
pytest tests/test_enrichment.py -v

# Run integration tests only
pytest tests/test_integration.py -v

# Run with coverage report
pytest --cov=app --cov-report=term-missing

# Run performance tests
pytest tests/test_performance.py --benchmark
```

### Debugging

```bash
# Check SecureToolExecutor
docker-compose exec worker python -c "from app.utils.secure_executor import SecureToolExecutor; print(SecureToolExecutor.DEFAULT_TIMEOUT)"

# Test HTTPx manually
docker-compose exec worker httpx -u https://example.com -json

# Check database connection
docker-compose exec api python -c "from app.database import engine; engine.connect()"

# Verify JWT secret
docker-compose exec api python -c "from app.config import settings; print(len(settings.jwt_secret_key))"
```

---

## TROUBLESHOOTING

### Common Issues

**Issue**: Tests failing with database connection errors
```bash
# Solution: Ensure test database is running
docker-compose exec postgres psql -U easm -d easm_test -c "SELECT 1"

# Create test database if missing
docker-compose exec postgres psql -U easm -c "CREATE DATABASE easm_test"
```

**Issue**: SecureToolExecutor times out
```bash
# Solution: Increase timeout in config
# File: app/config.py
tool_execution_timeout: int = 600  # Increase this value
```

**Issue**: API returns 401 Unauthorized
```bash
# Solution: Check JWT token
docker-compose exec api python -c "
from app.utils.auth import verify_token
token = 'your-token-here'
print(verify_token(token))
"
```

**Issue**: Rate limiting not working
```bash
# Solution: Verify slowapi is installed
docker-compose exec api pip list | grep slowapi

# Install if missing
docker-compose exec api pip install slowapi
```

---

## CODE SNIPPETS

### SecureToolExecutor Pattern

```python
from app.utils.secure_executor import SecureToolExecutor

@celery.task(name='app.tasks.enrichment.run_tool')
def run_tool(tenant_id: int):
    with SecureToolExecutor(tenant_id) as executor:
        # Create input file
        input_file = executor.create_input_file('input.txt', data)

        # Execute tool
        returncode, stdout, stderr = executor.execute(
            'tool-name',
            ['-arg', input_file, '-o', 'output.json'],
            timeout=600
        )

        # Read output
        results = executor.read_output_file('output.json')

        # Process results
        return process_results(results)
```

### API Endpoint Pattern

```python
from fastapi import APIRouter, Depends
from app.utils.auth import get_current_user, require_tenant_access

router = APIRouter(tags=["resource"])

@router.get("/{tenant_id}/resource")
def list_resource(
    tenant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    require_tenant_access(current_user, tenant_id, db)
    # Implementation
    return results
```

### Bulk Upsert Pattern

```python
from sqlalchemy.dialects.postgresql import insert

def bulk_upsert(records: List[dict], db: Session):
    stmt = insert(Model).values(records)
    stmt = stmt.on_conflict_do_update(
        index_elements=['unique_field'],
        set_={'updated_field': stmt.excluded.updated_field}
    )
    db.execute(stmt)
    db.commit()
```

---

## METRICS TO TRACK

### Daily Metrics
- Lines of code added/changed
- Tests written/passing
- Code review time
- Bugs found/fixed

### Weekly Metrics
- Test coverage percentage
- API endpoint count
- Average response time
- Critical issues remaining

### Sprint Metrics
- All success criteria met
- Deployment readiness score
- Technical debt added/removed
- Team velocity

---

## CONTACT & RESOURCES

### Documentation
- Sprint 2 Plan: `/Users/cere/Downloads/easm/SPRINT_2_DETAILED_PLAN.md`
- Sprint 2 TODO: `/Users/cere/Downloads/easm/SPRINT_2_TODO.md`
- Architecture: `/Users/cere/Downloads/easm/docs/architecture/`

### Reference Implementations
- SecureToolExecutor: `app/utils/secure_executor.py`
- Discovery Tasks: `app/tasks/discovery.py`
- Asset Repository: `app/repositories/asset_repository.py`
- Database Models: `app/models/database.py`

### External Resources
- FastAPI Docs: https://fastapi.tiangolo.com
- SQLAlchemy Docs: https://docs.sqlalchemy.org
- Celery Docs: https://docs.celeryproject.org
- ProjectDiscovery Tools: https://github.com/projectdiscovery

---

## DAILY CHECKLIST

### Every Morning
- [ ] Pull latest changes
- [ ] Check CI/CD status
- [ ] Review blockers
- [ ] Plan daily tasks

### Every Evening
- [ ] Commit and push changes
- [ ] Update task status
- [ ] Document blockers
- [ ] Prepare tomorrow's plan

### Every Week
- [ ] Review sprint progress
- [ ] Demo completed features
- [ ] Update documentation
- [ ] Plan next week

---

## DEPLOYMENT READINESS

### Pre-Deployment
- [ ] All tests passing
- [ ] Security audit passed
- [ ] Performance benchmarks met
- [ ] Documentation complete
- [ ] Code review approved

### Deployment
- [ ] Backup production database
- [ ] Run migrations
- [ ] Deploy new version
- [ ] Verify health checks
- [ ] Monitor logs

### Post-Deployment
- [ ] Smoke tests
- [ ] Performance monitoring
- [ ] Error tracking
- [ ] User feedback

---

**Document Version**: 1.0
**Last Updated**: October 23, 2025
**Status**: Ready for Sprint 2

---

*For detailed implementation guidance, see SPRINT_2_DETAILED_PLAN.md*
