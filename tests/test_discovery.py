"""
Tests for discovery tasks

Sprint 1 basic tests + Sprint 1.7 Amass tests
"""
import pytest
from unittest.mock import patch, MagicMock, mock_open, call
from app.tasks.discovery import (
    collect_seeds,
    run_subfinder,
    run_dnsx,
    process_discovery_results,
    run_amass,
    merge_discovery_results,
    run_parallel_enumeration
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

# ==================== Sprint 1.7 - Amass Tests ====================

def test_run_amass_no_domains():
    """Test Amass with no domains"""
    seed_data = {
        'domains': [],
        'asns': [],
        'ip_ranges': [],
        'keywords': []
    }

    result = run_amass(seed_data, 1)

    assert result['subdomains'] == []
    assert result['tenant_id'] == 1
    assert result['source'] == 'amass'

def test_run_amass_disabled():
    """Test Amass when disabled via configuration"""
    seed_data = {
        'domains': ['example.com'],
        'asns': [],
        'ip_ranges': [],
        'keywords': []
    }

    with patch('app.tasks.discovery.settings') as mock_settings:
        mock_settings.discovery_amass_enabled = False

        result = run_amass(seed_data, 1)

        assert result['subdomains'] == []
        assert result['tenant_id'] == 1
        assert result['source'] == 'amass'
        assert result.get('skipped') == True

def test_run_amass_with_domains():
    """Test Amass with domains - using SecureToolExecutor"""
    seed_data = {
        'domains': ['example.com'],
        'asns': [],
        'ip_ranges': [],
        'keywords': []
    }

    # Mock Amass JSONL output
    mock_amass_output = '''{"name": "sub1.example.com", "domain": "example.com"}
{"name": "sub2.example.com", "domain": "example.com"}
{"name": "sub3.example.com", "domain": "example.com"}'''

    with patch('app.utils.secure_executor.SecureToolExecutor') as MockExecutor, \
         patch('app.tasks.discovery.settings') as mock_settings, \
         patch('app.tasks.discovery.store_raw_output'):

        mock_settings.discovery_amass_enabled = True
        mock_settings.discovery_amass_timeout = 900

        # Setup mock executor
        mock_executor_instance = MagicMock()
        MockExecutor.return_value.__enter__.return_value = mock_executor_instance
        mock_executor_instance.create_input_file.return_value = 'domains.txt'
        mock_executor_instance.execute.return_value = (0, '', '')
        mock_executor_instance.read_output_file.return_value = mock_amass_output

        result = run_amass(seed_data, 1)

        assert 'subdomains' in result
        assert result['tenant_id'] == 1
        assert result['source'] == 'amass'
        assert len(result['subdomains']) == 3
        assert 'sub1.example.com' in result['subdomains']
        assert 'sub2.example.com' in result['subdomains']
        assert 'sub3.example.com' in result['subdomains']

def test_merge_discovery_results_no_overlap():
    """Test merging results with no overlap between Subfinder and Amass"""
    subfinder_result = {
        'subdomains': ['sub1.example.com', 'sub2.example.com'],
        'tenant_id': 1
    }

    amass_result = {
        'subdomains': ['sub3.example.com', 'sub4.example.com'],
        'tenant_id': 1,
        'source': 'amass'
    }

    with patch('app.tasks.discovery.store_raw_output'):
        result = merge_discovery_results(subfinder_result, amass_result, 1)

    assert result['tenant_id'] == 1
    assert len(result['subdomains']) == 4
    assert 'stats' in result
    assert result['stats']['subfinder'] == 2
    assert result['stats']['amass'] == 2
    assert result['stats']['total'] == 4
    assert result['stats']['overlap'] == 0
    assert result['stats']['unique_to_amass'] == 2

def test_merge_discovery_results_with_overlap():
    """Test merging results with overlap (duplicates) between tools"""
    subfinder_result = {
        'subdomains': ['sub1.example.com', 'sub2.example.com', 'sub3.example.com'],
        'tenant_id': 1
    }

    amass_result = {
        'subdomains': ['sub2.example.com', 'sub3.example.com', 'sub4.example.com'],
        'tenant_id': 1,
        'source': 'amass'
    }

    with patch('app.tasks.discovery.store_raw_output'):
        result = merge_discovery_results(subfinder_result, amass_result, 1)

    assert result['tenant_id'] == 1
    assert len(result['subdomains']) == 4  # sub1, sub2, sub3, sub4 (deduplicated)
    assert 'stats' in result
    assert result['stats']['subfinder'] == 3
    assert result['stats']['amass'] == 3
    assert result['stats']['total'] == 4
    assert result['stats']['overlap'] == 2  # sub2 and sub3
    assert result['stats']['unique_to_amass'] == 1  # sub4

def test_merge_discovery_results_all_overlap():
    """Test merging when Amass finds nothing new (all overlap)"""
    subfinder_result = {
        'subdomains': ['sub1.example.com', 'sub2.example.com'],
        'tenant_id': 1
    }

    amass_result = {
        'subdomains': ['sub1.example.com', 'sub2.example.com'],
        'tenant_id': 1,
        'source': 'amass'
    }

    with patch('app.tasks.discovery.store_raw_output'):
        result = merge_discovery_results(subfinder_result, amass_result, 1)

    assert result['tenant_id'] == 1
    assert len(result['subdomains']) == 2
    assert result['stats']['overlap'] == 2
    assert result['stats']['unique_to_amass'] == 0

def test_run_parallel_enumeration_amass_enabled():
    """Test parallel enumeration with Amass enabled"""
    seed_data = {
        'domains': ['example.com'],
        'asns': [],
        'ip_ranges': [],
        'keywords': []
    }

    subfinder_result = {'subdomains': ['sub1.example.com', 'sub2.example.com'], 'tenant_id': 1}
    amass_result = {'subdomains': ['sub2.example.com', 'sub3.example.com'], 'tenant_id': 1, 'source': 'amass'}
    merged_result = {
        'subdomains': ['sub1.example.com', 'sub2.example.com', 'sub3.example.com'],
        'tenant_id': 1,
        'stats': {'total': 3, 'subfinder': 2, 'amass': 2, 'overlap': 1, 'unique_to_amass': 1}
    }

    with patch('app.tasks.discovery.settings') as mock_settings, \
         patch('celery.group') as mock_group, \
         patch('app.tasks.discovery.merge_discovery_results') as mock_merge:

        mock_settings.discovery_amass_enabled = True

        # Mock Celery group to return results directly without Celery execution
        mock_async_result = MagicMock()
        mock_async_result.get.return_value = [subfinder_result, amass_result]
        mock_job = MagicMock()
        mock_job.apply_async.return_value = mock_async_result
        mock_group.return_value = mock_job

        # Mock merge
        mock_merge.return_value = merged_result

        result = run_parallel_enumeration(seed_data, 1)

        assert result['tenant_id'] == 1
        assert len(result['subdomains']) == 3
        assert 'stats' in result
        assert result['stats']['total'] == 3

def test_run_parallel_enumeration_amass_disabled():
    """Test parallel enumeration falls back to Subfinder when Amass disabled"""
    seed_data = {
        'domains': ['example.com'],
        'asns': [],
        'ip_ranges': [],
        'keywords': []
    }

    subfinder_result = {'subdomains': ['sub1.example.com', 'sub2.example.com'], 'tenant_id': 1}

    with patch('app.tasks.discovery.settings') as mock_settings, \
         patch('app.tasks.discovery.run_subfinder') as mock_subfinder:

        mock_settings.discovery_amass_enabled = False
        mock_subfinder.return_value = subfinder_result

        result = run_parallel_enumeration(seed_data, 1)

        assert result['subdomains'] == ['sub1.example.com', 'sub2.example.com']
        assert result['tenant_id'] == 1
        # Should call run_subfinder directly
        mock_subfinder.assert_called_once_with(seed_data, 1)

# ==================== Sprint 1.7 - Integration Tests ====================

def test_amass_in_allowed_tools_whitelist():
    """CRITICAL: Verify Amass is in the allowed tools whitelist

    This test ensures Amass can actually be executed by SecureToolExecutor.
    If this test fails, all Amass executions will fail in production.
    """
    from app.config import settings

    assert 'amass' in settings.tool_allowed_tools, \
        "Amass must be in tool_allowed_tools whitelist for SecureToolExecutor to allow execution"
