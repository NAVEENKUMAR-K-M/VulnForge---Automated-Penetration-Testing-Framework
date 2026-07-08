"""
HTTPX Enumeration plugin for VulnForge.
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


class HttpxPlugin(BasePlugin):
    """Executes ProjectDiscovery's httpx tool."""

    manifest = PluginManifest(
        name="httpx",
        display_name="HTTPX Enumeration",
        description="Fast and multi-purpose HTTP toolkit for probing web servers.",
        version="1.6.8",
        phase=PluginPhase.RECONNAISSANCE,
        default_config={
            "timeout": 10,
            "threads": 50,
            "follow_redirects": True,
        },
        plugin_metadata={
            "author": "ProjectDiscovery",
            "homepage": "https://github.com/projectdiscovery/httpx",
        }
    )

    async def check_dependencies(self) -> bool:
        """Check if httpx is installed and available in PATH."""
        result = await self._run_subprocess(["httpx", "-version"], timeout=10)
        return result.success

    async def execute(self) -> PluginExecutionResult:
        """Run httpx against the target and output JSON."""
        cmd = [
            "httpx",
            "-u", self.target,
            "-json",             # JSONL output
            "-silent",           # No banner
            "-sc",               # Status code
            "-location",         # Redirect location
            "-title",            # Page title
            "-td",               # Tech detect
            "-time",             # Response time
            "-t", str(self.config.get("threads", 50)),
            "-timeout", str(self.config.get("timeout", 10)),
        ]
        
        if self.config.get("follow_redirects", True):
            cmd.append("-fr")

        # Give it up to 15 minutes by default
        return await self._run_subprocess(cmd, timeout=900)

    def parse_results(self, raw_output: str) -> ParsedResults:
        """Parse httpx JSONL output into AssetCreate objects with metadata."""
        assets = []
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                
                # The primary URL (with scheme, host, port)
                url = data.get("url")
                if not url:
                    continue
                    
                # Collect all requested metadata
                metadata: dict[str, Any] = {}
                
                status_code = data.get("status_code")
                if status_code is not None:
                    metadata["status_code"] = status_code
                    
                location = data.get("location")
                if location:
                    metadata["redirect"] = location
                    
                # Determine HTTPS
                scheme = data.get("scheme", "")
                metadata["https"] = scheme.lower() == "https"
                
                # Response time
                response_time = data.get("time")
                if response_time:
                    metadata["response_time"] = response_time
                    
                # Title
                title = data.get("title")
                if title:
                    metadata["title"] = title
                    
                # Technologies
                tech = data.get("tech")
                if tech and isinstance(tech, list):
                    metadata["technologies"] = tech
                    structured = categorize_technologies(tech)
                    if structured:
                        metadata["structured_tech"] = structured
                
                assets.append(AssetCreate(
                    asset_type=AssetType.URL,
                    value=url,
                    source_tool=self.manifest.name,
                    metadata=metadata
                ))
            except json.JSONDecodeError:
                self.logger.warning("Failed to parse JSON line from httpx", line=line)
                
        return ParsedResults(vulnerabilities=[], assets=assets)
