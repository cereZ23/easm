"""
Performance testing module for EASM enrichment pipeline

This module contains comprehensive performance and load tests for:
- Tool execution (HTTPx, Naabu, TLSx, Katana)
- Database operations (bulk inserts, queries, concurrent access)
- Concurrent execution (parallel task processing)
- Stress testing (breaking points, resource limits)

Usage:
    pytest tests/performance/ -v --benchmark-only
    pytest tests/performance/ --benchmark-histogram
    bash scripts/run_performance_tests.sh
"""

__version__ = "1.0.0"
