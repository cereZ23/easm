"""
Enrichment data models for web technology, certificates, and endpoints

Extends the core Asset model with detailed enrichment data from
HTTPx, Naabu, TLSx, and Katana.

Sprint 2 Week 1 - New enrichment tools integration
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Index, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum

from app.models.database import Base


class AssetPriority(str, Enum):
    """Asset priority levels for tiered enrichment"""
    CRITICAL = "critical"  # 1-day TTL - Daily enrichment
    HIGH = "high"          # 3-day TTL - Every 3 days
    NORMAL = "normal"      # 7-day TTL - Weekly
    LOW = "low"            # 14-day TTL - Bi-weekly


class Certificate(Base):
    """
    TLS/SSL Certificate information from TLSx

    Stores certificate chain data, expiry information, and security posture.
    Used for SSL/TLS monitoring and vulnerability detection.

    Relationships:
        - Belongs to one Asset (many-to-one)

    Indexes:
        - asset_id for lookups
        - not_after for expiry alerts
        - is_expired for filtering
        - (asset_id, serial_number) unique constraint
    """
    __tablename__ = 'certificates'

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey('assets.id', ondelete='CASCADE'), nullable=False)

    # Certificate Identity
    subject_cn = Column(String(500))  # Common Name
    issuer = Column(String(500))      # Certificate Authority
    serial_number = Column(String(255))

    # Validity
    not_before = Column(DateTime)
    not_after = Column(DateTime)
    is_expired = Column(Boolean, default=False)
    days_until_expiry = Column(Integer)

    # Subject Alternative Names (SANs) - JSON array
    # Example: ["*.example.com", "example.com", "www.example.com"]
    san_domains = Column(JSON)

    # Security Configuration
    signature_algorithm = Column(String(100))  # SHA256withRSA, etc.
    public_key_algorithm = Column(String(100)) # RSA, EC, etc.
    public_key_bits = Column(Integer)          # 2048, 4096, etc.

    # Cipher Suites - JSON array
    # Example: ["TLS_AES_256_GCM_SHA384", "TLS_CHACHA20_POLY1305_SHA256"]
    cipher_suites = Column(JSON)

    # Certificate Chain - JSON array of cert objects
    # Example: [{"subject": "...", "issuer": "..."}, ...]
    chain = Column(JSON)

    # Vulnerabilities
    is_self_signed = Column(Boolean, default=False)
    is_wildcard = Column(Boolean, default=False)
    has_weak_signature = Column(Boolean, default=False)  # MD5, SHA1

    # Metadata
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    raw_data = Column(JSON)  # Full TLSx output for debugging

    # Relationship
    # TODO: Re-enable after fixing circular import
    # asset = relationship("Asset", back_populates="certificates")

    __table_args__ = (
        Index('idx_asset_cert', 'asset_id'),
        Index('idx_expiry', 'not_after'),
        Index('idx_expired', 'is_expired'),
        Index('idx_asset_serial', 'asset_id', 'serial_number', unique=True),
    )

    def __repr__(self):
        return f"<Certificate(id={self.id}, cn='{self.subject_cn}', expires={self.not_after})>"

    @property
    def is_expiring_soon(self, days: int = 30) -> bool:
        """Check if certificate expires within N days"""
        if not self.days_until_expiry:
            return False
        return 0 < self.days_until_expiry <= days


class Endpoint(Base):
    """
    HTTP Endpoints discovered by Katana web crawler

    Represents URLs, API endpoints, and web paths discovered through crawling.
    Used for attack surface mapping and API discovery.

    Relationships:
        - Belongs to one Asset (many-to-one)

    Indexes:
        - asset_id for lookups
        - endpoint_type for filtering
        - is_api for API discovery
        - (asset_id, url, method) unique constraint
    """
    __tablename__ = 'endpoints'

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey('assets.id', ondelete='CASCADE'), nullable=False)

    # Endpoint Identity
    url = Column(String(2048), nullable=False)
    path = Column(String(1024))  # /api/v1/users
    method = Column(String(10), default='GET')  # GET, POST, PUT, DELETE, etc.

    # Request Parameters - JSON objects
    # Example query_params: {"id": "123", "page": "1"}
    query_params = Column(JSON)

    # Example body_params: {"username": "test", "email": "test@example.com"}
    body_params = Column(JSON)

    # Custom headers observed during crawling
    headers = Column(JSON)

    # Response
    status_code = Column(Integer)
    content_type = Column(String(200))
    content_length = Column(Integer)

    # Classification
    endpoint_type = Column(String(50))  # api, form, file, redirect, external, static
    is_external = Column(Boolean, default=False)  # External link (different domain)
    is_api = Column(Boolean, default=False)       # Looks like API endpoint

    # Discovery Source
    source_url = Column(String(2048))  # Page where this endpoint was found
    depth = Column(Integer, default=0)  # Crawl depth from seed URL

    # Metadata
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    raw_data = Column(JSON)  # Full Katana output

    # Relationship
    # TODO: Re-enable after fixing circular import
    # asset = relationship("Asset", back_populates="endpoints")

    __table_args__ = (
        Index('idx_asset_endpoint', 'asset_id'),
        Index('idx_endpoint_type', 'endpoint_type'),
        Index('idx_is_api', 'is_api'),
        Index('idx_asset_url', 'asset_id', 'url', 'method', unique=True),
    )

    def __repr__(self):
        return f"<Endpoint(id={self.id}, method='{self.method}', url='{self.url[:50]}')>"

    @property
    def is_sensitive_endpoint(self) -> bool:
        """Check if endpoint appears to be sensitive (admin, login, api)"""
        sensitive_keywords = [
            'admin', 'login', 'auth', 'api', 'password',
            'reset', 'token', 'key', 'secret', 'config'
        ]

        url_lower = self.url.lower()
        return any(keyword in url_lower for keyword in sensitive_keywords)
