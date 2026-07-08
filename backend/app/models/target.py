"""
Target ORM model.

A Target defines the authorized scope of a penetration test.  Every scan
must reference a target, creating an unbreakable chain:

    Finding → Scan → Target → Authorization scope

This ensures no scan is ever run against an unauthorized asset.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    String,
    Text,
    Boolean,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.scan import Scan
    from app.models.vulnerability import Vulnerability
    from app.models.target_tag import TargetTag


class TargetType(str, enum.Enum):
    """Classification of the target asset type.

    Values:
        HOST:     Single IP address (e.g., ``192.168.1.1``).
        NETWORK:  CIDR range (e.g., ``10.0.0.0/24``).
        URL:      Fully qualified URL (e.g., ``https://app.example.com``).
        DOMAIN:   Domain name (e.g., ``example.com``).
    """

    HOST = "host"
    NETWORK = "network"
    URL = "url"
    DOMAIN = "domain"


class Target(TimestampedBase):
    """ORM model for the ``targets`` table.

    Attributes:
        name:           Human-readable label for this target.
        description:    Longer description of what this target is.
        target_type:    Classification of the target (host, network, etc.).
        value:          The actual scannable value (IP, CIDR, URL, domain).
        scope_notes:    Written authorization and any explicit exclusions.
        is_active:      Soft-disable without deleting historical scan data.
        created_by_id:  FK to the user who registered this target.
    """

    __tablename__ = "targets"
    __table_args__ = (
        CheckConstraint(
            "char_length(trim(value)) > 0",
            name="ck_targets_value_nonempty",
        ),
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable label for this target (e.g., 'Production Web Server').",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional detailed description of the target asset.",
    )
    target_type: Mapped[TargetType] = mapped_column(
        Enum(TargetType, values_callable=lambda obj: [e.value for e in obj], name="target_type_enum"),
        nullable=False,
        index=True,
        doc="Asset classification: host | network | url | domain.",
    )
    value: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        doc="The scannable value — IP address, CIDR, URL, or domain name.",
    )
    scope_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Written authorization note and any explicit out-of-scope exclusions.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        index=True,
        doc="Soft-disable flag. Inactive targets cannot be selected for new scans.",
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_targets_users"),
        nullable=False,
        index=True,
        doc="FK to the user who registered this target.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    created_by: Mapped[User] = relationship(
        "User",
        foreign_keys=[created_by_id],
        back_populates="created_targets",
        lazy="select",
    )
    tags: Mapped[list[TargetTag]] = relationship(
        "TargetTag",
        back_populates="target",
        cascade="all, delete-orphan",
        lazy="select",
    )
    scans: Mapped[list[Scan]] = relationship(
        "Scan",
        back_populates="target",
        lazy="select",
    )
    vulnerabilities: Mapped[list[Vulnerability]] = relationship(
        "Vulnerability",
        back_populates="target",
        lazy="select",
    )
