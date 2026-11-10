"""
Curated writeups connector — the legal "real writeups" slot.

Reads writeups from a local JSON file you control (``RAG_CURATED_PATH``, else a
bundled starter file). This is how you add real disclosed bug-bounty writeups
you are authorised to use — curate them into the file rather than scraping a
platform. Each entry maps directly to a WriteupIngestInput.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.models.writeup import WriteupSource
from app.schemas.writeup import WriteupIngestInput
from app.services.rag.connectors.base import WriteupConnector, WriteupConnectorError

logger = get_logger(__name__)

_BUNDLED = Path(__file__).resolve().parent.parent / "data" / "curated_writeups.json"


class CuratedConnector(WriteupConnector):
    """Ingests writeups from a local, user-maintained JSON file."""

    name = "curated"

    def _path(self) -> Path:
        configured = getattr(self._settings, "rag_curated_path", None)
        if configured:
            return Path(configured)
        return _BUNDLED

    async def fetch(self, limit: int = 50) -> list[WriteupIngestInput]:
        path = self._path()
        if not path.exists():
            logger.warning("connector.curated.missing_file", path=str(path))
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise WriteupConnectorError(f"Curated file unreadable: {exc}") from exc

        if not isinstance(raw, list):
            raise WriteupConnectorError("Curated file must be a JSON array of writeups.")

        items: list[WriteupIngestInput] = []
        for entry in raw[:limit]:
            mapped = self._map(entry)
            if mapped is not None:
                items.append(mapped)
        logger.info("connector.curated.fetched", count=len(items), path=str(path))
        return items

    def _map(self, entry: dict[str, Any]) -> WriteupIngestInput | None:
        if not entry.get("title") or not entry.get("content"):
            return None
        source = entry.get("source")
        try:
            source_enum = WriteupSource(source) if source else WriteupSource.MANUAL
        except ValueError:
            source_enum = WriteupSource.MANUAL
        return WriteupIngestInput(
            title=entry["title"],
            content=entry["content"],
            source=source_enum,
            source_url=entry.get("source_url") or None,
            source_ref=entry.get("source_ref"),
            summary=entry.get("summary"),
            vuln_class=entry.get("vuln_class"),
            cwe_id=entry.get("cwe_id"),
            severity=entry.get("severity"),
            tech_stack=entry.get("tech_stack", []),
            tags=entry.get("tags", []),
            metadata=entry.get("metadata", {}),
        )
