"""
DiscoveredAsset Pydantic schemas.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import Field, field_validator

from app.models.asset import AssetType
from app.schemas.common import TimestampedResponse, VulnForgeBaseModel


class AssetCreate(VulnForgeBaseModel):
    """Schema for a newly discovered asset reported by a plugin."""

    asset_type: AssetType
    value: str = Field(min_length=1, max_length=500)
    source_tool: str = Field(
        min_length=1, 
        max_length=100, 
        description="The machine name of the plugin that discovered this (e.g., 'subfinder')."
    )

    @field_validator("value")
    @classmethod
    def strip_value(cls, v: str) -> str:
        return v.strip().lower()


class AssetResponse(TimestampedResponse):
    """API response for a DiscoveredAsset record."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    target_id: uuid.UUID
    scan_id: uuid.UUID | None
    asset_type: AssetType
    value: str
    source_tools: list[str]
    is_active: bool
