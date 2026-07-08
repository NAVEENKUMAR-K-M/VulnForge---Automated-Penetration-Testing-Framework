"""
Assetfinder plugin for VulnForge.
"""

from __future__ import annotations

import re

from app.core.plugin_base import BasePlugin
from app.models.asset import AssetType
from app.models.plugin import PluginPhase
from app.schemas.asset import AssetCreate
from app.schemas.plugin import ParsedResults, PluginExecutionResult, PluginManifest


class AssetfinderPlugin(BasePlugin):
    """Executes tomnomnom's assetfinder."""

    manifest = PluginManifest(
        name="assetfinder",
        display_name="Assetfinder Enum",
        description="Find domains and subdomains related to a given domain.",
        version="0.1.1",
        phase=PluginPhase.RECONNAISSANCE,
        default_config={
            "subs_only": True,    # Only show subdomains
        },
        plugin_metadata={
            "author": "tomnomnom",
            "homepage": "https://github.com/tomnomnom/assetfinder",
        }
    )

    async def check_dependencies(self) -> bool:
        """Check if assetfinder is installed and available in PATH."""
        # assetfinder doesn't have a -version flag that exits 0 cleanly without a domain
        # We can just test it by running it against a dummy domain or checking help
        result = await self._run_subprocess(["assetfinder", "-h"], timeout=5)
        # Even if help exits non-zero on some CLI tools, if we get output, it's there
        return "Usage:" in result.raw_output or result.success

    async def execute(self) -> PluginExecutionResult:
        """Run assetfinder against the target."""
        cmd = ["assetfinder"]
        
        if self.config.get("subs_only"):
            cmd.append("--subs-only")
            
        cmd.append(self.target)

        # Assetfinder is usually very fast
        return await self._run_subprocess(cmd, timeout=300)

    def parse_results(self, raw_output: str) -> ParsedResults:
        """Parse assetfinder text output into AssetCreate objects."""
        assets = []
        
        # Regex to loosely validate it looks like a domain name
        domain_pattern = re.compile(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")
        
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
                
            # assetfinder outputs one domain per line
            # We do a basic validation to ensure it doesn't ingest random garbage
            if domain_pattern.match(line):
                assets.append(AssetCreate(
                    asset_type=AssetType.DOMAIN,
                    value=line,
                    source_tool=self.manifest.name,
                ))
            else:
                self.logger.warning("Ignoring invalid domain from assetfinder", line=line)
                
        return ParsedResults(vulnerabilities=[], assets=assets)
