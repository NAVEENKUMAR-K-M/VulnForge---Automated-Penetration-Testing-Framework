"""
Writeup repository — corpus data access, dedupe, and vector similarity search.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.writeup import Writeup, WriteupChunk
from app.repositories.base import BaseRepository


class WriteupRepository(BaseRepository[Writeup, dict, dict]):
    """Data access for the RAG writeup corpus."""

    model = Writeup

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_hash(self, content_hash: str) -> Writeup | None:
        """Return an existing writeup by content hash (dedupe lookup)."""
        stmt = select(Writeup).where(Writeup.content_hash == content_hash)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create_writeup(
        self, data: dict[str, Any], chunks: list[dict[str, Any]]
    ) -> Writeup:
        """Insert a writeup and its embedded chunks in one transaction."""
        writeup = Writeup(**data)
        self._session.add(writeup)
        await self._session.flush()  # assign writeup.id

        for ch in chunks:
            self._session.add(WriteupChunk(writeup_id=writeup.id, **ch))

        await self._session.flush()
        await self._session.refresh(writeup)
        return writeup

    async def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int = 5,
        vuln_class: str | None = None,
        cwe_id: str | None = None,
        tech: str | None = None,
    ) -> list[tuple[WriteupChunk, Writeup, float]]:
        """Cosine-similarity search over chunk embeddings, filtered by metadata.

        Returns ``(chunk, writeup, similarity)`` tuples ordered by closeness,
        where similarity = 1 − cosine_distance (higher is closer).
        """
        distance = WriteupChunk.embedding.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(WriteupChunk, Writeup, distance)
            .join(Writeup, Writeup.id == WriteupChunk.writeup_id)
            .where(WriteupChunk.embedding.isnot(None))
        )
        if vuln_class:
            stmt = stmt.where(Writeup.vuln_class == vuln_class)
        if cwe_id:
            stmt = stmt.where(Writeup.cwe_id == cwe_id)
        if tech:
            # JSONB containment: tech_stack @> ["<tech>"]
            stmt = stmt.where(Writeup.tech_stack.contains([tech]))

        stmt = stmt.order_by(distance).limit(top_k)
        rows = await self._session.execute(stmt)
        results: list[tuple[WriteupChunk, Writeup, float]] = []
        for chunk, writeup, dist in rows.all():
            results.append((chunk, writeup, 1.0 - float(dist)))
        return results

    async def stats(self) -> dict[str, Any]:
        """Return corpus counts: totals and breakdowns by source + vuln_class."""
        total_writeups = (
            await self._session.execute(select(func.count(Writeup.id)))
        ).scalar_one()
        total_chunks = (
            await self._session.execute(select(func.count(WriteupChunk.id)))
        ).scalar_one()

        by_source_rows = await self._session.execute(
            select(Writeup.source, func.count(Writeup.id)).group_by(Writeup.source)
        )
        by_source = {row[0].value: row[1] for row in by_source_rows.all()}

        by_class_rows = await self._session.execute(
            select(Writeup.vuln_class, func.count(Writeup.id))
            .where(Writeup.vuln_class.isnot(None))
            .group_by(Writeup.vuln_class)
        )
        by_vuln_class = {row[0]: row[1] for row in by_class_rows.all()}

        return {
            "total_writeups": total_writeups,
            "total_chunks": total_chunks,
            "by_source": by_source,
            "by_vuln_class": by_vuln_class,
        }
