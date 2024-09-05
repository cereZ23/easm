# CI/CD Integration and Testing Guide

Complete guide for continuous integration, continuous deployment, and automated testing for the EASM platform.

## Table of Contents

1. [Overview](#overview)
2. [GitHub Actions Setup](#github-actions-setup)
3. [Local Testing](#local-testing)
4. [Docker Testing Environment](#docker-testing-environment)
5. [Coverage Requirements](#coverage-requirements)
6. [Test Execution Strategy](#test-execution-strategy)
7. [Security Scanning](#security-scanning)
8. [Performance Monitoring](#performance-monitoring)
9. [Troubleshooting](#troubleshooting)

## Overview

The EASM platform uses a comprehensive testing strategy with multiple layers:

- **Unit Tests**: Fast, isolated tests for individual components
- **Integration Tests**: Tests for complete workflows with real dependencies
- **Security Tests**: Vulnerability and attack prevention verification
- **Performance Tests**: Scalability and efficiency benchmarks
- **Code Quality**: Linting, formatting, and type checking

## GitHub Actions Setup

### Workflow Configuration

The test suite runs automatically via GitHub Actions (`.github/workflows/tests.yml`):

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Manual workflow dispatch

**Test Matrix:**
- Python versions: 3.10, 3.11, 3.12
- Services: PostgreSQL 15, Redis 7, MinIO latest

**Stages:**
1. Unit tests with coverage
2. Integration tests
3. Security tests
4. Performance tests
5. Code quality checks
6. Security scanning

### Setting Up Repository Secrets

Required secrets for CI/CD:

```bash
# GitHub Repository Settings > Secrets and Variables > Actions

CODECOV_TOKEN          # For coverage reporting
DATABASE_URL           # Test database connection
DOCKER_USERNAME        # For Docker registry (optional)
DOCKER_PASSWORD        # For Docker registry (optional)
```

### Branch Protection Rules

Recommended settings:

```yaml
Branch: main
✓ Require status checks to pass
  ✓ test (3.10)
  ✓ test (3.11)
  ✓ test (3.12)
  ✓ security-scan
  ✓ lint
✓ Require code review (1)
✓ Include administrators
```

## Local Testing

### Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
./run_tests.sh --coverage

# Run specific category
./run_tests.sh --unit
./run_tests.sh --security
./run_tests.sh --performance
```

### Test Runner Options

```bash
# Run with coverage and HTML report
./run_tests.sh --coverage --report

# Run in parallel for speed
./run_tests.sh --parallel

# Run with verbose output
./run_tests.sh --verbose

# Combine options
./run_tests.sh --unit --parallel --coverage
```

### Manual pytest Commands

```bash
# All tests with coverage
pytest tests/ --cov=app --cov-report=html --cov-report=term -v

# Unit tests only
pytest tests/test_secure_executor.py tests/test_repositories.py -v

# Integration tests
pytest tests/test_integration_discovery.py -v

# Security tests
pytest tests/test_security.py -v

# Performance tests with timing
pytest tests/test_performance.py -v --durations=10

# Run in parallel
pytest tests/ -n auto

# Run with specific markers
pytest -m "not slow" -v
pytest -m security -v
pytest -m integration -v
```

## Docker Testing Environment

### Using Docker Compose

Start test services:

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f minio

# Stop services
docker-compose down
```

### Docker Compose Configuration

Create `docker-compose.test.yml`:

```yaml
version: '3.8'

services:
  postgres-test:
    image: postgres:15
    environment:
      POSTGRES_USER: easm
      POSTGRES_PASSWORD: easm_password
      POSTGRES_DB: easm_test
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U easm"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis-test:
    image: redis:7-alpine
    ports:
      - "6380:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  minio-test:
    image: minio/minio:latest
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin123
    ports:
      - "9001:9000"
    command: server /data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### Running Tests in Docker

```bash
# Run tests in Docker container
docker-compose -f docker-compose.test.yml run --rm test pytest tests/ -v

# With coverage
docker-compose -f docker-compose.test.yml run --rm test pytest tests/ --cov=app

# Specific test suite
docker-compose -f docker-compose.test.yml run --rm test pytest tests/test_security.py -v
```

## Coverage Requirements

### Target Coverage Levels

| Module | Target | Priority |
|--------|--------|----------|
| secure_executor.py | 90%+ | Critical |
| asset_repository.py | 85%+ | Critical |
| discovery.py | 80%+ | High |
| database.py | 95%+ | High |
| Overall | 80%+ | Required |

### Checking Coverage

```bash
# Generate coverage report
pytest tests/ --cov=app --cov-report=term --cov-report=html

# View HTML report
open htmlcov/index.html

# Check specific module
pytest tests/ --cov=app.utils.secure_executor --cov-report=term

# Fail if coverage below threshold
pytest tests/ --cov=app --cov-fail-under=80
```

### Coverage Configuration

In `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["app"]
branch = true

[tool.coverage.report]
precision = 2
show_missing = true
fail_under = 80
```

### Viewing Coverage Gaps

```bash
# Show missing lines
coverage report -m

# Show branch coverage
coverage report --show-missing

# Generate detailed report
coverage html
```

## Test Execution Strategy

### Pre-commit Testing

Run before every commit:

```bash
# Fast unit tests only
pytest tests/test_secure_executor.py tests/test_repositories.py -v

# Should complete in < 10 seconds
```

### Pre-push Testing

Run before pushing:

```bash
# All unit tests + security tests
./run_tests.sh --unit --security --parallel

# Should complete in < 30 seconds
```

### Pull Request Testing

Full test suite runs automatically:

```bash
# Complete test suite
./run_tests.sh --coverage --report

# Includes:
# - Unit tests
# - Integration tests
# - Security tests
# - Performance tests
# - Code quality checks
```

### Release Testing

Before release:

```bash
# Full test suite with benchmarks
pytest tests/ --cov=app --cov-report=html -v --durations=20

# Manual verification:
# - Integration tests with real services
# - Security scan results review
# - Performance benchmark comparison
```

## Security Scanning

### Bandit (Python Security Linter)

```bash
# Install
pip install bandit

# Run scan
bandit -r app/ -f json -o bandit-report.json

# Review high-severity issues
bandit -r app/ -ll

# Exclude false positives
bandit -r app/ -x tests/
```

### Safety (Dependency Vulnerability Scan)

```bash
# Install
pip install safety

# Check dependencies
safety check

# Check with detailed output
safety check --full-report

# Check specific file
safety check -r requirements.txt
```

### OWASP Dependency Check

```bash
# Using Docker
docker run --rm -v $(pwd):/src owasp/dependency-check \
  --scan /src --format HTML --project EASM

# Review report
open dependency-check-report.html
```

### Custom Security Tests

Run comprehensive security test suite:

```bash
# All security tests
pytest tests/test_security.py -v

# Specific security categories
pytest tests/test_security.py::TestCommandInjectionPrevention -v
pytest tests/test_security.py::TestSQLInjectionPrevention -v
pytest tests/test_security.py::TestMultiTenantIsolationSecurity -v
```

## Performance Monitoring

### Benchmark Tests

```bash
# Run performance tests
pytest tests/test_performance.py -v --durations=10

# With benchmarking
pytest tests/test_performance.py -v --benchmark-only

# Save benchmark results
pytest tests/test_performance.py --benchmark-save=baseline

# Compare with baseline
pytest tests/test_performance.py --benchmark-compare=baseline
```

### Performance Metrics

Track these metrics:

```python
# Bulk operations
- 100 records: < 1s
- 1000 records: < 5s
- 5000 records: < 20s

# Query performance
- By ID: < 0.1s
- By tenant: < 0.5s
- Critical assets: < 0.5s

# Memory usage
- Bulk upsert (5000): < 100MB increase
- Query large dataset: < 50MB increase
```

### Profiling

```bash
# Install profiling tools
pip install pytest-profiling memory_profiler

# Run with profiling
pytest tests/test_performance.py --profile

# Memory profiling
mprof run pytest tests/test_performance.py
mprof plot

# Line profiling
kernprof -l tests/test_performance.py
python -m line_profiler tests/test_performance.py.lprof
```

## Code Quality Checks

### Linting with flake8

```bash
# Install
pip install flake8

# Run linting
flake8 app/ tests/

# With specific rules
flake8 app/ --max-line-length=120 --ignore=E501,W503

# Generate report
flake8 app/ --format=html --htmldir=flake-report
```

### Formatting with Black

```bash
# Install
pip install black

# Check formatting
black --check app/ tests/

# Auto-format
black app/ tests/

# With specific line length
black --line-length=120 app/
```

### Import Sorting with isort

```bash
# Install
pip install isort

# Check imports
isort --check-only app/ tests/

# Auto-sort
isort app/ tests/

# With profile
isort --profile=black app/
```

### Type Checking with mypy

```bash
# Install
pip install mypy

# Run type checking
mypy app/

# With strict mode
mypy --strict app/

# Generate report
mypy app/ --html-report mypy-report
```

### Pre-commit Hooks

Install pre-commit hooks:

```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
EOF

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection
psql -h localhost -U easm -d easm_test

# Reset database
docker-compose down -v
docker-compose up -d postgres
```

#### 2. MinIO Connection Errors

```bash
# Check MinIO is running
curl http://localhost:9000/minio/health/live

# Check credentials
docker-compose logs minio

# Reset MinIO
docker-compose restart minio
```

#### 3. Test Failures

```bash
# Run with verbose output
pytest tests/test_file.py -vv

# Run with print statements
pytest tests/test_file.py -s

# Run with debugger
pytest tests/test_file.py --pdb

# Run only failed tests
pytest --lf
```

#### 4. Coverage Issues

```bash
# Clear coverage cache
coverage erase

# Re-run with coverage
pytest tests/ --cov=app --cov-report=term

# Check for missing __init__.py files
find app -type d ! -path "*/.*" -exec test -f {}/__init__.py \; -print
```

#### 5. Performance Test Failures

```bash
# Run without parallel execution
pytest tests/test_performance.py -v

# Check system resources
htop

# Increase timeouts temporarily
pytest tests/test_performance.py -v --timeout=300
```

### Debugging Tips

```bash
# Show test output
pytest -s

# Show locals on failure
pytest -l

# Full traceback
pytest --tb=long

# Stop on first failure
pytest -x

# Run specific test
pytest tests/test_file.py::test_function -v

# Show fixture setup
pytest --setup-show
```

### CI/CD Troubleshooting

1. **GitHub Actions Failures**
   - Check workflow logs
   - Verify service health checks
   - Check environment variables
   - Review dependency versions

2. **Timeout Issues**
   - Increase job timeout
   - Run tests in parallel
   - Cache dependencies
   - Use faster runners

3. **Flaky Tests**
   - Identify with `pytest --flake-finder`
   - Add retries with `pytest-rerunfailures`
   - Fix timing issues
   - Improve test isolation

## Best Practices

1. **Run tests frequently**: Commit often, test often
2. **Keep tests fast**: Unit tests < 10s, full suite < 5min
3. **Maintain coverage**: Target 80%+ on critical paths
4. **Review security scans**: Check before merging
5. **Monitor performance**: Track metrics over time
6. **Update dependencies**: Regular security updates
7. **Document failures**: Note recurring issues
8. **Isolate tests**: Each test independent
9. **Use fixtures**: Leverage conftest.py
10. **Review reports**: Check coverage and quality regularly

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

## Support

For CI/CD and testing issues:
1. Check this guide
2. Review GitHub Actions logs
3. Check service status
4. Consult the development team
