"""
Feroxbuster Directory Enumeration plugin for VulnForge.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.plugin_base import BasePlugin
from app.models.asset import AssetType
from app.models.plugin import PluginPhase
from app.schemas.asset import AssetCreate
from app.schemas.plugin import ParsedResults, PluginExecutionResult, PluginManifest


class FeroxbusterPlugin(BasePlugin):
    """Executes Feroxbuster for fast, simple, recursive content discovery."""

    manifest = PluginManifest(
        name="feroxbuster",
        display_name="Feroxbuster Directory Scanner",
        description="A fast, simple, recursive content discovery tool written in Rust.",
        version="2.10.2",
        phase=PluginPhase.RECONNAISSANCE,
        default_config={
            "wordlist": "/usr/share/wordlists/dirb/common.txt",
            "threads": 50,
            "depth": 2,
        },
        plugin_metadata={
            "author": "Epi",
            "homepage": "https://github.com/epi05/feroxbuster",
        }
    )

    async def check_dependencies(self) -> bool:
        """Check if feroxbuster is installed and available in PATH."""
        result = await self._run_subprocess(["feroxbuster", "--version"], timeout=10)
        return result.success

    async def execute(self) -> PluginExecutionResult:
        """Run feroxbuster against the target and output JSON."""
        wordlist = self.config.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        
        target_url = self.target
        if not target_url.startswith("http"):
            target_url = f"http://{self.target}"
            
        cmd = [
            "feroxbuster",
            "-u", target_url,
            "-w", wordlist,
            "-t", str(self.config.get("threads", 50)),
            "-d", str(self.config.get("depth", 2)),
            "--json",
            "--silent"
        ]
        
        return await self._run_subprocess(cmd, timeout=1800)

    def parse_results(self, raw_output: str) -> ParsedResults:
        """Parse Feroxbuster JSONL output into AssetCreate objects."""
        assets = []
        
        if not raw_output.strip():
            return ParsedResults(vulnerabilities=[], assets=[])
            
        for line in raw_output.splitlines():
            line = line.strip()
            if not line:
                continue
                
            try:
                # Feroxbuster --json outputs JSON Lines
                item = json.loads(line)
                
                # We only want to process endpoints/responses, not errors or other message types
                if item.get("type") != "response":
                    continue
                    
                url = item.get("url")
                if not url:
                    continue
                    
                metadata: dict[str, Any] = {}
                
                status_code = item.get("status")
                if status_code is not None:
                    metadata["status_code"] = status_code
                    
                content_length = item.get("content_length")
                if content_length is not None:
                    metadata["content_length"] = content_length
                    
                words = item.get("word_count")
                if words is not None:
                    metadata["words"] = words
                    
                lines = item.get("line_count")
                if lines is not None:
                    metadata["lines"] = lines
                    
                assets.append(AssetCreate(
                    asset_type=AssetType.URL,
                    value=url,
                    source_tool=self.manifest.name,
                    metadata=metadata
                ))
                
            except json.JSONDecodeError:
                self.logger.warning("Failed to parse JSON line from feroxbuster", line=line)
                
        return ParsedResults(vulnerabilities=[], assets=assets)
