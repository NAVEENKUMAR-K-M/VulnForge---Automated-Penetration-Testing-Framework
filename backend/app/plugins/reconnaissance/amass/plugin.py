"""
Amass plugin for VulnForge.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import asyncio

from app.core.plugin_base import BasePlugin
from app.models.asset import AssetType
from app.models.plugin import PluginPhase
from app.schemas.asset import AssetCreate
from app.schemas.plugin import ParsedResults, PluginExecutionResult, PluginManifest


class AmassPlugin(BasePlugin):
    """Executes OWASP Amass."""

    manifest = PluginManifest(
        name="amass",
        display_name="OWASP Amass Enum",
        description="In-depth Attack Surface Mapping and Asset Discovery.",
        version="4.2.0",
        phase=PluginPhase.RECONNAISSANCE,
        default_config={
            "passive": True,    # Default to passive mode to avoid multi-hour scans
            "timeout": 30,      # Minutes
        },
        plugin_metadata={
            "author": "OWASP",
            "homepage": "https://github.com/owasp-amass/amass",
        }
    )

    async def check_dependencies(self) -> bool:
        """Check if amass is installed and available in PATH."""
        result = await self._run_subprocess(["amass", "-version"], timeout=10)
        return result.success

    async def execute(self) -> PluginExecutionResult:
        """Run amass against the target."""
        # amass can be messy with stdout, so we write to a temporary JSON file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp_file:
            tmp_path = tmp_file.name

        cmd = [
            "amass", "enum",
            "-d", self.target,
            "-json", tmp_path,
            "-timeout", str(self.config.get("timeout", 30)),
        ]
        
        if self.config.get("passive"):
            cmd.append("-passive")

        # Give it up to max config timeout + 5 minutes grace
        timeout_seconds = (self.config.get("timeout", 30) + 5) * 60
        result = await self._run_subprocess(cmd, timeout=timeout_seconds)

        # Instead of returning raw stdout from Amass (which is often just progress logs),
        # we read the JSON output file and place it in the raw_output for parsing.
        try:
            with open(tmp_path, "r", encoding="utf-8") as f:
                json_data = f.read()
            result.raw_output = json_data
        except Exception as e:
            self.logger.error("Failed to read amass JSON output file", error=str(e))
            result.success = False
            result.error_message = f"Failed to read output: {e}"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return result

    def parse_results(self, raw_output: str) -> ParsedResults:
        """Parse Amass JSON output into AssetCreate objects.
        
        Amass JSON structure usually contains a "name" field for the discovered asset.
        """
        assets = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                name = data.get("name")
                if name:
                    assets.append(AssetCreate(
                        asset_type=AssetType.DOMAIN,
                        value=name,
                        source_tool=self.manifest.name,
                    ))
            except json.JSONDecodeError:
                self.logger.warning("Failed to parse JSON line from amass", line=line)
                
        return ParsedResults(vulnerabilities=[], assets=assets)
