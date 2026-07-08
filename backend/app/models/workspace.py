"""
Workspace ORM models — engagement/project management layer.

A Workspace is a logical container that groups a security engagement:
    - Client information (name, contact)
    - Engagement dates (start, end)
    - Associated Scans and their findings
    - Member roster with per-workspace role assignments

Design Decisions:
    1. Soft-delete: Workspaces are never hard-deleted — they are archived.
       This preserves the historical audit trail of a pentest engagement.
    2. Membership table: ``workspace_members`` manages per-workspace roles
       independently of the platform-level ``users.role``.  An ANALYST on
       the platform is still a VIEWER in a workspace they were not explicitly
       invited to.
    3. Owner FK: ``owner_id`` is the designated primary contact and always
       has OWNER-level access within the workspace, regardless of the
       ``workspace_members`` table.
    4. Settings JSONB: Workspace-level defaults (e.g., allowed scan types,
       notification preferences) live in a flexible JSONB column to avoid
       premature schema ossification.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedBase, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.scan import Scan
    from app.models.scope import ScopeRule
    from app.models.scan_profile import ScanProfile
    from app.models.target import Target


# ── Enumerations ──────────────────────────────────────────────────────────────

class WorkspaceStatus(str, enum.Enum):
    """Lifecycle status of a workspace/engagement.

    Values:
        ACTIVE:    Engagement is ongoing — scans can be created and run.
        COMPLETED: Engagement concluded — read-only, can still generate reports.
        ARCHIVED:  Soft-deleted — hidden from default list views.
    """

    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class WorkspaceMemberRole(str, enum.Enum):
    """Per-workspace role governing access within that specific engagement.

    Values:
        OWNER:   Full control: edit workspace, manage members, delete.
        MEMBER:  Can create scans, triage vulnerabilities, generate reports.
        VIEWER:  Read-only: can view scans, findings, and reports.

    This is INDEPENDENT of the platform-level ``UserRole``.  A platform
    ANALYST who is a workspace VIEWER can only read within that workspace.
    """

    OWNER = "owner"
    MEMBER = "member"
    VIEWER = "viewer"


# ── Models ────────────────────────────────────────────────────────────────────

class Workspace(TimestampedBase):
    """ORM model for the ``workspaces`` table.

    Attributes:
        name:            Short, descriptive engagement name.
        description:     Extended description of scope and objectives.
        client_name:     Name of the organisation being assessed.
        client_contact:  Primary contact at the client organisation.
        status:          Lifecycle state (active, completed, archived).
        start_date:      Planned engagement start date.
        end_date:        Planned engagement end date.
        is_archived:     Quick boolean flag for archive filtering (denormalised).
        owner_id:        FK to the user who created and owns this workspace.
        settings:        JSONB bag of workspace-level configuration.
    """

    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_workspaces_dates",
        ),
        CheckConstraint(
            "char_length(trim(name)) > 0",
            name="ck_workspaces_name_nonempty",
        ),
        Index("idx_workspaces_owner_id", "owner_id"),
        Index("idx_workspaces_status", "status"),
        Index(
            "idx_workspaces_active",
            "status",
            postgresql_where=text("is_archived = FALSE"),
        ),
    )

    name: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        doc="Short, descriptive engagement name.",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Extended description of scope, objectives, and methodology.",
    )
    client_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        doc="Name of the organisation being assessed.",
    )
    client_contact: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        doc="Primary contact name or email at the client organisation.",
    )
    status: Mapped[WorkspaceStatus] = mapped_column(
        Enum(WorkspaceStatus, values_callable=lambda obj: [e.value for e in obj], name="workspace_status_enum"),
        nullable=False,
        default=WorkspaceStatus.ACTIVE,
        server_default=WorkspaceStatus.ACTIVE.value,
        doc="Lifecycle state of this workspace.",
    )
    start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Planned engagement start date (date only, no timezone).",
    )
    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Planned engagement end date (date only, no timezone).",
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        doc="Soft-delete flag. Archived workspaces are hidden from default views.",
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_workspaces_owner"),
        nullable=False,
        doc="FK to the creating user who owns this workspace.",
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        doc="JSONB bag of workspace-level configuration overrides.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    owner: Mapped[User] = relationship(
        "User",
        foreign_keys=[owner_id],
        back_populates="owned_workspaces",
        lazy="select",
    )
    members: Mapped[list[WorkspaceMember]] = relationship(
        "WorkspaceMember",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="select",
    )
    scans: Mapped[list[Scan]] = relationship(
        "Scan",
        back_populates="workspace",
        lazy="select",
    )
    scope_rules: Mapped[list[ScopeRule]] = relationship(
        "ScopeRule",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="select",
    )
    scan_profiles: Mapped[list[ScanProfile]] = relationship(
        "ScanProfile",
        foreign_keys="ScanProfile.workspace_id",
        back_populates="workspace",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def is_editable(self) -> bool:
        """Return True if new scans and edits are allowed.

        Returns:
            bool: True if status is ACTIVE and not archived.
        """
        return self.status == WorkspaceStatus.ACTIVE and not self.is_archived

    @property
    def is_overdue(self) -> bool:
        """Return True if the end date has passed and workspace is still active.

        Returns:
            bool: True if today is past end_date and status is ACTIVE.
        """
        if self.end_date is None:
            return False
        return date.today() > self.end_date and self.status == WorkspaceStatus.ACTIVE


class WorkspaceMember(UUIDPrimaryKeyMixin, Base):
    """ORM model for the ``workspace_members`` table.

    Tracks per-workspace role assignments for each user.

    Design:
        Does NOT use ``TimestampedBase`` — membership rows are immutable
        once created.  If a role changes, the old row is deleted and a new
        one inserted (preserves audit integrity via the separate audit_logs table).

    Attributes:
        workspace_id:   FK to the workspace.
        user_id:        FK to the member user.
        role:           Per-workspace access level.
        invited_by_id:  FK to the user who issued the invitation.
        joined_at:      UTC timestamp when membership was established.
    """

    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "user_id",
            name="uq_workspace_members_pair",
        ),
        Index("idx_wm_workspace_id", "workspace_id"),
        Index("idx_wm_user_id", "user_id"),
        Index("idx_wm_role", "role"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
            name="fk_wm_workspaces",
        ),
        nullable=False,
        doc="FK to the parent workspace.",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_wm_users"),
        nullable=False,
        doc="FK to the member user.",
    )
    role: Mapped[WorkspaceMemberRole] = mapped_column(
        Enum(WorkspaceMemberRole, values_callable=lambda obj: [e.value for e in obj], name="workspace_member_role_enum"),
        nullable=False,
        doc="Per-workspace access level for this member.",
    )
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_wm_invited_by"),
        nullable=True,
        doc="FK to the user who invited this member.",
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
        doc="UTC timestamp when this membership was created.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="members",
        lazy="select",
    )
    user: Mapped[User] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="workspace_memberships",
        lazy="select",
    )
    invited_by: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[invited_by_id],
        lazy="select",
    )


class WorkspaceTarget(TimestampedBase):
    """Junction table linking global targets to workspaces."""

    __tablename__ = "workspace_targets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "target_id", name="uq_workspace_targets_pair"),
        Index("idx_workspace_targets_workspace_id", "workspace_id"),
        Index("idx_workspace_targets_target_id", "target_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE", name="fk_workspace_targets_workspaces"),
        nullable=False,
        doc="The workspace this target is associated with.",
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="CASCADE", name="fk_workspace_targets_targets"),
        nullable=False,
        doc="The global target associated with the workspace.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    workspace: Mapped[Workspace] = relationship("Workspace")
    target: Mapped[Target] = relationship("Target")
