"""
Base plugin class defining the contract for all VulnForge scanning plugins.

Architecture:
    Every plugin (e.g., Nmap, Nuclei, Nikto) must inherit from BasePlugin.
    The scan engine instantiates the plugin, calls `check_dependencies()`, 
    then `execute()`, and finally `parse_results()`.

    This enforces a strict separation of concerns:
    - Subprocess execution/API calls (execute)
    - Output translation (parse_results)
"""

from __future__ import annotations

import abc
import asyncio
from typing import Any

from app.core.logging import get_logger
from app.schemas.plugin import PluginExecutionResult, PluginManifest
from app.schemas.vulnerability import VulnerabilityCreate

logger = get_logger(__name__)


class BasePlugin(abc.ABC):
    """Abstract base class for all VulnForge plugins.

    Attributes:
        manifest (PluginManifest): Declarative metadata about the plugin.
                                   Must be defined by the subclass.
    """

    # Subclasses MUST override this with a valid PluginManifest instance.
    manifest: PluginManifest

    def __init__(self, config: dict[str, Any], target: str) -> None:
        """Initialize the plugin for a specific execution.

        Args:
            config: The resolved configuration (Plugin.default_config merged with 
                    ScanProfilePlugin.config_override and Scan.configuration).
            target: The target value (IP, domain, CIDR, URL) to assess.
        """
        self.config = config
        self.target = target
        self.logger = logger.bind(
            plugin_name=self.manifest.name,
            target=target,
        )

    @classmethod
    def get_manifest(cls) -> PluginManifest:
        """Return the plugin's metadata manifest."""
        if not hasattr(cls, "manifest") or not isinstance(cls.manifest, PluginManifest):
            raise NotImplementedError(
                f"Plugin {cls.__name__} must define a valid `manifest` class attribute."
            )
        return cls.manifest

    @abc.abstractmethod
    async def check_dependencies(self) -> bool:
        """Verify that required underlying tools (e.g., CLI binaries) are available.

        Returns:
            bool: True if dependencies are met, False otherwise.
        """
        pass

    @abc.abstractmethod
    async def execute(self) -> PluginExecutionResult:
        """Execute the security tool against the target.

        This method handles spawning the subprocess, feeding inputs, waiting for
        completion, and capturing stdout/stderr.

        Returns:
            PluginExecutionResult: Normalized outcome containing raw output.
        """
        pass

    @abc.abstractmethod
    def parse_results(self, raw_output: str) -> list[VulnerabilityCreate]:
        """Translate tool-specific raw output into VulnForge vulnerability records.

        This method is purely synchronous and computationally focused.

        Args:
            raw_output: The `raw_output` field from the PluginExecutionResult.

        Returns:
            list[VulnerabilityCreate]: Structured findings.
        """
        pass

    async def _run_subprocess(self, cmd: list[str], timeout: int = 3600) -> PluginExecutionResult:
        """Helper method to safely execute a subprocess with timeout and output capture.

        Most CLI-based plugins should use this instead of raw asyncio.create_subprocess_exec.

        Args:
            cmd: Command and arguments list (e.g., ["nmap", "-p-", "127.0.0.1"]).
            timeout: Maximum execution time in seconds.

        Returns:
            PluginExecutionResult
        """
        self.logger.debug("Executing subprocess", command=" ".join(cmd))
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            
            stdout_text = stdout_data.decode(errors="replace")
            stderr_text = stderr_data.decode(errors="replace")

            if proc.returncode != 0:
                self.logger.warning(
                    "Subprocess returned non-zero exit code",
                    returncode=proc.returncode,
                    stderr=stderr_text,
                )
                # Some tools (like Nmap) return non-zero in non-fatal ways, but generally we treat it as an error
                # Subclasses might need to override this behavior depending on the tool.
                return PluginExecutionResult(
                    success=False,
                    raw_output=f"STDOUT:\n{stdout_text}\n\nSTDERR:\n{stderr_text}",
                    error_message=f"Command exited with code {proc.returncode}",
                )

            return PluginExecutionResult(
                success=True,
                raw_output=stdout_text,
            )

        except asyncio.TimeoutError:
            self.logger.error("Subprocess execution timed out", timeout_seconds=timeout)
            return PluginExecutionResult(
                success=False,
                raw_output="",
                error_message=f"Execution timed out after {timeout} seconds",
            )
        except Exception as e:
            self.logger.exception("Subprocess execution failed")
            return PluginExecutionResult(
                success=False,
                raw_output="",
                error_message=str(e),
            )
