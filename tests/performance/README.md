# EASM Enrichment Pipeline Performance Tests

Comprehensive performance and load testing suite for the EASM enrichment infrastructure.

## Overview

This test suite validates the performance characteristics of the enrichment pipeline built in Sprint 2 (13.5K LOC). It covers:

- **Tool Execution Performance**: HTTPx, Naabu, TLSx, Katana
- **Database Performance**: Bulk inserts, queries, concurrent access
- **Concurrent Execution**: Parallel task processing, resource utilization
- **Stress Testing**: Breaking points, failure recovery, resource limits

## Test Categories

### 1. Tool Execution Performance Tests

Benchmark individual ProjectDiscovery tool performance:

```bash
pytest tests/performance/test_enrichment_performance.py::TestToolExecutionPerformance -v
```

**Tests:**
- `test_httpx_performance_small`: 10 URLs
- `test_httpx_performance_medium`: 50 URLs
- `test_httpx_performance_large`: 100 URLs
- `test_naabu_performance_top_ports`: Top 100 ports
- `test_naabu_performance_full_range`: Port range 1-10000
- `test_tlsx_performance`: 20 hosts certificate analysis
- `test_katana_performance_shallow`: Depth 1 crawl
- `test_katana_performance_deep`: Depth 3 crawl

**Expected Performance:**
- HTTPx: 200 URLs/second
- Naabu: 50 hosts/second (top 100 ports)
- TLSx: 30 certificates/second
- Katana: 10 pages/second (depth 1)

### 2. Database Performance Tests

Benchmark PostgreSQL operations with realistic data:

```bash
pytest tests/performance/test_enrichment_performance.py::TestDatabasePerformance -v
```

**Tests:**
- `test_bulk_insert_small`: 100 records
- `test_bulk_insert_medium`: 1,000 records
- `test_bulk_insert_large`: 10,000 records
- `test_query_performance_simple`: Basic SELECT queries
- `test_query_performance_complex`: Queries with JOINs
- `test_concurrent_writes`: 10 parallel write operations

**Expected Performance:**
- Bulk inserts: 5,000 records/second
- Simple queries: < 50ms
- Complex queries: < 100ms
- Concurrent writes: 1,000 records/second

### 3. Concurrent Execution Tests

Test parallel tool execution and resource usage:

```bash
pytest tests/performance/test_enrichment_performance.py::TestConcurrentExecution -v
```

**Tests:**
- `test_parallel_tool_execution_5`: 5 parallel operations
- `test_parallel_tool_execution_10`: 10 parallel operations
- `test_parallel_tool_execution_20`: 20 parallel operations
- `test_memory_usage_under_load`: Memory profiling
- `test_database_connection_pool_limits`: Connection pool stress
- `test_deadlock_detection`: Concurrent transaction safety

**Expected Performance:**
- 10 parallel operations: < 3s
- Memory per operation: ~10MB
- Connection pool: 60+ concurrent operations

### 4. Stress Testing

Find breaking points and test system resilience:

```bash
pytest tests/performance/test_enrichment_performance.py::TestStressTesting -v -s
```

**Tests:**
- `test_httpx_breaking_point`: Find max URLs processable
- `test_database_breaking_point`: Find max batch size
- `test_malformed_input_handling`: Edge case handling
- `test_resource_limit_enforcement`: CPU/memory limits
- `test_recovery_from_failures`: Fault tolerance

## Running Tests

### Quick Run (Benchmarks Only)

```bash
pytest tests/performance/ -v --benchmark-only
```

### Full Run with Histograms

```bash
pytest tests/performance/ -v --benchmark-only --benchmark-histogram
```

### Save Baseline

```bash
pytest tests/performance/ -v --benchmark-only --benchmark-save=baseline
```

### Compare Against Baseline

```bash
pytest tests/performance/ -v --benchmark-only --benchmark-compare=baseline
```

### Run with Performance Report

```bash
bash scripts/run_performance_tests.sh
```

### Run with Stress Tests

```bash
bash scripts/run_performance_tests.sh --stress
```

## Performance Metrics

### Key Performance Indicators (KPIs)

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| HTTPx (100 URLs) | < 2s | < 6s |
| Naabu (top 100 ports) | < 1s | < 2s |
| TLSx (20 hosts) | < 1.5s | < 3s |
| Bulk Insert (1000 records) | < 1s | < 2s |
| Query (simple) | < 20ms | < 50ms |
| Query (complex) | < 50ms | < 100ms |
| Memory per operation | < 10MB | < 50MB |
| Concurrent operations | 10-15 | 20 max |

### Resource Limits

Default resource limits enforced by `SecureToolExecutor`:

- **Timeout**: 300s (5 minutes)
- **CPU Time**: 600s (10 minutes)
- **Memory**: 2GB
- **File Size**: 100MB

## Prerequisites

### Docker Services

Performance tests require PostgreSQL and Redis:

```bash
docker-compose up -d postgres redis
```

### Python Dependencies

```bash
pip install pytest pytest-benchmark numpy psutil sqlalchemy
```

### Database Setup

Tests create a temporary database `easm_perf_test`:

```sql
CREATE DATABASE easm_perf_test;
```

Database is automatically cleaned up after tests complete.

## Test Results

### Results Directory Structure

```
test_results/performance/
├── tools_benchmark.json        # Tool execution benchmarks
├── tools_histogram.svg         # Tool performance histogram
├── tools_output.log           # Tool test output
├── db_benchmark.json          # Database benchmarks
├── db_histogram.svg           # Database performance histogram
├── db_output.log              # Database test output
├── concurrent_benchmark.json  # Concurrent execution benchmarks
├── concurrent_output.log      # Concurrent test output
├── stress_output.log          # Stress test output
└── performance_report.md      # Comprehensive analysis report
```

### Benchmark JSON Format

```json
{
  "machine_info": { ... },
  "commit_info": { ... },
  "benchmarks": [
    {
      "name": "test_httpx_performance_small",
      "group": "tools",
      "stats": {
        "min": 0.145,
        "max": 0.189,
        "mean": 0.162,
        "median": 0.159,
        "stddev": 0.015,
        "rounds": 10
      }
    }
  ]
}
```

## Optimization Recommendations

The performance report includes detailed optimization recommendations:

### Priority 1: Critical Optimizations

1. **Database Indexing**
   - Add composite indexes on frequently queried columns
   - Expected impact: 50-70% query performance improvement

2. **Batch Processing Configuration**
   - Optimize batch sizes per tool
   - Expected impact: 30-40% throughput improvement

3. **Connection Pool Tuning**
   - Increase pool size and overflow limits
   - Expected impact: 50% more concurrent operations

### Priority 2: Performance Enhancements

4. **Redis Caching**
   - Cache frequently accessed data
   - Expected impact: 80% reduction in database reads

5. **Tool Execution Optimization**
   - Fine-tune tool parameters
   - Expected impact: 40-60% execution speedup

6. **Query Optimization**
   - Use prepared statements and pagination
   - Expected impact: 30% reduction in query time

### Priority 3: Scalability Improvements

7. **Rate Limiting**
   - Implement per-tenant rate limits
   - Expected impact: Prevent system overload

8. **Horizontal Scaling**
   - Prepare for multi-node deployment
   - Expected impact: Linear scaling

9. **Monitoring & Alerting**
   - Track key performance metrics
   - Expected impact: Proactive issue detection

## Interpreting Results

### Benchmark Statistics

- **min**: Fastest execution time
- **max**: Slowest execution time
- **mean**: Average execution time
- **median**: Middle value (50th percentile)
- **stddev**: Standard deviation (consistency)
- **rounds**: Number of test iterations

### Performance Assertions

Tests include performance assertions:

```python
assert stats.mean < 1.0, "HTTPx (10 URLs) should complete in < 1s"
assert stats.stddev < 0.2, "Performance should be consistent"
```

Failures indicate performance regressions.

### Histogram Interpretation

Histogram SVG files visualize execution time distribution:

- **Narrow distribution**: Consistent performance
- **Wide distribution**: High variance
- **Multiple peaks**: Different code paths
- **Long tail**: Occasional slow operations

## Continuous Performance Monitoring

### CI/CD Integration

Add to GitHub Actions workflow:

```yaml
- name: Run Performance Tests
  run: |
    docker-compose up -d postgres redis
    bash scripts/run_performance_tests.sh

- name: Check for Regressions
  run: |
    pytest tests/performance/ \
      --benchmark-only \
      --benchmark-compare=baseline \
      --benchmark-compare-fail=mean:20%
```

### Performance Regression Detection

The script checks for regressions:

```bash
# 20% regression threshold
if mean > baseline * 1.2:
    echo "⚠️  REGRESSION DETECTED"
    exit 1
```

### Alerting

Set up alerts for performance degradation:

- Mean execution time > baseline + 20%
- 95th percentile > critical threshold
- Error rate > 5%
- Memory usage > 4GB

## Troubleshooting

### Tests Timing Out

Increase timeout limits:

```python
@pytest.mark.benchmark(group="tools", min_rounds=5, max_time=120)
```

### Memory Errors

Reduce batch sizes in stress tests:

```python
for batch_size in [100, 500, 1000]:  # Instead of [100, 500, ..., 50000]
```

### Database Connection Errors

Check PostgreSQL connection:

```bash
docker exec easm-postgres pg_isready -U easm
psql -h localhost -p 15432 -U easm -d easm
```

### Docker Services Not Running

Start required services:

```bash
docker-compose up -d postgres redis
docker-compose ps  # Verify status
```

### Permission Errors

Ensure script is executable:

```bash
chmod +x scripts/run_performance_tests.sh
```

## Best Practices

### Running Performance Tests

1. **Isolated Environment**: Run on dedicated hardware
2. **Consistent State**: Clear caches between runs
3. **Minimal Load**: Close unnecessary applications
4. **Multiple Runs**: Average results from 5+ runs
5. **Baseline Comparison**: Compare against known baseline

### Writing Performance Tests

1. **Use pytest-benchmark**: Leverage built-in benchmarking
2. **Include Warmup**: Add warmup rounds for JIT
3. **Control Variables**: Use fixtures for test data
4. **Assert Performance**: Set expected thresholds
5. **Document Results**: Explain expected values

### Analyzing Results

1. **Focus on Trends**: Look for patterns over time
2. **Consider Context**: Account for system load
3. **Investigate Outliers**: Understand slow operations
4. **Validate Assumptions**: Verify expected behavior
5. **Iterate**: Continuously optimize

## References

- [pytest-benchmark Documentation](https://pytest-benchmark.readthedocs.io/)
- [PostgreSQL Performance Tips](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Python Performance Tips](https://wiki.python.org/moin/PythonSpeed/PerformanceTips)
- [ProjectDiscovery Tool Documentation](https://docs.projectdiscovery.io/)

## Support

For issues or questions:

1. Check test output logs in `test_results/performance/`
2. Review the performance report: `performance_report.md`
3. Consult the optimization recommendations
4. Run stress tests to identify bottlenecks: `--stress`

---

**Sprint 2 Performance Testing Suite** - Comprehensive validation of 13.5K LOC enrichment infrastructure
