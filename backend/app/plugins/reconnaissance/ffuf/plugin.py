"""
FFUF Directory Enumeration plugin for VulnForge.
"""

from __future__ import annotations

import json
import os
from typing import Any

from app.core.plugin_base import BasePlugin
from app.models.asset import AssetType
from app.models.plugin import PluginPhase
from app.schemas.asset import AssetCreate
from app.schemas.plugin import ParsedResults, PluginExecutionResult, PluginManifest


class FfufPlugin(BasePlugin):
    """Executes FFUF for fast web fuzzer and directory enumeration."""

    manifest = PluginManifest(
        name="ffuf",
        display_name="FFUF Directory Fuzzer",
        description="Fast web fuzzer written in Go for discovering hidden directories.",
        version="2.1.0",
        phase=PluginPhase.RECONNAISSANCE,
        default_config={
            "wordlist": "/usr/share/wordlists/dirb/common.txt",
            "threads": 40,
            "timeout": 10,
        },
        plugin_metadata={
            "author": "joohoi",
            "homepage": "https://github.com/ffuf/ffuf",
        }
    )

    async def check_dependencies(self) -> bool:
        """Check if ffuf is installed and available in PATH."""
        result = await self._run_subprocess(["ffuf", "-V"], timeout=10)
        return result.success

    async def execute(self) -> PluginExecutionResult:
        """Run ffuf against the target and output JSON."""
        wordlist = self.config.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
        
        # Determine the target URL
        target_url = self.target
        if not target_url.startswith("http"):
            # FFUF requires HTTP/HTTPS, default to HTTP if not provided
            target_url = f"http://{self.target}"
            
        # Ensure target ends with FUZZ or we append it
        if "FUZZ" not in target_url:
            if not target_url.endswith("/"):
                target_url += "/"
            target_url += "FUZZ"
            
        # Write to a temporary file since passing large JSON via stdout can sometimes be messy with ffuf
        # But we'll try stdout first using standard pipe if possible, or use a temp file
        # Actually ffuf supports stdout using `-o /dev/stdout` or just `-o stdout` in some versions,
        # but the safest way is a temporary file which we read afterwards.
        # To keep it simple and consistent with BaseModel, we use subprocess stdout capture: `-o stdout -of json`
        
        cmd = [
            "ffuf",
            "-u", target_url,
            "-w", wordlist,
            "-t", str(self.config.get("threads", 40)),
            "-timeout", str(self.config.get("timeout", 10)),
            "-o", "stdout",
            "-of", "json",
            "-s" # Silent mode so only the JSON is printed
        ]
        
        return await self._run_subprocess(cmd, timeout=1800)

    def parse_results(self, raw_output: str) -> ParsedResults:
        """Parse FFUF JSON output into AssetCreate objects."""
        assets = []
        
        if not raw_output.strip():
            return ParsedResults(vulnerabilities=[], assets=[])
            
        try:
            # FFUF outputs a single JSON object containing a "results" array
            data = json.loads(raw_output)
            results = data.get("results", [])
            
            for item in results:
                url = item.get("url")
                if not url:
                    continue
                    
                metadata: dict[str, Any] = {}
                
                status_code = item.get("status")
                if status_code is not None:
                    metadata["status_code"] = status_code
                    
                content_length = item.get("length")
                if content_length is not None:
                    metadata["content_length"] = content_length
                    
                words = item.get("words")
                if words is not None:
                    metadata["words"] = words
                    
                lines = item.get("lines")
                if lines is not None:
                    metadata["lines"] = lines
                    
                redirectlocation = item.get("redirectlocation")
                if redirectlocation:
                    metadata["redirect"] = redirectlocation
                
                content_type = item.get("content-type")
                if content_type:
                    metadata["content_type"] = content_type
                
                assets.append(AssetCreate(
                    asset_type=AssetType.URL,
                    value=url,
                    source_tool=self.manifest.name,
                    metadata=metadata
                ))
                
        except json.JSONDecodeError:
            self.logger.warning("Failed to parse JSON output from ffuf")
            
        return ParsedResults(vulnerabilities=[], assets=assets)
