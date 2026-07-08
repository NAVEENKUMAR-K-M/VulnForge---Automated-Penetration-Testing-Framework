"""
ScanPluginExecution ORM model.

Tracks the execution of a single plugin within a scan.  One scan may
run multiple plugins either sequentially or in parallel — each gets its
own row providing full per-plugin observability.

``raw_output`` stores sanitized tool stdout/stderr for forensic audit.
It is stored as TEXT (not JSONB) because raw tool output is unstructured
and size-unbounded.  Parsers transform it into structured findings.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase

if TYPE_CHECKING:
    from app.models.scan import Scan
    from app.models.plugin import Plugin
    from app.models.vulnerability import Vulnerability


class PluginExecutionStatus(str, enum.Enum):
    """Lifecycle states of a plugin execution within a scan.

    Values:
        PENDING:    Queued but not started.
        RUNNING:    Process is active.
        COMPLETED:  Finished with exit code 0.
        FAILED:     Non-zero exit code or uncaught exception.
        SKIPPED:    Deliberately not run (e.g., prerequisites not met).
        TIMED_OUT:  Killed after exceeding ``PLUGIN_EXECUTION_TIMEOUT``.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


class ScanPluginExecution(TimestampedBase):
    """ORM model for the ``scan_plugin_executions`` table.

    Attributes:
        scan_id:       FK to the parent scan.
        plugin_id:     FK to the plugin registry entry.
        status:        Current execution state.
        configuration: Per-execution plugin config (overrides plugin defaults).
        raw_output:    Sanitized stdout/stderr from the tool subprocess.
        started_at:    When the subprocess was launched.
        completed_at:  When the subprocess terminated.
        exit_code:     OS exit code from the subprocess.
        error_message: Human-readable error if status is ``failed`` or ``timed_out``.
    """

    __tablename__ = "scan_plugin_executions"

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE", name="fk_spe_scans"),
        nullable=False,
        index=True,
        doc="FK to the parent scan.",
    )
    plugin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plugins.id", ondelete="RESTRICT", name="fk_spe_plugins"),
        nullable=False,
        index=True,
        doc="FK to the plugin registry entry.",
    )
    status: Mapped[PluginExecutionStatus] = mapped_column(
        Enum(PluginExecutionStatus, values_callable=lambda obj: [e.value for e in obj], name="plugin_exec_status_enum"),
        nullable=False,
        default=PluginExecutionStatus.PENDING,
        server_default=PluginExecutionStatus.PENDING.value,
        index=True,
        doc="Current execution state.",
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        doc="Per-execution plugin configuration overriding defaults.",
    )
    raw_output: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Sanitized stdout/stderr captured from the tool subprocess.",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when the subprocess was launched.",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp when the subprocess terminated.",
    )
    exit_code: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
        doc="OS exit code from the tool subprocess (0 = success).",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Human-readable error message if execution failed.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    scan: Mapped[Scan] = relationship(
        "Scan",
        back_populates="plugin_executions",
        lazy="select",
    )
    plugin: Mapped[Plugin] = relationship(
        "Plugin",
        back_populates="executions",
        lazy="select",
    )
    vulnerabilities: Mapped[list[Vulnerability]] = relationship(
        "Vulnerability",
        back_populates="plugin_execution",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def duration_seconds(self) -> float | None:
        """Return plugin execution duration in seconds.

        Returns:
            float | None: Duration in seconds, or None if not completed.
        """
        if self.started_at is None or self.completed_at is None:
            return None
        start = self.started_at.replace(tzinfo=None)
        end = self.completed_at.replace(tzinfo=None)
        return (end - start).total_seconds()
