# EASM Platform Test Suite

Comprehensive test suite for the External Attack Surface Management (EASM) platform Sprint 1.5 implementation.

## Overview

This test suite provides extensive coverage of the EASM platform with:
- **80%+ code coverage** on critical modules
- **Unit tests** for all core components
- **Integration tests** for complete workflows
- **Security tests** for vulnerability prevention
- **Performance tests** for scalability verification

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures and configuration
├── test_secure_executor.py          # SecureToolExecutor unit tests
├── test_repositories.py             # Repository layer unit tests
├── test_models.py                   # Database model tests
├── test_discovery.py                # Discovery task tests
├── test_integration_discovery.py    # Full pipeline integration tests
├── test_security.py                 # Security vulnerability tests
├── test_performance.py              # Performance and scalability tests
└── README.md                        # This file
```

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install -r requirements.txt
```

Ensure services are running (for integration tests):
```bash
docker-compose up -d postgres redis minio
```

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test Categories

**Unit Tests Only:**
```bash
pytest tests/test_secure_executor.py tests/test_repositories.py tests/test_models.py -v
```

**Integration Tests:**
```bash
pytest tests/test_integration_discovery.py -v
```

**Security Tests:**
```bash
pytest tests/test_security.py -v
```

**Performance Tests:**
```bash
pytest tests/test_performance.py -v --durations=10
```

### Run Tests with Coverage

```bash
pytest tests/ --cov=app --cov-report=html --cov-report=term
```

View coverage report:
```bash
open htmlcov/index.html
```

### Run Tests in Parallel

```bash
pytest tests/ -n auto
```

### Run Specific Tests

```bash
# Run single test file
pytest tests/test_secure_executor.py -v

# Run single test class
pytest tests/test_secure_executor.py::TestSecureToolExecutorValidation -v

# Run single test function
pytest tests/test_secure_executor.py::TestSecureToolExecutorValidation::test_validate_allowed_tool -v
```

## Test Categories

### 1. Unit Tests

**test_secure_executor.py** - 70+ tests
- Tool validation and whitelisting
- Argument sanitization
- Resource limit enforcement
- File operations
- Context manager behavior
- Security controls

**test_repositories.py** - 50+ tests
- AssetRepository CRUD operations
- EventRepository operations
- Bulk operations and performance
- Multi-tenant isolation
- Error handling

**test_models.py** - Basic model tests
- Model creation and validation
- Enum value verification
- Relationship testing

### 2. Integration Tests

**test_integration_discovery.py** - 25+ tests
- Complete discovery pipeline
- Database operations with real DB
- Task chaining
- Multi-tenant isolation
- Error recovery
- Batch processing

### 3. Security Tests

**test_security.py** - 60+ tests
- **Command Injection Prevention**
  - Shell metacharacter escaping
  - Tool name validation
  - Environment variable injection blocking

- **SQL Injection Prevention**
  - Parameterized query verification
  - Metadata field safety
  - Bulk operation security

- **Path Traversal Prevention**
  - Filename validation
  - Symlink attack prevention
  - Absolute path restrictions

- **Multi-tenant Isolation**
  - Cross-tenant access prevention
  - Tenant ID tampering protection
  - File system isolation

- **Resource Limits**
  - CPU limit enforcement
  - Memory limit enforcement
  - Timeout enforcement

- **Input Validation**
  - Unicode attack handling
  - Control character filtering
  - XSS prevention in metadata

### 4. Performance Tests

**test_performance.py** - 30+ tests
- Batch processing efficiency
  - 100, 1000, 5000 record batches
  - Bulk vs individual inserts

- Database query performance
  - Index effectiveness
  - Pagination performance
  - Complex query optimization

- Memory usage monitoring
  - Bulk operation memory
  - Query memory usage
  - Memory leak detection

- Concurrent operations
  - Parallel reads
  - Mixed read/write workloads

- Scalability metrics
  - Linear scaling verification
  - Growing dataset performance

## Test Fixtures

The `conftest.py` file provides extensive fixtures for testing:

### Database Fixtures
- `db_engine` - In-memory SQLite engine
- `db_session` - Database session
- `test_db` - Alias for backward compatibility

### Entity Fixtures
- `tenant` - Test tenant
- `tenant_with_api_keys` - Tenant with API keys
- `multiple_tenants` - Multiple tenants for isolation testing
- `sample_asset` - Single asset
- `multiple_assets` - Multiple assets
- `critical_assets` - High-risk assets
- `sample_seeds` - Seed collection
- `sample_events` - Event collection
- `sample_service` - Service instance
- `sample_finding` - Vulnerability finding

### Mock Fixtures
- `mock_subprocess` - Mock subprocess.run
- `mock_minio` - Mock MinIO client
- `mock_celery` - Mock Celery tasks
- `mock_secure_executor` - Mock SecureToolExecutor

### Factory Fixtures
- `asset_factory` - Create asset data
- `discovery_result_factory` - Create discovery results
- `seed_data_factory` - Create seed data

### Utility Fixtures
- `temp_file` - Temporary file with cleanup
- `temp_dir` - Temporary directory with cleanup
- `test_env` - Test environment variables
- `freeze_time` - Freeze time for consistent tests
- `performance_timer` - Performance timing helper

## Coverage Goals

| Module | Target Coverage | Current Status |
|--------|----------------|----------------|
| secure_executor.py | 90%+ | Comprehensive |
| asset_repository.py | 85%+ | Comprehensive |
| discovery.py | 80%+ | Good |
| database.py | 95%+ | Excellent |

## Performance Benchmarks

Expected performance (on standard hardware):

| Operation | Records | Target Time |
|-----------|---------|-------------|
| Bulk upsert | 100 | < 1s |
| Bulk upsert | 1,000 | < 5s |
| Bulk upsert | 5,000 | < 20s |
| Query by ID | N/A | < 0.1s |
| Batch events | 1,000 | < 2s |
| Full pipeline | 1,000 assets | < 10s |

## CI/CD Integration

### GitHub Actions

The test suite runs automatically on:
- Push to main/develop branches
- Pull requests
- Manual workflow dispatch

Workflow includes:
1. **Unit Tests** - All unit tests with coverage
2. **Integration Tests** - Full pipeline tests
3. **Security Tests** - Vulnerability scans
4. **Performance Tests** - Benchmark verification
5. **Code Quality** - Linting and type checking
6. **Security Scanning** - Bandit and Safety checks

### Test Environments

Tests run against:
- Python 3.10, 3.11, 3.12
- PostgreSQL 15
- Redis 7
- MinIO latest

### Coverage Reports

Coverage reports are:
- Generated for each PR
- Uploaded to Codecov
- Available as artifacts
- Tracked over time

## Writing New Tests

### Test Structure

Follow this pattern:

```python
class TestFeatureName:
    """Test description"""

    def test_specific_behavior(self, fixture):
        """Test a specific behavior"""
        # Arrange
        data = setup_test_data()

        # Act
        result = function_under_test(data)

        # Assert
        assert result == expected_value
```

### Naming Conventions

- Test files: `test_<module>.py`
- Test classes: `TestFeatureName`
- Test functions: `test_specific_behavior`

### Using Fixtures

```python
def test_with_fixtures(db_session, tenant, sample_asset):
    """Use fixtures for setup"""
    repo = AssetRepository(db_session)
    asset = repo.get_by_id(sample_asset.id)
    assert asset is not None
```

### Mocking External Dependencies

```python
@patch('subprocess.run')
def test_with_mock(mock_run):
    """Mock external dependencies"""
    mock_run.return_value = MagicMock(returncode=0)
    result = function_that_calls_subprocess()
    assert result is not None
```

### Performance Tests

```python
def test_performance(performance_timer):
    """Test performance requirements"""
    performance_timer.start()

    # Perform operation
    result = expensive_operation()

    elapsed = performance_timer.stop()
    performance_timer.assert_faster_than(1.0, "Operation took too long")
```

## Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.integration
def test_integration_feature():
    """Integration test"""
    pass

@pytest.mark.security
def test_security_feature():
    """Security test"""
    pass

@pytest.mark.performance
def test_performance_feature():
    """Performance test"""
    pass

@pytest.mark.slow
def test_slow_feature():
    """Slow running test"""
    pass
```

Run specific markers:
```bash
pytest -m integration
pytest -m security
pytest -m "not slow"
```

## Debugging Tests

### Run with verbose output
```bash
pytest tests/test_file.py -vv
```

### Run with print statements
```bash
pytest tests/test_file.py -s
```

### Run with debugger
```bash
pytest tests/test_file.py --pdb
```

### Run failed tests only
```bash
pytest --lf
```

### Run with detailed trace
```bash
pytest tests/test_file.py -vv --tb=long
```

## Continuous Testing

### Watch mode (with pytest-watch)
```bash
pip install pytest-watch
ptw tests/
```

### Pre-commit hook

Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
pytest tests/ --cov=app --cov-fail-under=80
```

## Troubleshooting

### Tests fail to connect to database

Ensure PostgreSQL is running:
```bash
docker-compose up -d postgres
export DATABASE_URL=postgresql://easm:easm_password@localhost:5432/easm_test
```

### MinIO connection errors

Ensure MinIO is running:
```bash
docker-compose up -d minio
export MINIO_ENDPOINT=localhost:9000
```

### Import errors

Ensure you're in the project root and have installed dependencies:
```bash
pip install -r requirements.txt
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Slow tests

Run only fast tests:
```bash
pytest -m "not slow"
```

Or run in parallel:
```bash
pytest -n auto
```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Use Fixtures**: Leverage conftest.py fixtures
3. **Mock External Calls**: Don't make real API calls in tests
4. **Test Edge Cases**: Include boundary conditions
5. **Clear Assertions**: Use descriptive assertion messages
6. **Performance Awareness**: Keep tests fast
7. **Coverage Goals**: Aim for 80%+ coverage on critical paths
8. **Security Testing**: Always test security controls
9. **Documentation**: Document complex test scenarios
10. **Regular Updates**: Keep tests in sync with code changes

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [unittest.mock Guide](https://docs.python.org/3/library/unittest.mock.html)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/20/core/testing.html)

## Support

For questions or issues with tests:
1. Check this README
2. Review test examples in the test files
3. Check CI/CD logs for failures
4. Consult the team on test strategy

## Metrics

Current test suite metrics:
- **Total Tests**: 235+
- **Test Files**: 8
- **Code Coverage**: 80%+ on critical paths
- **Average Runtime**: ~30 seconds (unit tests)
- **Parallel Runtime**: ~10 seconds (with pytest-xdist)
