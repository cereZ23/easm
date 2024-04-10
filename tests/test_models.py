"""
Tests for database models

Sprint 1 basic tests
"""
import pytest
from app.models.database import (
    Tenant, Asset, Service, Finding, Event, Seed,
    AssetType, FindingSeverity, FindingStatus, EventKind
)

def test_tenant_model():
    """Test Tenant model creation"""
    tenant = Tenant(
        name="Test Tenant",
        slug="test-tenant",
        contact_policy="test@example.com"
    )

    assert tenant.name == "Test Tenant"
    assert tenant.slug == "test-tenant"
    assert tenant.contact_policy == "test@example.com"

def test_asset_model():
    """Test Asset model creation"""
    asset = Asset(
        tenant_id=1,
        type=AssetType.SUBDOMAIN,
        identifier="sub.example.com",
        risk_score=15.5,
        is_active=True
    )

    assert asset.tenant_id == 1
    assert asset.type == AssetType.SUBDOMAIN
    assert asset.identifier == "sub.example.com"
    assert asset.risk_score == 15.5
    assert asset.is_active == True

def test_service_model():
    """Test Service model creation"""
    service = Service(
        asset_id=1,
        port=443,
        protocol="https",
        http_title="Test Page",
        http_status=200
    )

    assert service.asset_id == 1
    assert service.port == 443
    assert service.protocol == "https"
    assert service.http_title == "Test Page"
    assert service.http_status == 200

def test_finding_model():
    """Test Finding model creation"""
    finding = Finding(
        asset_id=1,
        source="nuclei",
        template_id="CVE-2021-12345",
        name="Test Vulnerability",
        severity=FindingSeverity.HIGH,
        cvss_score=7.5,
        status=FindingStatus.OPEN
    )

    assert finding.asset_id == 1
    assert finding.source == "nuclei"
    assert finding.severity == FindingSeverity.HIGH
    assert finding.cvss_score == 7.5
    assert finding.status == FindingStatus.OPEN

def test_event_model():
    """Test Event model creation"""
    event = Event(
        asset_id=1,
        kind=EventKind.NEW_ASSET,
        payload='{"test": "data"}'
    )

    assert event.asset_id == 1
    assert event.kind == EventKind.NEW_ASSET
    assert event.payload == '{"test": "data"}'

def test_seed_model():
    """Test Seed model creation"""
    seed = Seed(
        tenant_id=1,
        type="domain",
        value="example.com",
        enabled=True
    )

    assert seed.tenant_id == 1
    assert seed.type == "domain"
    assert seed.value == "example.com"
    assert seed.enabled == True

def test_asset_type_enum():
    """Test AssetType enum values"""
    assert AssetType.DOMAIN.value == "domain"
    assert AssetType.SUBDOMAIN.value == "subdomain"
    assert AssetType.IP.value == "ip"
    assert AssetType.URL.value == "url"
    assert AssetType.SERVICE.value == "service"

def test_finding_severity_enum():
    """Test FindingSeverity enum values"""
    assert FindingSeverity.INFO.value == "info"
    assert FindingSeverity.LOW.value == "low"
    assert FindingSeverity.MEDIUM.value == "medium"
    assert FindingSeverity.HIGH.value == "high"
    assert FindingSeverity.CRITICAL.value == "critical"

def test_finding_status_enum():
    """Test FindingStatus enum values"""
    assert FindingStatus.OPEN.value == "open"
    assert FindingStatus.SUPPRESSED.value == "suppressed"
    assert FindingStatus.FIXED.value == "fixed"

def test_event_kind_enum():
    """Test EventKind enum values"""
    assert EventKind.NEW_ASSET.value == "new_asset"
    assert EventKind.OPEN_PORT.value == "open_port"
    assert EventKind.NEW_CERT.value == "new_cert"
    assert EventKind.NEW_PATH.value == "new_path"
    assert EventKind.TECH_CHANGE.value == "tech_change"
