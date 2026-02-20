from __future__ import annotations

"""
Certificate Schemas

Pydantic models for TLS/SSL certificates
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class CertificateResponse(BaseModel):
    """Certificate response"""

    id: int = Field(..., description="Certificate ID")
    asset_id: int = Field(..., description="Asset ID")
    subject_cn: Optional[str] = Field(None, description="Subject Common Name")
    issuer: Optional[str] = Field(None, description="Issuer name")
    serial_number: Optional[str] = Field(None, description="Serial number")
    not_before: Optional[datetime] = Field(None, description="Valid from date")
    not_after: Optional[datetime] = Field(None, description="Valid until date")
    is_expired: bool = Field(default=False, description="Is certificate expired")
    days_until_expiry: Optional[int] = Field(None, description="Days until expiry")
    san_domains: Optional[List[str]] = Field(None, description="Subject Alternative Names")
    signature_algorithm: Optional[str] = Field(None, description="Signature algorithm")
    public_key_algorithm: Optional[str] = Field(None, description="Public key algorithm")
    public_key_bits: Optional[int] = Field(None, description="Public key size in bits")
    cipher_suites: Optional[List[str]] = Field(None, description="Supported cipher suites")
    is_self_signed: bool = Field(default=False, description="Is self-signed certificate")
    is_wildcard: bool = Field(default=False, description="Is wildcard certificate")
    has_weak_signature: bool = Field(default=False, description="Has weak signature (MD5, SHA1)")
    first_seen: datetime = Field(..., description="First seen timestamp")
    last_seen: datetime = Field(..., description="Last seen timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 789,
                "asset_id": 123,
                "subject_cn": "*.example.com",
                "issuer": "Let's Encrypt Authority X3",
                "serial_number": "04:7f:a1:b3:9e:2d:8c:4f",
                "not_before": "2024-01-01T00:00:00Z",
                "not_after": "2024-04-01T23:59:59Z",
                "is_expired": False,
                "days_until_expiry": 45,
                "san_domains": ["*.example.com", "example.com"],
                "signature_algorithm": "SHA256withRSA",
                "public_key_algorithm": "RSA",
                "public_key_bits": 2048,
                "cipher_suites": ["TLS_AES_256_GCM_SHA384", "TLS_CHACHA20_POLY1305_SHA256"],
                "is_self_signed": False,
                "is_wildcard": True,
                "has_weak_signature": False,
                "first_seen": "2024-01-01T00:00:00Z",
                "last_seen": "2024-01-15T12:00:00Z"
            }
        }
    )


class CertificateListRequest(BaseModel):
    """Certificate list filter parameters"""

    asset_id: Optional[int] = Field(None, description="Filter by asset ID")
    is_expired: Optional[bool] = Field(None, description="Filter by expiration status")
    is_expiring_soon: Optional[bool] = Field(None, description="Filter expiring within 30 days")
    is_self_signed: Optional[bool] = Field(None, description="Filter by self-signed status")
    is_wildcard: Optional[bool] = Field(None, description="Filter by wildcard status")
    has_weak_signature: Optional[bool] = Field(None, description="Filter by weak signature")
    issuer: Optional[str] = Field(None, description="Filter by issuer")
    search: Optional[str] = Field(None, description="Search in CN, issuer, SAN domains")
    sort_by: Optional[str] = Field("not_after", description="Sort field")
    sort_order: Optional[str] = Field("asc", description="Sort order (asc/desc)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_expired": False,
                "is_expiring_soon": True,
                "is_self_signed": False,
                "issuer": "Let's Encrypt",
                "sort_by": "days_until_expiry",
                "sort_order": "asc"
            }
        }
    )


class CertificateHealthResponse(BaseModel):
    """Certificate health summary"""

    total_certificates: int = Field(..., description="Total number of certificates")
    expired: int = Field(..., description="Number of expired certificates")
    expiring_soon: int = Field(..., description="Expiring within 30 days")
    self_signed: int = Field(..., description="Number of self-signed certificates")
    weak_signature: int = Field(..., description="Number with weak signatures")
    wildcard: int = Field(..., description="Number of wildcard certificates")
    by_issuer: Dict[str, int] = Field(..., description="Distribution by issuer")
    by_key_size: Dict[str, int] = Field(..., description="Distribution by key size")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_certificates": 450,
                "expired": 5,
                "expiring_soon": 12,
                "self_signed": 8,
                "weak_signature": 2,
                "wildcard": 125,
                "by_issuer": {
                    "Let's Encrypt": 380,
                    "DigiCert": 45,
                    "Self-signed": 8,
                    "Other": 17
                },
                "by_key_size": {
                    "2048": 400,
                    "4096": 45,
                    "1024": 5
                }
            }
        }
    )
