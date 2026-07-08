"""
Nmap Port Scanner plugin for VulnForge.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from app.core.plugin_base import BasePlugin
from app.models.asset import AssetType
from app.models.plugin import PluginPhase
from app.schemas.asset import AssetCreate
from app.schemas.plugin import ParsedResults, PluginExecutionResult, PluginManifest


class NmapPlugin(BasePlugin):
    """Executes Nmap for port scanning, service detection, and OS fingerprinting."""

    manifest = PluginManifest(
        name="nmap",
        display_name="Nmap Port Scanner",
        description="Network exploration tool and security / port scanner.",
        version="7.94",
        phase=PluginPhase.RECONNAISSANCE,
        default_config={
            "timing_template": 3,    # -T3
            "service_detection": True, # -sV
            "os_detection": True,      # -O
            "top_ports": 1000,         # --top-ports
        },
        plugin_metadata={
            "author": "Gordon Lyon (Fyodor)",
            "homepage": "https://nmap.org/",
        }
    )

    async def check_dependencies(self) -> bool:
        """Check if nmap is installed and available in PATH."""
        result = await self._run_subprocess(["nmap", "-V"], timeout=10)
        return result.success

    async def execute(self) -> PluginExecutionResult:
        """Run nmap against the target and output XML."""
        cmd = [
            "nmap",
            self.target,
            "-oX", "-",          # Output XML to stdout
            f"-T{self.config.get('timing_template', 3)}",
        ]
        
        if self.config.get("service_detection", True):
            cmd.append("-sV")
            
        if self.config.get("os_detection", True):
            cmd.append("-O")
            
        top_ports = self.config.get("top_ports")
        if top_ports:
            cmd.extend(["--top-ports", str(top_ports)])

        # Nmap scans can take a long time, give it up to 30 minutes
        return await self._run_subprocess(cmd, timeout=1800)

    def parse_results(self, raw_output: str) -> ParsedResults:
        """Parse Nmap XML output into AssetCreate objects."""
        assets = []
        
        if not raw_output.strip():
            return ParsedResults(vulnerabilities=[], assets=[])
            
        try:
            root = ET.fromstring(raw_output)
            
            for host in root.findall('host'):
                status = host.find('status')
                if status is not None and status.get('state') != 'up':
                    continue
                    
                # Get IP addresses
                ip_addr = None
                for address in host.findall('address'):
                    if address.get('addrtype') in ('ipv4', 'ipv6'):
                        ip_addr = address.get('addr')
                        break
                        
                if not ip_addr:
                    continue
                
                # Extract OS Detection
                os_metadata: dict[str, Any] = {}
                os_el = host.find('os')
                if os_el is not None:
                    osmatch = os_el.find('osmatch')
                    if osmatch is not None:
                        os_metadata["os_match"] = osmatch.get('name')
                        os_metadata["os_accuracy"] = osmatch.get('accuracy')
                        
                        osclass = osmatch.find('osclass')
                        if osclass is not None:
                            os_metadata["os_family"] = osclass.get('osfamily')
                            os_metadata["os_gen"] = osclass.get('osgen')
                            
                # Register IP as an asset
                assets.append(AssetCreate(
                    asset_type=AssetType.IP,
                    value=ip_addr,
                    source_tool=self.manifest.name,
                    metadata=os_metadata
                ))
                
                # Extract Ports & Services
                ports_el = host.find('ports')
                if ports_el is not None:
                    for port in ports_el.findall('port'):
                        state_el = port.find('state')
                        if state_el is None or state_el.get('state') != 'open':
                            continue
                            
                        port_id = port.get('portid')
                        protocol = port.get('protocol')
                        
                        port_metadata: dict[str, Any] = {
                            "state": state_el.get('state'),
                            "protocol": protocol,
                        }
                        
                        service_el = port.find('service')
                        if service_el is not None:
                            port_metadata["service"] = service_el.get('name')
                            port_metadata["product"] = service_el.get('product')
                            port_metadata["version"] = service_el.get('version')
                            port_metadata["extrainfo"] = service_el.get('extrainfo')
                            
                        # Clean up None values
                        port_metadata = {k: v for k, v in port_metadata.items() if v is not None}
                        
                        # Register Port as an asset (format: ip:port/protocol)
                        assets.append(AssetCreate(
                            asset_type=AssetType.PORT,
                            value=f"{ip_addr}:{port_id}/{protocol}",
                            source_tool=self.manifest.name,
                            metadata=port_metadata
                        ))
                        
        except ET.ParseError:
            self.logger.error("Failed to parse Nmap XML output")
            
        return ParsedResults(vulnerabilities=[], assets=assets)
