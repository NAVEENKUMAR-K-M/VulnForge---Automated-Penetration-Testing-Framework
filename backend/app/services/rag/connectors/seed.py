"""Seed connector — exposes the bundled original seed corpus as a source."""

from __future__ import annotations

from app.schemas.writeup import WriteupIngestInput
from app.services.rag.connectors.base import WriteupConnector
from app.services.rag.sources import get_seed_writeups


class SeedConnector(WriteupConnector):
    """Returns the built-in, original seed writeups (offline, ToS-free)."""

    name = "seed"

    async def fetch(self, limit: int = 50) -> list[WriteupIngestInput]:
        return get_seed_writeups()[:limit]
