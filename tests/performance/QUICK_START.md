# Performance Testing Quick Start Guide

## 30 Second Setup

```bash
# 1. Start Docker services
docker-compose up -d postgres redis

# 2. Activate virtual environment
source venv/bin/activate

# 3. Install dependencies
pip install pytest pytest-benchmark numpy psutil

# 4. Run all performance tests
bash scripts/run_performance_tests.sh
```

## Common Commands

### Run All Performance Tests

```bash
pytest tests/performance/ -v --benchmark-only
```

### Run Specific Test Class

```bash
# Tool execution tests only
pytest tests/performance/test_enrichment_performance.py::TestToolExecutionPerformance -v

# Database tests only
pytest tests/performance/test_enrichment_performance.py::TestDatabasePerformance -v

# Concurrent execution tests only
pytest tests/performance/test_enrichment_performance.py::TestConcurrentExecution -v

# Stress tests only (takes longer)
pytest tests/performance/test_enrichment_performance.py::TestStressTesting -v -s
```

### Run Single Test

```bash
pytest tests/performance/test_enrichment_performance.py::TestToolExecutionPerformance::test_httpx_performance_small -v
```

### Generate Histograms

```bash
pytest tests/performance/ -v --benchmark-only --benchmark-histogram
```

### Save Baseline

```bash
pytest tests/performance/ -v --benchmark-only --benchmark-save=sprint2_baseline
```

### Compare to Baseline

```bash
pytest tests/performance/ -v --benchmark-only --benchmark-compare=sprint2_baseline
```

### Run with Full Script (Recommended)

```bash
# Standard run
bash scripts/run_performance_tests.sh

# With stress tests
bash scripts/run_performance_tests.sh --stress
```

## Understanding Results

### Console Output

```
============================= test session starts ==============================

tests/performance/test_enrichment_performance.py::TestToolExecutionPerformance::test_httpx_performance_small PASSED

-------------------------- benchmark: 1 tests --------------------------
Name                              Min      Max     Mean   StdDev   Median   Rounds
----------------------------------------------------------------------------------
test_httpx_performance_small    0.145    0.189    0.162    0.015    0.159     10
----------------------------------------------------------------------------------
```

### What to Look For

- **Mean**: Average execution time (main metric)
- **StdDev**: Consistency (lower is better)
- **Median**: Typical execution time (50th percentile)
- **Rounds**: Number of test iterations

### Performance Thresholds

| Test | Good | Warning | Critical |
|------|------|---------|----------|
| HTTPx (10 URLs) | < 0.5s | 0.5-1s | > 1s |
| HTTPx (100 URLs) | < 2s | 2-6s | > 6s |
| DB Insert (1000) | < 1s | 1-2s | > 2s |
| Query (simple) | < 20ms | 20-50ms | > 50ms |
| Parallel (10) | < 1.5s | 1.5-3s | > 3s |

## Results Location

All results saved to: `test_results/performance/`

```
test_results/performance/
├── tools_benchmark.json           # Tool performance data
├── tools_histogram.svg            # Tool performance graph
├── db_benchmark.json              # Database performance data
├── db_histogram.svg               # Database performance graph
├── concurrent_benchmark.json      # Concurrent execution data
├── performance_report.md          # Full analysis + recommendations
└── *.log                          # Detailed test logs
```

## Interpreting Histograms

Histograms show execution time distribution:

- **Tall narrow peak**: Consistent performance ✅
- **Wide spread**: High variance ⚠️
- **Multiple peaks**: Different code paths
- **Long right tail**: Occasional slow operations

## Quick Troubleshooting

### Tests Fail to Start

```bash
# Check Docker services
docker-compose ps

# Should see postgres and redis running
# If not:
docker-compose up -d postgres redis
docker-compose logs postgres
```

### Database Connection Errors

```bash
# Test PostgreSQL connection
psql -h localhost -p 15432 -U easm -d easm

# If fails, restart:
docker-compose restart postgres
```

### Import Errors

```bash
# Ensure you're in virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -e .
pip install pytest pytest-benchmark numpy psutil
```

### Memory Errors

```bash
# Increase Docker memory limit (Docker Desktop)
# Or reduce batch sizes in stress tests
pytest tests/performance/ -v -k "not stress"
```

## Performance Baselines

See `tests/performance/baseline_metrics.json` for:

- Expected execution times
- Throughput targets
- Resource limits
- Breaking points

## Optimization Recommendations

After running tests, see:

```
test_results/performance/performance_report.md
```

Contains:
- Detailed analysis of results
- Prioritized optimization recommendations
- Expected performance improvements
- Implementation roadmap

## Next Steps

1. **Review Results**: Check `performance_report.md`
2. **Identify Bottlenecks**: Look for tests exceeding thresholds
3. **Apply Optimizations**: Implement Priority 1 recommendations
4. **Re-test**: Run tests again to validate improvements
5. **Set Baseline**: Save results as new baseline

## CI/CD Integration

Add to GitHub Actions:

```yaml
- name: Performance Tests
  run: |
    docker-compose up -d postgres redis
    bash scripts/run_performance_tests.sh

- name: Upload Results
  uses: actions/upload-artifact@v3
  with:
    name: performance-results
    path: test_results/performance/
```

## Advanced Usage

### Custom Warmup Rounds

```bash
pytest tests/performance/ --benchmark-warmup=on --benchmark-warmup-iterations=5
```

### Custom Min Rounds

```bash
pytest tests/performance/ --benchmark-min-rounds=10
```

### Disable Garbage Collection

```bash
pytest tests/performance/ --benchmark-disable-gc
```

### JSON Output Only

```bash
pytest tests/performance/ --benchmark-only --benchmark-json=results.json
```

### Compare Multiple Baselines

```bash
pytest tests/performance/ --benchmark-compare=0001,0002,0003
```

## Support

For detailed information, see:
- `tests/performance/README.md` - Full documentation
- `tests/performance/test_enrichment_performance.py` - Test source
- [pytest-benchmark docs](https://pytest-benchmark.readthedocs.io/)

## Quick Reference

```bash
# Standard workflow
docker-compose up -d postgres redis        # 1. Start services
source venv/bin/activate                   # 2. Activate environment
bash scripts/run_performance_tests.sh      # 3. Run all tests
cat test_results/performance/performance_report.md  # 4. Review results

# Individual test classes
pytest tests/performance/ -k "ToolExecution" -v    # Tool tests
pytest tests/performance/ -k "Database" -v         # DB tests
pytest tests/performance/ -k "Concurrent" -v       # Concurrency tests
pytest tests/performance/ -k "Stress" -v -s        # Stress tests

# Comparison workflow
pytest tests/performance/ --benchmark-save=before  # Save current
# Make changes...
pytest tests/performance/ --benchmark-compare=before  # Compare

# Results
ls test_results/performance/              # List all results
open test_results/performance/*.svg       # View histograms
cat test_results/performance/performance_report.md  # Read report
```

---

**Sprint 2 Performance Testing** - Validate enrichment infrastructure performance before production deployment
