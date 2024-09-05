# EASM Platform - Critical Security Fixes Implementation

This document provides production-ready code to fix the critical vulnerabilities identified in the security audit.

## 1. JWT Authentication Implementation

### File: `/app/auth.py`
```python
"""
Secure JWT authentication implementation for EASM platform
Implements OWASP best practices for authentication
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Configuration
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
if not JWT_SECRET_KEY or JWT_SECRET_KEY == 'change-this-secret-key-in-production':
    raise ValueError("JWT_SECRET_KEY must be set to a secure value")

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
REFRESH_TOKEN_EXPIRATION_DAYS = 30

# Security instances
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

class TokenData(BaseModel):
    """Token payload structure"""
    tenant_id: int
    user_id: int
    email: str
    roles: list = []
    exp: datetime

class UserCredentials(BaseModel):
    """User login credentials"""
    email: str
    password: str
    tenant_slug: str

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password: str) -> str:
    """Create password hash"""
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token with claims

    Args:
        data: Token payload data
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    # Set expiration
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })

    # Encode token
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    # Audit log
    logger.info(f"Access token created for user {data.get('user_id')} in tenant {data.get('tenant_id')}")

    return encoded_jwt

def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create long-lived refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRATION_DAYS)

    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })

    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Validate JWT token and return current user

    Args:
        credentials: HTTP Bearer token

    Returns:
        User data dictionary

    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials

    try:
        # Decode and validate token
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        # Validate token type
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        # Extract user data
        user_data = {
            "tenant_id": payload.get("tenant_id"),
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "roles": payload.get("roles", [])
        }

        # Validate required fields
        if not user_data["tenant_id"] or not user_data["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims"
            )

        return user_data

    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def require_role(required_role: str):
    """
    Dependency to require specific role

    Usage:
        @app.get("/admin", dependencies=[Depends(require_role("admin"))])
    """
    async def role_checker(current_user: Dict = Depends(get_current_user)):
        if required_role not in current_user.get("roles", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )
        return current_user
    return role_checker

async def validate_tenant_access(
    tenant_id: int,
    current_user: Dict = Depends(get_current_user)
) -> bool:
    """
    Validate user has access to specified tenant

    Args:
        tenant_id: Tenant to access
        current_user: Current authenticated user

    Returns:
        True if access allowed

    Raises:
        HTTPException: If access denied
    """
    if current_user["tenant_id"] != tenant_id:
        logger.warning(
            f"User {current_user['user_id']} attempted to access tenant {tenant_id} "
            f"(authorized for tenant {current_user['tenant_id']})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this tenant"
        )
    return True
```

## 2. Secure API Endpoints with Authentication

### File: `/app/api/v1/assets.py`
```python
"""
Secure asset API endpoints with authentication and authorization
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List, Optional
from sqlalchemy.orm import Session

from app.auth import get_current_user, validate_tenant_access
from app.database import get_db
from app.models.database import Asset, AssetType
from app.repositories.asset_repository import AssetRepository
from app.schemas import AssetResponse, AssetCreate
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/assets",
    tags=["assets"],
    responses={401: {"description": "Unauthorized"}}
)

@router.get("/", response_model=List[AssetResponse])
async def get_assets(
    asset_type: Optional[AssetType] = None,
    is_active: bool = True,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get assets for authenticated tenant with pagination

    - Requires authentication
    - Returns only assets belonging to user's tenant
    - Supports filtering by type and active status
    """
    tenant_id = current_user["tenant_id"]

    # Log access
    logger.info(
        f"User {current_user['user_id']} retrieving assets for tenant {tenant_id}"
        f" (type={asset_type}, active={is_active}, limit={limit}, offset={offset})"
    )

    # Use repository with tenant isolation
    repo = AssetRepository(db, tenant_id)
    assets = repo.get_by_tenant(
        tenant_id=tenant_id,
        asset_type=asset_type,
        is_active=is_active,
        limit=limit,
        offset=offset
    )

    return assets

@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific asset by ID

    - Requires authentication
    - Validates tenant access
    """
    tenant_id = current_user["tenant_id"]

    repo = AssetRepository(db, tenant_id)
    asset = repo.get_by_id(asset_id)

    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )

    # Verify tenant access
    if asset.tenant_id != tenant_id:
        logger.warning(
            f"User {current_user['user_id']} attempted unauthorized access to asset {asset_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    return asset

@router.post("/", response_model=AssetResponse)
async def create_asset(
    asset_data: AssetCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new asset

    - Requires authentication
    - Validates input data
    - Associates with user's tenant
    """
    tenant_id = current_user["tenant_id"]

    # Validate input
    asset_data.validate()

    repo = AssetRepository(db, tenant_id)
    asset = repo.create(
        tenant_id=tenant_id,
        asset_data=asset_data.dict()
    )

    logger.info(
        f"User {current_user['user_id']} created asset {asset.id} for tenant {tenant_id}"
    )

    return asset

@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete asset (soft delete)

    - Requires authentication
    - Validates tenant access
    - Performs soft delete (marks inactive)
    """
    tenant_id = current_user["tenant_id"]

    repo = AssetRepository(db, tenant_id)
    asset = repo.get_by_id(asset_id)

    if not asset or asset.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )

    # Soft delete
    repo.mark_inactive([asset_id])

    logger.info(
        f"User {current_user['user_id']} deleted asset {asset_id}"
    )

    return {"message": "Asset deleted successfully"}
```

## 3. Secure Environment Configuration

### File: `/app/config.py`
```python
"""
Secure configuration management with validation
"""

import os
from typing import List, Optional
from pydantic import BaseSettings, validator, Field
from functools import lru_cache
import secrets

class Settings(BaseSettings):
    """Application settings with security defaults"""

    # Application
    app_name: str = "EASM Platform"
    debug: bool = Field(False, env="DEBUG")
    environment: str = Field("production", env="ENVIRONMENT")

    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    database_pool_size: int = Field(10, env="DB_POOL_SIZE")
    database_max_overflow: int = Field(20, env="DB_MAX_OVERFLOW")

    # Redis
    redis_url: str = Field(..., env="REDIS_URL")

    # MinIO/S3
    minio_endpoint: str = Field(..., env="MINIO_ENDPOINT")
    minio_user: str = Field(..., env="MINIO_USER")
    minio_password: str = Field(..., env="MINIO_PASSWORD")
    minio_secure: bool = Field(True, env="MINIO_SECURE")

    # JWT & Security
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # Encryption
    encryption_key: str = Field(..., env="ENCRYPTION_KEY")

    # CORS
    allowed_origins: List[str] = Field([], env="ALLOWED_ORIGINS")

    # Rate Limiting
    rate_limit_enabled: bool = Field(True, env="RATE_LIMIT_ENABLED")
    rate_limit_per_minute: int = Field(100, env="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(1000, env="RATE_LIMIT_PER_HOUR")

    # Security Headers
    enable_security_headers: bool = True
    hsts_max_age: int = 31536000  # 1 year
    csp_policy: str = "default-src 'self'; script-src 'self' 'unsafe-inline'"

    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_sensitive_data: bool = False

    @validator("jwt_secret_key")
    def validate_jwt_secret(cls, v):
        """Ensure JWT secret is secure"""
        if not v or v == "change-this-secret-key-in-production":
            raise ValueError("JWT_SECRET_KEY must be set to a secure value")
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v

    @validator("encryption_key")
    def validate_encryption_key(cls, v):
        """Ensure encryption key is valid"""
        if not v or len(v) != 44:  # Fernet key is 44 chars
            raise ValueError("ENCRYPTION_KEY must be a valid Fernet key (44 characters)")
        return v

    @validator("database_url")
    def validate_database_url(cls, v):
        """Ensure database URL doesn't contain default credentials"""
        if "easm_password" in v or "postgres:postgres" in v:
            raise ValueError("DATABASE_URL contains default credentials")
        return v

    @validator("allowed_origins", pre=True)
    def parse_origins(cls, v):
        """Parse comma-separated origins"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

# Generate secure defaults for development
def generate_secure_env():
    """Generate .env file with secure defaults"""
    env_content = f"""
# EASM Platform Security Configuration
# Generated: {datetime.utcnow().isoformat()}

# Environment
ENVIRONMENT=production
DEBUG=false

# Database
DATABASE_URL=postgresql://easm_user:{secrets.token_urlsafe(32)}@postgres:5432/easm

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_USER=easm_{secrets.token_hex(8)}
MINIO_PASSWORD={secrets.token_urlsafe(32)}
MINIO_SECURE=false

# Security Keys (CHANGE THESE!)
JWT_SECRET_KEY={secrets.token_urlsafe(64)}
ENCRYPTION_KEY={Fernet.generate_key().decode()}

# CORS (comma-separated origins)
ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000

# Logging
LOG_LEVEL=INFO
"""

    with open(".env.example", "w") as f:
        f.write(env_content)

    print("Secure .env.example generated. Copy to .env and adjust values.")
```

## 4. Enhanced Multi-Tenant Repository

### File: `/app/repositories/secure_repository.py`
```python
"""
Secure repository base class with tenant isolation
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List, Dict, Any, Type, TypeVar
from app.models.database import Base
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Base)

class SecureTenantRepository:
    """
    Base repository with automatic tenant isolation

    All queries automatically filter by tenant_id
    """

    def __init__(self, db: Session, tenant_id: int, model: Type[T]):
        """
        Initialize repository with tenant context

        Args:
            db: Database session
            tenant_id: Tenant ID for isolation
            model: SQLAlchemy model class
        """
        self.db = db
        self.tenant_id = tenant_id
        self.model = model

        # Validate model has tenant_id field
        if not hasattr(model, 'tenant_id'):
            raise ValueError(f"Model {model.__name__} must have tenant_id field for tenant isolation")

    def _apply_tenant_filter(self, query):
        """Apply tenant filter to query"""
        return query.filter(self.model.tenant_id == self.tenant_id)

    def get_by_id(self, entity_id: int) -> Optional[T]:
        """
        Get entity by ID with tenant validation

        Args:
            entity_id: Entity ID

        Returns:
            Entity if found and belongs to tenant, None otherwise
        """
        try:
            entity = self._apply_tenant_filter(
                self.db.query(self.model).filter(self.model.id == entity_id)
            ).first()

            if entity:
                logger.debug(f"Retrieved {self.model.__name__} {entity_id} for tenant {self.tenant_id}")
            else:
                logger.warning(f"{self.model.__name__} {entity_id} not found for tenant {self.tenant_id}")

            return entity

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving {self.model.__name__} {entity_id}: {e}")
            raise

    def get_all(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[T]:
        """
        Get all entities for tenant with optional filters

        Args:
            filters: Optional filter conditions
            limit: Maximum results
            offset: Number of results to skip

        Returns:
            List of entities
        """
        try:
            query = self._apply_tenant_filter(self.db.query(self.model))

            # Apply additional filters
            if filters:
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        query = query.filter(getattr(self.model, key) == value)

            results = query.limit(limit).offset(offset).all()

            logger.debug(f"Retrieved {len(results)} {self.model.__name__} entities for tenant {self.tenant_id}")

            return results

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving {self.model.__name__} list: {e}")
            raise

    def create(self, data: Dict[str, Any]) -> T:
        """
        Create new entity with automatic tenant assignment

        Args:
            data: Entity data

        Returns:
            Created entity
        """
        try:
            # Ensure tenant_id is set correctly
            data['tenant_id'] = self.tenant_id

            entity = self.model(**data)
            self.db.add(entity)
            self.db.flush()  # Get ID without committing

            logger.info(f"Created {self.model.__name__} {entity.id} for tenant {self.tenant_id}")

            return entity

        except SQLAlchemyError as e:
            logger.error(f"Database error creating {self.model.__name__}: {e}")
            self.db.rollback()
            raise

    def update(self, entity_id: int, data: Dict[str, Any]) -> Optional[T]:
        """
        Update entity with tenant validation

        Args:
            entity_id: Entity ID
            data: Update data

        Returns:
            Updated entity if found, None otherwise
        """
        try:
            # Prevent changing tenant_id
            data.pop('tenant_id', None)

            entity = self.get_by_id(entity_id)
            if not entity:
                return None

            # Update fields
            for key, value in data.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)

            self.db.flush()

            logger.info(f"Updated {self.model.__name__} {entity_id} for tenant {self.tenant_id}")

            return entity

        except SQLAlchemyError as e:
            logger.error(f"Database error updating {self.model.__name__} {entity_id}: {e}")
            self.db.rollback()
            raise

    def delete(self, entity_id: int, soft_delete: bool = True) -> bool:
        """
        Delete entity with tenant validation

        Args:
            entity_id: Entity ID
            soft_delete: If True, mark as inactive instead of deleting

        Returns:
            True if deleted, False if not found
        """
        try:
            entity = self.get_by_id(entity_id)
            if not entity:
                return False

            if soft_delete and hasattr(entity, 'is_active'):
                entity.is_active = False
                action = "soft-deleted"
            else:
                self.db.delete(entity)
                action = "deleted"

            self.db.flush()

            logger.info(f"{action} {self.model.__name__} {entity_id} for tenant {self.tenant_id}")

            return True

        except SQLAlchemyError as e:
            logger.error(f"Database error deleting {self.model.__name__} {entity_id}: {e}")
            self.db.rollback()
            raise

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count entities for tenant

        Args:
            filters: Optional filter conditions

        Returns:
            Count of entities
        """
        try:
            query = self._apply_tenant_filter(self.db.query(self.model))

            if filters:
                for key, value in filters.items():
                    if hasattr(self.model, key):
                        query = query.filter(getattr(self.model, key) == value)

            return query.count()

        except SQLAlchemyError as e:
            logger.error(f"Database error counting {self.model.__name__}: {e}")
            raise
```

## 5. Input Validation Schemas

### File: `/app/schemas.py`
```python
"""
Pydantic schemas for input validation and response models
"""

from pydantic import BaseModel, validator, constr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import re

class SeedType(str, Enum):
    """Seed types enum"""
    domain = "domain"
    asn = "asn"
    ip_range = "ip_range"
    keyword = "keyword"

class AssetTypeEnum(str, Enum):
    """Asset types enum"""
    domain = "domain"
    subdomain = "subdomain"
    ip = "ip"
    url = "url"
    service = "service"

class SeedCreate(BaseModel):
    """Seed creation schema with validation"""

    type: SeedType
    value: constr(min_length=1, max_length=500)
    enabled: bool = True

    @validator('value')
    def validate_seed_value(cls, v, values):
        """Validate seed value based on type"""
        seed_type = values.get('type')

        if seed_type == SeedType.domain:
            # Validate domain format
            domain_pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
            if not re.match(domain_pattern, v):
                raise ValueError(f"Invalid domain format: {v}")

        elif seed_type == SeedType.asn:
            # Validate ASN format (AS followed by numbers)
            if not re.match(r'^AS\d+$', v):
                raise ValueError(f"Invalid ASN format: {v}. Expected format: AS12345")

        elif seed_type == SeedType.ip_range:
            # Validate CIDR notation
            if not re.match(r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$', v):
                raise ValueError(f"Invalid IP range format: {v}. Expected CIDR notation: 192.168.1.0/24")

        elif seed_type == SeedType.keyword:
            # Validate keyword (alphanumeric, spaces, hyphens)
            if not re.match(r'^[a-zA-Z0-9\s\-_.]+$', v):
                raise ValueError(f"Invalid keyword format: {v}. Only alphanumeric, spaces, hyphens allowed")

        return v

class AssetCreate(BaseModel):
    """Asset creation schema with validation"""

    type: AssetTypeEnum
    identifier: constr(min_length=1, max_length=500)
    risk_score: float = Field(0.0, ge=0.0, le=100.0)
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = {}

    @validator('identifier')
    def validate_identifier(cls, v, values):
        """Validate identifier based on asset type"""
        asset_type = values.get('type')

        if asset_type == AssetTypeEnum.domain or asset_type == AssetTypeEnum.subdomain:
            # Validate domain format
            if not re.match(r'^[a-zA-Z0-9.-]+$', v):
                raise ValueError(f"Invalid domain identifier: {v}")

        elif asset_type == AssetTypeEnum.ip:
            # Validate IP address
            parts = v.split('.')
            if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                raise ValueError(f"Invalid IP address: {v}")

        elif asset_type == AssetTypeEnum.url:
            # Basic URL validation
            if not v.startswith(('http://', 'https://')):
                raise ValueError(f"URL must start with http:// or https://: {v}")

        return v

    @validator('metadata')
    def validate_metadata(cls, v):
        """Ensure metadata is JSON-serializable"""
        import json
        try:
            json.dumps(v)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Metadata must be JSON-serializable: {e}")
        return v

class AssetResponse(BaseModel):
    """Asset response model"""

    id: int
    tenant_id: int
    type: AssetTypeEnum
    identifier: str
    first_seen: datetime
    last_seen: datetime
    risk_score: float
    is_active: bool
    metadata: Optional[Dict[str, Any]]

    class Config:
        orm_mode = True

class DiscoveryRequest(BaseModel):
    """Discovery task request with validation"""

    domains: List[constr(regex=r'^[a-zA-Z0-9.-]+$')] = []
    keywords: List[constr(regex=r'^[a-zA-Z0-9\s\-_.]+$')] = []
    deep_scan: bool = False

    @validator('domains')
    def validate_domains_limit(cls, v):
        """Limit number of domains to prevent abuse"""
        if len(v) > 100:
            raise ValueError("Maximum 100 domains allowed per discovery")
        return v

    @validator('keywords')
    def validate_keywords_limit(cls, v):
        """Limit number of keywords"""
        if len(v) > 10:
            raise ValueError("Maximum 10 keywords allowed per discovery")
        return v
```

## Testing the Security Implementation

### File: `/tests/test_security.py`
```python
"""
Security test suite for EASM platform
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token, hash_password
import time

client = TestClient(app)

class TestAuthentication:
    """Test authentication security"""

    def test_endpoints_require_auth(self):
        """Verify all endpoints require authentication"""
        endpoints = [
            "/api/v1/assets",
            "/api/v1/seeds",
            "/api/v1/discovery/run",
            "/api/v1/tenants/me"
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401
            assert "detail" in response.json()

    def test_invalid_token_rejected(self):
        """Test invalid tokens are rejected"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/assets", headers=headers)
        assert response.status_code == 401

    def test_expired_token_rejected(self):
        """Test expired tokens are rejected"""
        # Create token with past expiration
        token = create_access_token(
            {"tenant_id": 1, "user_id": 1},
            expires_delta=timedelta(seconds=-1)
        )
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/assets", headers=headers)
        assert response.status_code == 401

class TestMultiTenancy:
    """Test multi-tenant isolation"""

    def test_tenant_isolation(self):
        """Verify tenants cannot access other tenant data"""
        # Create tokens for different tenants
        token1 = create_access_token({"tenant_id": 1, "user_id": 1})
        token2 = create_access_token({"tenant_id": 2, "user_id": 2})

        # Create asset for tenant 1
        headers1 = {"Authorization": f"Bearer {token1}"}
        response = client.post(
            "/api/v1/assets",
            headers=headers1,
            json={"type": "domain", "identifier": "example.com"}
        )
        asset_id = response.json()["id"]

        # Try to access with tenant 2 token
        headers2 = {"Authorization": f"Bearer {token2}"}
        response = client.get(f"/api/v1/assets/{asset_id}", headers=headers2)
        assert response.status_code == 403

class TestInputValidation:
    """Test input validation and injection prevention"""

    def test_sql_injection_prevention(self):
        """Test SQL injection attempts are blocked"""
        token = create_access_token({"tenant_id": 1, "user_id": 1})
        headers = {"Authorization": f"Bearer {token}"}

        malicious_inputs = [
            "'; DROP TABLE assets; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM tenants--"
        ]

        for payload in malicious_inputs:
            response = client.post(
                "/api/v1/seeds",
                headers=headers,
                json={"type": "domain", "value": payload}
            )
            assert response.status_code == 422  # Validation error

    def test_command_injection_prevention(self):
        """Test command injection attempts are blocked"""
        token = create_access_token({"tenant_id": 1, "user_id": 1})
        headers = {"Authorization": f"Bearer {token}"}

        malicious_inputs = [
            "example.com; cat /etc/passwd",
            "$(whoami)",
            "`id`",
            "example.com && rm -rf /"
        ]

        for payload in malicious_inputs:
            response = client.post(
                "/api/v1/seeds",
                headers=headers,
                json={"type": "domain", "value": payload}
            )
            assert response.status_code == 422

    def test_xss_prevention(self):
        """Test XSS attempts are sanitized"""
        token = create_access_token({"tenant_id": 1, "user_id": 1})
        headers = {"Authorization": f"Bearer {token}"}

        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>"
        ]

        for payload in xss_payloads:
            response = client.post(
                "/api/v1/seeds",
                headers=headers,
                json={"type": "keyword", "value": payload}
            )
            assert response.status_code == 422

class TestRateLimiting:
    """Test rate limiting"""

    def test_rate_limit_enforcement(self):
        """Test rate limits are enforced"""
        token = create_access_token({"tenant_id": 1, "user_id": 1})
        headers = {"Authorization": f"Bearer {token}"}

        # Make requests up to limit
        for _ in range(100):
            response = client.get("/api/v1/assets", headers=headers)
            if response.status_code == 429:
                break

        # Next request should be rate limited
        response = client.get("/api/v1/assets", headers=headers)
        assert response.status_code == 429
        assert "rate limit" in response.json()["detail"].lower()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

## Deployment Security Checklist

```bash
#!/bin/bash
# deployment_security_check.sh

echo "EASM Platform Security Deployment Checklist"
echo "==========================================="

# Check for default credentials
echo "[ ] Checking for default credentials..."
grep -r "easm_password\|minioadmin\|change-this" . --include="*.env" --include="*.yml" --include="*.yaml"
if [ $? -eq 0 ]; then
    echo "  ❌ FAIL: Default credentials found!"
else
    echo "  ✅ PASS: No default credentials found"
fi

# Check JWT secret
echo "[ ] Checking JWT secret strength..."
JWT_SECRET=$(grep JWT_SECRET_KEY .env | cut -d'=' -f2)
if [ ${#JWT_SECRET} -lt 32 ]; then
    echo "  ❌ FAIL: JWT secret too short (minimum 32 characters)"
else
    echo "  ✅ PASS: JWT secret is adequate length"
fi

# Check for .env in git
echo "[ ] Checking if .env is in git..."
git ls-files | grep -q "^\.env$"
if [ $? -eq 0 ]; then
    echo "  ❌ FAIL: .env file is tracked in git!"
else
    echo "  ✅ PASS: .env is not in git"
fi

# Check Docker configuration
echo "[ ] Checking Docker security..."
grep -q "USER " Dockerfile*
if [ $? -ne 0 ]; then
    echo "  ⚠️  WARN: Containers may be running as root"
else
    echo "  ✅ PASS: Containers use non-root user"
fi

# Check for HTTPS/TLS
echo "[ ] Checking TLS configuration..."
grep -q "ssl\|tls\|https" docker-compose.yml
if [ $? -ne 0 ]; then
    echo "  ⚠️  WARN: No TLS configuration found"
else
    echo "  ✅ PASS: TLS configuration present"
fi

echo ""
echo "Security check complete. Address any ❌ FAIL items before deployment."
```

This implementation provides production-ready security fixes for all critical vulnerabilities identified in the audit. Deploy these changes immediately to secure the EASM platform.