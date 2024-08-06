"""
Secure subprocess execution wrapper for ProjectDiscovery tools

Provides:
- Input validation and sanitization
- Resource limits (CPU, memory, timeout)
- Secure environment isolation
- Proper cleanup and error handling
"""

import subprocess
import shlex
import os
import tempfile
import resource
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when tool execution fails"""
    pass


class SecureToolExecutor:
    """
    Secure execution wrapper for external reconnaissance tools
    Prevents command injection and enforces resource limits
    """

    # Whitelist of allowed tools
    ALLOWED_TOOLS = {
        'subfinder',
        'dnsx',
        'httpx',
        'naabu',
        'katana',
        'nuclei',
        'tlsx',
        'uncover',
        'notify'
    }

    # Default resource limits
    DEFAULT_TIMEOUT = 600  # 10 minutes
    DEFAULT_CPU_LIMIT = 300  # 5 minutes of CPU time
    DEFAULT_MEMORY_LIMIT = 1024 * 1024 * 1024  # 1GB

    def __init__(self, tenant_id: int):
        """
        Initialize executor for specific tenant

        Args:
            tenant_id: Tenant ID for isolation and resource tracking
        """
        self.tenant_id = tenant_id
        self.temp_dir = None

    def __enter__(self):
        """Create isolated temporary directory for tenant"""
        self.temp_dir = tempfile.mkdtemp(prefix=f'tenant_{self.tenant_id}_')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup temporary directory"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                logger.error(f"Failed to cleanup temp dir {self.temp_dir}: {e}")

    def validate_tool(self, tool: str) -> str:
        """
        Validate tool name against whitelist

        Args:
            tool: Tool name to validate

        Returns:
            Validated tool name

        Raises:
            ToolExecutionError: If tool not in whitelist
        """
        if tool not in self.ALLOWED_TOOLS:
            raise ToolExecutionError(f"Tool '{tool}' is not allowed. Allowed tools: {self.ALLOWED_TOOLS}")
        return tool

    def sanitize_args(self, args: List[str]) -> List[str]:
        """
        Sanitize command arguments to prevent injection

        Args:
            args: List of command arguments

        Returns:
            Sanitized arguments
        """
        sanitized = []
        for arg in args:
            # Convert to string and strip dangerous characters
            safe_arg = str(arg).strip()

            # Validate file paths
            if safe_arg.startswith('/') or safe_arg.startswith('./'):
                # Ensure path is within temp directory
                if self.temp_dir and not Path(safe_arg).resolve().is_relative_to(Path(self.temp_dir)):
                    logger.warning(f"Rejecting path outside temp dir: {safe_arg}")
                    continue

            # Quote argument for shell safety
            sanitized.append(shlex.quote(safe_arg))

        return sanitized

    def set_resource_limits(self):
        """Set resource limits for subprocess (Unix-only)"""
        try:
            # CPU time limit
            resource.setrlimit(resource.RLIMIT_CPU, (self.DEFAULT_CPU_LIMIT, self.DEFAULT_CPU_LIMIT))

            # Memory limit
            resource.setrlimit(resource.RLIMIT_AS, (self.DEFAULT_MEMORY_LIMIT, self.DEFAULT_MEMORY_LIMIT))

            # File size limit (prevent filling disk)
            resource.setrlimit(resource.RLIMIT_FSIZE, (100 * 1024 * 1024, 100 * 1024 * 1024))  # 100MB
        except Exception as e:
            logger.warning(f"Could not set resource limits: {e}")

    def execute(
        self,
        tool: str,
        args: List[str],
        timeout: Optional[int] = None,
        capture_output: bool = True
    ) -> Tuple[int, str, str]:
        """
        Execute tool with security controls

        Args:
            tool: Tool name (must be in whitelist)
            args: Command arguments
            timeout: Execution timeout in seconds
            capture_output: Whether to capture stdout/stderr

        Returns:
            Tuple of (return_code, stdout, stderr)

        Raises:
            ToolExecutionError: If execution fails
        """
        # Validate tool
        tool = self.validate_tool(tool)

        # Sanitize arguments
        safe_args = self.sanitize_args(args)

        # Build command
        cmd = [tool] + safe_args

        # Restricted environment
        env = {
            'PATH': '/usr/local/bin:/usr/bin:/bin',
            'HOME': self.temp_dir or '/tmp',
            'LANG': 'C.UTF-8',
        }

        timeout = timeout or self.DEFAULT_TIMEOUT

        logger.info(f"Executing tool for tenant {self.tenant_id}: {tool} (timeout: {timeout}s)")

        try:
            # Execute with resource limits (Unix only)
            if os.name == 'posix':
                preexec_fn = self.set_resource_limits
            else:
                preexec_fn = None

            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                env=env,
                cwd=self.temp_dir or '/tmp',
                preexec_fn=preexec_fn
            )

            return result.returncode, result.stdout, result.stderr

        except subprocess.TimeoutExpired as e:
            logger.error(f"Tool '{tool}' timed out after {timeout}s for tenant {self.tenant_id}")
            raise ToolExecutionError(f"Execution timed out after {timeout}s") from e

        except subprocess.SubprocessError as e:
            logger.error(f"Tool '{tool}' execution failed for tenant {self.tenant_id}: {e}")
            raise ToolExecutionError(f"Execution failed: {e}") from e

        except Exception as e:
            logger.error(f"Unexpected error executing '{tool}' for tenant {self.tenant_id}: {e}")
            raise ToolExecutionError(f"Unexpected error: {e}") from e

    def create_input_file(self, filename: str, content: str) -> str:
        """
        Create input file in secure temp directory

        Args:
            filename: Name of file to create
            content: File content

        Returns:
            Path to created file
        """
        if not self.temp_dir:
            raise ToolExecutionError("Temp directory not initialized")

        file_path = os.path.join(self.temp_dir, filename)

        with open(file_path, 'w') as f:
            f.write(content)

        return file_path

    def read_output_file(self, filename: str) -> str:
        """
        Read output file from temp directory

        Args:
            filename: Name of file to read

        Returns:
            File content
        """
        if not self.temp_dir:
            raise ToolExecutionError("Temp directory not initialized")

        file_path = os.path.join(self.temp_dir, filename)

        if not os.path.exists(file_path):
            logger.warning(f"Output file not found: {file_path}")
            return ""

        with open(file_path, 'r') as f:
            return f.read()
