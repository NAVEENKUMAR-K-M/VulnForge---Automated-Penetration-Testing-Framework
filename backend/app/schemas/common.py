"""
Common Pydantic schemas shared across VulnForge API.

Provides:
    - Standardised paginated response envelope
    - Standardised error response shape
    - Base response with consistent timestamp serialisation
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class VulnForgeBaseModel(BaseModel):
    """Base Pydantic model with shared configuration.

    Configuration:
        - ``from_attributes=True``: Enables reading from SQLAlchemy ORM instances.
        - ``populate_by_name=True``: Allows both field alias and field name.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class TimestampedResponse(VulnForgeBaseModel):
    """Response base that includes UUID, created_at, and updated_at."""

    id: UUID = Field(description="Unique identifier.")
    created_at: datetime = Field(description="UTC creation timestamp.")
    updated_at: datetime = Field(description="UTC last-updated timestamp.")


class PaginatedResponse(VulnForgeBaseModel, Generic[DataT]):
    """Generic paginated response envelope.

    Type Parameters:
        DataT: The item type within the ``items`` list.

    Example:
        PaginatedResponse[UserResponse]
    """

    items: list[DataT] = Field(description="Page of results.")
    total: int = Field(description="Total number of matching records.", ge=0)
    page: int = Field(description="Current page number (1-indexed).", ge=1)
    page_size: int = Field(description="Number of items per page.", ge=1)
    pages: int = Field(description="Total number of pages.", ge=0)

    @classmethod
    def build(
        cls,
        items: list[DataT],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[DataT]":
        """Construct a PaginatedResponse from raw values.

        Args:
            items:     The current page of items.
            total:     Total number of matching records.
            page:      Current 1-indexed page number.
            page_size: Number of items per page.

        Returns:
            PaginatedResponse[DataT]: Fully populated paginated response.
        """
        import math
        pages = math.ceil(total / page_size) if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )


class ErrorDetail(VulnForgeBaseModel):
    """Single error detail object in an error response."""

    field: str | None = Field(
        default=None,
        description="The field that caused the error, if applicable.",
    )
    message: str = Field(description="Human-readable error description.")
    code: str | None = Field(
        default=None,
        description="Machine-readable error code.",
    )


class ErrorResponse(VulnForgeBaseModel):
    """Standardised error response envelope returned by all API error handlers."""

    error: str = Field(description="Short error type identifier.")
    message: str = Field(description="Human-readable summary of the error.")
    details: list[ErrorDetail] | None = Field(
        default=None,
        description="Optional list of per-field validation errors.",
    )
    request_id: str | None = Field(
        default=None,
        description="Request correlation ID for log tracing.",
    )


class MessageResponse(VulnForgeBaseModel):
    """Simple confirmation response with a single message field."""

    message: str = Field(description="Confirmation or status message.")
