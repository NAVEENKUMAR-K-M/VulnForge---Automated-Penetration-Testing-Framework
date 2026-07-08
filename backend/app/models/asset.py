"""
DiscoveredAsset ORM model.

Stores assets (subdomains, IPs, open ports) found during Reconnaissance scans.
Designed for heavy deduplication: if multiple tools (Subfinder, Amass) find the
same subdomain in the same workspace, they are merged into a single record 
with `source_tools` containing both names.
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase

if TYPE_CHECKING:
    from app.models.scan import Scan
    from app.models.target import Target
    from app.models.workspace import Workspace


class AssetType(str, enum.Enum):
    """Classification of the discovered asset."""

    DOMAIN = "domain"
    IP = "ip"
    PORT = "port"
    URL = "url"
    CLOUD_RESOURCE = "cloud_resource"
    OTHER = "other"


class DiscoveredAsset(TimestampedBase):
    """ORM model for the ``discovered_assets`` table.

    Attributes:
        workspace_id: FK to the workspace (for multitenancy isolation).
        target_id:    FK to the parent target this asset belongs to.
        scan_id:      FK to the scan that first discovered this asset.
        asset_type:   Classification (domain, IP, etc.).
        value:        The actual scannable value (e.g., 'api.example.com').
        source_tools: List of tools that discovered this (e.g., ['subfinder', 'amass']).
        is_active:    Soft-delete flag.
    """

    __tablename__ = "discovered_assets"
    __table_args__ = (
        # Ensure we don't have duplicate assets per workspace
        UniqueConstraint(
            "workspace_id", "value", "asset_type",
            name="uq_discovered_assets_workspace_value_type"
        ),
        Index("idx_discovered_assets_target_id", "target_id"),
        Index("idx_discovered_assets_scan_id", "scan_id"),
        Index(
            "idx_discovered_assets_active",
            "is_active",
            postgresql_where=text("is_active = TRUE"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE", name="fk_assets_workspaces"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="CASCADE", name="fk_assets_targets"),
        nullable=False,
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="SET NULL", name="fk_assets_scans"),
        nullable=True,
        doc="The scan that first discovered this asset.",
    )
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, name="asset_type_enum"),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )
    source_tools: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        doc="Array of plugin names that reported this asset.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        lazy="select",
    )
    target: Mapped[Target] = relationship(
        "Target",
        lazy="select",
    )
    scan: Mapped[Scan | None] = relationship(
        "Scan",
        lazy="select",
    )
