"""
Plugin Pydantic schemas — structures for plugin metadata, execution results, and configs.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import Field

from app.models.plugin import PluginPhase
from app.schemas.common import TimestampedResponse, VulnForgeBaseModel


class PluginManifest(VulnForgeBaseModel):
    """Declarative metadata attached to every plugin class.
    
    Used by the PluginLoader and PluginRegistry to synchronize the database
    with the on-disk plugin implementations.
    """
    name: str = Field(
        min_length=1, 
        max_length=100, 
        description="Unique machine name (e.g., 'nmap_scanner')."
    )
    display_name: str = Field(
        min_length=1, 
        max_length=200, 
        description="Human-readable name."
    )
    description: str = Field(description="Detailed description of what the plugin does.")
    version: str = Field(description="Semantic version (e.g., '1.0.0').")
    phase: PluginPhase = Field(description="PTES phase this plugin belongs to.")
    default_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Default configuration schema (JSON-serializable)."
    )
    plugin_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary extra metadata (author, homepage, requirements)."
    )


class PluginExecutionResult(VulnForgeBaseModel):
    """The normalized outcome of a plugin execution.
    
    Returned by `BasePlugin.execute()`. 
    """
    success: bool = Field(description="True if the plugin executed without crashing.")
    raw_output: str = Field(description="Raw stdout/stderr or tool output.")
    error_message: str | None = Field(default=None, description="Error reason if success=False.")
    # We leave findings/vulnerabilities to be parsed out of raw_output by `parse_results` 
    # to maintain separation of execution vs parsing.


class PluginResponse(TimestampedResponse):
    """API response for a Plugin record."""
    name: str
    display_name: str
    description: str | None
    version: str
    phase: PluginPhase
    is_enabled: bool
    is_builtin: bool
    module_path: str
    default_config: dict[str, Any]
    plugin_metadata: dict[str, Any]


class ParsedResults(VulnForgeBaseModel):
    """The final parsed output from a plugin execution."""
    
    vulnerabilities: list[Any] = Field(default_factory=list, description="List of VulnerabilityCreate objects.")
    assets: list[Any] = Field(default_factory=list, description="List of AssetCreate objects.")

