from __future__ import annotations

"""
Common Pydantic Schemas

Shared models for pagination, errors, and responses
"""

from typing import List, Optional, Any, Generic, TypeVar
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

T = TypeVar('T')


class ErrorResponse(BaseModel):
    """Standard error response"""

    error: str = Field(..., description="Error type")
    detail: str = Field(..., description="Error detail message")
    status_code: int = Field(..., description="HTTP status code")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "NotFound",
                "detail": "Asset not found",
                "status_code": 404
            }
        }
    )


class SuccessResponse(BaseModel):
    """Standard success response"""

    success: bool = Field(default=True, description="Operation success")
    message: str = Field(..., description="Success message")
    data: Optional[Any] = Field(None, description="Optional response data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": None
            }
        }
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard paginated response

    Generic type allows reuse for any model
    """

    items: List[T] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "page_size": 50,
                "total_pages": 2
            }
        }
    )


class HealthCheck(BaseModel):
    """Health check response"""

    status: str = Field(..., description="Overall health status")
    services: dict = Field(..., description="Individual service statuses")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "services": {
                    "database": {"status": "connected"},
                    "redis": {"status": "connected"},
                    "minio": {"status": "connected"}
                }
            }
        }
    )


class DateRangeFilter(BaseModel):
    """Date range filter for queries"""

    start_date: Optional[datetime] = Field(None, description="Start date")
    end_date: Optional[datetime] = Field(None, description="End date")


class BulkOperationResult(BaseModel):
    """Result of bulk operation"""

    success_count: int = Field(..., description="Number of successful operations")
    failure_count: int = Field(..., description="Number of failed operations")
    errors: List[str] = Field(default_factory=list, description="List of errors")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success_count": 95,
                "failure_count": 5,
                "errors": [
                    "Asset 'example.com' already exists",
                    "Invalid domain format: 'not-a-domain'"
                ]
            }
        }
    )


class TaskResponse(BaseModel):
    """Async task response"""

    task_id: str = Field(..., description="Celery task ID")
    status: str = Field(..., description="Task status (queued, running, completed, failed)")
    message: str = Field(..., description="Status message")
    data: Optional[Any] = Field(None, description="Optional task data")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "status": "queued",
                "message": "Nuclei scan queued for tenant 2",
                "data": None
            }
        }
    )
