"""
Web attack-surface Pydantic schemas — endpoints and captured transactions.

``HttpEndpointCreate`` / ``HttpTransactionCreate`` are what plugins emit in
``ParsedResults``; the repository deduplicates and persists them.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import Field

from app.models.web import HttpMethod, ParameterLocation, TransactionSource
from app.schemas.common import TimestampedResponse, VulnForgeBaseModel


class EndpointParameter(VulnForgeBaseModel):
    """A single request parameter descriptor."""

    name: str = Field(min_length=1, max_length=255)
    location: ParameterLocation = Field(default=ParameterLocation.QUERY)
    example: str | None = Field(default=None, max_length=2048)


class HttpEndpointCreate(VulnForgeBaseModel):
    """A discovered endpoint emitted by a plugin."""

    method: HttpMethod = Field(default=HttpMethod.GET)
    url: str = Field(min_length=1, max_length=2048)
    status_code: int | None = Field(default=None, ge=100, le=599)
    content_type: str | None = Field(default=None, max_length=255)
    parameters: list[EndpointParameter] = Field(default_factory=list)
    source_tool: str = Field(min_length=1, max_length=100)
    requires_auth: bool = Field(default=False)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HttpEndpointResponse(TimestampedResponse):
    """API representation of a discovered endpoint."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    target_id: uuid.UUID
    scan_id: uuid.UUID | None
    method: HttpMethod
    url: str
    status_code: int | None
    content_type: str | None
    parameters: list[dict[str, Any]]
    source_tools: list[str]
    requires_auth: bool
    is_active: bool
    metadata_dict: dict[str, Any] = Field(alias="metadata")


class HttpTransactionCreate(VulnForgeBaseModel):
    """A captured request/response pair emitted by a plugin or agent."""

    source: TransactionSource = Field(default=TransactionSource.CRAWLER)
    method: HttpMethod = Field(default=HttpMethod.GET)
    url: str = Field(min_length=1, max_length=2048)
    request_headers: dict[str, Any] = Field(default_factory=dict)
    request_body: str | None = None
    status_code: int | None = Field(default=None, ge=100, le=599)
    response_headers: dict[str, Any] = Field(default_factory=dict)
    response_body: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    notes: str | None = None
    endpoint_url: str | None = Field(
        default=None,
        description="URL used to associate this transaction with a known endpoint.",
    )


class HttpTransactionResponse(TimestampedResponse):
    """API representation of a captured transaction."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    endpoint_id: uuid.UUID | None
    scan_id: uuid.UUID | None
    vulnerability_id: uuid.UUID | None
    source: TransactionSource
    method: HttpMethod
    url: str
    request_headers: dict[str, Any]
    request_body: str | None
    status_code: int | None
    response_headers: dict[str, Any]
    response_body: str | None
    duration_ms: int | None
    notes: str | None
