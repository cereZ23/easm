"""
Centralized logging configuration for EASM platform

Provides structured logging with support for both JSON and text formats.
Integrates with Sentry for error tracking in production.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging

    Outputs log records as JSON for easy parsing by log aggregation tools.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra fields from record
        if hasattr(record, 'tenant_id'):
            log_data['tenant_id'] = record.tenant_id
        if hasattr(record, 'asset_id'):
            log_data['asset_id'] = record.asset_id
        if hasattr(record, 'task_id'):
            log_data['task_id'] = record.task_id
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id

        return json.dumps(log_data)


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Optional[Path] = None,
    rotation_size: str = "100MB",
    retention_days: int = 30
) -> None:
    """
    Configure application logging

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type (json or text)
        log_file: Optional path to log file
        rotation_size: Size threshold for log rotation (e.g., "100MB")
        retention_days: Number of days to retain old logs
    """
    # Parse rotation size to bytes
    rotation_bytes = _parse_size(rotation_size)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    if log_format == "json":
        console_handler.setFormatter(JSONFormatter())
    else:
        console_formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)

    root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=rotation_bytes,
            backupCount=retention_days
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))

        if log_format == "json":
            file_handler.setFormatter(JSONFormatter())
        else:
            file_formatter = logging.Formatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)

        root_logger.addHandler(file_handler)

    # Silence noisy third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('celery').setLevel(logging.INFO)


def _parse_size(size_str: str) -> int:
    """
    Parse size string to bytes

    Args:
        size_str: Size string like "100MB", "1GB"

    Returns:
        Size in bytes
    """
    size_str = size_str.upper().strip()

    if size_str.endswith('GB'):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith('KB'):
        return int(size_str[:-2]) * 1024
    else:
        return int(size_str)


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance for a module

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class TenantLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds tenant context to all log messages

    Usage:
        logger = TenantLoggerAdapter(logging.getLogger(__name__), {'tenant_id': 123})
        logger.info("Processing discovery")  # Will include tenant_id in output
    """

    def process(self, msg, kwargs):
        """Add extra context to log record"""
        extra = kwargs.get('extra', {})
        extra.update(self.extra)
        kwargs['extra'] = extra
        return msg, kwargs


def setup_sentry(
    dsn: Optional[str] = None,
    environment: Optional[str] = None,
    traces_sample_rate: float = 0.1
) -> None:
    """
    Configure Sentry error tracking

    Args:
        dsn: Sentry DSN
        environment: Environment name (production, staging, etc.)
        traces_sample_rate: Sampling rate for performance traces (0.0 to 1.0)
    """
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.redis import RedisIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            integrations=[
                CeleryIntegration(),
                SqlalchemyIntegration(),
                RedisIntegration(),
            ],
            # Filter out sensitive data
            before_send=_filter_sensitive_data,
        )

        logging.info(f"Sentry initialized for environment: {environment}")
    except ImportError:
        logging.warning("Sentry SDK not installed, error tracking disabled")


def _filter_sensitive_data(event, hint):
    """
    Filter sensitive data from Sentry events

    Args:
        event: Sentry event dict
        hint: Event hint

    Returns:
        Filtered event or None to drop
    """
    # Remove sensitive environment variables
    if 'contexts' in event and 'environment' in event['contexts']:
        env = event['contexts']['environment']
        sensitive_keys = ['SECRET_KEY', 'JWT_SECRET_KEY', 'PASSWORD', 'API_KEY']
        for key in list(env.keys()):
            if any(sensitive in key.upper() for sensitive in sensitive_keys):
                env[key] = '[REDACTED]'

    return event
