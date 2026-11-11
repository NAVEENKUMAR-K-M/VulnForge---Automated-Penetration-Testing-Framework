"""
Web attack-surface ORM models.

Bug hunting is request-centric, so VulnForge models the discovered web surface
(``http_endpoints``) and the concrete request/response pairs that act as evidence
and are replayable (``http_transactions``). Endpoints are deduplicated per
(workspace, method, url); transactions are append-only proof captured by the
crawler, the DAST scanner, the agent, or a human.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase

if TYPE_CHECKING:
    from app.models.scan import Scan
    from app.models.target import Target
    from app.models.vulnerability import Vulnerability
    from app.models.workspace import Workspace


class HttpMethod(str, enum.Enum):
    """HTTP method for an endpoint or captured transaction."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"


class ParameterLocation(str, enum.Enum):
    """Where a request parameter is carried."""

    QUERY = "query"
    BODY = "body"
    PATH = "path"
    HEADER = "header"
    COOKIE = "cookie"
    JSON = "json"


class TransactionSource(str, enum.Enum):
    """What produced a captured transaction."""

    CRAWLER = "crawler"
    DAST = "dast"
    AGENT = "agent"
    MANUAL = "manual"
    VERIFICATION = "verification"


class HttpEndpoint(TimestampedBase):
    """A discovered request-able endpoint (method + URL + parameters).

    Deduplicated per (workspace, method, url). ``parameters`` is a list of
    ``{"name", "location", "example"}`` dicts so active testers know what to
    fuzz without re-crawling.
    """

    __tablename__ = "http_endpoints"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "method", "url",
            name="uq_http_endpoints_workspace_method_url",
        ),
        Index("idx_http_endpoints_target_id", "target_id"),
        Index("idx_http_endpoints_scan_id", "scan_id"),
        Index(
            "idx_http_endpoints_active",
            "is_active",
            postgresql_where=text("is_active = TRUE"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE", name="fk_http_endpoints_workspaces"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="CASCADE", name="fk_http_endpoints_targets"),
        nullable=False,
    )
    scan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="SET NULL", name="fk_http_endpoints_scans"),
        nullable=True,
        doc="The scan that first discovered this endpoint.",
    )
    method: Mapped[HttpMethod] = mapped_column(
        Enum(HttpMethod, values_callable=lambda obj: [e.value for e in obj], name="http_method_enum"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parameters: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        doc="List of {name, location, example} parameter descriptors.",
    )
    source_tools: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        doc="Plugins that reported this endpoint.",
    )
    metadata_dict: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        doc="Title, content length, detected tech, auth requirement, notes.",
    )
    requires_auth: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("FALSE"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("TRUE"),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    workspace: Mapped[Workspace] = relationship("Workspace", lazy="select")
    target: Mapped[Target] = relationship("Target", lazy="select")
    scan: Mapped[Scan | None] = relationship("Scan", lazy="select")


class HttpTransaction(TimestampedBase):
    """A captured request/response pair — evidence and a replayable record.

    Append-only. Optionally linked to the endpoint it exercised and the
    vulnerability it proves.
    """

    __tablename__ = "http_transactions"
    __table_args__ = (
        Index("idx_http_transactions_workspace_id", "workspace_id"),
        Index("idx_http_transactions_endpoint_id", "endpoint_id"),
        Index("idx_http_transactions_vulnerability_id", "vulnerability_id"),
        Index("idx_http_transactions_scan_id", "scan_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE", name="fk_http_tx_workspaces"),
        nullable=False,
    )
    endpoint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("http_endpoints.id", ondelete="SET NULL", name="fk_http_tx_endpoints"),
        nullable=True,
    )
    scan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="SET NULL", name="fk_http_tx_scans"),
        nullable=True,
    )
    vulnerability_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vulnerabilities.id", ondelete="SET NULL", name="fk_http_tx_vulns"),
        nullable=True,
        doc="The finding this transaction is evidence for, if any.",
    )
    source: Mapped[TransactionSource] = mapped_column(
        Enum(TransactionSource, values_callable=lambda obj: [e.value for e in obj], name="http_tx_source_enum"),
        nullable=False,
        default=TransactionSource.CRAWLER,
        server_default=TransactionSource.CRAWLER.value,
    )
    method: Mapped[HttpMethod] = mapped_column(
        Enum(HttpMethod, values_callable=lambda obj: [e.value for e in obj], name="http_method_enum", create_type=False),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    request_headers: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"),
    )
    request_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_headers: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"),
    )
    response_body: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Response body, truncated to a sane cap by the writer.",
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    endpoint: Mapped[HttpEndpoint | None] = relationship("HttpEndpoint", lazy="select")
    vulnerability: Mapped[Vulnerability | None] = relationship("Vulnerability", lazy="select")
