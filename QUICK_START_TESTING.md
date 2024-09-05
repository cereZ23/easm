# Quick Start - EASM Testing Guide

Get up and running with the EASM test suite in 5 minutes.

## Installation

```bash
# 1. Navigate to project directory
cd /Users/cere/Downloads/easm

# 2. Install dependencies
pip install -r requirements.txt

# 3. Make test runner executable
chmod +x run_tests.sh
```

## Run Tests

### Option 1: Use Test Runner Script (Recommended)

```bash
# Run all tests with coverage
./run_tests.sh --coverage

# Run unit tests only (fastest)
./run_tests.sh --unit

# Run with HTML coverage report
./run_tests.sh --coverage --report
```

### Option 2: Use pytest Directly

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov-report=term -v

# Specific test file
pytest tests/test_secure_executor.py -v
```

## Test Categories

```bash
# Unit tests (fast, ~10 seconds)
./run_tests.sh --unit

# Integration tests (requires services)
./run_tests.sh --integration

# Security tests
./run_tests.sh --security

# Performance tests
./run_tests.sh --performance
```

## View Results

```bash
# Generate HTML coverage report
./run_tests.sh --coverage --report

# Open coverage report in browser
open htmlcov/index.html
```

## Common Use Cases

### Before Committing

```bash
# Quick unit tests
pytest tests/test_secure_executor.py tests/test_repositories.py -v
```

### Before Push

```bash
# Unit + security tests
./run_tests.sh --unit --security --parallel
```

### Before Release

```bash
# Full test suite with coverage
./run_tests.sh --coverage --report
```

## Troubleshooting

### Tests Fail?

```bash
# Run with verbose output
pytest tests/test_file.py -vv

# Run single test
pytest tests/test_file.py::test_name -v

# Run with debugger
pytest tests/test_file.py --pdb
```

### Need Services?

```bash
# Start PostgreSQL, Redis, MinIO
docker-compose up -d

# Check services
docker-compose ps
```

### Import Errors?

```bash
# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Verify installation
pip list | grep pytest
```

## Test File Reference

| File | Purpose | Test Count |
|------|---------|------------|
| `test_secure_executor.py` | SecureToolExecutor tests | 70+ |
| `test_repositories.py` | Repository tests | 50+ |
| `test_security.py` | Security tests | 60+ |
| `test_performance.py` | Performance tests | 30+ |
| `test_integration_discovery.py` | Integration tests | 25+ |

## Quick Commands

```bash
# Fast unit tests
pytest tests/test_secure_executor.py -v

# All tests with coverage
./run_tests.sh --coverage

# Parallel execution
pytest tests/ -n auto

# Security tests only
pytest tests/test_security.py -v

# Performance benchmarks
pytest tests/test_performance.py --durations=10

# Failed tests only
pytest --lf

# Coverage report
coverage report
```

## Next Steps

1. ✅ Review test results
2. ✅ Check coverage report
3. ✅ Read `tests/README.md` for details
4. ✅ See `CI_CD_TESTING.md` for CI/CD setup
5. ✅ Run tests before committing

## Help

- 📖 Full documentation: `tests/README.md`
- 🔧 CI/CD guide: `CI_CD_TESTING.md`
- 📊 Test summary: `TEST_SUITE_SUMMARY.md`
- 💬 Issues? Check the troubleshooting sections

---

**Ready to test!** Start with: `./run_tests.sh --coverage`
