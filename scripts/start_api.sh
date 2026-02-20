#!/bin/bash

###############################################################################
# EASM Platform API Startup Script
#
# This script starts the FastAPI server with proper configuration for
# development or production environments.
#
# Usage:
#   ./scripts/start_api.sh [development|production]
#
# Examples:
#   ./scripts/start_api.sh              # Start in development mode
#   ./scripts/start_api.sh production   # Start in production mode
###############################################################################

set -e  # Exit on error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default to development mode
MODE="${1:-development}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}EASM Platform API Startup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Determine project root (parent of scripts directory)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo -e "${GREEN}Project root:${NC} $PROJECT_ROOT"
echo -e "${GREEN}Mode:${NC} $MODE"
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo -e "  Python version: $PYTHON_VERSION"

REQUIRED_VERSION="3.11"
if ! python -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
    echo -e "${RED}Error: Python 3.11+ required${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓ Python version OK${NC}"
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}Warning: Virtual environment not activated${NC}"

    # Check if venv exists
    if [ -d "$PROJECT_ROOT/venv" ]; then
        echo -e "Activating virtual environment..."
        source "$PROJECT_ROOT/venv/bin/activate"
        echo -e "  ${GREEN}✓ Virtual environment activated${NC}"
    else
        echo -e "${RED}Error: Virtual environment not found at $PROJECT_ROOT/venv${NC}"
        echo -e "Run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Virtual environment active:${NC} $VIRTUAL_ENV"
fi
echo ""

# Check if .env file exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo -e "Creating .env from .env.example..."

    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
        echo -e "  ${GREEN}✓ Created .env file${NC}"
        echo -e "  ${YELLOW}Please review and update .env with your configuration${NC}"
    else
        echo -e "${RED}Error: .env.example not found${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ .env file found${NC}"
fi
echo ""

# Check database connection
echo -e "${YELLOW}Checking database connection...${NC}"
if python -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from app.config import settings
from sqlalchemy import create_engine, text
try:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    print('  ✓ Database connection OK')
    sys.exit(0)
except Exception as e:
    print(f'  ✗ Database connection failed: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1; then
    echo -e "  ${GREEN}✓ Database connection OK${NC}"
else
    echo -e "${RED}Error: Cannot connect to database${NC}"
    echo -e "Make sure PostgreSQL is running and credentials are correct in .env"
    echo -e ""
    echo -e "To start PostgreSQL with Docker:"
    echo -e "  docker-compose up -d postgres"
    exit 1
fi
echo ""

# Check Redis connection
echo -e "${YELLOW}Checking Redis connection...${NC}"
if python -c "
import sys
sys.path.insert(0, '$PROJECT_ROOT')
from app.config import settings
import redis
try:
    r = redis.from_url(settings.redis_url, socket_connect_timeout=2)
    r.ping()
    r.close()
    print('  ✓ Redis connection OK')
    sys.exit(0)
except Exception as e:
    print(f'  ✗ Redis connection failed: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1; then
    echo -e "  ${GREEN}✓ Redis connection OK${NC}"
else
    echo -e "${RED}Error: Cannot connect to Redis${NC}"
    echo -e "Make sure Redis is running and credentials are correct in .env"
    echo -e ""
    echo -e "To start Redis with Docker:"
    echo -e "  docker-compose up -d redis"
    exit 1
fi
echo ""

# Run migrations
echo -e "${YELLOW}Running database migrations...${NC}"
if alembic upgrade head; then
    echo -e "  ${GREEN}✓ Migrations complete${NC}"
else
    echo -e "${RED}Error: Migration failed${NC}"
    exit 1
fi
echo ""

# Configure based on mode
if [ "$MODE" = "production" ]; then
    echo -e "${BLUE}Starting API in PRODUCTION mode${NC}"
    echo ""

    # Production configuration
    HOST="${API_HOST:-0.0.0.0}"
    PORT="${API_PORT:-8000}"
    WORKERS="${API_WORKERS:-4}"

    echo -e "Configuration:"
    echo -e "  Host: $HOST"
    echo -e "  Port: $PORT"
    echo -e "  Workers: $WORKERS"
    echo ""

    # Set production environment
    export ENVIRONMENT=production

    echo -e "${GREEN}Starting server...${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # Start with multiple workers (no reload)
    exec uvicorn app.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers "$WORKERS" \
        --log-level info \
        --access-log \
        --no-use-colors
else
    echo -e "${BLUE}Starting API in DEVELOPMENT mode${NC}"
    echo ""

    # Development configuration
    HOST="${API_HOST:-0.0.0.0}"
    PORT="${API_PORT:-8000}"

    echo -e "Configuration:"
    echo -e "  Host: $HOST"
    echo -e "  Port: $PORT"
    echo -e "  Auto-reload: ${GREEN}Enabled${NC}"
    echo ""

    # Set development environment
    export ENVIRONMENT=development
    export DEBUG=true

    echo -e "${GREEN}Starting server with auto-reload...${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e ""
    echo -e "${GREEN}API Documentation:${NC} http://${HOST}:${PORT}/api/docs"
    echo -e "${GREEN}ReDoc:${NC} http://${HOST}:${PORT}/api/redoc"
    echo -e "${GREEN}Health Check:${NC} http://${HOST}:${PORT}/health"
    echo -e ""
    echo -e "${YELLOW}Press CTRL+C to stop${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # Start with single worker and reload
    exec uvicorn app.main:app \
        --reload \
        --host "$HOST" \
        --port "$PORT" \
        --log-level debug
fi
