"""
ScanProfile Pydantic schemas — request/response contracts.

Schemas:
    ProfilePluginConfig      → Per-plugin config within a profile (create/update)
    ScanProfileCreate        → Create profile (POST body)
    ScanProfileUpdate        → Partial update (PATCH body)
    ScanProfileClone         → Clone a profile
    PluginToggle             → Enable/disable a single plugin in a profile
    ScanProfilePluginUpdate  → Update plugin config override
    ScanProfilePluginResponse→ Full plugin entry in profile
    ScanProfileResponse      → Full profile response
    ScanProfileSummary       → Lightweight list-view
    BuiltinProfileSeed       → Internal: seeds builtin profiles on startup
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.models.scan import Priority, ScanType
from app.models.scan_profile import ProfileType
from app.schemas.common import TimestampedResponse, VulnForgeBaseModel
from app.utils.target_validators import validate_tag


# ── Plugin Config Sub-Schema ───────────────────────────────────────────────────

class ProfilePluginConfig(VulnForgeBaseModel):
    """Configuration for a single plugin within a profile."""

    plugin_id: uuid.UUID = Field(description="Plugin UUID.")
    is_enabled: bool = Field(
        default=True,
        description="Whether this plugin runs when the profile is used.",
    )
    execution_order: int = Field(
        default=0,
        ge=0,
        description="Execution order within the profile (ascending).",
    )
    config_override: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "JSON overrides merged with Plugin.default_config at scan dispatch. "
            "Keys must match the plugin's declared config schema."
        ),
    )


# ── Request Schemas ────────────────────────────────────────────────────────────

class ScanProfileCreate(VulnForgeBaseModel):
    """Payload for creating a new scan profile."""

    name: str = Field(
        min_length=1,
        max_length=200,
        description="Unique human-readable profile name.",
        examples=["Q2 Web Assessment", "Client XYZ Infrastructure"],
    )
    profile_type: ProfileType = Field(
        description=(
            "Profile classification:\n"
            "- **quick_recon**: Fast passive recon (~5 min)\n"
            "- **external_assessment**: Full external perimeter (~2 hr)\n"
            "- **infrastructure**: Network deep-dive (~4 hr)\n"
            "- **web_assessment**: Web app focused (~2 hr)\n"
            "- **custom**: User-defined, no default plugins"
        ),
        examples=["custom", "web_assessment"],
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Description of what this profile assesses.",
    )
    workspace_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Scope to a specific workspace. "
            "NULL = platform-wide profile (visible to all workspaces)."
        ),
    )
    default_scan_type: ScanType = Field(
        default=ScanType.FULL,
        description="Scan type applied to scans created from this profile.",
    )
    default_priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Default queue priority.",
    )
    timeout_minutes: int | None = Field(
        default=None,
        ge=1,
        le=1440,  # max 24 hours
        description="Per-scan timeout in minutes (1–1440). NULL = system default.",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Searchable labels (max 10).",
        examples=[["external", "quarterly", "web"]],
    )
    plugins: list[ProfilePluginConfig] = Field(
        default_factory=list,
        max_length=50,
        description=(
            "Initial plugin set. Each entry references a Plugin UUID. "
            "For builtin profile types, the default plugin set is applied "
            "automatically if this list is empty."
        ),
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: list) -> list[str]:
        seen: set[str] = set()
        result = []
        for raw in v:
            tag = validate_tag(str(raw))
            if tag not in seen:
                seen.add(tag)
                result.append(tag)
        return result


class ScanProfileUpdate(VulnForgeBaseModel):
    """Partial update payload for a scan profile.

    Builtin profiles cannot be updated (enforced by service).
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Updated profile name.",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
    )
    default_scan_type: ScanType | None = Field(default=None)
    default_priority: Priority | None = Field(default=None)
    timeout_minutes: int | None = Field(
        default=None, ge=1, le=1440,
        description="Set to 0 to clear (revert to system default).",
    )
    tags: list[str] | None = Field(
        default=None, max_length=10,
    )
    is_active: bool | None = Field(
        default=None,
        description="Enable or disable the profile.",
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        return v.strip() if v else v

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: list | None) -> list[str] | None:
        if v is None:
            return None
        seen: set[str] = set()
        result = []
        for raw in v:
            tag = validate_tag(str(raw))
            if tag not in seen:
                seen.add(tag)
                result.append(tag)
        return result


class ScanProfileClone(VulnForgeBaseModel):
    """Clone an existing profile (builtin or custom) into a new custom profile."""

    name: str = Field(
        min_length=1,
        max_length=200,
        description="Name for the new cloned profile.",
        examples=["Web Assessment — Client XYZ"],
    )
    workspace_id: uuid.UUID | None = Field(
        default=None,
        description="Workspace for the cloned profile. NULL = platform-wide.",
    )
    description: str | None = Field(
        default=None,
        max_length=1000,
        description="Override description for the clone.",
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class PluginToggle(VulnForgeBaseModel):
    """Enable or disable a single plugin in a profile."""

    is_enabled: bool = Field(description="True to enable, False to disable.")


class ScanProfilePluginUpdate(VulnForgeBaseModel):
    """Update a plugin entry in a profile."""

    is_enabled: bool | None = Field(default=None)
    execution_order: int | None = Field(default=None, ge=0)
    config_override: dict[str, Any] | None = Field(
        default=None,
        description="Replace config_override entirely with this value.",
    )


class ProfilePluginAdd(VulnForgeBaseModel):
    """Add a plugin to a profile."""

    plugin_id: uuid.UUID = Field(description="Plugin UUID to add.")
    is_enabled: bool = Field(default=True)
    execution_order: int = Field(default=0, ge=0)
    config_override: dict[str, Any] = Field(default_factory=dict)


# ── Response Schemas ───────────────────────────────────────────────────────────

class ScanProfilePluginResponse(VulnForgeBaseModel):
    """Plugin entry within a scan profile response."""

    id: uuid.UUID = Field(description="ScanProfilePlugin record UUID.")
    profile_id: uuid.UUID
    plugin_id: uuid.UUID
    is_enabled: bool
    execution_order: int
    config_override: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    # Flattened plugin info for UI convenience
    plugin_name: str = Field(description="Plugin machine name.")
    plugin_display_name: str = Field(description="Plugin human-readable name.")
    plugin_phase: str = Field(description="PTES phase.")
    plugin_version: str = Field(description="Plugin version.")
    plugin_is_enabled: bool = Field(description="Global plugin enable state.")


class ScanProfileResponse(TimestampedResponse):
    """Full scan profile representation."""

    name: str
    profile_type: ProfileType
    description: str | None
    is_builtin: bool
    is_active: bool
    workspace_id: uuid.UUID | None
    created_by_id: uuid.UUID | None
    default_scan_type: ScanType
    default_priority: Priority
    timeout_minutes: int | None
    tags: list[str]
    cloned_from_id: uuid.UUID | None
    plugin_count: int = Field(description="Number of enabled plugins.")
    total_plugin_entries: int = Field(description="Total plugin entries (incl. disabled).")
    plugins: list[ScanProfilePluginResponse] = Field(default_factory=list)


class ScanProfileSummary(VulnForgeBaseModel):
    """Lightweight profile representation for list views."""

    id: uuid.UUID
    name: str
    profile_type: ProfileType
    description: str | None
    is_builtin: bool
    is_active: bool
    workspace_id: uuid.UUID | None
    created_by_id: uuid.UUID | None
    default_scan_type: ScanType
    default_priority: Priority
    timeout_minutes: int | None
    tags: list[str]
    cloned_from_id: uuid.UUID | None
    plugin_count: int
    created_at: datetime
    updated_at: datetime
