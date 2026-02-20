from __future__ import annotations

"""
Finding Schemas

Pydantic models for vulnerability findings
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class FindingResponse(BaseModel):
    """Finding response"""

    id: int = Field(..., description="Finding ID")
    asset_id: int = Field(..., description="Asset ID")
    source: str = Field(..., description="Finding source (nuclei, manual, custom)")
    template_id: Optional[str] = Field(None, description="Nuclei template ID")
    name: str = Field(..., description="Finding name")
    severity: str = Field(..., description="Severity level")
    cvss_score: Optional[float] = Field(None, description="CVSS score")
    cve_id: Optional[str] = Field(None, description="CVE identifier")
    evidence: Optional[Dict[str, Any]] = Field(None, description="Evidence/proof data")
    first_seen: datetime = Field(..., description="First seen timestamp")
    last_seen: datetime = Field(..., description="Last seen timestamp")
    status: str = Field(..., description="Finding status (open, suppressed, fixed)")

    # Related asset info (for joined queries)
    asset_identifier: Optional[str] = Field(None, description="Asset identifier")
    asset_type: Optional[str] = Field(None, description="Asset type")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 999,
                "asset_id": 123,
                "source": "nuclei",
                "template_id": "CVE-2024-1234",
                "name": "Apache Log4j RCE Vulnerability",
                "severity": "critical",
                "cvss_score": 9.8,
                "cve_id": "CVE-2024-1234",
                "evidence": {
                    "url": "https://api.example.com/vulnerable-endpoint",
                    "matched_at": "header",
                    "matcher": "log4j-jndi"
                },
                "first_seen": "2024-01-15T10:00:00Z",
                "last_seen": "2024-01-15T12:00:00Z",
                "status": "open",
                "asset_identifier": "api.example.com",
                "asset_type": "subdomain"
            }
        }
    )


class FindingListRequest(BaseModel):
    """Finding list filter parameters"""

    asset_id: Optional[int] = Field(None, description="Filter by asset ID")
    severity: Optional[str] = Field(None, description="Filter by severity")
    min_severity: Optional[str] = Field(None, description="Minimum severity (info, low, medium, high, critical)")
    status: Optional[str] = Field(None, description="Filter by status")
    source: Optional[str] = Field(None, description="Filter by source")
    cve_id: Optional[str] = Field(None, description="Filter by CVE ID")
    template_id: Optional[str] = Field(None, description="Filter by template ID")
    search: Optional[str] = Field(None, description="Search in name, CVE ID, template ID")
    min_cvss_score: Optional[float] = Field(None, description="Minimum CVSS score")
    sort_by: Optional[str] = Field("last_seen", description="Sort field")
    sort_order: Optional[str] = Field("desc", description="Sort order (asc/desc)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "severity": "critical",
                "status": "open",
                "source": "nuclei",
                "min_cvss_score": 7.0,
                "sort_by": "cvss_score",
                "sort_order": "desc"
            }
        }
    )


class FindingUpdate(BaseModel):
    """Update finding request"""

    status: Optional[str] = Field(None, description="Update status (open, suppressed, fixed)")
    notes: Optional[str] = Field(None, description="Notes/comments")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "suppressed",
                "notes": "False positive - WAF rule triggered"
            }
        }
    )


class FindingDetailResponse(FindingResponse):
    """Detailed finding response with full evidence"""

    asset: Optional[Any] = Field(None, description="Full asset details")
    remediation: Optional[str] = Field(None, description="Remediation guidance")
    references: Optional[list[str]] = Field(None, description="Reference URLs")
    tags: Optional[list[str]] = Field(None, description="Finding tags")

    model_config = ConfigDict(from_attributes=True)


class FindingStatsResponse(BaseModel):
    """Finding statistics"""

    total_findings: int = Field(..., description="Total number of findings")
    by_severity: Dict[str, int] = Field(..., description="Distribution by severity")
    by_status: Dict[str, int] = Field(..., description="Distribution by status")
    by_source: Dict[str, int] = Field(..., description="Distribution by source")
    open_findings: int = Field(..., description="Number of open findings")
    critical_open: int = Field(..., description="Open critical findings")
    high_open: int = Field(..., description="Open high severity findings")
    average_cvss: Optional[float] = Field(None, description="Average CVSS score")
    top_cves: list[Dict[str, Any]] = Field(..., description="Most common CVEs")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_findings": 235,
                "by_severity": {
                    "critical": 5,
                    "high": 25,
                    "medium": 80,
                    "low": 100,
                    "info": 25
                },
                "by_status": {
                    "open": 180,
                    "suppressed": 30,
                    "fixed": 25
                },
                "by_source": {
                    "nuclei": 215,
                    "manual": 20
                },
                "open_findings": 180,
                "critical_open": 5,
                "high_open": 20,
                "average_cvss": 6.4,
                "top_cves": [
                    {"cve_id": "CVE-2024-1234", "count": 8},
                    {"cve_id": "CVE-2024-5678", "count": 5}
                ]
            }
        }
    )


class SeverityDistribution(BaseModel):
    """Severity distribution over time"""

    date: datetime = Field(..., description="Date")
    critical: int = Field(..., description="Critical findings")
    high: int = Field(..., description="High severity findings")
    medium: int = Field(..., description="Medium severity findings")
    low: int = Field(..., description="Low severity findings")
    info: int = Field(..., description="Info findings")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15T00:00:00Z",
                "critical": 5,
                "high": 25,
                "medium": 80,
                "low": 100,
                "info": 25
            }
        }
    )
