"""
Base declarative model with shared mixins for all VulnForge ORM entities.

Architecture Decision:
    All SQLAlchemy models inherit from ``TimestampedBase``, which composes
    ``UUIDPrimaryKeyMixin`` and ``TimestampMixin``.  This eliminates duplication
    of ``id``, ``created_at``, and ``updated_at`` across every table while
    keeping each mixin single-purpose (SRP).

    ``updated_at`` is maintained by a PostgreSQL trigger AND by SQLAlchemy's
    ``onupdate`` — the trigger is the authoritative source; the ORM-level
    ``onupdate`` acts as a safety net for bulk operations that bypass the ORM.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all VulnForge models.

    Provides a shared metadata object and enables the ``mapped_column``
    annotation style introduced in SQLAlchemy 2.0.
    """

    type_annotation_map: dict[Any, Any] = {
        datetime: DateTime(timezone=True),
        uuid.UUID: UUID(as_uuid=True),
    }


class UUIDPrimaryKeyMixin:
    """Mixin that provides a UUID v4 primary key column.

    Uses PostgreSQL's ``gen_random_uuid()`` function as the server-side
    default so the PK is generated at the DB level — this is safer than
    relying on the ORM to generate it, as it ensures uniqueness even for
    bulk inserts that bypass the ORM layer.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        default=uuid.uuid4,
        doc="Universally unique identifier for this record.",
    )


class TimestampMixin:
    """Mixin that provides ``created_at`` and ``updated_at`` audit timestamps.

    Both columns use ``TIMESTAMPTZ`` (timestamp with time zone) — all times
    are stored in UTC.  The application layer never stores naive datetimes.

    ``updated_at`` uses a dual-maintenance strategy:
        - ``onupdate=datetime.utcnow`` handles ORM-layer updates.
        - A PostgreSQL trigger (defined in the Alembic migration) handles
          bulk SQL updates that bypass the ORM.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
        doc="UTC timestamp of record creation. Never modified after insert.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        onupdate=datetime.utcnow,
        nullable=False,
        doc="UTC timestamp of the most recent update to this record.",
    )


class TimestampedBase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Abstract base combining UUID PK and audit timestamps.

    All VulnForge domain models inherit from this class.  It is declared
    ``__abstract__ = True`` so SQLAlchemy does not attempt to map it to
    a table directly.
    """

    __abstract__ = True

    def __repr__(self) -> str:
        """Return a deterministic developer-friendly representation."""
        return f"<{self.__class__.__name__} id={self.id}>"
