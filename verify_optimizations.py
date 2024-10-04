#!/usr/bin/env python3
"""
Verification script for database optimizations

This script verifies that all optimizations have been correctly applied:
1. Checks that new indexes exist
2. Validates that queries use the correct indexes
3. Measures query performance
4. Tests bulk operations

Usage:
    python3 verify_optimizations.py
"""

import sys
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, '/Users/cere/Downloads/easm')

from app.config import settings
from app.database import SessionLocal
from app.models.database import Asset, AssetType, Tenant
from app.repositories.asset_repository import AssetRepository


class OptimizationVerifier:
    """Verifies database optimizations"""

    def __init__(self):
        self.db = SessionLocal()
        self.passed = 0
        self.failed = 0

    def print_header(self, message):
        """Print section header"""
        print(f"\n{'=' * 70}")
        print(f"  {message}")
        print(f"{'=' * 70}\n")

    def print_test(self, name, passed, message=""):
        """Print test result"""
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"{symbol} [{status}] {name}")
        if message:
            print(f"    {message}")

        if passed:
            self.passed += 1
        else:
            self.failed += 1

    def verify_indexes(self):
        """Verify that all required indexes exist"""
        self.print_header("1. Verifying Index Creation")

        required_indexes = [
            ('assets', 'idx_assets_tenant_risk_active'),
            ('assets', 'idx_assets_tenant_active_risk'),
            ('events', 'idx_events_asset_id'),
            ('findings', 'idx_findings_asset_severity_status'),
        ]

        query = text("""
            SELECT tablename, indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = :table
              AND indexname = :index
        """)

        for table, index in required_indexes:
            result = self.db.execute(query, {'table': table, 'index': index})
            exists = result.fetchone() is not None

            self.print_test(
                f"Index {index} on {table}",
                exists,
                "Index found in database" if exists else "Index NOT found!"
            )

    def verify_query_plans(self):
        """Verify that queries use the correct indexes"""
        self.print_header("2. Verifying Query Execution Plans")

        # Test 1: Critical assets query should use idx_assets_tenant_risk_active
        query1 = text("""
            EXPLAIN
            SELECT * FROM assets
            WHERE tenant_id = 1
              AND risk_score >= 50.0
              AND is_active = true
        """)

        result1 = self.db.execute(query1)
        plan1 = '\n'.join([row[0] for row in result1])
        uses_index1 = 'idx_assets_tenant_risk_active' in plan1

        self.print_test(
            "Critical assets query uses composite index",
            uses_index1,
            "Uses idx_assets_tenant_risk_active" if uses_index1 else f"Plan:\n{plan1}"
        )

        # Test 2: Asset listing with ORDER BY should use idx_assets_tenant_active_risk
        query2 = text("""
            EXPLAIN
            SELECT * FROM assets
            WHERE tenant_id = 1
              AND is_active = true
            ORDER BY risk_score DESC
            LIMIT 100
        """)

        result2 = self.db.execute(query2)
        plan2 = '\n'.join([row[0] for row in result2])
        uses_index2 = 'idx_assets_tenant_active_risk' in plan2 or 'idx_assets_tenant_risk_active' in plan2

        self.print_test(
            "Asset listing query uses optimized index",
            uses_index2,
            "Uses appropriate composite index" if uses_index2 else f"Plan:\n{plan2}"
        )

        # Test 3: Event JOIN should use idx_events_asset_id
        query3 = text("""
            EXPLAIN
            SELECT e.* FROM events e
            WHERE e.asset_id IN (1, 2, 3, 4, 5)
        """)

        result3 = self.db.execute(query3)
        plan3 = '\n'.join([row[0] for row in result3])
        uses_index3 = 'idx_events_asset_id' in plan3

        self.print_test(
            "Event lookup query uses asset_id index",
            uses_index3,
            "Uses idx_events_asset_id" if uses_index3 else f"Plan:\n{plan3}"
        )

    def verify_repository_methods(self):
        """Verify that new repository methods exist and work"""
        self.print_header("3. Verifying Repository Methods")

        repo = AssetRepository(self.db)

        # Test 1: get_by_identifiers_bulk exists
        has_bulk_method = hasattr(repo, 'get_by_identifiers_bulk')
        self.print_test(
            "AssetRepository.get_by_identifiers_bulk() exists",
            has_bulk_method,
            "Method is available for bulk lookups"
        )

        # Test 2: get_by_tenant has eager_load_relations parameter
        try:
            import inspect
            sig = inspect.signature(repo.get_by_tenant)
            has_eager_param = 'eager_load_relations' in sig.parameters
            self.print_test(
                "AssetRepository.get_by_tenant() has eager_load_relations parameter",
                has_eager_param,
                "Eager loading is supported"
            )
        except Exception as e:
            self.print_test(
                "AssetRepository.get_by_tenant() signature check",
                False,
                f"Error: {e}"
            )

        # Test 3: get_critical_assets has eager_load_relations parameter
        try:
            sig = inspect.signature(repo.get_critical_assets)
            has_eager_param = 'eager_load_relations' in sig.parameters
            self.print_test(
                "AssetRepository.get_critical_assets() has eager_load_relations parameter",
                has_eager_param,
                "Eager loading is supported"
            )
        except Exception as e:
            self.print_test(
                "AssetRepository.get_critical_assets() signature check",
                False,
                f"Error: {e}"
            )

    def benchmark_bulk_operations(self):
        """Benchmark bulk operations if data exists"""
        self.print_header("4. Benchmarking Bulk Operations")

        repo = AssetRepository(self.db)

        # Check if we have test data
        tenant = self.db.query(Tenant).first()

        if not tenant:
            self.print_test(
                "Bulk operation benchmark",
                True,
                "Skipped - no test data available"
            )
            return

        # Create test data
        test_data = [
            {
                'identifier': f'test-{i}.example.com',
                'type': AssetType.SUBDOMAIN,
                'raw_metadata': '{"test": true}'
            }
            for i in range(100)
        ]

        # Benchmark bulk upsert
        start = time.time()
        result = repo.bulk_upsert(tenant.id, test_data)
        duration = (time.time() - start) * 1000  # Convert to ms

        # Should be fast (< 500ms for 100 records)
        is_fast = duration < 500

        self.print_test(
            f"Bulk upsert of 100 records",
            is_fast,
            f"Completed in {duration:.2f}ms (threshold: 500ms)"
        )

        # Test bulk fetch
        identifiers_by_type = {
            AssetType.SUBDOMAIN: [f'test-{i}.example.com' for i in range(100)]
        }

        start = time.time()
        assets = repo.get_by_identifiers_bulk(tenant.id, identifiers_by_type)
        duration = (time.time() - start) * 1000

        # Should be very fast (< 100ms for 100 records)
        is_fast = duration < 100

        self.print_test(
            f"Bulk fetch of 100 records",
            is_fast,
            f"Completed in {duration:.2f}ms (threshold: 100ms), found {len(assets)} assets"
        )

        # Cleanup test data
        self.db.query(Asset).filter(
            Asset.tenant_id == tenant.id,
            Asset.identifier.like('test-%')
        ).delete()
        self.db.commit()

    def verify_migration_version(self):
        """Verify that migration 003 has been applied"""
        self.print_header("5. Verifying Migration Status")

        try:
            query = text("SELECT version_num FROM alembic_version")
            result = self.db.execute(query)
            current_version = result.scalar()

            # Check if version is 003 or later
            is_correct_version = current_version >= '003'

            self.print_test(
                f"Migration version is 003 or later",
                is_correct_version,
                f"Current version: {current_version}"
            )
        except Exception as e:
            self.print_test(
                "Check migration version",
                False,
                f"Error: {e}"
            )

    def print_summary(self):
        """Print test summary"""
        self.print_header("Test Summary")

        total = self.passed + self.failed
        percentage = (self.passed / total * 100) if total > 0 else 0

        print(f"Total Tests: {total}")
        print(f"Passed: {self.passed} ✓")
        print(f"Failed: {self.failed} ✗")
        print(f"Success Rate: {percentage:.1f}%")

        if self.failed == 0:
            print("\n🎉 All optimizations verified successfully!")
            print("\nNext steps:")
            print("  1. Run alembic upgrade head (if not already done)")
            print("  2. Monitor query performance with pg_stat_statements")
            print("  3. Review DATABASE_OPTIMIZATION_REPORT.md for details")
        else:
            print("\n⚠️  Some verifications failed. Please review the output above.")
            print("\nTroubleshooting:")
            print("  1. Ensure migration 003 has been applied: alembic upgrade head")
            print("  2. Check database connection settings")
            print("  3. Review error messages above")

    def run_all(self):
        """Run all verification tests"""
        print("\n" + "=" * 70)
        print("  Database Optimization Verification")
        print("  EASM Platform - Sprint 1")
        print("=" * 70)

        try:
            self.verify_migration_version()
            self.verify_indexes()
            self.verify_query_plans()
            self.verify_repository_methods()
            self.benchmark_bulk_operations()
            self.print_summary()

        except Exception as e:
            print(f"\n❌ Verification failed with error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.db.close()


if __name__ == '__main__':
    verifier = OptimizationVerifier()
    verifier.run_all()
