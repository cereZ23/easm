from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum, Float, Boolean, Index, JSON
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class Tenant(Base):
    __tablename__ = 'tenants'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    contact_policy = Column(Text)
    osint_api_keys = Column(Text)  # JSON encrypted field for OSINT providers
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assets = relationship("Asset", back_populates="tenant", cascade="all, delete-orphan")
    seeds = relationship("Seed", back_populates="tenant", cascade="all, delete-orphan")
    memberships = relationship("TenantMembership", back_populates="tenant", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant(id={self.id}, name='{self.name}', slug='{self.slug}')>"


class AssetType(enum.Enum):
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP = "ip"
    URL = "url"
    SERVICE = "service"


class Asset(Base):
    __tablename__ = 'assets'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    type = Column(Enum(AssetType), nullable=False)
    identifier = Column(String(500), nullable=False)  # Domain, IP, URL
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    risk_score = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    raw_metadata = Column(Text)  # JSON field for flexible attrs

    # Sprint 2: Enrichment tracking
    last_enriched_at = Column(DateTime)
    enrichment_status = Column(String(50), default='pending')  # pending, enriched, failed

    # Sprint 2: Tiered enrichment - Priority-based scheduling
    priority = Column(String(20), default='normal')  # critical, high, normal, low
    priority_updated_at = Column(DateTime)
    priority_auto_calculated = Column(Boolean, default=True)  # False if manually set

    tenant = relationship("Tenant", back_populates="assets")
    services = relationship("Service", back_populates="asset", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="asset", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="asset", cascade="all, delete-orphan")

    # Sprint 2: New enrichment relationships
    certificates = relationship("Certificate", back_populates="asset", cascade="all, delete-orphan")
    endpoints = relationship("Endpoint", back_populates="asset", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_tenant_type', 'tenant_id', 'type'),
        Index('idx_identifier', 'identifier'),
        Index('idx_tenant_identifier', 'tenant_id', 'identifier'),
        Index('idx_unique_asset', 'tenant_id', 'identifier', 'type', unique=True),  # For bulk upsert
        Index('idx_asset_priority_enrichment', 'tenant_id', 'priority', 'last_enriched_at'),  # Sprint 2
        Index('idx_enrichment_status', 'enrichment_status'),  # Sprint 2
    )

    def __repr__(self):
        return f"<Asset(id={self.id}, type={self.type.value}, identifier='{self.identifier}')>"


class Service(Base):
    __tablename__ = 'services'

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey('assets.id'), nullable=False)
    port = Column(Integer)
    protocol = Column(String(50))
    product = Column(String(255))
    version = Column(String(100))
    tls_fingerprint = Column(String(255))
    http_title = Column(String(500))
    http_status = Column(Integer)
    technologies = Column(Text)  # JSON array
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)

    # Sprint 2: HTTPx enrichment fields
    web_server = Column(String(200))      # nginx, Apache, IIS
    http_technologies = Column(JSON)      # ["PHP", "WordPress", "jQuery"]
    http_headers = Column(JSON)           # Full response headers
    response_time_ms = Column(Integer)    # Response time in milliseconds
    content_length = Column(Integer)      # Content length in bytes
    redirect_url = Column(String(2048))   # Final URL after redirects
    screenshot_url = Column(String(500))  # MinIO URL to screenshot (optional)

    # Sprint 2: TLSx enrichment fields
    has_tls = Column(Boolean, default=False)
    tls_version = Column(String(50))      # TLSv1.3, TLSv1.2

    # Sprint 2: Enrichment tracking
    enriched_at = Column(DateTime)        # Last enrichment timestamp
    enrichment_source = Column(String(50)) # httpx, naabu, tlsx

    asset = relationship("Asset", back_populates="services")

    __table_args__ = (
        Index('idx_asset_port', 'asset_id', 'port'),
        Index('idx_enrichment_source', 'enrichment_source'),  # Sprint 2
        Index('idx_has_tls', 'has_tls'),  # Sprint 2
    )

    def __repr__(self):
        return f"<Service(id={self.id}, port={self.port}, protocol='{self.protocol}')>"


class FindingStatus(enum.Enum):
    OPEN = "open"
    SUPPRESSED = "suppressed"
    FIXED = "fixed"


class FindingSeverity(enum.Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Finding(Base):
    __tablename__ = 'findings'

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey('assets.id'), nullable=False)
    source = Column(String(50), default='nuclei')  # nuclei, manual, custom
    template_id = Column(String(255))
    name = Column(String(500), nullable=False)
    severity = Column(Enum(FindingSeverity), nullable=False)
    cvss_score = Column(Float)
    cve_id = Column(String(50))
    evidence = Column(Text)  # JSON
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(FindingStatus), default=FindingStatus.OPEN)

    asset = relationship("Asset", back_populates="findings")

    __table_args__ = (
        Index('idx_asset_severity', 'asset_id', 'severity'),
        Index('idx_status', 'status'),
        Index('idx_severity_status', 'severity', 'status'),
    )

    def __repr__(self):
        return f"<Finding(id={self.id}, name='{self.name}', severity={self.severity.value})>"


class EventKind(enum.Enum):
    NEW_ASSET = "new_asset"
    OPEN_PORT = "open_port"
    NEW_CERT = "new_cert"
    NEW_PATH = "new_path"
    TECH_CHANGE = "tech_change"


class Event(Base):
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey('assets.id'), nullable=False)
    kind = Column(Enum(EventKind), nullable=False)
    payload = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    asset = relationship("Asset", back_populates="events")

    __table_args__ = (
        Index('idx_created_at', 'created_at'),
        Index('idx_kind_created', 'kind', 'created_at'),
    )

    def __repr__(self):
        return f"<Event(id={self.id}, kind={self.kind.value}, created_at={self.created_at})>"


class Seed(Base):
    __tablename__ = 'seeds'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id'), nullable=False)
    type = Column(String(50))  # domain, asn, ip_range, keyword
    value = Column(String(500), nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="seeds")

    __table_args__ = (
        Index('idx_tenant_enabled', 'tenant_id', 'enabled'),
    )

    def __repr__(self):
        return f"<Seed(id={self.id}, type='{self.type}', value='{self.value}')>"
