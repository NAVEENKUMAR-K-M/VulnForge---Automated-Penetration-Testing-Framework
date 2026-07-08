"""
User ORM model.

Represents an authenticated platform user.  Passwords are NEVER stored in
plaintext — only bcrypt hashes.  Brute-force protection is implemented via
``failed_login_attempts`` and ``locked_until``.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase

if TYPE_CHECKING:
    from app.models.scan import Scan
    from app.models.target import Target
    from app.models.report import Report
    from app.models.vulnerability import Vulnerability
    from app.models.user_session import UserSession
    from app.models.vulnerability_note import VulnerabilityNote
    from app.models.audit_log import AuditLog
    from app.models.workspace import Workspace, WorkspaceMember
    from app.models.scan_profile import ScanProfile


class UserRole(str, enum.Enum):
    """Enumeration of platform roles with ascending privilege levels.

    Design:
        ``str`` mixin ensures SQLAlchemy serialises the value (not the name)
        into JSONB columns and Pydantic schemas receive a plain string.

    Roles:
        admin:   Full platform access including user management and plugin config.
        analyst: Can create scans, triage findings, and generate reports.
        viewer:  Read-only access to scan results and reports.
    """

    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class User(TimestampedBase):
    """SQLAlchemy ORM model for the ``users`` table.

    Attributes:
        username:               Unique display name (3–50 chars, no spaces).
        email:                  Unique email address used for authentication.
        hashed_password:        bcrypt hash.  Plaintext is NEVER persisted.
        full_name:              Optional display name for reports.
        role:                   Platform role governing access control.
        is_active:              Soft-disable accounts without deletion.
        is_superuser:           Bypass all permission checks. Audited.
        last_login_at:          UTC timestamp of last successful authentication.
        failed_login_attempts:  Counter reset on successful login.
        locked_until:           If set and in the future, reject all logins.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("char_length(username) >= 3", name="ck_users_username_len"),
        CheckConstraint("failed_login_attempts >= 0", name="ck_users_attempts"),
    )

    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        doc="Unique username (3–50 characters).",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        doc="Unique email address. Used as login identifier.",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="bcrypt-hashed password. Never the plaintext.",
    )
    full_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        doc="Optional full display name used in reports.",
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda obj: [e.value for e in obj], name="user_role_enum"),
        nullable=False,
        default=UserRole.VIEWER,
        server_default=UserRole.VIEWER.value,
        index=True,
        doc="Platform role governing access control.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        index=True,
        doc="Whether this account is enabled. Use this for soft-disable.",
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        doc="Superuser flag. Bypasses all role-based checks. Audited.",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC timestamp of the last successful login.",
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        doc="Counter of consecutive failed login attempts. Reset on success.",
    )
    password_reset_token_hash: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        doc="SHA-256 hex digest of the active password reset token. None if no reset is pending.",
    )
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="UTC expiry of the password reset token. Token is invalid if this is in the past.",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="If set and in the future, all login attempts are rejected.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    sessions: Mapped[list[UserSession]] = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
        doc="Active and historical refresh token sessions.",
    )
    created_targets: Mapped[list[Target]] = relationship(
        "Target",
        foreign_keys="Target.created_by_id",
        back_populates="created_by",
        lazy="select",
    )
    created_scans: Mapped[list[Scan]] = relationship(
        "Scan",
        foreign_keys="Scan.created_by_id",
        back_populates="created_by",
        lazy="select",
    )
    assigned_scans: Mapped[list[Scan]] = relationship(
        "Scan",
        foreign_keys="Scan.assigned_to_id",
        back_populates="assigned_to",
        lazy="select",
    )
    generated_reports: Mapped[list[Report]] = relationship(
        "Report",
        foreign_keys="Report.generated_by_id",
        back_populates="generated_by",
        lazy="select",
    )
    verified_vulnerabilities: Mapped[list[Vulnerability]] = relationship(
        "Vulnerability",
        foreign_keys="Vulnerability.verified_by_id",
        back_populates="verified_by",
        lazy="select",
    )
    vulnerability_notes: Mapped[list[VulnerabilityNote]] = relationship(
        "VulnerabilityNote",
        back_populates="author",
        lazy="select",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        "AuditLog",
        back_populates="actor",
        lazy="select",
    )
    owned_workspaces: Mapped[list[Workspace]] = relationship(
        "Workspace",
        foreign_keys="Workspace.owner_id",
        back_populates="owner",
        lazy="select",
    )
    workspace_memberships: Mapped[list[WorkspaceMember]] = relationship(
        "WorkspaceMember",
        foreign_keys="WorkspaceMember.user_id",
        back_populates="user",
        lazy="select",
    )
    created_targets: Mapped[list[Target]] = relationship(
        "Target",
        foreign_keys="Target.created_by_id",
        back_populates="created_by",
        lazy="select",
    )
    scan_profiles: Mapped[list[ScanProfile]] = relationship(
        "ScanProfile",
        foreign_keys="ScanProfile.created_by_id",
        back_populates="created_by",
        lazy="select",
    )

    @property
    def is_locked(self) -> bool:
        """Return True if the account is currently locked out.

        Returns:
            bool: True if ``locked_until`` is set and is in the future.
        """
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until.replace(tzinfo=None)

    @property
    def display_name(self) -> str:
        """Return the best available name for display in UIs and reports.

        Returns:
            str: ``full_name`` if set, otherwise ``username``.
        """
        return self.full_name or self.username
