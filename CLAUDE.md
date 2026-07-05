# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A multi-tenant **External Attack Surface Management (EASM)** platform that orchestrates ProjectDiscovery tools (subfinder, amass, dnsx, httpx, naabu, tlsx, katana, nuclei, uncover) for continuous security reconnaissance. Backend is FastAPI + Celery + PostgreSQL + Redis + MinIO; frontend is Vue 3.

Surviving reference docs (the historical sprint/report/status markdown was removed): `README.md`, `CLAUDE.md`, `API_DOCUMENTATION.md`, `TENANT_ISOLATION_ARCHITECTURE.md`, `SECURITY_QUICK_REFERENCE.md`, `easm.md` (original design, Italian). Trust the code over any doc.

## Commands

Everything runs through Docker Compose (`make help` lists targets):

```bash
make up              # Start all services (postgres, redis, minio, api, worker, beat, ui)
make down            # Stop
make logs-worker     # Follow worker logs (also logs-api, logs-beat)
make db-migrate      # alembic upgrade head (inside api container)
make db-shell        # psql into the DB
make shell-worker    # bash into worker container
make test            # pytest -v inside the worker container
```

Tests run **inside the worker container** (they need postgres/redis/minio):

```bash
docker-compose exec worker pytest                              # all
docker-compose exec worker pytest tests/test_discovery.py      # one file
docker-compose exec worker pytest tests/test_discovery.py::TestClass::test_name  # one test
docker-compose exec worker pytest -m integration               # by marker
docker-compose exec worker pytest --cov=app tests/             # coverage
```

Markers (see `pytest.ini`): `integration`, `security`, `performance`, `slow`, `benchmark`. `run_tests.sh` wraps categories/coverage/parallel with colored output.

Database migrations:

```bash
docker-compose exec api alembic revision --autogenerate -m "description"
docker-compose exec api alembic upgrade head
docker-compose exec api alembic downgrade -1
```

Frontend (`frontend/`): `npm run dev` (Vite), `npm run build` (`vue-tsc && vite build`), `npm run lint` (eslint --fix).

Python style: `black` and `isort` with line-length **120** (config in `pyproject.toml`).

### Non-standard host ports

Host port mappings are deliberately offset to avoid collisions — do not assume defaults:

| Service | Host port |
|---------|-----------|
| API | 18000 |
| Frontend (UI) | 13000 |
| PostgreSQL | 15432 |
| Redis | 16379 |
| MinIO API / Console | 9000 / 9001 |

`app/config.py` defaults (`postgres_port=15432`, `redis_port=16379`, `minio_endpoint=localhost:19000`) target these when running code outside Docker. Inside the compose network, services use standard internal ports (5432/6379/9000) via env overrides in `docker-compose.yml`.

## Architecture

### Two-process backend, one codebase

The same `app/` package runs as three roles:
- **api** (`app/main.py`) — FastAPI REST API, JWT auth, all read/write endpoints.
- **worker** (`app/celery_app.py`) — Celery worker executing the scanning tasks.
- **beat** — Celery Beat scheduler (daily full discovery at 02:00 UTC; critical-asset watch every 30 min).

Celery config, Beat schedule, and task signal handlers all live in `app/celery_app.py`. Tasks are registered via the `include=[...]` list there — **a new task module must be added to that list** or its tasks won't be discovered.

### The scanning pipeline (the core of the product)

Data flows through three Celery task stages, each writing assets/findings to Postgres and raw tool output to MinIO:

```
Seeds (domains/ASNs/keywords)
  → discovery   (app/tasks/discovery.py):  uncover → subfinder + amass (parallel) → merge/dedup → dnsx
  → enrichment  (app/tasks/enrichment.py): httpx (tech fingerprint) → naabu (ports) → tlsx (certs) → katana (crawl → populates Endpoints)
  → scanning    (app/tasks/scanning.py):   katana crawl (feeds URLs) → nuclei (CVE detection) → risk scoring
```

Enrichment auto-triggers after discovery (`enrichment_auto_trigger`), and is **tiered by asset priority** (`critical`/`high`/`normal`/`low` on `Asset.priority`).

### Every external tool goes through SecureToolExecutor

`app/utils/secure_executor.py` (`SecureToolExecutor`) is the **only** sanctioned way to shell out to recon tools. It enforces an allowlist (`settings.tool_allowed_tools`), no-shell argv execution (guards against command injection), per-tool timeouts, and resource limits (CPU/memory/file-size via `resource`). It is constructed per-tenant (`SecureToolExecutor(tenant_id)`). Never call `subprocess` directly for a scanner — extend the allowlist and use this wrapper.

### Adding a new scanner

The shape is: add the binary to `tool_allowed_tools` in `app/config.py` → write a `@celery.task` in the appropriate `app/tasks/*.py` that calls `SecureToolExecutor` → parse results into repository writes → store raw output in MinIO → wire config timeouts/limits in `config.py` → add tests. Model it on the existing tasks in `app/tasks/enrichment.py` (e.g. `run_httpx`, `run_naabu`).

### Multi-tenancy is enforced everywhere

Tenant isolation is a hard invariant, not a convenience:
- **DB**: every domain table carries `tenant_id`; all queries filter by it. Models in `app/models/database.py` (Tenant, Asset, Service, Finding, Event, Seed, Suppression) and `app/models/enrichment.py` (Certificate, Endpoint).
- **Storage**: separate MinIO buckets per tenant (`tenant-1`, `tenant-2`, …).
- **Auth**: users belong to tenants via `TenantMembership` (`app/models/auth.py`); superusers cross tenants. See `TENANT_ISOLATION_ARCHITECTURE.md` if you touch this boundary.
- **Executor**: constructed per-tenant for resource attribution.

When adding endpoints or queries, scope by `tenant_id` and derive it from the authenticated user — never trust a client-supplied tenant id.

### Backend layering

```
app/
  main.py                 FastAPI app: middleware, CORS, gzip, rate limiting (slowapi), routers
  config.py               Pydantic Settings — single source of config; validates prod secrets
  celery_app.py           Celery app + Beat schedule + task include list
  database.py             SQLAlchemy engine/session
  api/
    routers/              REST endpoints (auth, tenants, assets, services, certificates,
                          endpoints, findings, onboarding, scanning)
    schemas/              Pydantic request/response models
    dependencies.py       DI: current user, tenant scoping, DB session
    middleware.py, errors.py, validators.py
  models/                 SQLAlchemy ORM (database.py, enrichment.py, auth.py)
  repositories/           Data-access layer (asset/service/certificate/endpoint/finding)
  services/               Business logic: risk_scoring.py, scanning/ (nuclei_service,
                          template_manager, suppression_service)
  tasks/                  Celery tasks: discovery, enrichment, scanning, alerting
  core/                   security.py, audit.py, rate_limiter.py
  security/jwt_auth.py    JWT (RS256 preferred, HS256 dev fallback)
  utils/                  secure_executor, storage (MinIO), secrets (encryption),
                          validators, logger
```

Routers → repositories/services → models. Business logic lives in `services/` and `repositories/`, not in routers or tasks.

### Config & secrets

All configuration is centralized in `app/config.py` via Pydantic `Settings` (env vars, `.env` fallback; copy from `.env.example`). When `environment=production`, a `model_validator` **hard-fails startup** if secrets are weak/default (SECRET_KEY, JWT_SECRET_KEY, POSTGRES_PASSWORD, MinIO creds, wildcard CORS, missing Redis password). Set `ENVIRONMENT=development` to bypass locally. Generate secrets with `scripts/generate_secrets.py`. JWT defaults to RS256 (needs key paths); falls back to HS256 for dev.

### Frontend

Vue 3 + TypeScript + Vite in `frontend/`. Pinia stores (`src/stores/`: auth, tenant, theme), TanStack Query for server state, Axios client (`src/api/client.ts`) with typed API modules per resource, Vue Router, Tailwind, Chart.js. Views under `src/views/` mirror backend resources. `VITE_API_BASE_URL` points at the API (`http://localhost:18000` in compose).

### Alembic migrations

Numbered sequentially in `alembic/versions/` (`001_initial_schema` → `005_enrichment_performance_indexes`). Migration 004 (enrichment models) has manual SQL and a documented rollback (`manual_migration_004.sql`, `ROLLBACK_PROCEDURE_004.md`) — respect that when altering enrichment tables.

## Conventions

- Keep tenant scoping in every new query and endpoint; derive tenant from the authenticated principal.
- Route all external-tool execution through `SecureToolExecutor`; add new binaries to `tool_allowed_tools`.
- Register new Celery task modules in the `include` list in `app/celery_app.py`.
- Add per-tool timeouts/rate-limits/config to `app/config.py` rather than hardcoding in tasks.
- Store raw tool output in MinIO (via `app/utils/storage.py`) and structured results in the DB.
