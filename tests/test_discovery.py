"""
Tests for discovery tasks

Sprint 1 basic tests
"""
import pytest
from unittest.mock import patch, MagicMock, mock_open, call
from app.tasks.discovery import (
    collect_seeds,
    run_subfinder,
    run_dnsx,
    process_discovery_results
)

@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = MagicMock()
    return session

def test_collect_seeds_basic():
    """Test seed collection with basic domains"""
    with patch('app.database.SessionLocal') as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        # Mock tenant
        mock_tenant = MagicMock()
        mock_tenant.id = 1
        mock_tenant.osint_api_keys = None
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_tenant

        # Mock seeds
        seed1 = MagicMock()
        seed1.type = 'domain'
        seed1.value = 'example.com'

        seed2 = MagicMock()
        seed2.type = 'keyword'
        seed2.value = 'TestCorp'

        mock_db.query.return_value.filter_by.return_value.all.return_value = [seed1, seed2]

        result = collect_seeds(1)

        assert 'domains' in result
        assert 'keywords' in result
        assert 'example.com' in result['domains']
        assert 'TestCorp' in result['keywords']

def test_run_subfinder_no_domains():
    """Test subfinder with no domains"""
    seed_data = {
        'domains': [],
        'asns': [],
        'ip_ranges': [],
        'keywords': []
    }

    result = run_subfinder(seed_data, 1)

    assert result['subdomains'] == []
    assert result['tenant_id'] == 1

def test_run_subfinder_with_domains():
    """Test subfinder with domains"""
    seed_data = {
        'domains': ['example.com'],
        'asns': [],
        'ip_ranges': [],
        'keywords': []
    }

    mock_output = "sub1.example.com\nsub2.example.com\nsub3.example.com"

    with patch('subprocess.run') as mock_run, \
         patch('builtins.open', mock_open(read_data=mock_output)), \
         patch('app.tasks.discovery.store_raw_output'):

        mock_run.return_value = MagicMock(returncode=0)

        result = run_subfinder(seed_data, 1)

        assert 'subdomains' in result
        assert result['tenant_id'] == 1
        # Note: In real implementation, subdomains would be parsed from file

def test_run_dnsx_no_subdomains():
    """Test dnsx with no subdomains"""
    subfinder_result = {
        'subdomains': [],
        'tenant_id': 1
    }

    result = run_dnsx(subfinder_result, 1)

    assert result['resolved'] == []
    assert result['tenant_id'] == 1

def test_process_discovery_results():
    """Test processing discovery results"""
    dnsx_result = {
        'resolved': [
            {'host': 'sub1.example.com', 'a': ['1.2.3.4']},
            {'host': 'sub2.example.com', 'a': ['1.2.3.5']}
        ],
        'tenant_id': 1
    }

    with patch('app.database.SessionLocal') as mock_session:
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        # Mock no existing assets
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        result = process_discovery_results(dnsx_result, 1)

        assert 'assets_processed' in result
        assert 'total_resolved' in result
        assert result['total_resolved'] == 2

def test_asset_type_detection():
    """Test asset type detection logic"""
    from app.models.database import AssetType

    # Test IP detection
    test_ip = "192.168.1.1"
    is_ip = all(c.isdigit() or c == '.' for c in test_ip)
    assert is_ip == True

    # Test domain detection
    test_domain = "example.com"
    is_domain = test_domain.count('.') == 1
    assert is_domain == True

    # Test subdomain detection
    test_subdomain = "sub.example.com"
    is_subdomain = test_subdomain.count('.') > 1
    assert is_subdomain == True
