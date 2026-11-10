"""
Writeup source connectors.

Each connector fetches disclosed, redistributable security knowledge from a
public source and yields ``WriteupIngestInput`` items for the ingestion
pipeline. Connectors must only pull public content and must preserve a
``source_url`` so retrieved context can be cited.

Registry: ``get_connector(name)`` returns a connector instance; the
``AVAILABLE_CONNECTORS`` mapping drives the API and the scheduled task.

Legality note: the bundled connectors use public, documented APIs over
explicitly-redistributable data (e.g. the GitHub Advisory Database is CC-BY
4.0). Scraping bug-bounty platforms (HackerOne/Bugcrowd) is ToS-sensitive and is
deliberately NOT shipped here — add such a connector only with the source's
permission and keep it opt-in.
"""

from __future__ import annotations

from app.core.config import Settings
from app.core.exceptions import ValidationError
from app.services.rag.connectors.base import WriteupConnector, WriteupConnectorError
from app.services.rag.connectors.curated import CuratedConnector
from app.services.rag.connectors.exploitdb import ExploitDbConnector
from app.services.rag.connectors.github_advisories import GitHubAdvisoryConnector
from app.services.rag.connectors.nvd import NvdConnector
from app.services.rag.connectors.osv import OsvConnector
from app.services.rag.connectors.seed import SeedConnector
from app.services.rag.connectors.wstg import WstgConnector

# name -> connector class
AVAILABLE_CONNECTORS: dict[str, type[WriteupConnector]] = {
    GitHubAdvisoryConnector.name: GitHubAdvisoryConnector,
    NvdConnector.name: NvdConnector,
    OsvConnector.name: OsvConnector,
    ExploitDbConnector.name: ExploitDbConnector,
    WstgConnector.name: WstgConnector,
    CuratedConnector.name: CuratedConnector,
    SeedConnector.name: SeedConnector,
}


def get_connector(name: str, settings: Settings) -> WriteupConnector:
    """Return a connector instance by name, or raise if unknown."""
    cls = AVAILABLE_CONNECTORS.get(name)
    if cls is None:
        raise ValidationError(
            f"Unknown source '{name}'. Available: {sorted(AVAILABLE_CONNECTORS)}"
        )
    return cls(settings)


__all__ = [
    "WriteupConnector",
    "WriteupConnectorError",
    "GitHubAdvisoryConnector",
    "NvdConnector",
    "OsvConnector",
    "ExploitDbConnector",
    "WstgConnector",
    "CuratedConnector",
    "SeedConnector",
    "AVAILABLE_CONNECTORS",
    "get_connector",
]
