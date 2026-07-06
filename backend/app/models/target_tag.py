"""
TargetTag ORM model — flexible labeling for target organization.

Stored in a dedicated table (not an array column) so tags can be indexed
and used in efficient JOIN queries:
    e.g., "Find all open critical vulnerabilities on production targets."
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.target import Target


class TargetTag(UUIDPrimaryKeyMixin, Base):
    """ORM model for the ``target_tags`` table.

    Design Note:
        Tags only have a ``created_at`` column (no ``updated_at``) because
        tags are immutable — to change a tag, delete and recreate it.
        This prevents confusion about whether a tag edit invalidates
        historical scan context.

    Attributes:
        target_id:  FK to the parent target.
        tag:        Lowercase label string (e.g., ``production``, ``internal``).
        created_at: Immutable creation timestamp.
    """

    __tablename__ = "target_tags"
    __table_args__ = (
        UniqueConstraint("target_id", "tag", name="uq_target_tags_pair"),
        CheckConstraint("char_length(trim(tag)) > 0", name="ck_target_tags_nonempty"),
    )

    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="CASCADE", name="fk_target_tags_targets"),
        nullable=False,
        index=True,
        doc="FK to the parent target.",
    )
    tag: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Lowercase tag label (e.g., 'production', 'web-app', 'internal').",
    )
    created_at: Mapped[datetime] = mapped_column(
        doc="Immutable creation timestamp. Tags are not updated, only recreated.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    target: Mapped[Target] = relationship(
        "Target",
        back_populates="tags",
        lazy="select",
    )
