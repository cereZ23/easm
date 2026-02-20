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

from app.config import settings

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when tool execution fails"""
    pass


class SecureToolExecutor:
    """
    Secure execution wrapper for external reconnaissance tools
    Prevents command injection and enforces resource limits
    """

    # Default resource limits
    DEFAULT_TIMEOUT = 300  # 5 minutes
    DEFAULT_CPU_LIMIT = 600  # 10 minutes CPU time
    DEFAULT_MEMORY_LIMIT = 8 * 1024 * 1024 * 1024  # 8GB (increased for Nuclei)
    DEFAULT_FILE_SIZE_LIMIT = 100 * 1024 * 1024  # 100MB

    def __init__(self, tenant_id: int):
        """
        Initialize executor for specific tenant

        Args:
            tenant_id: Tenant ID for isolation and resource tracking
        """
        self.tenant_id = tenant_id
        self.temp_dir: Optional[Path] = None
        self.allowed_tools = settings.tool_allowed_tools
        self.timeout = settings.tool_execution_timeout
        self.max_output_size = settings.tool_execution_max_output_size

    def __enter__(self):
        """Create isolated temporary directory for tenant"""
        if settings.tool_temp_dir:
            settings.tool_temp_dir.mkdir(parents=True, exist_ok=True)
            self.temp_dir = Path(tempfile.mkdtemp(
                prefix=f'tenant_{self.tenant_id}_',
                dir=settings.tool_temp_dir
            ))
        else:
            self.temp_dir = Path(tempfile.mkdtemp(prefix=f'tenant_{self.tenant_id}_'))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup temporary directory"""
        if self.temp_dir and self.temp_dir.exists():
            try:
                import shutil
                shutil.rmtree(self.temp_dir)
                logger.debug(f"Cleaned up temp dir: {self.temp_dir}")
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
        if tool not in self.allowed_tools:
            raise ToolExecutionError(f"Tool '{tool}' is not allowed. Allowed tools: {self.allowed_tools}")
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

            # Block command injection attempts
            dangerous_chars = [';', '&', '|', '$', '`', '\n', '\r']
            if any(char in safe_arg for char in dangerous_chars):
                logger.warning(f"Rejecting argument with dangerous characters: {safe_arg}")
                continue

            # Validate file paths
            if safe_arg.startswith('/') or safe_arg.startswith('./'):
                # Ensure path is within temp directory
                try:
                    arg_path = Path(safe_arg).resolve()
                    if self.temp_dir and not arg_path.is_relative_to(self.temp_dir):
                        logger.warning(f"Rejecting path outside temp dir: {safe_arg}")
                        continue
                except (ValueError, OSError) as e:
                    logger.warning(f"Invalid path: {safe_arg} - {e}")
                    continue

            sanitized.append(safe_arg)

        return sanitized

    def set_resource_limits(self):
        """Set resource limits for subprocess (Unix-only)"""
        try:
            # CPU time limit
            resource.setrlimit(resource.RLIMIT_CPU, (self.DEFAULT_CPU_LIMIT, self.DEFAULT_CPU_LIMIT))

            # Memory limit
            resource.setrlimit(resource.RLIMIT_AS, (self.DEFAULT_MEMORY_LIMIT, self.DEFAULT_MEMORY_LIMIT))

            # File size limit (prevent filling disk)
            resource.setrlimit(resource.RLIMIT_FSIZE, (self.DEFAULT_FILE_SIZE_LIMIT, self.DEFAULT_FILE_SIZE_LIMIT))
        except Exception as e:
            logger.warning(f"Could not set resource limits: {e}")

    def execute(
        self,
        tool: str,
        args: List[str],
        timeout: Optional[int] = None,
        capture_output: bool = True,
        stdin_data: Optional[str] = None
    ) -> Tuple[int, str, str]:
        """
        Execute tool with security controls

        Args:
            tool: Tool name (must be in whitelist)
            args: Command arguments
            timeout: Execution timeout in seconds
            capture_output: Whether to capture stdout/stderr
            stdin_data: Optional data to pass to stdin

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

        # Restricted environment (include /usr/local/pd-tools for ProjectDiscovery tools)
        env = {
            'PATH': '/usr/local/pd-tools:/usr/local/bin:/usr/bin:/bin',
            'HOME': str(self.temp_dir) if self.temp_dir else '/tmp',
            'LANG': 'C.UTF-8',
        }

        timeout = timeout or self.timeout

        logger.info(f"Executing tool for tenant {self.tenant_id}: {tool} (timeout: {timeout}s)")

        try:
            # Execute with resource limits (Unix only)
            if os.name == 'posix':
                preexec_fn = self.set_resource_limits
            else:
                preexec_fn = None

            result = subprocess.run(
                cmd,
                input=stdin_data,  # Pass stdin data if provided
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                env=env,
                cwd=str(self.temp_dir) if self.temp_dir else '/tmp',
                preexec_fn=preexec_fn,
                shell=False  # CRITICAL: Never use shell=True
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

        Raises:
            ToolExecutionError: If temp directory not initialized
        """
        if not self.temp_dir:
            raise ToolExecutionError("Temp directory not initialized")

        # Sanitize filename to prevent path traversal
        safe_filename = Path(filename).name
        file_path = self.temp_dir / safe_filename

        try:
            file_path.write_text(content, encoding='utf-8')
            logger.debug(f"Created input file: {file_path}")
            return str(file_path)
        except Exception as e:
            raise ToolExecutionError(f"Failed to create input file: {e}") from e

    def read_output_file(self, filename: str) -> str:
        """
        Read output file from temp directory

        Args:
            filename: Name of file to read

        Returns:
            File content

        Raises:
            ToolExecutionError: If temp directory not initialized
        """
        if not self.temp_dir:
            raise ToolExecutionError("Temp directory not initialized")

        # Sanitize filename to prevent path traversal
        safe_filename = Path(filename).name
        file_path = self.temp_dir / safe_filename

        if not file_path.exists():
            logger.warning(f"Output file not found: {file_path}")
            return ""

        try:
            # Check file size to prevent reading huge files
            file_size = file_path.stat().st_size
            if file_size > self.max_output_size:
                raise ToolExecutionError(
                    f"Output file too large: {file_size} bytes (max: {self.max_output_size})"
                )

            content = file_path.read_text(encoding='utf-8')
            logger.debug(f"Read output file: {file_path} ({file_size} bytes)")
            return content
        except UnicodeDecodeError:
            logger.error(f"Failed to decode output file: {file_path}")
            return ""
        except Exception as e:
            raise ToolExecutionError(f"Failed to read output file: {e}") from e
