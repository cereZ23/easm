"""
Integration tests for Nuclei vulnerability scanning pipeline

Tests end-to-end workflow:
- Scan execution
- Finding storage
- Deduplication
- Suppression
- Risk score updates
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import (
    Asset, AssetType, Finding, FindingSeverity,
    FindingStatus, Suppression, Tenant
)
from app.services.scanning.nuclei_service import NucleiService
from app.services.scanning.suppression_service import SuppressionService
from app.repositories.finding_repository import FindingRepository
from app.repositories.asset_repository import AssetRepository


class TestNucleiIntegration:
    """Integration tests for Nuclei scanning pipeline"""

    @pytest.fixture
    def db_session(self):
        """
        Create test database session

        Note: In real tests, this would use a test database
        """
        from app.database import SessionLocal
        db = SessionLocal()
        yield db
        db.close()

    @pytest.fixture
    def test_tenant(self, db_session: Session):
        """Create test tenant"""
        tenant = Tenant(
            name="Test Tenant",
            slug="test-tenant",
            contact_policy="Test policy"
        )
        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)
        yield tenant

        # Cleanup
        db_session.delete(tenant)
        db_session.commit()

    @pytest.fixture
    def test_asset(self, db_session: Session, test_tenant):
        """Create test asset"""
        asset = Asset(
            tenant_id=test_tenant.id,
            type=AssetType.DOMAIN,
            identifier="example.com",
            risk_score=0.0,
            is_active=True
        )
        db_session.add(asset)
        db_session.commit()
        db_session.refresh(asset)
        yield asset

        # Cleanup
        db_session.delete(asset)
        db_session.commit()

    def test_finding_repository_bulk_upsert(
        self,
        db_session: Session,
        test_tenant,
        test_asset
    ):
        """Test bulk upserting findings"""
        finding_repo = FindingRepository(db_session)

        # Create test findings
        findings = [
            {
                'asset_id': test_asset.id,
                'template_id': 'CVE-2021-12345',
                'name': 'Test Vulnerability 1',
                'severity': 'critical',
                'cvss_score': 9.8,
                'cve_id': 'CVE-2021-12345',
                'matched_at': 'https://example.com/vuln1',
                'host': 'example.com',
                'matcher_name': 'version-check',
                'source': 'nuclei'
            },
            {
                'asset_id': test_asset.id,
                'template_id': 'CVE-2021-67890',
                'name': 'Test Vulnerability 2',
                'severity': 'high',
                'cvss_score': 7.5,
                'cve_id': 'CVE-2021-67890',
                'matched_at': 'https://example.com/vuln2',
                'host': 'example.com',
                'matcher_name': 'body-check',
                'source': 'nuclei'
            }
        ]

        # First insert
        result = finding_repo.bulk_upsert_findings(findings, test_tenant.id)

        assert result['created'] == 2
        assert result['updated'] == 0
        assert result['total_processed'] == 2

        # Verify findings stored
        stored_findings = finding_repo.get_findings(
            tenant_id=test_tenant.id,
            asset_id=test_asset.id
        )
        assert len(stored_findings) == 2

        # Update (re-insert same findings)
        result = finding_repo.bulk_upsert_findings(findings, test_tenant.id)

        assert result['created'] == 0
        assert result['updated'] == 2  # Should update, not create new

        # Verify still only 2 findings (deduplication worked)
        stored_findings = finding_repo.get_findings(
            tenant_id=test_tenant.id,
            asset_id=test_asset.id
        )
        assert len(stored_findings) == 2

        # Cleanup
        finding_repo.delete_by_asset(test_asset.id)
