"""
Scan ORM model — the central orchestration entity.

A Scan represents a time-boxed execution of security tools against a single
Target.  The scan drives a state machine:

    pending → running → completed
                     ↘ failed
                     ↘ cancelled
              ↕ paused (analyst hold)

The ``celery_task_id`` field links to the Celery distributed task so scan
jobs can be monitored, cancelled, or retried through the task queue.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.target import Target
    from app.models.vulnerability import Vulnerability
    from app.models.scan_plugin_execution import ScanPluginExecution
    from app.models.report import Report
    from app.models.workspace import Workspace


class ScanStatus(str, enum.Enum):
    """Lifecycle states of a scan job.

    Design:
        States are linear with one fork at completion.
        ``paused`` is a valid intermediate hold state.
    """

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScanType(str, enum.Enum):
    """Scope of the scan — which PTES phases to execute.

    Values:
        RECONNAISSANCE:      Only recon plugins (nmap, shodan).
        VULNERABILITY:       Only vuln scanner plugins (nuclei, nikto).
        EXPLOITATION:        Only exploitation plugins (metasploit, sqlmap).
        FULL:                All phases in sequence.
    """

    RECONNAISSANCE = "reconnaissance"
    VULNERABILITY = "vulnerability"
    EXPLOITATION = "exploitation"
    FULL = "full"


class Priority(str, enum.Enum):
    """Scan scheduling priority for queue ordering."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Scan(TimestampedBase):
    """ORM model for the ``scans`` table.

    Attributes:
        name:            Human-readable scan label.
        description:     Optional context about the scan purpose.
        status:          Current lifecycle state.
        target_id:       FK to the target being scanned.
        created_by_id:   FK to the user who initiated the scan.
        assigned_to_id:  FK to the analyst responsible for reviewing results.
        scan_type:       Which phase(s) to execute.
        priority:        Queue scheduling priority.
        scheduled_at:    Optional future start time.
        started_at:      Actual start timestamp (set by the Celery worker).
        completed_at:    Actual completion timestamp.
        configuration:   JSONB scan-level overrides applied to all plugins.
        error_message:   Failure reason if ``status == failed``.
        celery_task_id:  Celery task ID for monitoring and cancellation.
    """

    __tablename__ = "scans"
    __table_args__ = (
        CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="ck_scans_completed_after_started",
        ),
        Index("idx_scans_status", "status"),
        Index("idx_scans_priority", "priority"),
        Index(
            "idx_scans_celery_task",
            "celery_task_id",
            postgresql_where=text("celery_task_id IS NOT NULL"),
        ),
        Index(
            "idx_scans_scheduled",
            "scheduled_at",
            postgresql_where=text("scheduled_at IS NOT NULL"),
        ),
    )

    name: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        doc="Human-readable scan label (e.g., 'Q1 2026 External Assessment').",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional context about the scan purpose and methodology.",
    )
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, values_callable=lambda obj: [e.value for e in obj], name="scan_status_enum"),
        nullable=False,
        default=ScanStatus.PENDING,
        server_default=ScanStatus.PENDING.value,
        doc="Current lifecycle state of this scan.",
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="RESTRICT", name="fk_scans_targets"),
        nullable=False,
        index=True,
        doc="FK to the target being assessed.",
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_scans_created_by"),
        nullable=False,
        index=True,
        doc="FK to the user who initiated this scan.",
    )
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_scans_assigned_to"),
        nullable=True,
        doc="FK to the analyst assigned to review findings.",
    )
    scan_type: Mapped[ScanType] = mapped_column(
        Enum(ScanType, values_callable=lambda obj: [e.value for e in obj], name="scan_type_enum"),
        nullable=False,
        index=True,
        doc="Which PTES phases to execute.",
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, values_callable=lambda obj: [e.value for e in obj], name="priority_enum"),
        nullable=False,
        default=Priority.MEDIUM,
        server_default=Priority.MEDIUM.value,
        doc="Queue scheduling priority.",
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Optional UTC timestamp for a future scheduled start.",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Actual UTC start timestamp, set by the Celery worker when execution begins.",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Actual UTC completion timestamp.",
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        doc="Scan-level configuration overrides applied to all plugin executions.",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Failure reason populated when status transitions to 'failed'.",
    )
    celery_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Celery task ID used to monitor, cancel, or retry this scan.",
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "workspaces.id",
            ondelete="SET NULL",
            name="fk_scans_workspace",
        ),
        nullable=True,
        index=True,
        doc="FK to the workspace/engagement this scan belongs to. NULL for ungrouped scans.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    target: Mapped[Target] = relationship(
        "Target",
        back_populates="scans",
        lazy="select",
    )
    created_by: Mapped[User] = relationship(
        "User",
        foreign_keys=[created_by_id],
        back_populates="created_scans",
        lazy="select",
    )
    assigned_to: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[assigned_to_id],
        back_populates="assigned_scans",
        lazy="select",
    )
    plugin_executions: Mapped[list[ScanPluginExecution]] = relationship(
        "ScanPluginExecution",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="select",
    )
    vulnerabilities: Mapped[list[Vulnerability]] = relationship(
        "Vulnerability",
        back_populates="scan",
        cascade="all, delete-orphan",
        lazy="select",
    )
    reports: Mapped[list[Report]] = relationship(
        "Report",
        secondary="report_scans",
        back_populates="scans",
        lazy="select",
    )
    workspace: Mapped[Workspace | None] = relationship(
        "Workspace",
        back_populates="scans",
        lazy="select",
    )

    @property
    def duration_seconds(self) -> float | None:
        """Return scan duration in seconds, or None if not completed.

        Returns:
            float | None: Duration in seconds, or None.
        """
        if self.started_at is None or self.completed_at is None:
            return None
        start = self.started_at.replace(tzinfo=None)
        end = self.completed_at.replace(tzinfo=None)
        return (end - start).total_seconds()

    @property
    def is_terminal(self) -> bool:
        """Return True if the scan has reached a terminal state.

        Returns:
            bool: True for completed, failed, or cancelled states.
        """
        return self.status in {
            ScanStatus.COMPLETED,
            ScanStatus.FAILED,
            ScanStatus.CANCELLED,
        }
