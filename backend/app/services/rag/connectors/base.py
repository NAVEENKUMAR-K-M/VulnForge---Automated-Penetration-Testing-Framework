"""Connector interface + shared helpers (CWE → vuln-class mapping)."""

from __future__ import annotations

import abc

from app.core.config import Settings
from app.core.exceptions import VulnForgeError
from app.schemas.writeup import WriteupIngestInput

# Map common CWE ids to VulnForge's short vuln-class labels for retrieval filters.
CWE_TO_CLASS: dict[str, str] = {
    "CWE-79": "xss",
    "CWE-89": "sqli",
    "CWE-78": "command-injection",
    "CWE-77": "command-injection",
    "CWE-94": "code-injection",
    "CWE-918": "ssrf",
    "CWE-22": "path-traversal",
    "CWE-23": "path-traversal",
    "CWE-98": "lfi-rfi",
    "CWE-502": "deserialization",
    "CWE-611": "xxe",
    "CWE-352": "csrf",
    "CWE-639": "idor",
    "CWE-284": "access-control",
    "CWE-285": "access-control",
    "CWE-862": "access-control",
    "CWE-863": "access-control",
    "CWE-287": "auth",
    "CWE-798": "hardcoded-credentials",
    "CWE-434": "file-upload",
    "CWE-601": "open-redirect",
    "CWE-538": "info-disclosure",
    "CWE-200": "info-disclosure",
    "CWE-1333": "redos",
    "CWE-400": "dos",
}


def vuln_class_for_cwe(cwe_id: str | None) -> str | None:
    """Return the short vuln-class for a CWE id, if known."""
    if not cwe_id:
        return None
    return CWE_TO_CLASS.get(cwe_id.strip().upper())


class WriteupConnectorError(VulnForgeError):
    """Raised when a connector cannot fetch from its source (upstream failure)."""

    status_code: int = 502
    message: str = "A writeup source connector failed."


class WriteupConnector(abc.ABC):
    """Fetches writeups from one public source."""

    #: Stable machine name used in config, the API, and the registry.
    name: str = "base"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @abc.abstractmethod
    async def fetch(self, limit: int = 50) -> list[WriteupIngestInput]:
        """Return up to ``limit`` writeups from the source (newest first)."""
