"""
Gowitness Screenshot Capture plugin for VulnForge.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from app.core.plugin_base import BasePlugin
from app.models.asset import AssetType
from app.models.plugin import PluginPhase
from app.schemas.asset import AssetCreate
from app.schemas.plugin import ParsedResults, PluginExecutionResult, PluginManifest


class GowitnessPlugin(BasePlugin):
    """Executes Gowitness to capture screenshots of live web interfaces."""

    manifest = PluginManifest(
        name="gowitness",
        display_name="Gowitness Screenshotter",
        description="A golang, web screenshot utility using Chrome Headless.",
        version="2.5.1",
        phase=PluginPhase.RECONNAISSANCE,
        default_config={
            "timeout": 15,
            "resolution": "1920,1080",
        },
        plugin_metadata={
            "author": "SensePost",
            "homepage": "https://github.com/sensepost/gowitness",
        }
    )

    async def check_dependencies(self) -> bool:
        """Check if gowitness is installed and available in PATH."""
        result = await self._run_subprocess(["gowitness", "version"], timeout=10)
        return result.success

    async def execute(self) -> PluginExecutionResult:
        """Run gowitness against the target."""
        target_url = self.target
        if not target_url.startswith("http"):
            target_url = f"http://{self.target}"
            
        # Define storage directory for screenshots
        storage_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../storage/screenshots"))
        os.makedirs(storage_dir, exist_ok=True)
        
        # Generate a unique filename for this screenshot
        filename = f"{uuid.uuid4().hex}.png"
        self._screenshot_path = os.path.join(storage_dir, filename)
        
        cmd = [
            "gowitness",
            "single",
            "--url", target_url,
            "--resolution", str(self.config.get("resolution", "1920,1080")),
            "--timeout", str(self.config.get("timeout", 15)),
            "--screenshot-path", storage_dir,
            "--screenshot-format", "png",
            # gowitness defaults to storing to gowitness.sqlite3, we just want the image
        ]
        
        # We don't have a direct way in older gowitness to specify the exact filename easily,
        # but modern versions support it, or we can just rename the file it generates.
        # Actually, `gowitness single` saves the file named after the URL in the target directory by default.
        # Let's just use the destination directory, and then parse the filesystem to find the new file,
        # or we can pass a destination file parameter if supported.
        # According to gowitness docs: `gowitness single --destination /path/to/file.png`
        cmd.extend(["--destination", self._screenshot_path])
        
        return await self._run_subprocess(cmd, timeout=300)

    def parse_results(self, raw_output: str) -> ParsedResults:
        """Parse Gowitness outcome. Since it doesn't output JSON, we just check if the file exists."""
        assets = []
        
        # Check if the screenshot was actually created
        if hasattr(self, '_screenshot_path') and os.path.exists(self._screenshot_path):
            
            target_url = self.target
            if not target_url.startswith("http"):
                target_url = f"http://{self.target}"
                
            metadata = {
                "screenshot_path": self._screenshot_path
            }
            
            assets.append(AssetCreate(
                asset_type=AssetType.URL,
                value=target_url,
                source_tool=self.manifest.name,
                metadata=metadata
            ))
        else:
            self.logger.warning(f"Gowitness failed to generate screenshot at {getattr(self, '_screenshot_path', 'unknown')}")
            
        return ParsedResults(vulnerabilities=[], assets=assets)
