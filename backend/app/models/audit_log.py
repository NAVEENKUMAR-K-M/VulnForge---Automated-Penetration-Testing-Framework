"""
AuditLog ORM model — immutable security audit trail.

Architecture Decision:
    This table is APPEND-ONLY.  No UPDATE or DELETE operations are ever
    issued against it.  The application layer enforces this, and a
    PostgreSQL row-level security policy can enforce it at the DB level
    in production.

    The table uses RANGE partitioning by ``created_at`` (quarterly) to
    maintain query performance as the audit log grows to millions of rows.
    Partitions are created via Alembic migrations.

    ``actor_id`` is nullable to capture unauthenticated events such as:
        - Failed login attempts
        - Unauthenticated API probe attempts
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuditOutcome(str, enum.Enum):
    """Outcome of the audited action.

    Values:
        SUCCESS: The action completed as intended.
        FAILURE: The action was rejected or caused an error.
    """

    SUCCESS = "success"
    FAILURE = "failure"


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """ORM model for the partitioned ``audit_logs`` table.

    Design Note:
        Because the table is partitioned, it does NOT inherit
        ``TimestampedBase`` (which adds ``updated_at``).  Partitioned
        tables must include the partition key in every row and cannot
        use a standard SERIAL primary key across partitions.

    Attributes:
        actor_id:      FK to the acting user. NULL for unauthenticated events.
        actor_ip:      Client IP address at the time of the action.
        action:        Dot-notation action identifier (e.g., 'scan.created').
        resource_type: The type of entity acted upon (e.g., 'scan').
        resource_id:   UUID of the specific entity acted upon.
        details:       JSONB blob with action-specific context.
        outcome:       success | failure.
        created_at:    Immutable partition key and event timestamp.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_actor_id", "actor_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_created_at", "created_at"),
        Index("idx_audit_outcome", "outcome"),
        {"postgresql_partition_by": "RANGE (created_at)"},
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_audit_logs_users"),
        nullable=True,
        doc="FK to the acting user. NULL for unauthenticated events.",
    )
    actor_ip: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        doc="Client IP address at the time of the event.",
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Dot-notation action identifier (e.g., 'scan.created', 'user.login').",
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Type of entity acted upon (e.g., 'scan', 'vulnerability', 'report').",
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        doc="UUID of the specific entity acted upon.",
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Action-specific context payload (before/after values, error codes, etc.).",
    )
    outcome: Mapped[AuditOutcome] = mapped_column(
        Enum(AuditOutcome, name="audit_outcome_enum"),
        nullable=False,
        doc="Outcome of the audited action: success | failure.",
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("NOW()"),
        nullable=False,
        doc="Immutable partition key and event timestamp (UTC).",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    actor: Mapped[User | None] = relationship(
        "User",
        back_populates="audit_logs",
        lazy="select",
    )
