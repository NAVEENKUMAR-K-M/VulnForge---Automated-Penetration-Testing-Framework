"""
Dummy Ping Plugin.

Used as a proof-of-concept for the plugin architecture.
Demonstrates how to define a manifest, execute a subprocess, and parse results.
"""

from __future__ import annotations

import re

from app.core.plugin_base import BasePlugin
from app.models.plugin import PluginPhase
from app.schemas.plugin import PluginExecutionResult, PluginManifest
from app.schemas.vulnerability import Severity, VulnerabilityCreate


class PingPlugin(BasePlugin):
    """A simple plugin that runs ICMP ping against a target."""

    manifest = PluginManifest(
        name="ping_scanner",
        display_name="ICMP Ping Scanner",
        description="Checks if a host is alive using ICMP echo requests.",
        version="1.0.0",
        phase=PluginPhase.RECONNAISSANCE,
        default_config={
            "count": 4,      # Number of packets to send
            "timeout": 2,    # Timeout per packet
        },
        plugin_metadata={
            "author": "VulnForge Team",
            "requires_root": False,
        }
    )

    async def check_dependencies(self) -> bool:
        """Check if the `ping` command is available."""
        # A simple check: run ping -c 1 127.0.0.1 (or ping -n 1 on Windows)
        import sys
        cmd = ["ping", "-n", "1", "127.0.0.1"] if sys.platform == "win32" else ["ping", "-c", "1", "127.0.0.1"]
        result = await self._run_subprocess(cmd, timeout=5)
        return result.success

    async def execute(self) -> PluginExecutionResult:
        """Execute the ping command against the target."""
        count = self.config.get("count", 4)
        
        import sys
        if sys.platform == "win32":
            cmd = ["ping", "-n", str(count), self.target]
        else:
            cmd = ["ping", "-c", str(count), self.target]

        # Use the base class subprocess helper
        return await self._run_subprocess(cmd, timeout=30)

    def parse_results(self, raw_output: str) -> list[VulnerabilityCreate]:
        """Parse ping output to determine if host is alive.
        
        Note: Being "alive" isn't really a vulnerability, but we map it to an 
        informational finding for demonstration purposes.
        """
        findings = []

        # Very naive parsing: look for "ttl=" in the output to confirm it replied
        if "ttl=" in raw_output.lower():
            # Extract round-trip time if possible (naive regex)
            # e.g., time=15.2 ms or time=15ms
            match = re.search(r"time[=<](\d+(?:\.\d+)?)", raw_output.lower())
            latency = match.group(1) if match else "unknown"

            finding = VulnerabilityCreate(
                title=f"Host is Alive (ICMP): {self.target}",
                severity=Severity.INFORMATIONAL,
                description=f"The host {self.target} responded to ICMP echo requests.\n\nLatency: {latency}ms",
                remediation="No remediation required. This is an informational finding.",
                cvss_score=0.0,
                cve_id=None,
                proof=raw_output,
            )
            findings.append(finding)

        return findings
