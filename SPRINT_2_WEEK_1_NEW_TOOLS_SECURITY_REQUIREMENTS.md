# Sprint 2 Week 1 - New Tools Security Requirements
## HTTPx, Naabu, TLSx, and Katana Integration

**Document Version**: 1.0
**Author**: Security Audit Team
**Date**: 2025-10-23
**Current Security Score**: 9.0/10
**Target Security Score**: 9.5/10
**Sprint Phase**: Sprint 2 Week 1 (Tool Integration)

---

## Executive Summary

This document defines comprehensive security requirements for integrating 4 new enrichment tools (HTTPx, Naabu, TLSx, Katana) into the EASM platform. Building upon the 9.0/10 security score achieved in Sprint 2 Day 1, these requirements ensure that new external-facing tools maintain the high security standard while introducing minimal attack surface.

### Critical Security Principles

1. **Defense in Depth**: Multiple validation layers for all tools
2. **Zero Trust External Data**: All tool outputs are treated as untrusted
3. **Network Isolation**: Strict SSRF prevention and internal network protection
4. **Data Minimization**: Redact sensitive data before storage
5. **Least Privilege**: Tools run with minimal permissions

---

## Table of Contents

1. [Tool-Specific Security Requirements](#1-tool-specific-security-requirements)
2. [Input Validation Requirements](#2-input-validation-requirements)
3. [Output Sanitization Requirements](#3-output-sanitization-requirements)
4. [Network Security Controls](#4-network-security-controls)
5. [Resource Limits and Rate Limiting](#5-resource-limits-and-rate-limiting)
6. [Data Redaction Rules](#6-data-redaction-rules)
7. [Threat Model Analysis](#7-threat-model-analysis)
8. [Security Testing Requirements](#8-security-testing-requirements)
9. [Compliance and Legal Considerations](#9-compliance-and-legal-considerations)
10. [Implementation Guidance](#10-implementation-guidance)
11. [Security Checklist Updates](#11-security-checklist-updates)

---

## 1. Tool-Specific Security Requirements

### 1.1 HTTPx (Web Technology Fingerprinting)

**OWASP Reference**: A10:2021 - SSRF, A03:2021 - Injection, A04:2021 - Insecure Design

#### Attack Vectors
- SSRF to internal networks/cloud metadata endpoints
- Large response body DoS (memory exhaustion)
- XSS through stored HTML content
- Sensitive header leakage (Authorization, Cookie, API keys)
- Redirect chain attacks to internal resources

#### Security Requirements

**SR-HTTPx-001**: URL Validation
- **Priority**: CRITICAL
- **Requirement**: All URLs MUST be validated using URLValidator before execution
- **Implementation**:
  - Use existing URLValidator.validate_url()
  - Block schemes other than http/https
  - Validate hostname against DomainValidator
  - Block cloud metadata endpoints (169.254.169.254, metadata.google.internal, etc.)
  - Maximum URL length: 2048 characters
  - No URL encoding bypass attempts (double encoding, etc.)

**SR-HTTPx-002**: Response Size Limits
- **Priority**: HIGH
- **Requirement**: Response bodies MUST be truncated to prevent memory exhaustion
- **Implementation**:
  - Maximum response body size: 10MB (configurable via httpx_max_response_size)
  - Streaming download with size check before full read
  - Terminate connection if Content-Length > limit
  - Log truncation events for security monitoring

**SR-HTTPx-003**: Header Filtering
- **Priority**: CRITICAL
- **Requirement**: Sensitive headers MUST be redacted before storage
- **Implementation**:
  - Block list: authorization, cookie, set-cookie, x-api-key, x-auth-token, proxy-authorization, www-authenticate
  - Case-insensitive matching
  - Redact entire header value, not just mask
  - Log redaction count for audit

**SR-HTTPx-004**: HTML Content Sanitization
- **Priority**: HIGH
- **Requirement**: HTML content MUST be sanitized to prevent stored XSS
- **Implementation**:
  - Use bleach library for HTML sanitization
  - Strip all JavaScript (<script>, onclick, onerror, etc.)
  - Remove dangerous protocols (javascript:, data:, vbscript:)
  - Escape HTML entities for display
  - Store sanitization metadata for audit

**SR-HTTPx-005**: Redirect Chain Protection
- **Priority**: MEDIUM
- **Requirement**: Follow redirects with SSRF protection at each hop
- **Implementation**:
  - Maximum redirect depth: 5
  - Validate each redirect URL against URLValidator
  - Block internal IP redirects
  - Timeout for entire redirect chain: 30 seconds

**SR-HTTPx-006**: Request Headers Control
- **Priority**: MEDIUM
- **Requirement**: Control outbound request headers to prevent fingerprinting
- **Implementation**:
  - Fixed User-Agent: "EASM-Scanner/1.0"
  - No Accept-Language or other identifying headers
  - Standard Accept headers only
  - No cookies or authentication forwarding

---

### 1.2 Naabu (Port Scanning)

**OWASP Reference**: A01:2021 - Broken Access Control, A04:2021 - Insecure Design

#### Attack Vectors
- Scanning internal networks (SSRF variant)
- Scanning sensitive ports (RDP, SMB, SSH)
- Triggering IDS/IPS systems
- DoS through excessive scanning
- Legal compliance issues (unauthorized port scanning)

#### Security Requirements

**SR-Naabu-001**: Target Validation
- **Priority**: CRITICAL
- **Requirement**: All scan targets MUST be validated to prevent internal network scanning
- **Implementation**:
  - Use DomainValidator.validate_domain() with SSRF checks
  - Block all RFC1918 private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
  - Block loopback (127.0.0.0/8, ::1)
  - Block link-local (169.254.0.0/16, fe80::/10)
  - Block cloud metadata endpoints
  - Block carrier-grade NAT (100.64.0.0/10)
  - Resolve hostname and validate IP before scanning

**SR-Naabu-002**: Port Range Restrictions
- **Priority**: CRITICAL
- **Requirement**: Dangerous ports MUST be blocked to prevent abuse
- **Implementation**:
  - Blocked ports by default:
    - 22 (SSH) - sensitive authentication
    - 23 (Telnet) - legacy/insecure
    - 445 (SMB) - sensitive file sharing
    - 3389 (RDP) - sensitive remote desktop
    - 5432 (PostgreSQL) - database
    - 3306 (MySQL) - database
    - 6379 (Redis) - database
    - 27017 (MongoDB) - database
    - 1433 (MSSQL) - database
  - Allow override only for tenant admin with explicit consent
  - Maximum port range per scan: 1000 ports
  - Common port presets: top100, top1000, web (80,443,8080,8443)

**SR-Naabu-003**: Rate Limiting
- **Priority**: HIGH
- **Requirement**: Scanning rate MUST be limited to prevent network abuse
- **Implementation**:
  - Maximum packets per second: 1000 (configurable: naabu_max_pps)
  - Maximum concurrent scans per tenant: 3
  - Minimum interval between scans: 60 seconds
  - Global scan queue with tenant fairness
  - Exponential backoff on network errors

**SR-Naabu-004**: Scan Timeout
- **Priority**: HIGH
- **Requirement**: Scans MUST timeout to prevent resource exhaustion
- **Implementation**:
  - Per-host timeout: 30 seconds (configurable: naabu_host_timeout)
  - Total scan timeout: 600 seconds (10 minutes)
  - Graceful termination with partial results
  - Log timeout events for monitoring

**SR-Naabu-005**: Audit Logging
- **Priority**: HIGH
- **Requirement**: All scan activities MUST be logged for compliance and forensics
- **Implementation**:
  - Log: timestamp, tenant_id, user_id, target, port_range, result_count
  - Store in tamper-evident audit log
  - Retention: 90 days minimum
  - Alert on suspicious patterns (mass scanning, internal IPs)
  - Export capability for compliance reporting

**SR-Naabu-006**: User Consent
- **Priority**: MEDIUM
- **Requirement**: Users MUST consent to port scanning for legal compliance
- **Implementation**:
  - Display port scanning disclaimer on first use
  - Store consent timestamp per tenant
  - Require re-consent annually
  - Allow consent withdrawal (disables port scanning)
  - Terms: "Only scan assets you own or have permission to scan"

**SR-Naabu-007**: Network Capabilities
- **Priority**: CRITICAL
- **Requirement**: Container MUST run with minimal network capabilities
- **Implementation**:
  - CAP_NET_RAW for SYN scanning
  - No CAP_NET_ADMIN
  - Separate network namespace
  - No host network mode
  - Egress-only network policy

---

### 1.3 TLSx (TLS/SSL Certificate Analysis)

**OWASP Reference**: A02:2021 - Cryptographic Failures, A07:2021 - Identification and Authentication Failures

#### Attack Vectors
- Private key exposure through tool output
- Weak cipher information disclosure
- Certificate chain validation bypass
- Man-in-the-middle during certificate fetch
- Storage of sensitive cryptographic material

#### Security Requirements

**SR-TLSx-001**: Target Validation
- **Priority**: CRITICAL
- **Requirement**: TLS scan targets MUST be validated
- **Implementation**:
  - Use URLValidator with https:// scheme only
  - Validate hostname using DomainValidator
  - Block internal networks (same as Naabu)
  - Resolve hostname and validate IP
  - Port must be 443 unless explicitly specified (allowed: 8443, 4443)

**SR-TLSx-002**: Private Key Redaction
- **Priority**: CRITICAL
- **Requirement**: Private keys MUST NEVER be stored or logged
- **Implementation**:
  - Scan tool output for private key patterns:
    - "-----BEGIN PRIVATE KEY-----"
    - "-----BEGIN RSA PRIVATE KEY-----"
    - "-----BEGIN EC PRIVATE KEY-----"
    - Fields: privateKey, private_key, key, priv, secret_key
  - Replace entire value with "[REDACTED-PRIVATE-KEY]"
  - Alert security team if private key detected
  - Log redaction event with hash of key for forensics
  - Never store, even temporarily

**SR-TLSx-003**: Certificate Chain Validation
- **Priority**: HIGH
- **Requirement**: Certificate chains MUST be validated for security assessment
- **Implementation**:
  - Verify certificate chain completeness
  - Check signature validity
  - Validate certificate dates (notBefore, notAfter)
  - Detect self-signed certificates
  - Flag expired certificates
  - Store validation results, not raw certificates

**SR-TLSx-004**: Weak Cipher Detection
- **Priority**: MEDIUM
- **Requirement**: Weak ciphers MUST be detected and flagged
- **Implementation**:
  - Block list: SSL 2.0, SSL 3.0, TLS 1.0, TLS 1.1
  - Weak ciphers: RC4, DES, 3DES, MD5, EXPORT ciphers
  - Flag NULL ciphers
  - Prefer TLS 1.2 and TLS 1.3
  - Generate security score based on cipher strength

**SR-TLSx-005**: Connection Security
- **Priority**: MEDIUM
- **Requirement**: TLS analysis connection MUST be secure
- **Implementation**:
  - Use system CA bundle for validation
  - No certificate pinning (would prevent analysis)
  - Timeout: 30 seconds per connection
  - Maximum handshake attempts: 3
  - Log connection failures for monitoring

**SR-TLSx-006**: Output Sanitization
- **Priority**: HIGH
- **Requirement**: TLS tool output MUST be sanitized before storage
- **Implementation**:
  - Redact private keys (see SR-TLSx-002)
  - Remove internal IP addresses from certificate data
  - Sanitize email addresses to protect privacy
  - Hash certificate serial numbers for storage
  - Store only security-relevant data

---

### 1.4 Katana (Web Crawling)

**OWASP Reference**: A10:2021 - SSRF, A03:2021 - Injection, A01:2021 - Broken Access Control

#### Attack Vectors
- SSRF to internal networks via crawled links
- Infinite crawl loops (DoS)
- XSS through stored URLs and parameters
- Credential leakage in URLs
- robots.txt violation
- Form submission to sensitive endpoints

#### Security Requirements

**SR-Katana-001**: Seed URL Validation
- **Priority**: CRITICAL
- **Requirement**: Seed URLs MUST be validated before crawling
- **Implementation**:
  - Use URLValidator.validate_url()
  - Validate hostname using DomainValidator
  - Block internal networks and cloud metadata
  - Only http/https schemes
  - Maximum seed URL length: 2048 characters

**SR-Katana-002**: Crawl Scope Enforcement
- **Priority**: CRITICAL
- **Requirement**: Crawler MUST respect domain boundaries
- **Implementation**:
  - Stay within seed domain by default
  - Option: allow subdomains (*.example.com)
  - No cross-domain crawling unless explicitly allowed
  - Validate every discovered URL against scope
  - Block URL redirects outside scope
  - Maximum scope domains: 10

**SR-Katana-003**: URL Validation During Crawl
- **Priority**: CRITICAL
- **Requirement**: Every discovered URL MUST be validated
- **Implementation**:
  - Run URLValidator on each discovered link
  - Block javascript:, data:, file:, gopher: schemes
  - Block internal IP addresses in URLs
  - Block cloud metadata endpoints
  - Maximum URL length per discovered link: 2048 characters
  - Skip invalid URLs, log count

**SR-Katana-004**: Crawl Depth Limits
- **Priority**: HIGH
- **Requirement**: Crawl depth MUST be limited to prevent infinite loops
- **Implementation**:
  - Maximum depth: 3 levels (configurable: katana_max_depth)
  - Maximum pages per domain: 1000 (configurable: katana_max_pages)
  - Maximum crawl duration: 300 seconds (5 minutes)
  - Detect and break infinite redirect loops
  - Track visited URLs to prevent revisits

**SR-Katana-005**: robots.txt Compliance
- **Priority**: HIGH
- **Requirement**: Crawler MUST respect robots.txt
- **Implementation**:
  - Fetch robots.txt before crawling
  - Parse Disallow directives
  - Respect Crawl-delay directive
  - User-agent: "EASM-Scanner/1.0"
  - Timeout for robots.txt: 10 seconds
  - If robots.txt blocks crawler, abort with error

**SR-Katana-006**: Request Rate Limiting
- **Priority**: HIGH
- **Requirement**: Crawl rate MUST be limited per domain
- **Implementation**:
  - Default: 5 requests per second per domain
  - Respect Crawl-delay from robots.txt
  - Exponential backoff on HTTP errors (429, 503)
  - Maximum concurrent requests: 10
  - Polite crawling with delays

**SR-Katana-007**: Form Submission Control
- **Priority**: CRITICAL
- **Requirement**: Form submissions MUST be disabled by default
- **Implementation**:
  - No form submission without explicit tenant setting
  - Only GET forms by default
  - No POST/PUT/DELETE requests
  - No authentication form submission
  - Block sensitive form actions (login, register, delete, admin)

**SR-Katana-008**: Credential Detection
- **Priority**: HIGH
- **Requirement**: Credentials in URLs MUST be detected and redacted
- **Implementation**:
  - Detect patterns: password=, api_key=, token=, secret=
  - Redact parameter values before storage
  - Alert security team on credential detection
  - Store URL structure without credentials
  - Hash credential values for forensics

**SR-Katana-009**: XSS Prevention
- **Priority**: HIGH
- **Requirement**: Discovered URLs and content MUST be sanitized
- **Implementation**:
  - HTML escape all discovered URLs before storage
  - Sanitize URL parameters (remove script tags)
  - Strip dangerous characters from query strings
  - Use bleach library for HTML content
  - Store URLs as plain text, not executable content

**SR-Katana-010**: Response Size Limits
- **Priority**: MEDIUM
- **Requirement**: Crawled page size MUST be limited
- **Implementation**:
  - Maximum page size: 5MB
  - Skip large files (PDFs, videos, archives)
  - Check Content-Type and Content-Length headers
  - Timeout for page download: 30 seconds

**SR-Katana-011**: security.txt Compliance
- **Priority**: LOW
- **Requirement**: Respect security.txt if present
- **Implementation**:
  - Check for /.well-known/security.txt
  - Parse security policy
  - Option to skip domains with restrictive policies
  - Log security.txt presence for compliance

---

## 2. Input Validation Requirements

### 2.1 Universal Input Validation (All Tools)

**IVR-001**: Domain Validation
- **Implementation**: Use existing DomainValidator.validate_domain()
- **Rules**:
  - RFC 1123 compliant hostnames
  - Maximum length: 253 characters
  - Block dangerous characters: ; & | $ ` \n \r > < ( ) { } [ ] \ " ' %
  - Block path traversal: ../ ..\
  - Block command injection patterns
  - Block homograph attacks (non-ASCII)
  - Block internal TLDs: .local, .localhost, .internal, .corp, .home, .test, .invalid
  - Block cloud metadata endpoints
  - Block RFC1918 private networks
  - Block loopback and link-local addresses

**IVR-002**: URL Validation (HTTPx, Katana)
- **Implementation**: Use existing URLValidator.validate_url()
- **Rules**:
  - Allowed schemes: http, https only
  - Maximum length: 2048 characters
  - Validate hostname using DomainValidator
  - Block file://, gopher://, dict://, ftp://, ldap://, jar:, data:
  - Block null bytes in path
  - Block path traversal in URL path
  - Block URL encoding bypass (double encoding, etc.)

**IVR-003**: Port Validation (Naabu, TLSx)
- **Implementation**: New validator for port ranges
- **Rules**:
  - Valid port range: 1-65535
  - Block dangerous ports: 22, 23, 445, 3389, 5432, 3306, 6379, 27017, 1433
  - Maximum ports per scan: 1000
  - Parse port range formats: "80", "80-443", "80,443,8080"
  - Validate numeric values only

**IVR-004**: Depth Validation (Katana)
- **Implementation**: Integer validation with bounds
- **Rules**:
  - Minimum depth: 1
  - Maximum depth: 5
  - Default: 3
  - Must be integer
  - No negative values

**IVR-005**: Timeout Validation (All Tools)
- **Implementation**: Integer validation with bounds
- **Rules**:
  - Minimum timeout: 10 seconds
  - Maximum timeout: 1800 seconds (30 minutes)
  - Must be integer
  - No negative values

### 2.2 Input Validation Implementation Pattern

```python
# app/utils/tool_validators.py
from typing import Tuple, Optional, List
from app.utils.validators import DomainValidator, URLValidator

class ToolInputValidator:
    """Specialized validators for enrichment tools"""

    # Dangerous ports to block
    BLOCKED_PORTS = {22, 23, 445, 3389, 5432, 3306, 6379, 27017, 1433}

    @classmethod
    def validate_httpx_input(cls, url: str) -> Tuple[bool, Optional[str]]:
        """Validate HTTPx input URL"""
        # URL validation
        is_valid, error = URLValidator.validate_url(url)
        if not is_valid:
            return False, f"Invalid URL: {error}"

        # Additional checks for HTTPx
        from urllib.parse import urlparse
        parsed = urlparse(url)

        # Check response size expectations
        if parsed.path and len(parsed.path) > 1000:
            return False, "URL path too long (max 1000 chars)"

        return True, None

    @classmethod
    def validate_naabu_input(
        cls,
        target: str,
        ports: str,
        allow_dangerous_ports: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """Validate Naabu scan input"""
        # Target validation
        is_valid, error = DomainValidator.validate_domain(target)
        if not is_valid:
            return False, f"Invalid target: {error}"

        # Port validation
        port_list = cls._parse_port_range(ports)
        if port_list is None:
            return False, "Invalid port format"

        if len(port_list) > 1000:
            return False, "Too many ports (max 1000)"

        # Check for dangerous ports
        if not allow_dangerous_ports:
            dangerous_found = cls.BLOCKED_PORTS.intersection(set(port_list))
            if dangerous_found:
                return False, f"Blocked ports detected: {dangerous_found}"

        return True, None

    @classmethod
    def validate_tlsx_input(cls, url: str) -> Tuple[bool, Optional[str]]:
        """Validate TLSx input URL"""
        # URL validation
        is_valid, error = URLValidator.validate_url(url)
        if not is_valid:
            return False, f"Invalid URL: {error}"

        # Must be HTTPS
        from urllib.parse import urlparse
        parsed = urlparse(url)

        if parsed.scheme != 'https':
            return False, "TLS analysis requires HTTPS URL"

        # Validate port if specified
        if parsed.port:
            if parsed.port not in [443, 8443, 4443]:
                return False, f"Unusual TLS port: {parsed.port}"

        return True, None

    @classmethod
    def validate_katana_input(
        cls,
        seed_url: str,
        max_depth: int = 3,
        max_pages: int = 1000
    ) -> Tuple[bool, Optional[str]]:
        """Validate Katana crawl input"""
        # URL validation
        is_valid, error = URLValidator.validate_url(seed_url)
        if not is_valid:
            return False, f"Invalid seed URL: {error}"

        # Depth validation
        if not isinstance(max_depth, int) or max_depth < 1 or max_depth > 5:
            return False, "Depth must be between 1 and 5"

        # Page limit validation
        if not isinstance(max_pages, int) or max_pages < 1 or max_pages > 10000:
            return False, "Page limit must be between 1 and 10000"

        return True, None

    @staticmethod
    def _parse_port_range(port_str: str) -> Optional[List[int]]:
        """Parse port range string into list of ports"""
        try:
            ports = []
            for part in port_str.split(','):
                part = part.strip()
                if '-' in part:
                    start, end = part.split('-')
                    start, end = int(start), int(end)
                    if start > end or start < 1 or end > 65535:
                        return None
                    ports.extend(range(start, end + 1))
                else:
                    port = int(part)
                    if port < 1 or port > 65535:
                        return None
                    ports.append(port)
            return ports
        except:
            return None
```

---

## 3. Output Sanitization Requirements

### 3.1 Universal Output Sanitization (All Tools)

**OSR-001**: Size Limits
- **Requirement**: All tool outputs MUST be size-limited
- **Implementation**:
  - Maximum stdout size: 100MB (existing setting)
  - Maximum stderr size: 10MB
  - Truncate with "[TRUNCATED]" marker
  - Log truncation events

**OSR-002**: Control Character Removal
- **Requirement**: Remove control characters from output
- **Implementation**:
  - Strip ASCII control characters (0x00-0x1F except \n, \r, \t)
  - Remove ANSI escape sequences
  - Normalize line endings to \n

**OSR-003**: Log Injection Prevention
- **Requirement**: Sanitize output before logging
- **Implementation**:
  - Use InputSanitizer.sanitize_for_logging()
  - Escape newlines and special characters
  - Maximum log entry: 1000 characters

### 3.2 Tool-Specific Output Sanitization

#### HTTPx Output Sanitization

**OSR-HTTPx-001**: Sensitive Header Redaction
```python
class HTTPxOutputSanitizer:
    """Sanitize HTTPx JSON output"""

    SENSITIVE_HEADERS = {
        'authorization', 'cookie', 'set-cookie',
        'x-api-key', 'x-auth-token', 'proxy-authorization',
        'www-authenticate', 'x-csrf-token', 'x-xsrf-token'
    }

    def sanitize(self, output: dict) -> dict:
        """Sanitize HTTPx JSON output"""
        # Redact sensitive headers
        if 'headers' in output:
            output['headers'] = {
                k: '[REDACTED]' if k.lower() in self.SENSITIVE_HEADERS else v
                for k, v in output['headers'].items()
            }

        # Truncate response body
        if 'body' in output and len(output['body']) > 10_485_760:  # 10MB
            output['body'] = output['body'][:10_485_760]
            output['body_truncated'] = True

        # Sanitize HTML content
        if 'body' in output and 'text/html' in output.get('content_type', ''):
            import bleach
            output['body'] = bleach.clean(
                output['body'],
                tags=['p', 'br', 'div', 'span'],  # Very restrictive
                strip=True
            )

        # Add sanitization metadata
        output['sanitized_at'] = datetime.utcnow().isoformat()
        output['sanitizer_version'] = '1.0'

        return output
```

#### Naabu Output Sanitization

**OSR-Naabu-001**: Port Result Sanitization
```python
class NaabuOutputSanitizer:
    """Sanitize Naabu port scan results"""

    def sanitize(self, output: dict) -> dict:
        """Sanitize Naabu output"""
        # Limit number of ports stored
        if 'ports' in output and len(output['ports']) > 1000:
            output['ports'] = output['ports'][:1000]
            output['ports_truncated'] = True

        # Remove service banner details if too verbose
        if 'services' in output:
            for service in output['services']:
                if 'banner' in service and len(service['banner']) > 500:
                    service['banner'] = service['banner'][:500] + '...[truncated]'

        # Add metadata
        output['sanitized_at'] = datetime.utcnow().isoformat()

        return output
```

#### TLSx Output Sanitization

**OSR-TLSx-001**: Private Key Redaction
```python
class TLSxOutputSanitizer:
    """Sanitize TLSx certificate analysis output"""

    PRIVATE_KEY_PATTERNS = [
        r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----.*?-----END (?:RSA |EC |DSA )?PRIVATE KEY-----',
        r'"private_key"\s*:\s*"[^"]+',
        r'"key"\s*:\s*"[^"]+',
    ]

    SENSITIVE_FIELDS = [
        'private_key', 'privateKey', 'key', 'priv',
        'secret_key', 'secretKey'
    ]

    def sanitize(self, output: dict) -> dict:
        """Sanitize TLSx output - NEVER store private keys"""
        import re
        import json

        # Convert to JSON string for pattern matching
        output_str = json.dumps(output)

        # Check for private key patterns
        for pattern in self.PRIVATE_KEY_PATTERNS:
            if re.search(pattern, output_str, re.DOTALL | re.IGNORECASE):
                # SECURITY INCIDENT: Private key detected
                logger.critical(
                    "SECURITY ALERT: Private key detected in TLSx output! "
                    "Redacting and alerting security team."
                )
                # Alert security team
                self._alert_security_team("Private key detected in TLSx output")

        # Redact sensitive fields recursively
        output = self._redact_recursive(output)

        # Sanitize email addresses for privacy
        output_str = json.dumps(output)
        output_str = re.sub(
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            '[REDACTED-EMAIL]',
            output_str
        )
        output = json.loads(output_str)

        # Add metadata
        output['sanitized_at'] = datetime.utcnow().isoformat()
        output['private_key_redacted'] = True

        return output

    def _redact_recursive(self, obj):
        """Recursively redact sensitive fields"""
        if isinstance(obj, dict):
            for key in list(obj.keys()):
                if key.lower() in [f.lower() for f in self.SENSITIVE_FIELDS]:
                    obj[key] = '[REDACTED-PRIVATE-KEY]'
                else:
                    obj[key] = self._redact_recursive(obj[key])
        elif isinstance(obj, list):
            return [self._redact_recursive(item) for item in obj]
        return obj

    def _alert_security_team(self, message: str):
        """Alert security team of incident"""
        # Implementation: Send to SIEM, Slack, email, etc.
        pass
```

#### Katana Output Sanitization

**OSR-Katana-001**: URL and Credential Sanitization
```python
class KatanaOutputSanitizer:
    """Sanitize Katana crawl results"""

    CREDENTIAL_PATTERNS = [
        r'password=([^&\s]+)',
        r'api_key=([^&\s]+)',
        r'token=([^&\s]+)',
        r'secret=([^&\s]+)',
        r'auth=([^&\s]+)',
    ]

    def sanitize(self, output: dict) -> dict:
        """Sanitize Katana crawl output"""
        # Limit number of URLs
        if 'urls' in output and len(output['urls']) > 10000:
            output['urls'] = output['urls'][:10000]
            output['urls_truncated'] = True

        # Sanitize each URL
        if 'urls' in output:
            output['urls'] = [self._sanitize_url(url) for url in output['urls']]

        # Sanitize forms
        if 'forms' in output:
            output['forms'] = [self._sanitize_form(form) for form in output['forms']]

        # Add metadata
        output['sanitized_at'] = datetime.utcnow().isoformat()

        return output

    def _sanitize_url(self, url: str) -> str:
        """Sanitize individual URL"""
        import re
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

        # Parse URL
        parsed = urlparse(url)

        # Check for credentials in URL
        for pattern in self.CREDENTIAL_PATTERNS:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                logger.warning(f"Credential detected in URL: {pattern}")
                # Redact the value
                url = re.sub(
                    pattern,
                    lambda m: f"{m.group(0).split('=')[0]}=[REDACTED]",
                    url,
                    flags=re.IGNORECASE
                )

        # HTML escape for storage
        import html
        url = html.escape(url)

        # Maximum URL length
        if len(url) > 2048:
            url = url[:2048] + '...[truncated]'

        return url

    def _sanitize_form(self, form: dict) -> dict:
        """Sanitize form data"""
        # Redact sensitive field names
        sensitive_fields = ['password', 'passwd', 'pwd', 'secret', 'token', 'api_key']

        if 'fields' in form:
            for field in form['fields']:
                if any(s in field.get('name', '').lower() for s in sensitive_fields):
                    field['value'] = '[REDACTED]'

        return form
```

---

## 4. Network Security Controls

### 4.1 SSRF Prevention

**NSC-001**: Blocked IP Ranges
```python
# app/utils/network_security.py
import ipaddress
from typing import Tuple, Optional

class NetworkSecurityValidator:
    """Network security validation for SSRF prevention"""

    # RFC 1918 private networks
    BLOCKED_NETWORKS = [
        ipaddress.IPv4Network('10.0.0.0/8'),          # Private
        ipaddress.IPv4Network('172.16.0.0/12'),       # Private
        ipaddress.IPv4Network('192.168.0.0/16'),      # Private
        ipaddress.IPv4Network('127.0.0.0/8'),         # Loopback
        ipaddress.IPv4Network('169.254.0.0/16'),      # Link-local
        ipaddress.IPv4Network('224.0.0.0/4'),         # Multicast
        ipaddress.IPv4Network('240.0.0.0/4'),         # Reserved
        ipaddress.IPv4Network('0.0.0.0/8'),           # Current network
        ipaddress.IPv4Network('100.64.0.0/10'),       # Carrier-grade NAT
        ipaddress.IPv6Network('::1/128'),             # Loopback
        ipaddress.IPv6Network('fe80::/10'),           # Link-local
        ipaddress.IPv6Network('fc00::/7'),            # Unique local
        ipaddress.IPv6Network('ff00::/8'),            # Multicast
    ]

    # Cloud metadata endpoints
    BLOCKED_HOSTS = [
        '169.254.169.254',              # AWS/GCP/Azure/Oracle
        'metadata.google.internal',      # GCP
        'metadata.googleapis.com',       # GCP
        'metadata.aws',                  # AWS (potential)
        '100.100.100.200',              # Alibaba Cloud
        'metadata.tencentyun.com',      # Tencent Cloud
        '169.254.169.254',              # Generic cloud metadata
    ]

    @classmethod
    def is_safe_target(cls, hostname: str) -> Tuple[bool, Optional[str]]:
        """Check if target is safe (not internal network)"""
        import socket

        # Check blocked hostnames
        if hostname.lower() in [h.lower() for h in cls.BLOCKED_HOSTS]:
            return False, f"Blocked metadata endpoint: {hostname}"

        # Resolve hostname to IP
        try:
            ip_str = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_str)
        except (socket.gaierror, ValueError) as e:
            return False, f"Cannot resolve hostname: {e}"

        # Check if IP is in blocked ranges
        for network in cls.BLOCKED_NETWORKS:
            if ip in network:
                return False, f"Target resolves to blocked network: {network}"

        return True, None

    @classmethod
    def validate_redirect(cls, original_url: str, redirect_url: str) -> Tuple[bool, Optional[str]]:
        """Validate redirect destination for SSRF"""
        from urllib.parse import urlparse

        # Parse redirect URL
        parsed = urlparse(redirect_url)

        if not parsed.hostname:
            return False, "Redirect URL has no hostname"

        # Check if redirect target is safe
        return cls.is_safe_target(parsed.hostname)
```

**NSC-002**: DNS Resolution Validation
- Resolve hostnames to IPs before tool execution
- Validate resolved IPs against blocked ranges
- Detect DNS rebinding attempts (re-resolve and validate)
- Cache DNS results with TTL (max 300 seconds)

**NSC-003**: Network Namespace Isolation
- Run tools in separate Docker network namespace
- No host network mode
- Egress-only network policy
- Block inter-container communication

### 4.2 Blocked Resources Configuration

**NSC-004**: Comprehensive Blocked Resources List
```yaml
# config/blocked_resources.yaml
blocked_ip_ranges:
  # RFC 1918 Private Networks
  - 10.0.0.0/8
  - 172.16.0.0/12
  - 192.168.0.0/16

  # Loopback
  - 127.0.0.0/8
  - ::1/128

  # Link-Local
  - 169.254.0.0/16
  - fe80::/10

  # Carrier-Grade NAT
  - 100.64.0.0/10

  # Multicast
  - 224.0.0.0/4
  - ff00::/8

  # Reserved
  - 240.0.0.0/4
  - 0.0.0.0/8

  # Documentation (TEST-NET)
  - 192.0.2.0/24
  - 198.51.100.0/24
  - 203.0.113.0/24

  # Unique Local (IPv6)
  - fc00::/7

blocked_hostnames:
  # Cloud Metadata Endpoints
  - 169.254.169.254
  - metadata.google.internal
  - metadata.googleapis.com
  - metadata.aws
  - metadata.amazonaws.com
  - 100.100.100.200
  - metadata.tencentyun.com
  - metadata.packet.net
  - metadata.platformequinix.com

  # Local Hostnames
  - localhost
  - localhost.localdomain
  - ip6-localhost
  - ip6-loopback

blocked_ports:
  # Authentication Services
  - 22    # SSH
  - 23    # Telnet
  - 3389  # RDP

  # File Sharing
  - 445   # SMB
  - 139   # NetBIOS
  - 135   # MS RPC

  # Databases (configurable override for admins)
  - 5432  # PostgreSQL
  - 3306  # MySQL
  - 6379  # Redis
  - 27017 # MongoDB
  - 1433  # MS SQL
  - 5984  # CouchDB
  - 9200  # Elasticsearch

  # Administrative
  - 5900  # VNC
  - 5901  # VNC
  - 8080  # Common admin ports (conditional)

blocked_url_schemes:
  - file
  - gopher
  - dict
  - ftp
  - jar
  - data
  - javascript
  - vbscript
  - ldap
  - ldaps
  - sftp
  - tftp
```

---

## 5. Resource Limits and Rate Limiting

### 5.1 Tool-Specific Resource Limits

```yaml
# config/tool_limits.yaml

httpx:
  timeout: 300                    # 5 minutes total
  max_response_size: 10485760    # 10MB
  max_redirects: 5
  redirect_timeout: 30           # 30 seconds
  concurrent_requests: 10
  rate_limit_per_second: 10
  memory_limit: 512Mi
  cpu_limit: 500m

naabu:
  timeout: 600                    # 10 minutes total
  host_timeout: 30               # 30 seconds per host
  max_ports: 1000
  max_packets_per_second: 1000
  concurrent_scans: 3            # Per tenant
  scan_interval: 60              # Minimum seconds between scans
  memory_limit: 1Gi
  cpu_limit: 1000m
  capabilities:
    - CAP_NET_RAW               # Required for SYN scan

tlsx:
  timeout: 300                    # 5 minutes
  connection_timeout: 30         # 30 seconds per connection
  max_handshake_attempts: 3
  concurrent_connections: 5
  memory_limit: 256Mi
  cpu_limit: 250m

katana:
  timeout: 300                    # 5 minutes total
  max_depth: 3
  max_pages: 1000
  max_page_size: 5242880         # 5MB per page
  request_rate_per_second: 5
  concurrent_requests: 10
  page_timeout: 30               # 30 seconds per page
  memory_limit: 1Gi
  cpu_limit: 1000m
  respect_robots_txt: true
```

### 5.2 Rate Limiting Implementation

**RL-001**: Tenant-Level Rate Limiting
```python
# app/utils/rate_limiter.py
from datetime import datetime, timedelta
from typing import Optional
import redis

class ToolRateLimiter:
    """Rate limiting for tool execution"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def check_rate_limit(
        self,
        tenant_id: int,
        tool: str,
        limit_per_minute: int = 10
    ) -> Tuple[bool, Optional[str]]:
        """Check if tenant can execute tool"""
        key = f"rate_limit:{tenant_id}:{tool}:{datetime.utcnow().strftime('%Y%m%d%H%M')}"

        # Increment counter
        count = self.redis.incr(key)

        # Set expiry on first use
        if count == 1:
            self.redis.expire(key, 60)

        # Check limit
        if count > limit_per_minute:
            return False, f"Rate limit exceeded: {limit_per_minute} requests per minute"

        return True, None

    def check_concurrent_limit(
        self,
        tenant_id: int,
        tool: str,
        max_concurrent: int = 3
    ) -> Tuple[bool, Optional[str]]:
        """Check concurrent execution limit"""
        key = f"concurrent:{tenant_id}:{tool}"

        # Get current count
        count = int(self.redis.get(key) or 0)

        if count >= max_concurrent:
            return False, f"Concurrent limit exceeded: {max_concurrent} max"

        return True, None

    def acquire_slot(self, tenant_id: int, tool: str, execution_id: str):
        """Acquire execution slot"""
        key = f"concurrent:{tenant_id}:{tool}"
        self.redis.incr(key)
        self.redis.expire(key, 1800)  # 30 minutes max

        # Track execution ID
        tracking_key = f"execution:{execution_id}"
        self.redis.setex(tracking_key, 1800, tenant_id)

    def release_slot(self, tenant_id: int, tool: str, execution_id: str):
        """Release execution slot"""
        key = f"concurrent:{tenant_id}:{tool}"
        count = self.redis.decr(key)
        if count <= 0:
            self.redis.delete(key)

        # Remove tracking
        tracking_key = f"execution:{execution_id}"
        self.redis.delete(tracking_key)
```

**RL-002**: Global Rate Limiting
- Overall platform limit: 1000 tool executions per minute
- Per-tool limits configurable
- Exponential backoff on limit exceeded
- Priority queue for paid tiers

**RL-003**: Adaptive Rate Limiting
- Reduce limits on high error rates
- Increase limits for well-behaved tenants
- Track reputation score per tenant
- Automatic throttling on abuse detection

---

## 6. Data Redaction Rules

### 6.1 Comprehensive Redaction Patterns

```python
# app/utils/data_redaction.py
import re
from typing import Dict, List

class DataRedactor:
    """Centralized data redaction for sensitive information"""

    # Credential patterns (expanded)
    CREDENTIAL_PATTERNS = {
        'api_key': [
            r'api[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})',
            r'apikey["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})',
        ],
        'password': [
            r'password["\']?\s*[:=]\s*["\']?([^\s"\'&]{6,})',
            r'passwd["\']?\s*[:=]\s*["\']?([^\s"\'&]{6,})',
            r'pwd["\']?\s*[:=]\s*["\']?([^\s"\'&]{6,})',
        ],
        'token': [
            r'token["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})',
            r'auth[_-]?token["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{20,})',
        ],
        'secret': [
            r'secret["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})',
            r'client[_-]?secret["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})',
        ],
        'private_key': [
            r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----.*?-----END (?:RSA |EC |DSA )?PRIVATE KEY-----',
            r'private[_-]?key["\']?\s*[:=]\s*["\']?([^\s"\']{40,})',
        ],
        'jwt': [
            r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*',
        ],
        'aws_key': [
            r'AKIA[0-9A-Z]{16}',
            r'aws[_-]?access[_-]?key[_-]?id["\']?\s*[:=]\s*["\']?([A-Z0-9]{20})',
        ],
    }

    # Email patterns
    EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

    # Credit card patterns (PCI-DSS compliance)
    CC_PATTERN = r'\b(?:\d{4}[-\s]?){3}\d{4}\b'

    # IP address patterns (internal only)
    INTERNAL_IP_PATTERNS = [
        r'\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        r'\b172\.(1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}\b',
        r'\b192\.168\.\d{1,3}\.\d{1,3}\b',
        r'\b127\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
    ]

    # Session ID patterns
    SESSION_PATTERNS = [
        r'PHPSESSID=([a-zA-Z0-9]{20,})',
        r'JSESSIONID=([a-zA-Z0-9]{32,})',
        r'session[_-]?id["\']?\s*[:=]\s*["\']?([a-zA-Z0-9]{20,})',
    ]

    @classmethod
    def redact_credentials(cls, text: str) -> Tuple[str, List[str]]:
        """Redact all credential patterns from text"""
        redacted_types = []

        for cred_type, patterns in cls.CREDENTIAL_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.DOTALL | re.IGNORECASE):
                    text = re.sub(
                        pattern,
                        f'[REDACTED-{cred_type.upper()}]',
                        text,
                        flags=re.DOTALL | re.IGNORECASE
                    )
                    redacted_types.append(cred_type)

        return text, list(set(redacted_types))

    @classmethod
    def redact_email(cls, text: str, preserve_domain: bool = False) -> str:
        """Redact email addresses"""
        if preserve_domain:
            # Keep domain for analysis
            return re.sub(
                cls.EMAIL_PATTERN,
                lambda m: f'[REDACTED]@{m.group(0).split("@")[1]}',
                text
            )
        else:
            return re.sub(cls.EMAIL_PATTERN, '[REDACTED-EMAIL]', text)

    @classmethod
    def redact_internal_ips(cls, text: str) -> str:
        """Redact internal IP addresses"""
        for pattern in cls.INTERNAL_IP_PATTERNS:
            text = re.sub(pattern, '[REDACTED-INTERNAL-IP]', text)
        return text

    @classmethod
    def redact_credit_cards(cls, text: str) -> str:
        """Redact credit card numbers (PCI-DSS)"""
        return re.sub(cls.CC_PATTERN, '[REDACTED-CC]', text)

    @classmethod
    def redact_sessions(cls, text: str) -> str:
        """Redact session IDs"""
        for pattern in cls.SESSION_PATTERNS:
            text = re.sub(pattern, r'\1=[REDACTED-SESSION]', text)
        return text

    @classmethod
    def redact_all(cls, text: str) -> Tuple[str, Dict[str, int]]:
        """Apply all redaction rules and return statistics"""
        stats = {}

        # Credentials
        text, cred_types = cls.redact_credentials(text)
        stats['credentials'] = len(cred_types)

        # Emails
        original_len = len(text)
        text = cls.redact_email(text)
        stats['emails'] = (original_len - len(text)) // 10  # Rough estimate

        # Internal IPs
        original_len = len(text)
        text = cls.redact_internal_ips(text)
        stats['internal_ips'] = (original_len - len(text)) // 20

        # Credit cards
        original_len = len(text)
        text = cls.redact_credit_cards(text)
        stats['credit_cards'] = (original_len - len(text)) // 16

        # Sessions
        text = cls.redact_sessions(text)

        return text, stats
```

### 6.2 Redaction Policy by Tool

| Tool   | Redact Credentials | Redact Emails | Redact IPs | Redact HTML |
|--------|-------------------|---------------|------------|-------------|
| HTTPx  | Yes               | No*           | Internal   | Yes         |
| Naabu  | N/A               | N/A           | No         | N/A         |
| TLSx   | Yes (CRITICAL)    | Yes           | Internal   | N/A         |
| Katana | Yes               | Preserve**    | Internal   | Yes         |

*Preserve for contact discovery
**Preserve domain for analysis (user@[REDACTED].com becomes [REDACTED]@example.com)

---

## 7. Threat Model Analysis

### 7.1 Threat Actors

**TA-001**: External Attacker
- **Goal**: Exploit SSRF to access internal resources
- **Capabilities**: Can submit malicious domains/URLs
- **Mitigations**: Input validation, SSRF prevention, network isolation

**TA-002**: Malicious Tenant
- **Goal**: DoS platform, scan unauthorized targets, data exfiltration
- **Capabilities**: Valid account, can submit scan requests
- **Mitigations**: Rate limiting, resource limits, audit logging, tenant isolation

**TA-003**: Insider Threat
- **Goal**: Access other tenants' data, privilege escalation
- **Capabilities**: Database access, application knowledge
- **Mitigations**: Tenant isolation, audit logging, least privilege

**TA-004**: Supply Chain Attacker
- **Goal**: Compromise tool binaries
- **Capabilities**: MITM, compromised repositories
- **Mitigations**: Checksum validation (already implemented), signature verification

### 7.2 Attack Scenarios and Mitigations

#### Scenario 1: SSRF via HTTPx to AWS Metadata

**Attack Flow**:
1. Attacker submits URL: `http://169.254.169.254/latest/meta-data/iam/security-credentials/`
2. HTTPx executes request
3. AWS metadata returns IAM credentials
4. Credentials stored in database
5. Attacker retrieves credentials

**Mitigations**:
- **SR-HTTPx-001**: URL validation blocks metadata endpoint
- **NSC-001**: Network validator detects blocked IP
- **NSC-004**: IP 169.254.169.254 explicitly blocked
- **OSR-HTTPx-001**: Output sanitizer redacts any credentials
- **Impact**: Attack prevented at multiple layers (defense in depth)

#### Scenario 2: Port Scan of Internal Database

**Attack Flow**:
1. Attacker submits Naabu scan: target=192.168.1.10, ports=5432
2. Naabu scans internal PostgreSQL server
3. Discovers open port 5432
4. Attacker uses information for lateral movement

**Mitigations**:
- **SR-Naabu-001**: Target validation blocks RFC1918 addresses
- **SR-Naabu-002**: Port 5432 (PostgreSQL) blocked by default
- **SR-Naabu-005**: Scan attempt logged for security monitoring
- **NSC-003**: Network namespace prevents internal access
- **Impact**: Attack prevented at input validation

#### Scenario 3: Private Key Leakage via TLSx

**Attack Flow**:
1. Attacker submits TLSx scan of misconfigured server
2. Server mistakenly returns private key in response
3. TLSx tool captures private key
4. Private key stored in database
5. Attacker retrieves private key from results

**Mitigations**:
- **SR-TLSx-002**: Private key patterns detected and redacted
- **OSR-TLSx-001**: Output sanitizer alerts security team
- **OSR-TLSx-001**: Private key replaced with [REDACTED-PRIVATE-KEY]
- **SR-TLSx-002**: Security incident logged for forensics
- **Impact**: Private key never stored, security team alerted

#### Scenario 4: Infinite Crawl DoS via Katana

**Attack Flow**:
1. Attacker submits Katana crawl with seed URL to site with infinite pagination
2. Crawler follows pagination links indefinitely
3. Memory and CPU exhausted
4. Platform becomes unresponsive

**Mitigations**:
- **SR-Katana-004**: Maximum depth (3 levels) enforced
- **SR-Katana-004**: Maximum pages (1000) enforced
- **SR-Katana-004**: Total timeout (5 minutes) enforced
- **RL-001**: Resource limits (1GB memory, 1 CPU) enforced
- **SR-Katana-004**: Duplicate URL detection prevents loops
- **Impact**: Crawl terminates with partial results, no DoS

#### Scenario 5: Credential Leakage in Crawled URLs

**Attack Flow**:
1. Katana crawls site and discovers URL with password parameter
2. URL stored: `https://example.com/reset?token=SECRET123&password=MyPassword123`
3. Credentials visible in stored data
4. Cross-tenant access vulnerability allows other tenant to see URL

**Mitigations**:
- **SR-Katana-008**: Credential detection in URLs
- **OSR-Katana-001**: URL parameters redacted before storage
- **OSR-Katana-001**: Security alert on credential detection
- **Tenant Isolation**: Cross-tenant access prevented (already implemented)
- **Impact**: Credentials redacted, only structure stored

#### Scenario 6: XSS via Stored HTTPx Response

**Attack Flow**:
1. HTTPx fetches page with XSS payload: `<script>alert('XSS')</script>`
2. HTML content stored in database
3. Admin views results in UI
4. XSS executes in admin's browser

**Mitigations**:
- **SR-HTTPx-004**: HTML sanitization with bleach library
- **OSR-HTTPx-001**: JavaScript stripped from HTML
- **OSR-HTTPx-001**: Dangerous protocols removed
- **Frontend**: Content-Security-Policy prevents inline scripts
- **Impact**: XSS payload neutralized before storage

### 7.3 Threat Matrix

| Threat ID | Threat | Likelihood | Impact | Risk | Primary Mitigation |
|-----------|--------|------------|--------|------|-------------------|
| THR-001 | SSRF to AWS metadata via HTTPx | Medium | Critical | HIGH | URLValidator + NetworkSecurityValidator |
| THR-002 | SSRF to internal DB via Naabu | Medium | High | HIGH | DomainValidator + blocked ports |
| THR-003 | Private key exposure via TLSx | Low | Critical | MEDIUM | Private key redaction + alerts |
| THR-004 | Infinite crawl DoS via Katana | High | Medium | HIGH | Depth/page limits + timeouts |
| THR-005 | Credential leak in crawled URLs | Medium | High | HIGH | Credential detection + redaction |
| THR-006 | XSS via stored HTTPx response | Medium | Medium | MEDIUM | HTML sanitization |
| THR-007 | Port scan legal issues | Low | High | MEDIUM | User consent + audit logging |
| THR-008 | Resource exhaustion (any tool) | High | Medium | HIGH | Resource limits + rate limiting |
| THR-009 | robots.txt violation | Medium | Low | LOW | robots.txt compliance |
| THR-010 | Header injection via tool args | Low | High | MEDIUM | Argument sanitization |
| THR-011 | DNS rebinding attack | Low | High | MEDIUM | DNS re-validation |
| THR-012 | Redirect chain SSRF | Medium | High | HIGH | Per-redirect validation |
| THR-013 | Large response DoS | High | Medium | HIGH | Response size limits |
| THR-014 | Tenant cross-access via tools | Low | Critical | MEDIUM | Tenant isolation (existing) |
| THR-015 | Tool binary compromise | Low | Critical | MEDIUM | Checksum validation (existing) |

---

## 8. Security Testing Requirements

### 8.1 Unit Tests

**Test Coverage Requirements**: 90% minimum for security-critical code

```python
# tests/security/test_tool_validators.py
import pytest
from app.utils.tool_validators import ToolInputValidator
from app.utils.network_security import NetworkSecurityValidator

class TestHTTPxValidator:
    """Test HTTPx input validation"""

    def test_blocks_metadata_endpoint(self):
        """Test: Block AWS metadata endpoint"""
        url = "http://169.254.169.254/latest/meta-data/"
        is_valid, error = ToolInputValidator.validate_httpx_input(url)
        assert not is_valid
        assert "metadata" in error.lower()

    def test_blocks_internal_ip(self):
        """Test: Block RFC1918 private networks"""
        urls = [
            "http://10.0.0.1/",
            "http://192.168.1.1/",
            "http://172.16.0.1/"
        ]
        for url in urls:
            is_valid, error = ToolInputValidator.validate_httpx_input(url)
            assert not is_valid, f"Should block: {url}"

    def test_blocks_file_scheme(self):
        """Test: Block file:// scheme"""
        url = "file:///etc/passwd"
        is_valid, error = ToolInputValidator.validate_httpx_input(url)
        assert not is_valid
        assert "scheme" in error.lower()

    def test_allows_public_https(self):
        """Test: Allow valid HTTPS URL"""
        url = "https://example.com/"
        is_valid, error = ToolInputValidator.validate_httpx_input(url)
        assert is_valid
        assert error is None

class TestNaabuValidator:
    """Test Naabu input validation"""

    def test_blocks_internal_ip(self):
        """Test: Block internal IP addresses"""
        is_valid, error = ToolInputValidator.validate_naabu_input(
            "192.168.1.1", "80"
        )
        assert not is_valid

    def test_blocks_dangerous_ports(self):
        """Test: Block SSH, RDP, database ports"""
        dangerous_ports = ["22", "3389", "5432", "3306"]
        for port in dangerous_ports:
            is_valid, error = ToolInputValidator.validate_naabu_input(
                "example.com", port
            )
            assert not is_valid, f"Should block port: {port}"

    def test_allows_web_ports(self):
        """Test: Allow common web ports"""
        is_valid, error = ToolInputValidator.validate_naabu_input(
            "example.com", "80,443,8080"
        )
        assert is_valid

    def test_enforces_port_limit(self):
        """Test: Enforce maximum 1000 ports per scan"""
        ports = ",".join(str(i) for i in range(1, 1002))
        is_valid, error = ToolInputValidator.validate_naabu_input(
            "example.com", ports
        )
        assert not is_valid
        assert "1000" in error

class TestTLSxValidator:
    """Test TLSx input validation"""

    def test_requires_https(self):
        """Test: Require HTTPS scheme"""
        is_valid, error = ToolInputValidator.validate_tlsx_input(
            "http://example.com"
        )
        assert not is_valid
        assert "https" in error.lower()

    def test_blocks_metadata_endpoint(self):
        """Test: Block cloud metadata endpoints"""
        is_valid, error = ToolInputValidator.validate_tlsx_input(
            "https://metadata.google.internal/"
        )
        assert not is_valid

class TestKatanaValidator:
    """Test Katana input validation"""

    def test_enforces_depth_limit(self):
        """Test: Enforce depth between 1-5"""
        is_valid, error = ToolInputValidator.validate_katana_input(
            "https://example.com", max_depth=10
        )
        assert not is_valid
        assert "depth" in error.lower()

    def test_validates_seed_url(self):
        """Test: Validate seed URL format"""
        is_valid, error = ToolInputValidator.validate_katana_input(
            "not-a-url"
        )
        assert not is_valid

class TestOutputSanitizers:
    """Test output sanitization"""

    def test_httpx_redacts_auth_headers(self):
        """Test: Redact Authorization headers"""
        from app.utils.output_sanitizers import HTTPxOutputSanitizer

        output = {
            'headers': {
                'Authorization': 'Bearer SECRET_TOKEN',
                'Content-Type': 'text/html'
            }
        }

        sanitized = HTTPxOutputSanitizer().sanitize(output)
        assert sanitized['headers']['Authorization'] == '[REDACTED]'
        assert sanitized['headers']['Content-Type'] == 'text/html'

    def test_tlsx_redacts_private_keys(self):
        """Test: Redact private keys from TLSx output"""
        from app.utils.output_sanitizers import TLSxOutputSanitizer

        output = {
            'certificate': 'CERT_DATA',
            'private_key': '-----BEGIN PRIVATE KEY-----\nSECRET\n-----END PRIVATE KEY-----'
        }

        sanitized = TLSxOutputSanitizer().sanitize(output)
        assert sanitized['private_key'] == '[REDACTED-PRIVATE-KEY]'
        assert sanitized['certificate'] == 'CERT_DATA'

    def test_katana_redacts_credentials_in_urls(self):
        """Test: Redact credentials from URLs"""
        from app.utils.output_sanitizers import KatanaOutputSanitizer

        output = {
            'urls': [
                'https://example.com/reset?password=SECRET123',
                'https://example.com/api?api_key=APIKEY123'
            ]
        }

        sanitized = KatanaOutputSanitizer().sanitize(output)
        assert '[REDACTED]' in sanitized['urls'][0]
        assert '[REDACTED]' in sanitized['urls'][1]
        assert 'SECRET123' not in sanitized['urls'][0]
        assert 'APIKEY123' not in sanitized['urls'][1]

class TestNetworkSecurity:
    """Test network security controls"""

    def test_detects_private_networks(self):
        """Test: Detect RFC1918 private networks"""
        private_hosts = [
            '10.0.0.1',
            '172.16.0.1',
            '192.168.1.1',
            '127.0.0.1'
        ]

        for host in private_hosts:
            is_safe, error = NetworkSecurityValidator.is_safe_target(host)
            assert not is_safe, f"Should block: {host}"

    def test_allows_public_ips(self):
        """Test: Allow public IP addresses"""
        public_hosts = [
            '8.8.8.8',
            '1.1.1.1',
            'example.com'
        ]

        for host in public_hosts:
            is_safe, error = NetworkSecurityValidator.is_safe_target(host)
            assert is_safe, f"Should allow: {host}"

    def test_validates_redirects(self):
        """Test: Validate redirect destinations"""
        original = "https://example.com/"
        redirect = "http://169.254.169.254/meta-data/"

        is_safe, error = NetworkSecurityValidator.validate_redirect(
            original, redirect
        )
        assert not is_safe

class TestRateLimiting:
    """Test rate limiting"""

    @pytest.fixture
    def rate_limiter(self, redis_client):
        from app.utils.rate_limiter import ToolRateLimiter
        return ToolRateLimiter(redis_client)

    def test_enforces_per_minute_limit(self, rate_limiter):
        """Test: Enforce rate limit per minute"""
        tenant_id = 1
        tool = 'httpx'
        limit = 10

        # Make requests up to limit
        for i in range(limit):
            allowed, _ = rate_limiter.check_rate_limit(tenant_id, tool, limit)
            assert allowed, f"Request {i+1} should be allowed"

        # Next request should be blocked
        allowed, error = rate_limiter.check_rate_limit(tenant_id, tool, limit)
        assert not allowed
        assert "rate limit" in error.lower()

    def test_enforces_concurrent_limit(self, rate_limiter):
        """Test: Enforce concurrent execution limit"""
        tenant_id = 1
        tool = 'naabu'
        max_concurrent = 3

        # Acquire slots
        for i in range(max_concurrent):
            allowed, _ = rate_limiter.check_concurrent_limit(
                tenant_id, tool, max_concurrent
            )
            assert allowed
            rate_limiter.acquire_slot(tenant_id, tool, f"exec_{i}")

        # Next acquisition should fail
        allowed, error = rate_limiter.check_concurrent_limit(
            tenant_id, tool, max_concurrent
        )
        assert not allowed
```

### 8.2 Integration Tests

```python
# tests/integration/test_tool_security_integration.py
import pytest
from fastapi.testclient import TestClient

class TestToolSecurityIntegration:
    """Integration tests for tool security"""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self, client):
        # Login and get token
        response = client.post("/api/v1/auth/login", json={
            "username": "test_user",
            "password": "test_password"
        })
        token = response.json()['access_token']
        return {"Authorization": f"Bearer {token}"}

    def test_httpx_blocks_ssrf_attempt(self, client, auth_headers):
        """Test: HTTPx blocks SSRF to metadata endpoint"""
        response = client.post(
            "/api/v1/tools/httpx",
            headers=auth_headers,
            json={
                "url": "http://169.254.169.254/latest/meta-data/"
            }
        )

        assert response.status_code == 400
        assert "blocked" in response.json()['detail'].lower()

    def test_naabu_blocks_internal_scan(self, client, auth_headers):
        """Test: Naabu blocks internal network scan"""
        response = client.post(
            "/api/v1/tools/naabu",
            headers=auth_headers,
            json={
                "target": "192.168.1.1",
                "ports": "1-1000"
            }
        )

        assert response.status_code == 400
        assert "blocked" in response.json()['detail'].lower()

    def test_katana_respects_depth_limit(self, client, auth_headers):
        """Test: Katana enforces depth limit"""
        response = client.post(
            "/api/v1/tools/katana",
            headers=auth_headers,
            json={
                "seed_url": "https://example.com",
                "max_depth": 10  # Exceeds limit
            }
        )

        assert response.status_code == 400
        assert "depth" in response.json()['detail'].lower()

    def test_rate_limiting_enforcement(self, client, auth_headers):
        """Test: Rate limiting blocks excessive requests"""
        # Make requests up to limit
        for i in range(10):
            response = client.post(
                "/api/v1/tools/httpx",
                headers=auth_headers,
                json={"url": f"https://example{i}.com"}
            )
            assert response.status_code in [200, 202]

        # Next request should be rate limited
        response = client.post(
            "/api/v1/tools/httpx",
            headers=auth_headers,
            json={"url": "https://example-extra.com"}
        )

        assert response.status_code == 429
        assert "rate limit" in response.json()['detail'].lower()

    def test_output_sanitization_in_response(self, client, auth_headers, mocker):
        """Test: Output is sanitized before returning"""
        # Mock tool execution to return sensitive data
        mock_output = {
            'headers': {
                'Authorization': 'Bearer SECRET_TOKEN'
            }
        }

        mocker.patch(
            'app.tasks.run_httpx_tool',
            return_value=mock_output
        )

        response = client.post(
            "/api/v1/tools/httpx",
            headers=auth_headers,
            json={"url": "https://example.com"}
        )

        # Check that sensitive header is redacted
        result = response.json()
        assert result['headers']['Authorization'] == '[REDACTED]'
```

### 8.3 Penetration Testing Scenarios

**Manual Penetration Tests - Execute Before Deployment**

```bash
#!/bin/bash
# scripts/security_pentest.sh
# Penetration testing script for new tools

echo "=========================================="
echo "EASM Tool Security Penetration Tests"
echo "=========================================="

API_BASE="http://localhost:8000/api/v1"
TOKEN="your_test_token_here"

# Test 1: SSRF to AWS metadata
echo -e "\n[TEST 1] SSRF to AWS metadata endpoint"
curl -X POST "$API_BASE/tools/httpx" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "http://169.254.169.254/latest/meta-data/"}' \
  -w "\nStatus: %{http_code}\n"
echo "Expected: 400 Bad Request"

# Test 2: SSRF to GCP metadata
echo -e "\n[TEST 2] SSRF to GCP metadata endpoint"
curl -X POST "$API_BASE/tools/httpx" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "http://metadata.google.internal/computeMetadata/v1/"}' \
  -w "\nStatus: %{http_code}\n"
echo "Expected: 400 Bad Request"

# Test 3: Internal network scan
echo -e "\n[TEST 3] Scan internal network"
curl -X POST "$API_BASE/tools/naabu" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.1", "ports": "22,445,3389"}' \
  -w "\nStatus: %{http_code}\n"
echo "Expected: 400 Bad Request"

# Test 4: Command injection via domain
echo -e "\n[TEST 4] Command injection via domain"
curl -X POST "$API_BASE/tools/httpx" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "http://example.com;whoami/"}' \
  -w "\nStatus: %{http_code}\n"
echo "Expected: 400 Bad Request"

# Test 5: Path traversal
echo -e "\n[TEST 5] Path traversal in URL"
curl -X POST "$API_BASE/tools/httpx" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "http://example.com/../../etc/passwd"}' \
  -w "\nStatus: %{http_code}\n"
echo "Expected: 400 Bad Request (or safe handling)"

# Test 6: Rate limiting
echo -e "\n[TEST 6] Rate limiting enforcement"
for i in {1..15}; do
  curl -X POST "$API_BASE/tools/httpx" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"url\": \"https://example$i.com\"}" \
    -w "Request $i - Status: %{http_code}\n" \
    -s -o /dev/null
done
echo "Expected: First 10 succeed, rest return 429"

# Test 7: Crawl depth limit
echo -e "\n[TEST 7] Crawl depth limit enforcement"
curl -X POST "$API_BASE/tools/katana" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"seed_url": "https://example.com", "max_depth": 100}' \
  -w "\nStatus: %{http_code}\n"
echo "Expected: 400 Bad Request"

# Test 8: File scheme SSRF
echo -e "\n[TEST 8] File scheme SSRF attempt"
curl -X POST "$API_BASE/tools/katana" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"seed_url": "file:///etc/passwd"}' \
  -w "\nStatus: %{http_code}\n"
echo "Expected: 400 Bad Request"

# Test 9: Redirect to internal IP
echo -e "\n[TEST 9] Redirect to internal IP (requires test server)"
# This test requires a server that redirects to internal IP
# Setup: python3 -m http.server 8888 with redirect to 192.168.1.1
curl -X POST "$API_BASE/tools/httpx" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "http://localhost:8888/redirect-to-internal"}' \
  -w "\nStatus: %{http_code}\n"
echo "Expected: 400 Bad Request (blocked redirect)"

# Test 10: Cross-tenant access
echo -e "\n[TEST 10] Cross-tenant data access"
TOKEN_TENANT_A="tenant_a_token"
TOKEN_TENANT_B="tenant_b_token"

# Create scan as Tenant A
SCAN_ID=$(curl -X POST "$API_BASE/tools/httpx" \
  -H "Authorization: Bearer $TOKEN_TENANT_A" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}' \
  -s | jq -r '.scan_id')

# Try to access as Tenant B
curl -X GET "$API_BASE/scans/$SCAN_ID" \
  -H "Authorization: Bearer $TOKEN_TENANT_B" \
  -w "\nStatus: %{http_code}\n"
echo "Expected: 403 Forbidden"

echo -e "\n=========================================="
echo "Penetration Testing Complete"
echo "=========================================="
```

### 8.4 Automated Security Scanning

**CI/CD Security Checks**

```yaml
# .github/workflows/security-scan.yml
name: Security Scan

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  security-scan:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Run Bandit (Python security linter)
        run: |
          pip install bandit
          bandit -r app/ -f json -o bandit-report.json

      - name: Run Safety (dependency scanner)
        run: |
          pip install safety
          safety check --file requirements.txt --json

      - name: Run Trivy (container scanner)
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'

      - name: Run OWASP ZAP (dynamic scan)
        run: |
          docker run -v $(pwd):/zap/wrk/:rw -t owasp/zap2docker-stable \
            zap-api-scan.py -t http://localhost:8000/api/v1/openapi.json \
            -f openapi -r zap-report.html

      - name: Run custom security checklist
        run: |
          python scripts/security_checklist.py

      - name: Upload security reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: |
            bandit-report.json
            trivy-results.sarif
            zap-report.html
```

---

## 9. Compliance and Legal Considerations

### 9.1 Port Scanning Compliance

**Legal Requirements**

**COMP-001**: User Consent
- **Requirement**: Users MUST consent to port scanning before execution
- **Implementation**:
  ```python
  class PortScanConsent:
      """Manage port scanning consent"""

      CONSENT_TEXT = """
      Port Scanning Terms and Conditions

      By enabling port scanning, you acknowledge and agree that:

      1. You will ONLY scan networks, systems, and assets that you own or
         have explicit written permission to scan.

      2. Unauthorized port scanning may be illegal in your jurisdiction and
         may violate the Computer Fraud and Abuse Act (CFAA) in the United States
         or equivalent laws in other countries.

      3. You are solely responsible for compliance with all applicable laws
         and regulations.

      4. The platform provider is not responsible for your use of port
         scanning tools.

      5. All port scanning activities are logged and may be reported to
         authorities if abuse is detected.

      6. You will immediately stop scanning if requested by the target
         network owner.

      By clicking "I Agree", you certify that you have read, understood,
      and agree to these terms.
      """

      @staticmethod
      def require_consent(tenant_id: int) -> bool:
          """Check if tenant has consented to port scanning"""
          consent = db.query(PortScanConsentRecord).filter(
              PortScanConsentRecord.tenant_id == tenant_id,
              PortScanConsentRecord.is_valid == True
          ).first()

          if not consent:
              return False

          # Check if consent is still valid (1 year)
          if datetime.utcnow() - consent.consent_date > timedelta(days=365):
              return False

          return True

      @staticmethod
      def record_consent(tenant_id: int, user_id: int, ip_address: str):
          """Record user consent"""
          consent = PortScanConsentRecord(
              tenant_id=tenant_id,
              user_id=user_id,
              consent_date=datetime.utcnow(),
              ip_address=ip_address,
              user_agent=request.headers.get('User-Agent'),
              is_valid=True
          )
          db.add(consent)
          db.commit()
  ```

**COMP-002**: Audit Logging
- All port scans MUST be logged with:
  - Timestamp
  - Tenant ID
  - User ID
  - Target (domain/IP)
  - Port range
  - Scan duration
  - Results count
  - IP address of requester
- Retention: 90 days minimum (configurable: 180-365 days)
- Tamper-evident logging (append-only)

**COMP-003**: Rate Limiting for Abuse Prevention
- Maximum 10 scans per tenant per hour
- Maximum 100 scans per tenant per day
- Alert security team on threshold exceeded
- Automatic suspension on abuse detection

### 9.2 Web Crawling Compliance

**COMP-004**: robots.txt Compliance
- **Requirement**: Katana MUST respect robots.txt
- **Implementation**:
  - Fetch robots.txt before crawling
  - Parse User-agent directives
  - Respect Disallow rules
  - Honor Crawl-delay directive
  - If crawl is blocked, return error (not silently fail)
  - Cache robots.txt for 24 hours

**COMP-005**: security.txt Compliance
- **Requirement**: Respect security.txt if present
- **Implementation**:
  - Check for /.well-known/security.txt
  - Parse security policy
  - Option to skip domains with restrictive policies
  - Log security.txt presence

**COMP-006**: User-Agent Identification
- **Requirement**: Tools MUST identify themselves clearly
- **Implementation**:
  - User-Agent: "EASM-Scanner/1.0 (+https://easm-platform.example.com/bot)"
  - Provide contact information in User-Agent
  - Maintain information page about bot behavior

### 9.3 GDPR and Data Privacy

**COMP-007**: Data Minimization
- Only collect data necessary for EASM purposes
- Do not store full HTML content (only metadata)
- Redact email addresses (or preserve domain only)
- No collection of personal information from crawled pages

**COMP-008**: Right to Erasure
- Provide mechanism for domain owners to request data deletion
- Process deletion requests within 30 days
- Verify ownership before deletion

**COMP-009**: Data Retention
```python
# Data retention policy
DATA_RETENTION_POLICY = {
    'httpx_responses': 90,      # days
    'naabu_results': 180,       # days
    'tlsx_certificates': 365,   # days (longer for cert tracking)
    'katana_crawls': 90,        # days
    'audit_logs': 365,          # days (compliance requirement)
}
```

### 9.4 PCI-DSS Considerations

**COMP-010**: Credit Card Data Protection
- NEVER store credit card numbers
- Use DataRedactor to detect and redact CC patterns
- If detected, alert security team
- Scan all tool outputs for PCI data

### 9.5 Export Control Compliance

**COMP-011**: Restricted Destinations
- Block scanning of domains in sanctioned countries (if required by jurisdiction)
- Configurable blocked country list
- GeoIP validation for target domains (optional)

---

## 10. Implementation Guidance

### 10.1 Implementation Priority

**Phase 1 (Critical - Week 1 Days 1-2)**
1. Implement tool input validators (ToolInputValidator class)
2. Implement network security validator (NetworkSecurityValidator class)
3. Implement output sanitizers for all 4 tools
4. Update SecureToolExecutor with new validators

**Phase 2 (High - Week 1 Days 3-4)**
5. Implement rate limiting (ToolRateLimiter class)
6. Implement data redaction (DataRedactor class)
7. Add resource limits to tool configurations
8. Implement audit logging for sensitive operations

**Phase 3 (Medium - Week 1 Day 5)**
9. Implement port scan consent system
10. Add robots.txt compliance to Katana
11. Update security checklist script
12. Write unit tests (90% coverage target)

**Phase 4 (Testing - Week 2 Days 1-2)**
13. Integration testing
14. Penetration testing
15. Performance testing with security controls
16. Fix bugs and security issues

### 10.2 Code Integration Pattern

**Pattern: Secure Tool Execution Wrapper**

```python
# app/tasks/tool_tasks.py
from app.utils.secure_executor import SecureToolExecutor
from app.utils.tool_validators import ToolInputValidator
from app.utils.output_sanitizers import HTTPxOutputSanitizer
from app.utils.network_security import NetworkSecurityValidator
from app.utils.rate_limiter import ToolRateLimiter

@celery_app.task(bind=True)
def run_httpx_task(self, scan_id: int, url: str, tenant_id: int):
    """Execute HTTPx with full security controls"""

    # Phase 1: Input Validation
    is_valid, error = ToolInputValidator.validate_httpx_input(url)
    if not is_valid:
        raise ToolExecutionError(f"Input validation failed: {error}")

    # Phase 2: Network Security Check
    from urllib.parse import urlparse
    hostname = urlparse(url).hostname
    is_safe, error = NetworkSecurityValidator.is_safe_target(hostname)
    if not is_safe:
        raise ToolExecutionError(f"Network security check failed: {error}")

    # Phase 3: Rate Limiting Check
    rate_limiter = ToolRateLimiter(redis_client)
    allowed, error = rate_limiter.check_rate_limit(tenant_id, 'httpx', limit=10)
    if not allowed:
        raise ToolExecutionError(f"Rate limit exceeded: {error}")

    allowed, error = rate_limiter.check_concurrent_limit(tenant_id, 'httpx', max_concurrent=3)
    if not allowed:
        raise ToolExecutionError(f"Concurrent limit exceeded: {error}")

    # Phase 4: Acquire Execution Slot
    execution_id = self.request.id
    rate_limiter.acquire_slot(tenant_id, 'httpx', execution_id)

    try:
        # Phase 5: Execute Tool with SecureToolExecutor
        with SecureToolExecutor(tenant_id) as executor:
            returncode, stdout, stderr = executor.execute(
                tool='httpx',
                args=['-u', url, '-json', '-silent'],
                timeout=300
            )

        # Phase 6: Parse Output
        import json
        try:
            output = json.loads(stdout)
        except json.JSONDecodeError:
            raise ToolExecutionError(f"Invalid JSON output: {stdout[:100]}")

        # Phase 7: Sanitize Output
        sanitizer = HTTPxOutputSanitizer()
        sanitized_output = sanitizer.sanitize(output)

        # Phase 8: Store Results
        result = ToolResult(
            scan_id=scan_id,
            tool='httpx',
            tenant_id=tenant_id,
            output=sanitized_output,
            executed_at=datetime.utcnow()
        )
        db.add(result)
        db.commit()

        # Phase 9: Audit Logging
        audit_log = AuditLog(
            tenant_id=tenant_id,
            action='httpx_execution',
            resource=url,
            result='success',
            timestamp=datetime.utcnow()
        )
        db.add(audit_log)
        db.commit()

        return {'status': 'success', 'result_id': result.id}

    except Exception as e:
        # Error logging
        logger.error(f"HTTPx execution failed: {e}")

        # Audit log failure
        audit_log = AuditLog(
            tenant_id=tenant_id,
            action='httpx_execution',
            resource=url,
            result='failure',
            error=str(e),
            timestamp=datetime.utcnow()
        )
        db.add(audit_log)
        db.commit()

        raise

    finally:
        # Phase 10: Release Execution Slot
        rate_limiter.release_slot(tenant_id, 'httpx', execution_id)
```

### 10.3 Configuration Updates

**Update app/config.py**:

```python
# Add to Settings class

# HTTPx Configuration
httpx_max_response_size: int = 10 * 1024 * 1024  # 10MB
httpx_max_redirects: int = 5
httpx_redirect_timeout: int = 30
httpx_concurrent_requests: int = 10
httpx_rate_limit_per_second: int = 10

# Naabu Configuration
naabu_max_ports: int = 1000
naabu_max_packets_per_second: int = 1000
naabu_host_timeout: int = 30
naabu_concurrent_scans_per_tenant: int = 3
naabu_scan_interval: int = 60
naabu_require_consent: bool = True

# TLSx Configuration
tlsx_connection_timeout: int = 30
tlsx_max_handshake_attempts: int = 3
tlsx_concurrent_connections: int = 5

# Katana Configuration
katana_max_depth: int = 3
katana_max_pages: int = 1000
katana_max_page_size: int = 5 * 1024 * 1024  # 5MB
katana_request_rate_per_second: int = 5
katana_respect_robots_txt: bool = True
katana_page_timeout: int = 30

# Security Settings
security_block_internal_networks: bool = True
security_block_cloud_metadata: bool = True
security_require_https_for_tls: bool = True
security_redact_credentials: bool = True
security_redact_private_keys: bool = True
security_alert_on_private_key: bool = True

# Rate Limiting (per tenant per minute)
rate_limit_httpx: int = 10
rate_limit_naabu: int = 5
rate_limit_tlsx: int = 10
rate_limit_katana: int = 5
```

### 10.4 Database Schema Updates

**New Tables for Compliance**:

```sql
-- Port scan consent tracking
CREATE TABLE port_scan_consent (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    consent_date TIMESTAMP NOT NULL,
    expiry_date TIMESTAMP NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT,
    is_valid BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_tenant_consent UNIQUE (tenant_id)
);

-- Enhanced audit logging
CREATE TABLE tool_audit_log (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    tool VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    target TEXT NOT NULL,
    input_hash VARCHAR(64),  -- SHA256 of input for forensics
    result VARCHAR(20),  -- success, failure, blocked
    error_message TEXT,
    execution_time_ms INTEGER,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    INDEX idx_tenant_timestamp (tenant_id, timestamp),
    INDEX idx_tool_timestamp (tool, timestamp)
);

-- Security incidents
CREATE TABLE security_incidents (
    id SERIAL PRIMARY KEY,
    incident_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,  -- low, medium, high, critical
    tenant_id INTEGER REFERENCES tenants(id),
    user_id INTEGER REFERENCES users(id),
    description TEXT NOT NULL,
    details JSONB,
    detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'open',  -- open, investigating, resolved
    INDEX idx_severity (severity, detected_at),
    INDEX idx_status (status, detected_at)
);
```

---

## 11. Security Checklist Updates

### 11.1 Pre-Development Checklist

- [ ] Review all security requirements in this document
- [ ] Understand OWASP Top 10 2021 relevance
- [ ] Review existing security implementations (DomainValidator, SecureToolExecutor)
- [ ] Set up security testing environment
- [ ] Install security scanning tools (Bandit, Safety, OWASP ZAP)

### 11.2 During Development Checklist

**For Each Tool Integration**:

- [ ] Input validation implemented and tested
- [ ] Output sanitization implemented and tested
- [ ] Network security checks implemented
- [ ] Rate limiting configured
- [ ] Resource limits configured
- [ ] Audit logging added
- [ ] Unit tests written (90% coverage)
- [ ] Integration tests written
- [ ] Manual security testing performed
- [ ] Code review completed

**HTTPx-Specific**:
- [ ] URL validation using URLValidator
- [ ] Response size limits enforced
- [ ] Sensitive headers redacted
- [ ] HTML content sanitized
- [ ] Redirect chain protection implemented
- [ ] SSRF prevention verified

**Naabu-Specific**:
- [ ] Target validation with SSRF protection
- [ ] Dangerous ports blocked
- [ ] User consent system implemented
- [ ] Audit logging for all scans
- [ ] Rate limiting enforced
- [ ] CAP_NET_RAW capability minimized

**TLSx-Specific**:
- [ ] HTTPS-only validation
- [ ] Private key detection and redaction
- [ ] Certificate chain validation
- [ ] Weak cipher detection
- [ ] Security alerts for private keys

**Katana-Specific**:
- [ ] Seed URL validation
- [ ] Crawl scope enforcement
- [ ] Depth and page limits enforced
- [ ] robots.txt compliance
- [ ] Credential detection in URLs
- [ ] XSS prevention in stored URLs
- [ ] Form submission disabled by default

### 11.3 Pre-Deployment Checklist

**Security Testing**:
- [ ] All unit tests passing (90%+ coverage)
- [ ] All integration tests passing
- [ ] Penetration tests executed (see section 8.3)
- [ ] OWASP ZAP scan clean
- [ ] Bandit scan clean (no high/medium issues)
- [ ] Safety scan clean (no known vulnerabilities)
- [ ] Trivy container scan clean

**Configuration**:
- [ ] Resource limits configured
- [ ] Rate limits configured
- [ ] Timeout values validated
- [ ] Blocked resources list reviewed
- [ ] Tool allowlist verified
- [ ] Production secrets generated
- [ ] Environment variables set

**Documentation**:
- [ ] API documentation updated
- [ ] Security documentation updated
- [ ] User consent forms created
- [ ] Incident response plan updated

**Compliance**:
- [ ] Port scan consent system enabled
- [ ] Audit logging verified
- [ ] Data retention policy configured
- [ ] robots.txt compliance verified
- [ ] GDPR requirements met

**Monitoring**:
- [ ] Security alerts configured
- [ ] Audit log monitoring enabled
- [ ] Rate limit alerts configured
- [ ] Resource usage monitoring enabled
- [ ] SIEM integration configured

### 11.4 Post-Deployment Checklist

**First 24 Hours**:
- [ ] Monitor audit logs for anomalies
- [ ] Check rate limiting effectiveness
- [ ] Verify no security incidents
- [ ] Review error rates
- [ ] Validate tool execution success rates

**First Week**:
- [ ] Conduct security review meeting
- [ ] Analyze audit logs for patterns
- [ ] Adjust rate limits if needed
- [ ] Review security incidents (if any)
- [ ] Update security documentation

**First Month**:
- [ ] Comprehensive security assessment
- [ ] Penetration testing by third party (recommended)
- [ ] Review and update threat model
- [ ] Tune security controls based on usage
- [ ] Security training for team

### 11.5 Updated security_checklist.py

**Add New Checks**:

```python
# Add to SecurityChecker class in scripts/security_checklist.py

def check_tool_validators(self) -> Tuple[bool, str]:
    """Check tool input validators are implemented"""
    validator_file = self.project_root / 'app' / 'utils' / 'tool_validators.py'

    if not validator_file.exists():
        return False, "Tool validators not found"

    content = validator_file.read_text()

    required_validators = [
        'validate_httpx_input',
        'validate_naabu_input',
        'validate_tlsx_input',
        'validate_katana_input'
    ]

    missing = [v for v in required_validators if v not in content]

    if missing:
        return False, f"Missing validators: {', '.join(missing)}"

    return True, "All tool validators implemented"

def check_output_sanitizers(self) -> Tuple[bool, str]:
    """Check output sanitizers are implemented"""
    sanitizer_file = self.project_root / 'app' / 'utils' / 'output_sanitizers.py'

    if not sanitizer_file.exists():
        return False, "Output sanitizers not found"

    content = sanitizer_file.read_text()

    required_sanitizers = [
        'HTTPxOutputSanitizer',
        'NaabuOutputSanitizer',
        'TLSxOutputSanitizer',
        'KatanaOutputSanitizer'
    ]

    missing = [s for s in required_sanitizers if s not in content]

    if missing:
        return False, f"Missing sanitizers: {', '.join(missing)}"

    return True, "All output sanitizers implemented"

def check_network_security_validator(self) -> Tuple[bool, str]:
    """Check network security validator is implemented"""
    network_file = self.project_root / 'app' / 'utils' / 'network_security.py'

    if not network_file.exists():
        return False, "Network security validator not found"

    content = network_file.read_text()

    required_checks = [
        'BLOCKED_NETWORKS',
        'BLOCKED_HOSTS',
        'is_safe_target',
        'validate_redirect'
    ]

    missing = [c for c in required_checks if c not in content]

    if missing:
        return False, f"Missing network checks: {', '.join(missing)}"

    return True, "Network security validator comprehensive"

def check_rate_limiting_implementation(self) -> Tuple[bool, str]:
    """Check rate limiting is implemented"""
    rate_limiter_file = self.project_root / 'app' / 'utils' / 'rate_limiter.py'

    if not rate_limiter_file.exists():
        return False, "Rate limiter not found"

    content = rate_limiter_file.read_text()

    if 'check_rate_limit' not in content or 'check_concurrent_limit' not in content:
        return False, "Rate limiting methods not found"

    return True, "Rate limiting implemented"

def check_data_redaction(self) -> Tuple[bool, str]:
    """Check data redaction is implemented"""
    redactor_file = self.project_root / 'app' / 'utils' / 'data_redaction.py'

    if not redactor_file.exists():
        return False, "Data redactor not found"

    content = redactor_file.read_text()

    sensitive_types = ['credentials', 'email', 'private_key', 'internal_ip']

    missing = [t for t in sensitive_types if t not in content.lower()]

    if missing:
        return False, f"Missing redaction for: {', '.join(missing)}"

    return True, "Data redaction comprehensive"

def check_port_scan_consent(self) -> Tuple[bool, str]:
    """Check port scan consent system"""
    # Check database migration
    migrations = list((self.project_root / 'alembic' / 'versions').glob('*.py'))

    consent_migration = False
    for migration in migrations:
        content = migration.read_text()
        if 'port_scan_consent' in content:
            consent_migration = True
            break

    if not consent_migration:
        return False, "Port scan consent table not found in migrations"

    # Check consent implementation
    files = list((self.project_root / 'app').rglob('*.py'))
    for f in files:
        content = f.read_text()
        if 'PortScanConsent' in content:
            return True, "Port scan consent system implemented"

    return False, "Port scan consent implementation not found"

def check_audit_logging_for_tools(self) -> Tuple[bool, str]:
    """Check audit logging for tool execution"""
    # Check for tool_audit_log table
    migrations = list((self.project_root / 'alembic' / 'versions').glob('*.py'))

    audit_migration = False
    for migration in migrations:
        content = migration.read_text()
        if 'tool_audit_log' in content:
            audit_migration = True
            break

    if not audit_migration:
        return False, "Tool audit log table not found"

    return True, "Tool audit logging configured"
```

**Update run_all_checks() method to include new checks**:

```python
def run_all_checks(self) -> bool:
    """Run all security checks"""
    checks = [
        # ... existing checks ...

        # New tool security checks
        ("Check tool input validators", self.check_tool_validators, 10),
        ("Check output sanitizers", self.check_output_sanitizers, 10),
        ("Check network security validator", self.check_network_security_validator, 10),
        ("Check rate limiting implementation", self.check_rate_limiting_implementation, 5),
        ("Check data redaction", self.check_data_redaction, 10),
        ("Check port scan consent system", self.check_port_scan_consent, 5),
        ("Check audit logging for tools", self.check_audit_logging_for_tools, 5),
    ]

    # ... rest of existing code ...
```

---

## Summary and Security Score Impact

### Current Security Posture (9.0/10)
- Command injection prevention: ✅
- SSRF prevention (existing tools): ✅
- Tenant isolation: ✅
- Binary checksum validation: ✅
- Production secret validation: ✅

### New Requirements Impact

**Additions (+0.5 to score)**:
- ✅ Comprehensive input validation for 4 new tools
- ✅ Output sanitization with credential/PK redaction
- ✅ Network security validator for SSRF prevention
- ✅ Rate limiting per tool and tenant
- ✅ Audit logging for compliance
- ✅ Data redaction framework
- ✅ Port scan consent system
- ✅ robots.txt compliance

**Target Security Score: 9.5/10**

### Remaining Gaps (to reach 10.0/10)
- Multi-factor authentication (MFA) for users
- Web Application Firewall (WAF) integration
- Third-party penetration testing
- Security Operations Center (SOC) integration
- Bug bounty program
- Formal security certification (SOC 2, ISO 27001)

---

## Implementation Timeline

### Week 1 (Tool Integration with Security)

**Day 1-2 (Critical Security Implementations)**
- Implement ToolInputValidator with all 4 tool validators
- Implement NetworkSecurityValidator for SSRF prevention
- Implement output sanitizers for all 4 tools
- Unit tests for validators and sanitizers (90% coverage)

**Day 3-4 (Security Controls)**
- Implement ToolRateLimiter class
- Implement DataRedactor class
- Add resource limits to tool configurations
- Implement port scan consent system
- Integration tests for security controls

**Day 5 (Testing and Documentation)**
- Comprehensive security testing
- Update security checklist script
- Update API documentation
- Code review and bug fixes

### Week 2 (Validation and Deployment)

**Day 1-2 (Security Testing)**
- Penetration testing (manual and automated)
- OWASP ZAP scan
- Bandit and Safety scans
- Performance testing with security controls
- Fix identified issues

**Day 3 (Final Validation)**
- Run updated security_checklist.py (target: 100% pass)
- Final code review
- Security sign-off
- Deployment preparation

**Day 4-5 (Deployment and Monitoring)**
- Deploy to staging environment
- Security validation in staging
- Production deployment
- 24-hour security monitoring
- Post-deployment security review

---

## Conclusion

This comprehensive security requirements document provides detailed specifications for securely integrating HTTPx, Naabu, TLSx, and Katana into the EASM platform. By implementing these requirements, the platform will:

1. **Maintain 9.0/10 security score** and target **9.5/10**
2. **Prevent SSRF attacks** through multi-layer validation
3. **Protect sensitive data** through comprehensive redaction
4. **Ensure legal compliance** with consent and audit logging
5. **Enable secure operations** with rate limiting and resource controls

**Key Success Metrics**:
- ✅ Zero critical vulnerabilities
- ✅ 100% input validation coverage
- ✅ 90%+ test coverage for security code
- ✅ All penetration tests passed
- ✅ 100% security checklist compliance

**Next Steps**:
1. Review and approve this document
2. Begin Phase 1 implementation (Days 1-2)
3. Daily security stand-ups during implementation
4. Continuous testing and validation
5. Security sign-off before deployment

---

**Document Approval**:

- [ ] Security Lead
- [ ] Engineering Lead
- [ ] Product Owner
- [ ] Compliance Officer

**Version Control**:
- v1.0 - 2025-10-23 - Initial comprehensive requirements
