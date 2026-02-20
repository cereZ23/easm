"""
Enhanced input validation with security controls

Pydantic validators for:
- Domain validation (SSRF prevention)
- URL validation (SSRF prevention)
- IP address validation (block internal IPs)
- String sanitization (XSS prevention)
- Integer bounds checking
- Enum validation

OWASP References:
- A03:2021 - Injection
- A10:2023 - Server-Side Request Forgery (SSRF)
"""

import re
import ipaddress
from typing import Optional, List, Union
from urllib.parse import urlparse
import html

from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum

from app.utils.validators import DomainValidator, URLValidator


# ===========================
# Enums
# ===========================

class AssetType(str, Enum):
    """Asset types in EASM platform"""
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP = "ip"
    URL = "url"
    SERVICE = "service"


class SeverityLevel(str, Enum):
    """Finding severity levels"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScanStatus(str, Enum):
    """Scan status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class UserRole(str, Enum):
    """User roles"""
    ADMIN = "admin"
    USER = "user"
    READ_ONLY = "read-only"


# ===========================
# Base Validators
# ===========================

def validate_identifier(identifier: str) -> str:
    """
    Validate asset identifier (domain, IP, URL)

    Args:
        identifier: Asset identifier

    Returns:
        Validated identifier

    Raises:
        ValueError: If identifier is invalid or dangerous

    Security:
        - Prevents SSRF attacks
        - Blocks internal IPs
        - Validates format
    """
    if not identifier:
        raise ValueError("Identifier cannot be empty")

    identifier = identifier.strip().lower()

    # Check length
    if len(identifier) > 2048:
        raise ValueError("Identifier too long (max 2048 characters)")

    # Try to parse as URL first
    if identifier.startswith(('http://', 'https://')):
        is_valid, error = URLValidator.validate_url(identifier)
        if not is_valid:
            raise ValueError(f"Invalid URL: {error}")
        return identifier

    # Try to parse as IP address
    try:
        ip = ipaddress.ip_address(identifier)

        # Block private/internal IPs
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError("Internal/private IP addresses not allowed")

        # Block multicast and reserved
        if ip.is_multicast or ip.is_reserved:
            raise ValueError("Multicast/reserved IP addresses not allowed")

        return str(ip)

    except ValueError:
        # Not an IP, try domain
        pass

    # Validate as domain
    is_valid, error = DomainValidator.validate_domain(identifier, allow_wildcards=True)
    if not is_valid:
        raise ValueError(f"Invalid domain: {error}")

    return identifier


def sanitize_string(s: str, max_length: int = 1000) -> str:
    """
    Sanitize string input

    Args:
        s: String to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string

    Security:
        - HTML escapes (XSS prevention)
        - Removes control characters
        - Truncates long strings
    """
    if not s:
        return ""

    # Remove control characters
    s = ''.join(char for char in s if ord(char) >= 32 or char in '\n\r\t')

    # Truncate if too long
    if len(s) > max_length:
        s = s[:max_length]

    # HTML escape for XSS prevention
    s = html.escape(s)

    return s


def validate_integer_bounds(value: int, min_val: int = 0, max_val: int = 1000000) -> int:
    """
    Validate integer is within bounds

    Args:
        value: Integer value
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Validated integer

    Raises:
        ValueError: If out of bounds
    """
    if value < min_val:
        raise ValueError(f"Value must be >= {min_val}")
    if value > max_val:
        raise ValueError(f"Value must be <= {max_val}")
    return value


# ===========================
# Request Models
# ===========================

class SeedCreate(BaseModel):
    """Create seed (root domain, ASN, IP range)"""

    identifier: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., regex=r'^(domain|asn|ip_range|cidr)$')
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = Field(default_factory=list, max_items=20)

    @validator('identifier')
    def validate_identifier_field(cls, v, values):
        """Validate identifier based on type"""
        seed_type = values.get('type')

        if seed_type == 'domain':
            is_valid, error = DomainValidator.validate_domain(v)
            if not is_valid:
                raise ValueError(f"Invalid domain: {error}")
        elif seed_type == 'asn':
            # Validate ASN format (ASN12345 or AS12345)
            if not re.match(r'^AS(N)?[0-9]+$', v, re.IGNORECASE):
                raise ValueError("Invalid ASN format (use ASN12345 or AS12345)")
        elif seed_type in ['ip_range', 'cidr']:
            # Validate CIDR notation
            try:
                network = ipaddress.ip_network(v, strict=False)
                # Block private ranges
                if network.is_private:
                    raise ValueError("Private IP ranges not allowed")
            except ValueError as e:
                raise ValueError(f"Invalid IP range/CIDR: {e}")

        return v.strip().lower()

    @validator('description')
    def sanitize_description(cls, v):
        """Sanitize description"""
        if v:
            return sanitize_string(v, max_length=1000)
        return v

    @validator('tags')
    def validate_tags(cls, v):
        """Validate and sanitize tags"""
        if not v:
            return []

        # Limit number of tags
        if len(v) > 20:
            raise ValueError("Maximum 20 tags allowed")

        # Sanitize each tag
        sanitized_tags = []
        for tag in v:
            if not tag or not isinstance(tag, str):
                continue
            # Remove special characters, keep alphanumeric and hyphens
            tag = re.sub(r'[^a-zA-Z0-9-_]', '', tag.strip())
            if len(tag) > 50:
                tag = tag[:50]
            if tag:
                sanitized_tags.append(tag.lower())

        return sanitized_tags


class AssetCreate(BaseModel):
    """Create asset"""

    identifier: str = Field(..., min_length=1, max_length=2048)
    type: AssetType
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Optional[dict] = Field(default_factory=dict)

    @validator('identifier')
    def validate_identifier_field(cls, v):
        """Validate identifier"""
        return validate_identifier(v)

    @validator('metadata')
    def validate_metadata(cls, v):
        """Validate metadata doesn't contain sensitive keys"""
        if not v:
            return {}

        # Limit size
        if len(v) > 100:
            raise ValueError("Metadata can have maximum 100 keys")

        # Check for sensitive keys (shouldn't be in metadata)
        sensitive_keys = {'password', 'secret', 'token', 'api_key', 'private_key'}
        for key in v.keys():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                raise ValueError(f"Metadata cannot contain sensitive key: {key}")

        return v


class AssetUpdate(BaseModel):
    """Update asset"""

    metadata: Optional[dict] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None

    @validator('metadata')
    def validate_metadata(cls, v):
        """Validate metadata"""
        if v is None:
            return None

        if len(v) > 100:
            raise ValueError("Metadata can have maximum 100 keys")

        return v


class FindingCreate(BaseModel):
    """Create finding"""

    template_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=500)
    severity: SeverityLevel
    description: Optional[str] = Field(None, max_length=5000)
    evidence: Optional[str] = Field(None, max_length=10000)
    cvss_score: Optional[float] = Field(None, ge=0.0, le=10.0)
    cve_ids: Optional[List[str]] = Field(default_factory=list, max_items=50)

    @validator('template_id', 'name')
    def sanitize_text_fields(cls, v):
        """Sanitize text fields"""
        return sanitize_string(v, max_length=500)

    @validator('description', 'evidence')
    def sanitize_long_text_fields(cls, v):
        """Sanitize long text fields"""
        if v:
            return sanitize_string(v, max_length=10000)
        return v

    @validator('cve_ids')
    def validate_cve_ids(cls, v):
        """Validate CVE IDs"""
        if not v:
            return []

        validated = []
        for cve_id in v:
            # Validate CVE format (CVE-YYYY-NNNNN)
            if re.match(r'^CVE-\d{4}-\d{4,7}$', cve_id, re.IGNORECASE):
                validated.append(cve_id.upper())
            else:
                raise ValueError(f"Invalid CVE ID format: {cve_id}")

        return validated


class ScanCreate(BaseModel):
    """Create scan"""

    target_type: str = Field(..., regex=r'^(tenant|asset|domain)$')
    target_id: Union[int, str] = Field(...)
    scan_type: str = Field(..., regex=r'^(discovery|enrichment|vulnerability)$')
    priority: Optional[int] = Field(default=5, ge=1, le=10)
    options: Optional[dict] = Field(default_factory=dict)

    @validator('target_id')
    def validate_target_id(cls, v, values):
        """Validate target ID"""
        target_type = values.get('target_type')

        if target_type in ['tenant']:
            # Must be integer
            if not isinstance(v, int):
                raise ValueError("Tenant ID must be an integer")
            return validate_integer_bounds(v, min_val=1, max_val=1000000)
        else:
            # Can be string (domain, asset identifier)
            if isinstance(v, str):
                return sanitize_string(v, max_length=255)
            elif isinstance(v, int):
                return validate_integer_bounds(v, min_val=1, max_val=1000000)

        return v

    @validator('options')
    def validate_options(cls, v):
        """Validate scan options"""
        if not v:
            return {}

        # Limit options size
        if len(v) > 50:
            raise ValueError("Maximum 50 scan options allowed")

        # Validate specific option values
        allowed_options = {
            'rate_limit', 'timeout', 'depth', 'threads',
            'follow_redirects', 'verify_ssl', 'user_agent'
        }

        for key in v.keys():
            if key not in allowed_options:
                raise ValueError(f"Unknown scan option: {key}")

        return v


class UserCreate(BaseModel):
    """Create user"""

    email: str = Field(..., regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    username: str = Field(..., min_length=3, max_length=100, regex=r'^[a-zA-Z0-9_-]+$')
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)
    role: UserRole = Field(default=UserRole.USER)

    @validator('email')
    def validate_email(cls, v):
        """Validate email"""
        v = v.strip().lower()

        # Additional email validation
        if len(v) > 255:
            raise ValueError("Email too long")

        # Block disposable email domains (optional)
        disposable_domains = {'tempmail.com', 'guerrillamail.com', '10minutemail.com'}
        domain = v.split('@')[1]
        if domain in disposable_domains:
            raise ValueError("Disposable email addresses not allowed")

        return v

    @validator('password')
    def validate_password(cls, v):
        """
        Validate password strength

        Requirements:
        - At least 8 characters
        - Contains uppercase letter
        - Contains lowercase letter
        - Contains digit
        - Contains special character
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")

        if len(v) > 128:
            raise ValueError("Password too long (max 128 characters)")

        # Check complexity
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v)

        if not (has_upper and has_lower and has_digit and has_special):
            raise ValueError(
                "Password must contain uppercase, lowercase, digit, and special character"
            )

        # Check for common passwords (basic check)
        common_passwords = {
            'password', 'Password1!', 'Admin123!', 'Welcome1!',
            'Qwerty123!', 'Abc123!@#'
        }
        if v in common_passwords:
            raise ValueError("Password is too common")

        return v

    @validator('full_name')
    def sanitize_full_name(cls, v):
        """Sanitize full name"""
        if v:
            return sanitize_string(v, max_length=255)
        return v


class TokenRefresh(BaseModel):
    """Refresh token request"""

    refresh_token: str = Field(..., min_length=1, max_length=1000)


class PasswordChange(BaseModel):
    """Change password request"""

    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @validator('new_password')
    def validate_new_password(cls, v):
        """Validate new password (same rules as UserCreate)"""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")

        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v)

        if not (has_upper and has_lower and has_digit and has_special):
            raise ValueError(
                "Password must contain uppercase, lowercase, digit, and special character"
            )

        return v


class APIKeyCreate(BaseModel):
    """Create API key"""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    scopes: Optional[List[str]] = Field(default_factory=list, max_items=20)
    expires_days: Optional[int] = Field(None, ge=1, le=365)

    @validator('name')
    def sanitize_name(cls, v):
        """Sanitize name"""
        return sanitize_string(v, max_length=255)

    @validator('description')
    def sanitize_description(cls, v):
        """Sanitize description"""
        if v:
            return sanitize_string(v, max_length=1000)
        return v

    @validator('scopes')
    def validate_scopes(cls, v):
        """Validate scopes"""
        if not v:
            return []

        allowed_scopes = {
            'read:assets', 'write:assets', 'delete:assets',
            'read:findings', 'write:findings',
            'read:scans', 'write:scans',
            'admin'
        }

        for scope in v:
            if scope not in allowed_scopes:
                raise ValueError(f"Invalid scope: {scope}")

        return v


# ===========================
# Query Parameter Models
# ===========================

class PaginationParams(BaseModel):
    """Pagination parameters"""

    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

    @validator('limit')
    def validate_limit(cls, v):
        """Validate limit"""
        return validate_integer_bounds(v, min_val=1, max_val=1000)

    @validator('offset')
    def validate_offset(cls, v):
        """Validate offset"""
        return validate_integer_bounds(v, min_val=0, max_val=1000000)


class AssetFilters(BaseModel):
    """Asset filter parameters"""

    type: Optional[AssetType] = None
    confidence_min: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None
    tags: Optional[List[str]] = Field(None, max_items=20)
    search: Optional[str] = Field(None, max_length=255)

    @validator('search')
    def sanitize_search(cls, v):
        """Sanitize search query"""
        if v:
            return sanitize_string(v, max_length=255)
        return v

    @validator('tags')
    def sanitize_tags(cls, v):
        """Sanitize tags"""
        if v:
            return [re.sub(r'[^a-zA-Z0-9-_]', '', tag)[:50] for tag in v]
        return v


class FindingFilters(BaseModel):
    """Finding filter parameters"""

    severity: Optional[List[SeverityLevel]] = Field(None, max_items=5)
    status: Optional[str] = Field(None, regex=r'^(open|suppressed|fixed)$')
    min_cvss: Optional[float] = Field(None, ge=0.0, le=10.0)
    has_cve: Optional[bool] = None
    search: Optional[str] = Field(None, max_length=255)

    @validator('search')
    def sanitize_search(cls, v):
        """Sanitize search query"""
        if v:
            return sanitize_string(v, max_length=255)
        return v
