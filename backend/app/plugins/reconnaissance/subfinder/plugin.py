"""
Subfinder plugin for VulnForge.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.plugin_base import BasePlugin
from app.models.asset import AssetType
from app.models.plugin import PluginPhase
from app.schemas.asset import AssetCreate
from app.schemas.plugin import ParsedResults, PluginExecutionResult, PluginManifest


class SubfinderPlugin(BasePlugin):
    """Executes ProjectDiscovery's subfinder tool."""

    manifest = PluginManifest(
        name="subfinder",
        display_name="Subfinder Subdomain Enum",
        description="Fast passive subdomain enumeration tool by ProjectDiscovery.",
        version="2.6.6",
        phase=PluginPhase.RECONNAISSANCE,
        default_config={
            "all": False,        # Use all sources
            "timeout": 30,       # Seconds to wait per source
            "max_enum_time": 10, # Minutes max enum time
        },
        plugin_metadata={
            "author": "ProjectDiscovery",
            "homepage": "https://github.com/projectdiscovery/subfinder",
        }
    )

    async def check_dependencies(self) -> bool:
        """Check if subfinder is installed and available in PATH."""
        result = await self._run_subprocess(["subfinder", "-version"], timeout=10)
        return result.success

    async def execute(self) -> PluginExecutionResult:
        """Run subfinder against the target and output JSON."""
        cmd = [
            "subfinder",
            "-d", self.target,
            "-json",             # JSONL output
            "-silent",           # No banner
            "-t", str(self.config.get("timeout", 30)),
            "-max-time", str(self.config.get("max_enum_time", 10)),
        ]
        if self.config.get("all"):
            cmd.append("-all")

        # Give it up to 15 minutes by default
        return await self._run_subprocess(cmd, timeout=900)

    def parse_results(self, raw_output: str) -> ParsedResults:
        """Parse subfinder JSONL output into AssetCreate objects."""
        assets = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                host = data.get("host")
                if host:
                    assets.append(AssetCreate(
                        asset_type=AssetType.DOMAIN,
                        value=host,
                        source_tool=self.manifest.name,
                    ))
            except json.JSONDecodeError:
                self.logger.warning("Failed to parse JSON line from subfinder", line=line)
                
        return ParsedResults(vulnerabilities=[], assets=assets)
