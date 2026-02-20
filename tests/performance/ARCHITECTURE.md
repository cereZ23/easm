# Performance Testing Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                  EASM Performance Test Suite                     │
│                     (Sprint 2 Deliverable)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ pytest-benchmark
                              ▼
    ┌─────────────────────────────────────────────────────────────┐
    │              Test Categories (26 tests)                      │
    └─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│Tool Execution│      │   Database   │      │  Concurrent  │
│  (8 tests)   │      │  (6 tests)   │      │  (6 tests)   │
└──────────────┘      └──────────────┘      └──────────────┘
        │                     │                     │
        │                     │                     │
        └─────────────────────┴─────────────────────┘
                              │
                              ▼
                      ┌──────────────┐
                      │Stress Testing│
                      │  (6 tests)   │
                      └──────────────┘
```

## Test Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Test Execution Flow                       │
└─────────────────────────────────────────────────────────────────┘

1. Setup Phase
   ├── Start Docker (PostgreSQL + Redis)
   ├── Create test database (easm_perf_test)
   ├── Initialize test tenant
   └── Generate test data (URLs, assets)

2. Benchmark Phase
   ├── Warmup (3 rounds)
   ├── Main execution (5+ rounds)
   ├── Statistics collection
   └── Resource monitoring

3. Analysis Phase
   ├── Calculate metrics (mean, median, p95)
   ├── Compare to baselines
   ├── Detect regressions
   └── Generate recommendations

4. Reporting Phase
   ├── JSON benchmark results
   ├── SVG histograms
   ├── Performance report (markdown)
   └── Test logs

5. Cleanup Phase
   ├── Drop test database
   ├── Close connections
   └── Archive results
```

## Component Architecture

### 1. Tool Execution Performance

```
TestToolExecutionPerformance
├── test_httpx_performance_small (10 URLs)
│   ├── Setup: Mock executor with realistic delays
│   ├── Execute: HTTPx with JSON output
│   ├── Measure: Execution time + throughput
│   └── Assert: < 1s mean, < 0.2s stddev
│
├── test_httpx_performance_medium (50 URLs)
│   └── Assert: < 3s mean
│
├── test_httpx_performance_large (100 URLs)
│   └── Assert: < 6s mean
│
├── test_naabu_performance_top_ports
│   └── Assert: < 2s mean
│
├── test_naabu_performance_full_range
│   └── Assert: < 10s mean
│
├── test_tlsx_performance (20 hosts)
│   └── Assert: < 3s mean
│
├── test_katana_performance_shallow (depth 1)
│   └── Assert: < 2s mean
│
└── test_katana_performance_deep (depth 3)
    └── Assert: < 10s mean
```

### 2. Database Performance

```
TestDatabasePerformance
├── test_bulk_insert_small (100 records)
│   ├── Setup: Generate 100 asset records
│   ├── Execute: Bulk UPSERT with ON CONFLICT
│   ├── Measure: Throughput (records/second)
│   └── Assert: < 0.5s mean, > 2000 records/s
│
├── test_bulk_insert_medium (1,000 records)
│   └── Assert: < 2s mean, > 3000 records/s
│
├── test_bulk_insert_large (10,000 records)
│   ├── Batch processing (1000 per transaction)
│   └── Assert: < 15s mean
│
├── test_query_performance_simple
│   ├── Execute: SELECT with WHERE + LIMIT
│   └── Assert: < 0.05s (50ms) mean
│
├── test_query_performance_complex
│   ├── Execute: SELECT with LEFT JOIN + ORDER BY
│   └── Assert: < 0.1s (100ms) mean
│
└── test_concurrent_writes (10 threads)
    ├── Execute: 10 parallel bulk inserts
    ├── Monitor: Connection pool usage
    └── Assert: < 5s mean, all succeed
```

### 3. Concurrent Execution

```
TestConcurrentExecution
├── test_parallel_tool_execution_5
│   ├── Execute: 5 tools in parallel (ThreadPoolExecutor)
│   ├── Monitor: Completion time
│   └── Assert: < 2s mean
│
├── test_parallel_tool_execution_10
│   └── Assert: < 3s mean
│
├── test_parallel_tool_execution_20
│   └── Assert: < 5s mean
│
├── test_memory_usage_under_load
│   ├── Monitor: RSS memory (psutil)
│   ├── Execute: 50 concurrent operations
│   ├── Track: Initial, peak, final memory
│   └── Assert: < 500MB increase
│
├── test_database_connection_pool_limits
│   ├── Execute: 100 concurrent queries
│   ├── Pool: 20 connections + 40 overflow
│   ├── Monitor: Success/failure rate
│   └── Assert: >= 60 successful
│
└── test_deadlock_detection
    ├── Execute: Interleaved lock acquisition
    ├── Monitor: Deadlock occurrences
    └── Assert: Graceful handling
```

### 4. Stress Testing

```
TestStressTesting
├── test_httpx_breaking_point
│   ├── Test: 100, 500, 1K, 2K, 5K, 10K URLs
│   ├── Find: Maximum processable input
│   ├── Monitor: Memory constraint
│   └── Assert: >= 1000 URLs successful
│
├── test_database_breaking_point
│   ├── Test: 100, 500, 1K, 5K, 10K, 50K records
│   ├── Find: Maximum batch size
│   └── Assert: >= 10000 records successful
│
├── test_malformed_input_handling
│   ├── Test: 15 edge cases
│   │   ├── Large URLs (10K chars)
│   │   ├── Invalid characters (null, newline)
│   │   ├── Unicode (Chinese, Russian)
│   │   ├── Special ports (0, 65535)
│   │   ├── IPv6 addresses
│   │   └── Empty/whitespace
│   └── Assert: 0 crashes (100% graceful handling)
│
├── test_resource_limit_enforcement
│   ├── Test: CPU time limit (20s attempt)
│   ├── Test: Memory limit (large allocation)
│   ├── Test: Timeout enforcement (1s limit)
│   └── Assert: All limits enforced
│
├── test_recovery_from_failures
│   ├── Simulate: 30% failure rate
│   ├── Strategy: Retry with exponential backoff
│   ├── Execute: 20 operations, max 3 retries
│   └── Assert: > 60% recovery rate
│
└── test_recovery_from_connection_loss
    ├── Simulate: Connection pool exhaustion
    ├── Strategy: Automatic reconnection
    └── Assert: Successful recovery
```

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     Performance Test Data Flow                   │
└─────────────────────────────────────────────────────────────────┘

Input Generation
    ├── sample_urls() fixture → 100 URLs (mixed protocols/ports)
    ├── sample_assets() fixture → 100 Asset records
    └── Random data generation for stress tests

                    ↓

Tool Execution (Mocked)
    ├── SecureToolExecutor → Mock with realistic delays
    ├── Execute tools (httpx, naabu, tlsx, katana)
    └── Return JSON results

                    ↓

Database Operations (Real PostgreSQL)
    ├── Bulk INSERT with ON CONFLICT DO UPDATE
    ├── SELECT queries (simple + complex)
    └── Concurrent transactions

                    ↓

Metrics Collection
    ├── Execution time (pytest-benchmark)
    ├── Memory usage (psutil)
    ├── Throughput calculation
    └── Resource utilization

                    ↓

Statistical Analysis
    ├── Mean, median, stddev
    ├── Min, max, percentiles (p95, p99)
    ├── Rounds executed
    └── Comparison to baseline

                    ↓

Result Output
    ├── JSON: Structured benchmark data
    ├── SVG: Histogram visualization
    ├── Markdown: Human-readable report
    └── Logs: Detailed execution trace
```

## Technology Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                       Technology Components                      │
└─────────────────────────────────────────────────────────────────┘

Testing Framework
    ├── pytest 7.4.4          → Test runner
    ├── pytest-benchmark 4.0  → Performance benchmarking
    └── pytest-asyncio 0.23   → Async test support

Database
    ├── PostgreSQL 15 (Docker) → Realistic DB testing
    ├── SQLAlchemy 2.0         → ORM and connection pooling
    └── psycopg2-binary 2.9    → PostgreSQL driver

Monitoring
    ├── psutil 5.9            → System resource monitoring
    ├── numpy                 → Statistical analysis
    └── time.perf_counter     → High-resolution timing

Infrastructure
    ├── Docker Compose        → Isolated test environment
    ├── Redis 7 (Docker)      → Cache/queue testing
    └── MinIO (Docker)        → Object storage testing

Mocking
    ├── unittest.mock         → Tool execution mocking
    └── MagicMock             → Flexible test doubles
```

## Fixture Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Fixture Hierarchy                        │
└─────────────────────────────────────────────────────────────────┘

Module Scope (shared across test class)
    └── performance_db
        ├── Create PostgreSQL database
        ├── Initialize schema (Base.metadata.create_all)
        ├── Create test tenant
        └── Yield (db, tenant, engine)
        └── Cleanup: Drop database

Function Scope (per test)
    ├── sample_urls(performance_db)
    │   └── Generate 100 varied URLs
    │
    ├── sample_assets(performance_db)
    │   ├── Create 100 Asset records
    │   └── Commit to database
    │
    └── mock_tool_executor()
        ├── Patch SecureToolExecutor
        ├── Configure realistic side effects
        └── Return mock instance
```

## Benchmark Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│                  pytest-benchmark Configuration                  │
└─────────────────────────────────────────────────────────────────┘

Global Settings (pytest-benchmark.ini)
    ├── warmup: true (3 iterations)
    ├── min_rounds: 5
    ├── max_time: 60 seconds
    ├── stats: min, max, mean, median, stddev, rounds
    ├── compare: mean:5% (warning threshold)
    └── compare_fail: mean:20% (fail threshold)

Per-Test Overrides (decorators)
    @pytest.mark.benchmark(
        group="tools",         # Group related tests
        min_rounds=5,          # Minimum iterations
        max_time=60,           # Maximum benchmark time
        warmup=True            # Enable warmup
    )

Test Markers
    ├── @pytest.mark.performance  → All performance tests
    └── @pytest.mark.integration  → Requires Docker services
```

## Result Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                       Result File Structure                      │
└─────────────────────────────────────────────────────────────────┘

test_results/performance/
├── tools_benchmark.json
│   ├── machine_info: CPU, RAM, OS
│   ├── commit_info: Git hash, branch
│   └── benchmarks: Array of benchmark results
│       └── {name, group, stats{min,max,mean,...}}
│
├── tools_histogram.svg
│   └── Visual distribution of execution times
│
├── tools_output.log
│   ├── Test execution trace
│   ├── Assertion results
│   └── Performance metrics
│
├── db_benchmark.json
│   └── Database performance results
│
├── db_histogram.svg
│   └── Query time distribution
│
├── concurrent_benchmark.json
│   └── Concurrency test results
│
├── performance_report.md
│   ├── Executive Summary
│   ├── Key Findings
│   ├── Optimization Recommendations
│   │   ├── Priority 1: Critical
│   │   ├── Priority 2: Enhancements
│   │   └── Priority 3: Scalability
│   ├── Implementation Roadmap
│   └── Expected Outcomes
│
└── *.log
    └── Detailed test logs
```

## Performance Metrics Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    Metrics Collection Pipeline                   │
└─────────────────────────────────────────────────────────────────┘

1. Pre-execution
   ├── Record initial memory (psutil)
   ├── Start timer (time.perf_counter)
   └── Note system state

2. During execution (pytest-benchmark)
   ├── Warmup rounds (3x)
   ├── Timed rounds (5+ iterations)
   ├── Resource monitoring
   └── Statistics accumulation

3. Post-execution
   ├── Calculate statistics
   │   ├── min, max, mean, median
   │   ├── stddev (consistency)
   │   └── percentiles (p95, p99)
   ├── Record final memory
   ├── Calculate throughput
   └── Compare to baseline

4. Aggregation
   ├── Group by test category
   ├── Generate histograms
   ├── Detect regressions
   └── Create summary report
```

## Optimization Recommendation Engine

```
┌─────────────────────────────────────────────────────────────────┐
│              Optimization Recommendation Engine                  │
└─────────────────────────────────────────────────────────────────┘

Analysis Engine
    └── generate_performance_report()
        ├── Parse benchmark results
        ├── Identify bottlenecks
        ├── Calculate impact estimates
        └── Generate recommendations

Recommendation Structure
    ├── Priority 1: Critical (0-30 day impact)
    │   ├── Database indexing
    │   ├── Batch configuration
    │   └── Connection pool tuning
    │
    ├── Priority 2: Enhancements (30-60 day impact)
    │   ├── Redis caching
    │   ├── Tool optimization
    │   └── Query optimization
    │
    └── Priority 3: Scalability (60-90 day impact)
        ├── Rate limiting
        ├── Horizontal scaling
        └── Monitoring/alerting

Impact Estimates
    ├── Performance improvement %
    ├── Resource reduction %
    ├── Capacity increase multiplier
    └── Implementation effort (days)
```

## CI/CD Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                     CI/CD Integration Flow                       │
└─────────────────────────────────────────────────────────────────┘

GitHub Actions Workflow
    ├── Trigger: On push to main, weekly scheduled
    ├── Setup: Start Docker services
    ├── Execute: bash scripts/run_performance_tests.sh
    ├── Compare: Against baseline (fail on 20% regression)
    ├── Artifact: Upload test_results/performance/
    └── Notify: Alert on performance degradation

Baseline Management
    ├── Save baseline on release
    ├── Compare against latest baseline
    ├── Track performance trends
    └── Alert on sustained degradation
```

## Conclusion

This architecture provides:

1. **Comprehensive Coverage**: 26 tests across 4 categories
2. **Realistic Testing**: Real PostgreSQL, production-like data
3. **Actionable Results**: Detailed recommendations with impact estimates
4. **Continuous Monitoring**: Baseline comparison and regression detection
5. **Production Readiness**: Validates system under expected load

The modular design allows easy extension for new tools, metrics, or test scenarios.

---

**Architecture Designed for**: Sprint 2 Enrichment Infrastructure (13.5K LOC)
**Test Coverage**: Tool execution, database, concurrency, stress testing
**Expected Runtime**: 5-15 minutes (standard), 30-60 minutes (with stress tests)
