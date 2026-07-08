"""
WhatWeb plugin for VulnForge.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.plugin_base import BasePlugin
from app.models.asset import AssetType
from app.models.plugin import PluginPhase
from app.schemas.asset import AssetCreate
from app.schemas.plugin import ParsedResults, PluginExecutionResult, PluginManifest
from app.utils.tech_mapper import categorize_technologies


class WhatWebPlugin(BasePlugin):
    """Executes WhatWeb for aggressive technology fingerprinting."""

    manifest = PluginManifest(
        name="whatweb",
        display_name="WhatWeb Scanner",
        description="Next generation web scanner that identifies what websites are running.",
        version="0.5.5",
        phase=PluginPhase.RECONNAISSANCE,
        default_config={
            "aggression": 3,  # -a 3 (Aggressive)
            "timeout": 10,
        },
        plugin_metadata={
            "author": "Andrew Horton (urbanadventurer)",
            "homepage": "https://github.com/urbanadventurer/WhatWeb",
        }
    )

    async def check_dependencies(self) -> bool:
        """Check if whatweb is installed and available in PATH."""
        result = await self._run_subprocess(["whatweb", "--version"], timeout=10)
        return result.success

    async def execute(self) -> PluginExecutionResult:
        """Run whatweb against the target and output JSON."""
        cmd = [
            "whatweb",
            f"-a {self.config.get('aggression', 3)}",
            "--log-json=-",      # Output JSON to stdout
            "--quiet",
            self.target,
        ]
        
        # Give it up to 15 minutes by default
        return await self._run_subprocess(cmd, timeout=900)

    def parse_results(self, raw_output: str) -> ParsedResults:
        """Parse WhatWeb JSON output into AssetCreate objects with structured metadata."""
        assets = []
        
        if not raw_output.strip():
            return ParsedResults(vulnerabilities=[], assets=[])
            
        try:
            # WhatWeb --log-json outputs an array of results
            results = json.loads(raw_output)
            
            for item in results:
                url = item.get("target")
                if not url:
                    continue
                    
                plugins = item.get("plugins", {})
                
                # Extract technology names from plugins
                tech_list = list(plugins.keys())
                metadata: dict[str, Any] = {}
                
                if tech_list:
                    metadata["technologies"] = tech_list
                    structured = categorize_technologies(tech_list)
                    if structured:
                        metadata["structured_tech"] = structured
                        
                # Extract HTTP status code and title if available
                http_status = plugins.get("HTTPServer", {}).get("status")
                if http_status:
                    # sometimes status is a list like [200]
                    if isinstance(http_status, list) and http_status:
                        metadata["status_code"] = int(http_status[0])
                    else:
                        try:
                            metadata["status_code"] = int(http_status)
                        except (ValueError, TypeError):
                            pass
                            
                title_plugin = plugins.get("Title", {})
                if title_plugin and "string" in title_plugin:
                    title_vals = title_plugin["string"]
                    if isinstance(title_vals, list) and title_vals:
                        metadata["title"] = title_vals[0]
                        
                # Only add if we actually found technologies or metadata
                if metadata:
                    assets.append(AssetCreate(
                        asset_type=AssetType.URL,
                        value=url,
                        source_tool=self.manifest.name,
                        metadata=metadata
                    ))
                    
        except json.JSONDecodeError:
            self.logger.warning("Failed to parse JSON from whatweb")
            
        return ParsedResults(vulnerabilities=[], assets=assets)
