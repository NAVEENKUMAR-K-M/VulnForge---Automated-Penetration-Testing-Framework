"""
Report ORM model.

A Report is a generated document aggregating findings from one or more scans.
Report generation is an async operation (triggered via Celery) that can take
minutes for large assessments — the ``status`` column tracks the async lifecycle.

Many-to-many relationships to both ``scans`` and ``vulnerabilities`` are
managed via association tables ``report_scans`` and ``report_vulnerabilities``.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.scan import Scan
    from app.models.vulnerability import Vulnerability


class ReportType(str, enum.Enum):
    """Type of report document — determines template and content depth.

    Values:
        EXECUTIVE_SUMMARY: High-level business-focused report.
        TECHNICAL:         Full technical details including PoC and remediation.
        COMPLIANCE:        Compliance-oriented report (e.g., PCI-DSS, ISO 27001).
    """

    EXECUTIVE_SUMMARY = "executive_summary"
    TECHNICAL = "technical"
    COMPLIANCE = "compliance"


class ReportFormat(str, enum.Enum):
    """Output format of the generated report."""

    HTML = "html"
    PDF = "pdf"
    JSON = "json"


class ReportStatus(str, enum.Enum):
    """Async generation lifecycle states."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class Report(TimestampedBase):
    """ORM model for the ``reports`` table.

    Attributes:
        title:                   Report title.
        description:             Optional context note.
        report_type:             executive_summary | technical | compliance.
        format:                  html | pdf | json.
        status:                  Async generation state.
        file_path:               Filesystem path to the generated file.
        file_size_bytes:         Size of the generated file in bytes.
        generated_by_id:         FK to the requesting user.
        generation_started_at:   UTC timestamp when Celery task began.
        generation_completed_at: UTC timestamp when generation finished.
        error_message:           Failure reason if status is ``failed``.
    """

    __tablename__ = "reports"

    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        doc="Human-readable title of the report.",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional context note about this report's purpose or audience.",
    )
    report_type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, values_callable=lambda obj: [e.value for e in obj], name="report_type_enum"),
        nullable=False,
        index=True,
        doc="Report type: executive_summary | technical | compliance.",
    )
    format: Mapped[ReportFormat] = mapped_column(
        Enum(ReportFormat, values_callable=lambda obj: [e.value for e in obj], name="report_format_enum"),
        nullable=False,
        doc="Output format: html | pdf | json.",
    )
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, values_callable=lambda obj: [e.value for e in obj], name="report_status_enum"),
        nullable=False,
        default=ReportStatus.PENDING,
        server_default=ReportStatus.PENDING.value,
        index=True,
        doc="Async generation lifecycle state.",
    )
    file_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        doc="Absolute filesystem path to the generated report file.",
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        doc="Size of the generated file in bytes.",
    )
    generated_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_reports_users"),
        nullable=False,
        index=True,
        doc="FK to the user who requested this report.",
    )
    generation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when the Celery generation task began.",
    )
    generation_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when report generation completed.",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Failure reason if status is 'failed'.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    generated_by: Mapped[User] = relationship(
        "User",
        foreign_keys=[generated_by_id],
        back_populates="generated_reports",
        lazy="select",
    )
    scans: Mapped[list[Scan]] = relationship(
        "Scan",
        secondary="report_scans",
        back_populates="reports",
        lazy="select",
    )
    vulnerabilities: Mapped[list[Vulnerability]] = relationship(
        "Vulnerability",
        secondary="report_vulnerabilities",
        back_populates="reports",
        lazy="select",
    )
