"""
Plugin ORM model — the plugin registry.

Every plugin that VulnForge can execute must be registered here.
The registry is the authoritative source of truth for:
    - What plugins are available.
    - Which phase of the pentest they belong to.
    - Their default configuration schema.
    - Their Python module path for dynamic loading.

Plugins are seeded into the DB on application startup by the
``PluginRegistry.discover_and_sync()`` call in the app lifespan.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Enum, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase

if TYPE_CHECKING:
    from app.models.scan_plugin_execution import ScanPluginExecution


class PluginPhase(str, enum.Enum):
    """Penetration testing phase in which this plugin operates.

    Mirrors the PTES (Penetration Testing Execution Standard) methodology.
    """

    RECONNAISSANCE = "reconnaissance"
    VULNERABILITY_SCANNING = "vulnerability_scanning"
    EXPLOITATION = "exploitation"
    POST_EXPLOITATION = "post_exploitation"


class Plugin(TimestampedBase):
    """ORM model for the ``plugins`` table.

    Attributes:
        name:            Unique machine name (e.g., ``nmap_scanner``).
        display_name:    Human-readable name for the UI.
        description:     What this plugin does.
        version:         Semantic version string (e.g., ``1.0.0``).
        phase:           PTES phase this plugin belongs to.
        is_enabled:      Globally enable/disable without removing the plugin.
        is_builtin:      Distinguish bundled vs. third-party plugins.
        module_path:     Full Python import path to the plugin class.
        default_config:  JSONB schema of default plugin configuration.
        plugin_metadata: JSONB for arbitrary extra metadata (author, homepage).
    """

    __tablename__ = "plugins"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
        doc="Unique machine-readable identifier (e.g., 'nmap_scanner').",
    )
    display_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable name shown in the UI.",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Description of what this plugin does and what it outputs.",
    )
    version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Semantic version of the plugin (e.g., '1.2.3').",
    )
    phase: Mapped[PluginPhase] = mapped_column(
        Enum(PluginPhase, name="plugin_phase_enum"),
        nullable=False,
        index=True,
        doc="PTES phase: reconnaissance | vulnerability_scanning | exploitation | post_exploitation.",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        index=True,
        doc="Global enable/disable toggle. Disabled plugins are skipped during scan execution.",
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        doc="True for plugins bundled with VulnForge. False for third-party plugins.",
    )
    module_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Full Python import path to the plugin class "
            "(e.g., 'plugins.reconnaissance.nmap.plugin.NmapPlugin').",
    )
    default_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        doc="Default configuration schema. Individual scan executions can override this.",
    )
    plugin_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        doc="Arbitrary extra metadata: author, homepage, requirements, CVE coverage, etc.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    executions: Mapped[list[ScanPluginExecution]] = relationship(
        "ScanPluginExecution",
        back_populates="plugin",
        lazy="select",
    )
