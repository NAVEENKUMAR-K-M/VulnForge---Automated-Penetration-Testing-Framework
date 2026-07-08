"""
ScanProfile and ScanProfilePlugin ORM models.

Architecture:
    A ScanProfile is a reusable, named configuration template that defines:
        1. Which plugins to run (via ScanProfilePlugin join records)
        2. Per-plugin configuration overrides (stored on the join record)
        3. Scan-level defaults (scan_type, priority, timeout)

    When a Scan is created, the operator selects a profile.  The scan engine
    reads the profile's plugin list and per-plugin configs, merging them with
    any scan-level overrides the user provides.

    Profile ownership model:
        BUILTIN  profiles → shipped with VulnForge, read-only for all users.
                            Operators can CLONE them to create customised versions.
        CUSTOM   profiles → created by users, owned by a workspace or globally
                            (workspace_id = NULL means platform-wide profile).

    The five builtin profiles:
        quick_recon          → Passive recon only: DNS, WHOIS, port discovery
        external_assessment  → Full external attack surface: recon + vuln scan
        infrastructure       → Network-focused: CIDR, port scan, CVE detection
        web_assessment       → Web-focused: spidering, OWASP checks, headers
        custom               → Empty template, user configures from scratch

Design Decisions:
    - ScanProfilePlugin stores ``config_override`` as JSONB — it is merged
      with Plugin.default_config at scan dispatch time.
    - ``is_builtin`` profiles cannot be edited or deleted (enforced in service).
    - Cloning copies all ScanProfilePlugin rows with their overrides.
    - Profile → Plugin relationship uses an explicit join model (not a
      secondary table) so we can store per-profile per-plugin config.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase
from app.models.scan import Priority, ScanType

if TYPE_CHECKING:
    from app.models.plugin import Plugin
    from app.models.user import User
    from app.models.workspace import Workspace


# ── Enumerations ──────────────────────────────────────────────────────────────

class ProfileType(str, enum.Enum):
    """Classification of a scan profile.

    Values:
        QUICK_RECON:          Fast passive intelligence gathering.
                              Plugins: DNS enum, WHOIS, Shodan, port discovery.
                              Duration: ~5 minutes.
        EXTERNAL_ASSESSMENT:  Comprehensive external perimeter assessment.
                              Plugins: full recon + vulnerability scanning.
                              Duration: ~2 hours.
        INFRASTRUCTURE:       Network-focused deep assessment.
                              Plugins: CIDR sweep, Nmap, CVE detection, SSL audit.
                              Duration: ~4 hours.
        WEB_ASSESSMENT:       Web application-focused assessment.
                              Plugins: Nikto, Nuclei web templates, header checks,
                              directory bruteforce.
                              Duration: ~2 hours.
        CUSTOM:               User-defined. No default plugins. Full control.
    """

    QUICK_RECON = "quick_recon"
    EXTERNAL_ASSESSMENT = "external_assessment"
    INFRASTRUCTURE = "infrastructure"
    WEB_ASSESSMENT = "web_assessment"
    CUSTOM = "custom"


# ── ScanProfile ───────────────────────────────────────────────────────────────

class ScanProfile(TimestampedBase):
    """ORM model for the ``scan_profiles`` table.

    A ScanProfile is the central template entity.  Every scan created in
    VulnForge references a profile (optional — scans can use ad-hoc config).

    Attributes:
        name:            Unique, human-readable profile name.
        profile_type:    Built-in type classification or CUSTOM.
        description:     What this profile is designed to assess.
        is_builtin:      True for system-shipped profiles (read-only).
        is_active:       Soft-disable. Inactive profiles cannot be used for scans.
        workspace_id:    NULL → platform-wide; non-NULL → workspace-scoped.
        created_by_id:   NULL for builtin profiles; user UUID for custom ones.
        default_scan_type: The scan_type set on scans created from this profile.
        default_priority:  Queue priority for scans from this profile.
        timeout_minutes:   Per-scan timeout override (NULL = system default).
        tags:            Searchable labels (stored in JSONB for flexibility).
        cloned_from_id:  UUID of the profile this was cloned from (if any).
    """

    __tablename__ = "scan_profiles"
    __table_args__ = (
        CheckConstraint(
            "char_length(trim(name)) > 0",
            name="ck_scan_profiles_name_nonempty",
        ),
        CheckConstraint(
            "timeout_minutes IS NULL OR timeout_minutes > 0",
            name="ck_scan_profiles_timeout_positive",
        ),
        # Unique name per workspace (NULL workspace = platform-wide)
        # This requires a partial index because NULL != NULL in SQL
        Index(
            "idx_scan_profiles_workspace_id",
            "workspace_id",
        ),
        Index(
            "idx_scan_profiles_type",
            "profile_type",
        ),
        Index(
            "idx_scan_profiles_builtin",
            "is_builtin",
            postgresql_where=text("is_builtin = TRUE"),
        ),
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable profile name (e.g., 'Q1 External Assessment').",
    )
    profile_type: Mapped[ProfileType] = mapped_column(
        Enum(ProfileType, name="profile_type_enum"),
        nullable=False,
        doc="Classification of this profile.",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Description of what this profile assesses and which tools it uses.",
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
        doc="System-shipped profile. Cannot be edited or deleted.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        doc="Inactive profiles cannot be used for new scans.",
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
            name="fk_scan_profiles_workspace",
        ),
        nullable=True,
        index=True,
        doc="Workspace scope. NULL means this profile is available platform-wide.",
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="fk_scan_profiles_created_by",
        ),
        nullable=True,
        index=True,
        doc="Creator. NULL for builtin profiles.",
    )
    default_scan_type: Mapped[ScanType] = mapped_column(
        Enum(ScanType, name="scan_type_enum"),
        nullable=False,
        default=ScanType.FULL,
        server_default=ScanType.FULL.value,
        doc="The scan_type applied to scans created from this profile.",
    )
    default_priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority_enum"),
        nullable=False,
        default=Priority.MEDIUM,
        server_default=Priority.MEDIUM.value,
        doc="Default queue priority for scans created from this profile.",
    )
    timeout_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Per-scan timeout in minutes. NULL inherits the system default.",
    )
    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        doc="Searchable labels (e.g., ['external', 'web', 'quarterly']).",
    )
    cloned_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "scan_profiles.id",
            ondelete="SET NULL",
            name="fk_scan_profiles_cloned_from",
        ),
        nullable=True,
        doc="UUID of the profile this was cloned from. NULL for originals.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    workspace: Mapped[Workspace | None] = relationship(
        "Workspace",
        foreign_keys=[workspace_id],
        back_populates="scan_profiles",
        lazy="select",
    )
    created_by: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[created_by_id],
        back_populates="scan_profiles",
        lazy="select",
    )
    profile_plugins: Mapped[list[ScanProfilePlugin]] = relationship(
        "ScanProfilePlugin",
        back_populates="profile",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="ScanProfilePlugin.execution_order",
    )
    cloned_from: Mapped[ScanProfile | None] = relationship(
        "ScanProfile",
        foreign_keys=[cloned_from_id],
        remote_side="ScanProfile.id",
        lazy="select",
    )

    @property
    def plugin_count(self) -> int:
        """Return the number of enabled plugins in this profile."""
        return sum(1 for pp in self.profile_plugins if pp.is_enabled)


# ── ScanProfilePlugin ─────────────────────────────────────────────────────────

class ScanProfilePlugin(TimestampedBase):
    """Join table between ScanProfile and Plugin with per-profile plugin config.

    This is an explicit join model (not a plain association table) because it
    carries additional data:
        - ``is_enabled``:      Per-profile enable/disable toggle.
        - ``config_override``: JSON overrides merged with Plugin.default_config.
        - ``execution_order``: The order this plugin runs within the profile.

    At scan dispatch, the engine resolves configuration as:
        final_config = {**plugin.default_config, **profile_plugin.config_override}

    Attributes:
        profile_id:      FK to the parent ScanProfile.
        plugin_id:       FK to the Plugin being configured.
        is_enabled:      Whether this plugin runs when the profile is used.
        execution_order: Ascending integer for explicit execution sequencing.
        config_override: JSONB overrides applied to Plugin.default_config.
    """

    __tablename__ = "scan_profile_plugins"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "plugin_id",
            name="uq_scan_profile_plugins_pair",
        ),
        CheckConstraint(
            "execution_order >= 0",
            name="ck_scan_profile_plugins_order_nonneg",
        ),
        Index("idx_spp_profile_id", "profile_id"),
        Index("idx_spp_plugin_id", "plugin_id"),
        Index(
            "idx_spp_enabled",
            "profile_id",
            "is_enabled",
            postgresql_where=text("is_enabled = TRUE"),
        ),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "scan_profiles.id",
            ondelete="CASCADE",
            name="fk_spp_scan_profiles",
        ),
        nullable=False,
        doc="FK to the parent scan profile.",
    )
    plugin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "plugins.id",
            ondelete="CASCADE",
            name="fk_spp_plugins",
        ),
        nullable=False,
        doc="FK to the plugin being configured.",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        doc="Whether this plugin runs when the profile is used for a scan.",
    )
    execution_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        doc="Ascending order for explicit plugin sequencing within the profile.",
    )
    config_override: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        doc=(
            "Per-profile configuration overrides for this plugin. "
            "Merged with Plugin.default_config at scan dispatch: "
            "{**plugin.default_config, **config_override}."
        ),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    profile: Mapped[ScanProfile] = relationship(
        "ScanProfile",
        back_populates="profile_plugins",
        lazy="select",
    )
    plugin: Mapped[Plugin] = relationship(
        "Plugin",
        foreign_keys=[plugin_id],
        lazy="select",
    )
