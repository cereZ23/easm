"""
Security audit logging for EASM Platform

Logs all security-relevant events:
- Authentication attempts (success/failure)
- Authorization failures
- Data modifications
- Suspicious activity
- Configuration changes

OWASP References:
- A09:2021 - Security Logging and Monitoring Failures
- API10:2023 - Unsafe Consumption of APIs
"""

import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Text, Index, Boolean
from sqlalchemy.dialects.postgresql import JSONB

from app.database import get_db
from app.models.database import Base

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Security audit event types"""

    # Authentication events
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_TOKEN_REFRESH = "auth.token.refresh"
    AUTH_TOKEN_REVOKE = "auth.token.revoke"
    AUTH_PASSWORD_CHANGE = "auth.password.change"
    AUTH_PASSWORD_RESET = "auth.password.reset"

    # Authorization events
    AUTHZ_ACCESS_DENIED = "authz.access.denied"
    AUTHZ_PERMISSION_DENIED = "authz.permission.denied"
    AUTHZ_TENANT_VIOLATION = "authz.tenant.violation"

    # API Key events
    API_KEY_CREATE = "api_key.create"
    API_KEY_DELETE = "api_key.delete"
    API_KEY_USE = "api_key.use"
    API_KEY_INVALID = "api_key.invalid"

    # Data modification events
    DATA_CREATE = "data.create"
    DATA_UPDATE = "data.update"
    DATA_DELETE = "data.delete"
    DATA_EXPORT = "data.export"

    # Suspicious activity
    SUSPICIOUS_RATE_LIMIT = "suspicious.rate_limit"
    SUSPICIOUS_BRUTE_FORCE = "suspicious.brute_force"
    SUSPICIOUS_SQL_INJECTION = "suspicious.sql_injection"
    SUSPICIOUS_XSS = "suspicious.xss"
    SUSPICIOUS_SSRF = "suspicious.ssrf"
    SUSPICIOUS_PATH_TRAVERSAL = "suspicious.path_traversal"

    # Configuration changes
    CONFIG_CHANGE = "config.change"
    USER_CREATE = "user.create"
    USER_DELETE = "user.delete"
    USER_ROLE_CHANGE = "user.role.change"

    # System events
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"


class AuditLog(Base):
    """
    Audit log model for security events

    Stores all security-relevant events for compliance and forensics.
    """

    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)

    # Actor information
    user_id = Column(Integer, index=True)
    tenant_id = Column(Integer, index=True)
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(Text)

    # Event details
    action = Column(String(255), nullable=False)
    resource = Column(String(255))
    resource_id = Column(String(255))
    result = Column(String(50), nullable=False)  # success, failure, denied

    # Additional context
    details = Column(JSONB)  # Structured event data
    error_message = Column(Text)

    # Severity
    severity = Column(String(20), nullable=False)  # info, warning, critical

    # Request context
    request_id = Column(String(100))
    endpoint = Column(String(255))
    method = Column(String(10))

    __table_args__ = (
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_tenant_timestamp', 'tenant_id', 'timestamp'),
        Index('idx_audit_event_timestamp', 'event_type', 'timestamp'),
        Index('idx_audit_severity_timestamp', 'severity', 'timestamp'),
        Index('idx_audit_result', 'result'),
    )

    def __repr__(self):
        return (
            f"<AuditLog(id={self.id}, timestamp={self.timestamp}, "
            f"event_type='{self.event_type}', action='{self.action}', result='{self.result}')>"
        )


def log_audit_event(
    event_type: AuditEventType,
    action: str,
    result: str,
    user_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    resource: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    severity: str = "info",
    request_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    method: Optional[str] = None
):
    """
    Log a security audit event

    Args:
        event_type: Type of event (from AuditEventType enum)
        action: Human-readable action description
        result: Result of action (success, failure, denied)
        user_id: User ID (if authenticated)
        tenant_id: Tenant ID (if applicable)
        ip_address: Client IP address
        user_agent: User agent string
        resource: Resource type (user, asset, finding, etc.)
        resource_id: Resource identifier
        details: Additional structured data
        error_message: Error message (if failure)
        severity: Event severity (info, warning, critical)
        request_id: Request trace ID
        endpoint: API endpoint
        method: HTTP method

    Security:
        - All events are immutable (append-only)
        - Sensitive data is sanitized before logging
        - Events are indexed for efficient querying
        - Retention policy enforced at database level
    """

    # Sanitize details to prevent log injection
    if details:
        details = sanitize_log_data(details)

    # Sanitize error message
    if error_message:
        error_message = sanitize_log_string(error_message)

    # Create audit log entry
    audit_entry = AuditLog(
        timestamp=datetime.utcnow(),
        event_type=event_type.value,
        user_id=user_id,
        tenant_id=tenant_id,
        ip_address=ip_address,
        user_agent=sanitize_log_string(user_agent) if user_agent else None,
        action=action,
        resource=resource,
        resource_id=str(resource_id) if resource_id else None,
        result=result,
        details=details,
        error_message=error_message,
        severity=severity,
        request_id=request_id,
        endpoint=endpoint,
        method=method
    )

    try:
        # Write to database (async)
        db = next(get_db())
        db.add(audit_entry)
        db.commit()

        # Also log to application logger for real-time monitoring
        log_level = {
            "info": logging.INFO,
            "warning": logging.WARNING,
            "critical": logging.CRITICAL
        }.get(severity, logging.INFO)

        logger.log(
            log_level,
            f"AUDIT: {event_type.value} - {action} - {result}",
            extra={
                "event_type": event_type.value,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "ip_address": ip_address,
                "resource": resource,
                "resource_id": resource_id,
                "result": result,
                "severity": severity
            }
        )

    except Exception as e:
        # Never fail the application due to audit logging
        logger.error(f"Failed to write audit log: {e}", exc_info=True)


def sanitize_log_string(s: str, max_length: int = 1000) -> str:
    """
    Sanitize string for safe logging

    Args:
        s: String to sanitize
        max_length: Maximum length

    Returns:
        Sanitized string

    Security:
        - Removes control characters
        - Truncates long strings
        - Prevents log injection
    """
    if not s:
        return ""

    # Remove control characters except newline/tab
    s = ''.join(char for char in s if ord(char) >= 32 or char in '\n\t')

    # Truncate if too long
    if len(s) > max_length:
        s = s[:max_length] + "...[truncated]"

    # Escape newlines to prevent log injection
    s = s.replace('\n', '\\n').replace('\r', '\\r')

    return s


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize dictionary data for logging

    Args:
        data: Dictionary to sanitize

    Returns:
        Sanitized dictionary

    Security:
        - Removes sensitive fields (passwords, tokens, keys)
        - Truncates long values
        - Prevents object injection
    """
    if not isinstance(data, dict):
        return {}

    # Fields to redact
    sensitive_fields = {
        'password', 'secret', 'token', 'api_key', 'private_key',
        'access_token', 'refresh_token', 'authorization', 'cookie',
        'session', 'csrf_token', 'jwt'
    }

    sanitized = {}
    for key, value in data.items():
        # Redact sensitive fields
        if any(sensitive in key.lower() for sensitive in sensitive_fields):
            sanitized[key] = "[REDACTED]"
            continue

        # Recursively sanitize nested dicts
        if isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)
        # Sanitize strings
        elif isinstance(value, str):
            sanitized[key] = sanitize_log_string(value, max_length=500)
        # Truncate lists
        elif isinstance(value, list):
            if len(value) > 100:
                sanitized[key] = value[:100] + ["...[truncated]"]
            else:
                sanitized[key] = value
        # Keep primitives
        else:
            sanitized[key] = value

    return sanitized


def log_authentication_attempt(
    success: bool,
    username: str,
    ip_address: str,
    user_agent: Optional[str] = None,
    error_message: Optional[str] = None,
    user_id: Optional[int] = None,
    tenant_id: Optional[int] = None
):
    """
    Log authentication attempt

    Args:
        success: Whether authentication succeeded
        username: Username attempted
        ip_address: Client IP
        user_agent: User agent string
        error_message: Error message if failed
        user_id: User ID if successful
        tenant_id: Tenant ID if successful
    """
    log_audit_event(
        event_type=AuditEventType.AUTH_LOGIN_SUCCESS if success else AuditEventType.AUTH_LOGIN_FAILURE,
        action=f"User login: {username}",
        result="success" if success else "failure",
        user_id=user_id,
        tenant_id=tenant_id,
        ip_address=ip_address,
        user_agent=user_agent,
        resource="user",
        resource_id=username,
        error_message=error_message,
        severity="info" if success else "warning"
    )


def log_authorization_failure(
    user_id: int,
    tenant_id: int,
    action: str,
    resource: str,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    reason: Optional[str] = None
):
    """
    Log authorization failure

    Args:
        user_id: User ID
        tenant_id: Tenant ID
        action: Action attempted
        resource: Resource type
        resource_id: Resource ID
        ip_address: Client IP
        reason: Reason for denial
    """
    log_audit_event(
        event_type=AuditEventType.AUTHZ_PERMISSION_DENIED,
        action=action,
        result="denied",
        user_id=user_id,
        tenant_id=tenant_id,
        ip_address=ip_address,
        resource=resource,
        resource_id=resource_id,
        error_message=reason,
        severity="warning"
    )


def log_suspicious_activity(
    event_type: AuditEventType,
    description: str,
    ip_address: str,
    details: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    tenant_id: Optional[int] = None
):
    """
    Log suspicious activity

    Args:
        event_type: Type of suspicious activity
        description: Description of activity
        ip_address: Client IP
        details: Additional details
        user_id: User ID if known
        tenant_id: Tenant ID if applicable
    """
    log_audit_event(
        event_type=event_type,
        action=description,
        result="blocked",
        user_id=user_id,
        tenant_id=tenant_id,
        ip_address=ip_address,
        details=details,
        severity="critical"
    )


def log_data_modification(
    action: str,
    resource: str,
    resource_id: str,
    user_id: int,
    tenant_id: int,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
):
    """
    Log data modification

    Args:
        action: Action performed (create, update, delete)
        resource: Resource type
        resource_id: Resource ID
        user_id: User ID
        tenant_id: Tenant ID
        ip_address: Client IP
        details: Change details
    """
    event_type_map = {
        "create": AuditEventType.DATA_CREATE,
        "update": AuditEventType.DATA_UPDATE,
        "delete": AuditEventType.DATA_DELETE,
    }

    log_audit_event(
        event_type=event_type_map.get(action, AuditEventType.DATA_UPDATE),
        action=f"{action.capitalize()} {resource}",
        result="success",
        user_id=user_id,
        tenant_id=tenant_id,
        ip_address=ip_address,
        resource=resource,
        resource_id=resource_id,
        details=details,
        severity="info"
    )


def get_audit_logs(
    user_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    event_type: Optional[AuditEventType] = None,
    severity: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Query audit logs

    Args:
        user_id: Filter by user ID
        tenant_id: Filter by tenant ID
        event_type: Filter by event type
        severity: Filter by severity
        start_time: Filter by start time
        end_time: Filter by end time
        limit: Maximum results
        offset: Result offset

    Returns:
        List of audit log entries
    """
    db = next(get_db())
    query = db.query(AuditLog)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if tenant_id:
        query = query.filter(AuditLog.tenant_id == tenant_id)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type.value)
    if severity:
        query = query.filter(AuditLog.severity == severity)
    if start_time:
        query = query.filter(AuditLog.timestamp >= start_time)
    if end_time:
        query = query.filter(AuditLog.timestamp <= end_time)

    query = query.order_by(AuditLog.timestamp.desc())
    query = query.limit(limit).offset(offset)

    return query.all()
