.PHONY: help build up down restart logs clean test db-migrate db-reset

help:
	@echo "EASM Platform - Available Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make build       - Build Docker images"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo ""
	@echo "Development:"
	@echo "  make logs        - View all logs (follow)"
	@echo "  make logs-api    - View API logs"
	@echo "  make logs-worker - View worker logs"
	@echo "  make logs-beat   - View beat scheduler logs"
	@echo "  make test        - Run tests"
	@echo "  make shell-api   - Enter API container shell"
	@echo "  make shell-worker - Enter worker container shell"
	@echo ""
	@echo "Database:"
	@echo "  make db-migrate  - Run database migrations"
	@echo "  make db-reset    - Reset database (WARNING: deletes all data)"
	@echo "  make db-shell    - Enter PostgreSQL shell"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean       - Stop and remove all containers, volumes"

build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Waiting for services to start..."
	@sleep 5
	@echo "Services started!"
	@echo "API: http://localhost:8000"
	@echo "MinIO Console: http://localhost:9001"

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

logs-worker:
	docker-compose logs -f worker

logs-beat:
	docker-compose logs -f beat

test:
	docker-compose exec worker pytest -v

test-cov:
	docker-compose exec worker pytest --cov=app --cov-report=html tests/

shell-api:
	docker-compose exec api bash

shell-worker:
	docker-compose exec worker bash

db-migrate:
	docker-compose exec api alembic upgrade head

db-reset:
	@echo "WARNING: This will delete all data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v; \
		docker-compose up -d; \
	fi

db-shell:
	docker-compose exec postgres psql -U easm -d easm

clean:
	docker-compose down -v
	docker system prune -f

status:
	docker-compose ps
