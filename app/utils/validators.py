"""
Domain and input validation utilities for security

Provides comprehensive validation to prevent injection attacks and ensure
data integrity throughout the application.
"""

import re
import ipaddress
from typing import Optional, List, Tuple
from urllib.parse import urlparse
import tldextract
import logging

logger = logging.getLogger(__name__)


class DomainValidator:
    """
    Comprehensive domain validation with multiple security checks

    Prevents:
    - Command injection
    - SSRF attacks
    - Path traversal
    - Homograph attacks
    """

    # RFC 1123 compliant hostname regex
    HOSTNAME_REGEX = re.compile(
        r'^(?!-)(?:[a-zA-Z0-9-]{1,63}(?<!-)\.)*[a-zA-Z]{2,63}$'
    )

    # Blocked TLDs for security
    BLOCKED_TLDS = {'.local', '.localhost', '.internal', '.corp', '.home', '.test', '.invalid'}

    # Reserved IP ranges (RFC 1918, RFC 6890)
    RESERVED_NETWORKS = [
        ipaddress.IPv4Network('10.0.0.0/8'),
        ipaddress.IPv4Network('172.16.0.0/12'),
        ipaddress.IPv4Network('192.168.0.0/16'),
        ipaddress.IPv4Network('127.0.0.0/8'),
        ipaddress.IPv4Network('169.254.0.0/16'),
        ipaddress.IPv4Network('224.0.0.0/4'),
        ipaddress.IPv4Network('240.0.0.0/4'),
        ipaddress.IPv4Network('0.0.0.0/8'),
        ipaddress.IPv6Network('::1/128'),
        ipaddress.IPv6Network('fe80::/10'),
        ipaddress.IPv6Network('fc00::/7'),
        ipaddress.IPv6Network('ff00::/8'),
    ]

    # Cloud metadata endpoints to block
    METADATA_ENDPOINTS = [
        '169.254.169.254',  # AWS/GCP/Azure
        'metadata.google.internal',  # GCP
        'metadata.amazonaws.com',  # AWS
        '100.100.100.200',  # Alibaba Cloud
    ]

    @classmethod
    def validate_domain(cls, domain: str, allow_wildcards: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Validate a domain with comprehensive security checks

        Args:
            domain: Domain to validate
            allow_wildcards: Whether to allow wildcard domains (*.example.com)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not domain or not isinstance(domain, str):
            return False, "Domain must be a non-empty string"

        # Clean and normalize
        domain = domain.strip().lower()

        # Remove any whitespace
        if ' ' in domain or '\t' in domain or '\n' in domain or '\r' in domain:
            return False, "Domain contains whitespace characters"

        # Length check
        if len(domain) > 253:
            return False, "Domain exceeds maximum length (253 characters)"

        if len(domain) < 3:
            return False, "Domain too short (minimum 3 characters)"

        # Check for dangerous characters (command injection prevention)
        dangerous_chars = [
            ';', '&', '|', '$', '`', '\n', '\r', '>', '<',
            '(', ')', '{', '}', '[', ']', '\\', '"', "'",
            '\x00', '\x08', '\x0b', '\x0c', '\x1a'  # Control characters
        ]
        for char in dangerous_chars:
            if char in domain:
                return False, f"Domain contains dangerous character: {repr(char)}"

        # Check for URL encoding attempts
        if '%' in domain:
            return False, "Domain contains URL encoding"

        # Check for path traversal attempts
        if '../' in domain or '..\\' in domain:
            return False, "Domain contains path traversal attempt"

        # Handle wildcards
        if domain.startswith('*.'):
            if not allow_wildcards:
                return False, "Wildcard domains not allowed"
            domain = domain[2:]  # Remove wildcard for validation

        # Check for cloud metadata endpoints
        if domain in cls.METADATA_ENDPOINTS:
            return False, f"Blocked cloud metadata endpoint: {domain}"

        # Check for IP addresses (prevent SSRF to internal IPs)
        try:
            ip = ipaddress.ip_address(domain)

            # Block all IPv6 for now (can be configured)
            if isinstance(ip, ipaddress.IPv6Address):
                return False, "IPv6 addresses not allowed"

            # Check if IP is in reserved range
            for network in cls.RESERVED_NETWORKS:
                if ip in network:
                    return False, f"Domain resolves to reserved IP range: {network}"

            # Check metadata endpoints
            if str(ip) in cls.METADATA_ENDPOINTS:
                return False, f"Blocked metadata endpoint IP: {ip}"

            # Public IPs are allowed
            return True, None

        except ValueError:
            # Not an IP, continue with domain validation
            pass

        # Validate hostname format
        if not cls.HOSTNAME_REGEX.match(domain):
            return False, "Invalid domain format (RFC 1123)"

        # Extract TLD using tldextract (handles public suffix list)
        try:
            ext = tldextract.extract(domain)
        except Exception as e:
            return False, f"Failed to parse domain: {e}"

        # Must have a domain and TLD
        if not ext.domain or not ext.suffix:
            return False, "Invalid domain structure"

        # Check for blocked TLDs
        tld = f".{ext.suffix}" if ext.suffix else ""
        if tld in cls.BLOCKED_TLDS:
            return False, f"Blocked TLD: {tld}"

        # Check for homograph attacks (Unicode lookalikes)
        if not domain.isascii():
            return False, "Domain contains non-ASCII characters (potential homograph attack)"

        # Validate label lengths
        labels = domain.split('.')
        for label in labels:
            if len(label) > 63:
                return False, f"Domain label exceeds 63 characters: {label}"
            if not label:
                return False, "Empty domain label"
            # Check for invalid label start/end
            if label.startswith('-') or label.endswith('-'):
                return False, f"Domain label cannot start or end with hyphen: {label}"

        # Additional security checks for specific patterns
        suspicious_patterns = [
            r'xn--',  # Punycode (could be homograph attack)
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',  # IP-like pattern
            r'localhost',
            r'127\.0\.',
            r'192\.168\.',
            r'10\.',
            r'172\.(1[6-9]|2[0-9]|3[01])\.',
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, domain, re.IGNORECASE):
                return False, f"Domain matches suspicious pattern: {pattern}"

        logger.debug(f"Domain validation successful: {domain}")
        return True, None

    @classmethod
    def validate_domain_batch(cls, domains: List[str], allow_wildcards: bool = False) -> dict:
        """
        Validate multiple domains efficiently

        Args:
            domains: List of domains to validate
            allow_wildcards: Whether to allow wildcard domains

        Returns:
            Dict with validation results
        """
        results = {
            'valid': [],
            'invalid': [],
            'stats': {
                'total': len(domains),
                'valid_count': 0,
                'invalid_count': 0,
                'unique_errors': set()
            }
        }

        seen_domains = set()

        for domain in domains:
            # Skip duplicates
            if domain.lower() in seen_domains:
                continue
            seen_domains.add(domain.lower())

            is_valid, error = cls.validate_domain(domain, allow_wildcards)
            if is_valid:
                results['valid'].append(domain)
                results['stats']['valid_count'] += 1
            else:
                results['invalid'].append({
                    'domain': domain,
                    'error': error
                })
                results['stats']['invalid_count'] += 1
                results['stats']['unique_errors'].add(error)

        # Convert set to list for JSON serialization
        results['stats']['unique_errors'] = list(results['stats']['unique_errors'])

        return results

    @classmethod
    def sanitize_domain(cls, domain: str) -> Optional[str]:
        """
        Attempt to sanitize a domain to make it valid

        Args:
            domain: Domain to sanitize

        Returns:
            Sanitized domain or None if cannot be sanitized
        """
        if not domain:
            return None

        # Basic cleaning
        domain = domain.strip().lower()

        # Remove common prefixes
        prefixes_to_remove = ['http://', 'https://', 'ftp://', 'www.']
        for prefix in prefixes_to_remove:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]

        # Remove path component if present
        if '/' in domain:
            domain = domain.split('/')[0]

        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]

        # Validate the cleaned domain
        is_valid, _ = cls.validate_domain(domain)
        return domain if is_valid else None


class URLValidator:
    """
    URL validation for web crawling and HTTP tools
    """

    # Allowed schemes
    ALLOWED_SCHEMES = {'http', 'https'}

    # Blocked URL patterns (SSRF prevention)
    BLOCKED_PATTERNS = [
        r'file://',
        r'gopher://',
        r'dict://',
        r'ftp://',
        r'jar:',
        r'netdoc:',
        r'data:',
        r'ldap://',
        r'sftp://',
        r'tftp://',
    ]

    @classmethod
    def validate_url(cls, url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate URL for security

        Args:
            url: URL to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url or not isinstance(url, str):
            return False, "URL must be a non-empty string"

        # Length check
        if len(url) > 2048:
            return False, "URL exceeds maximum length (2048 characters)"

        # Check for blocked patterns
        for pattern in cls.BLOCKED_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return False, f"Blocked URL scheme: {pattern}"

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            return False, f"Invalid URL format: {e}"

        # Check scheme
        if parsed.scheme not in cls.ALLOWED_SCHEMES:
            return False, f"Invalid URL scheme: {parsed.scheme}"

        # Validate hostname using DomainValidator
        if parsed.hostname:
            is_valid, error = DomainValidator.validate_domain(parsed.hostname)
            if not is_valid:
                return False, f"Invalid hostname: {error}"

        # Check for suspicious path components
        if parsed.path:
            # Path traversal
            if '../' in parsed.path or '..\\' in parsed.path:
                return False, "URL contains path traversal"

            # Null bytes
            if '\x00' in parsed.path:
                return False, "URL contains null bytes"

        return True, None


class InputSanitizer:
    """
    General input sanitization utilities
    """

    @staticmethod
    def sanitize_for_logging(text: str, max_length: int = 1000) -> str:
        """
        Sanitize text for safe logging

        Args:
            text: Text to sanitize
            max_length: Maximum length

        Returns:
            Sanitized text
        """
        if not text:
            return ""

        # Remove control characters
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')

        # Truncate
        if len(text) > max_length:
            text = text[:max_length] + "...[truncated]"

        # Escape special characters
        text = text.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')

        return text

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent path traversal

        Args:
            filename: Filename to sanitize

        Returns:
            Sanitized filename
        """
        if not filename:
            return "unnamed"

        # Remove path components
        from pathlib import Path
        filename = Path(filename).name

        # Remove dangerous characters
        safe_chars = re.compile(r'[^a-zA-Z0-9._-]')
        filename = safe_chars.sub('_', filename)

        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:240] + ('.' + ext if ext else '')

        return filename or "unnamed"