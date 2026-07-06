"""
UserSession ORM model — stateful refresh token store for JWT rotation.

Architecture Decision:
    Refresh tokens are never stored in plaintext.  Only a SHA-256 hash
    (``refresh_token_hash``) is persisted.  When a client presents a refresh
    token, we hash it and do a DB lookup — the plaintext token only ever
    exists in memory and in the HTTP response.

    ``ip_address`` uses PostgreSQL's native ``INET`` type for proper CIDR
    comparisons without application-level string parsing.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase

if TYPE_CHECKING:
    from app.models.user import User


class UserSession(TimestampedBase):
    """ORM model for the ``user_sessions`` table.

    Each row represents one refresh token issuance.  On token rotation,
    the existing session is revoked (``is_revoked=True``) and a new row
    is inserted — providing a full token history for forensic analysis.

    Attributes:
        user_id:             FK to the owning user.
        refresh_token_hash:  SHA-256 hex digest of the raw refresh token.
        expires_at:          UTC expiry of this refresh token.
        is_revoked:          True if this token has been rotated or explicitly
                             invalidated (logout or security event).
        ip_address:          Client IP at the time of issuance.
        user_agent:          Client User-Agent string at time of issuance.
    """

    __tablename__ = "user_sessions"
    __table_args__ = (
        Index(
            "idx_user_sessions_token",
            "refresh_token_hash",
        ),
        Index(
            "idx_user_sessions_active",
            "user_id",
            "expires_at",
            postgresql_where=text("is_revoked = FALSE"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_user_sessions_users"),
        nullable=False,
        index=True,
        doc="FK to the user who owns this session.",
    )
    refresh_token_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        doc="SHA-256 hex digest of the raw refresh token. Never the plaintext.",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="UTC expiry timestamp after which the refresh token is invalid.",
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        doc="True if this session has been explicitly invalidated.",
    )
    ip_address: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        doc="Client IP address at the time this session was created.",
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="HTTP User-Agent header from the client that created this session.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped[User] = relationship(
        "User",
        back_populates="sessions",
        lazy="select",
        doc="The user who owns this session.",
    )

    @property
    def is_valid(self) -> bool:
        """Return True if this session is usable (not revoked and not expired).

        Returns:
            bool: True if the session can be used for token refresh.
        """
        if self.is_revoked:
            return False
        return datetime.utcnow() < self.expires_at.replace(tzinfo=None)
