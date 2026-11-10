"""
Retrieval service — embed a query and return the most similar writeup chunks,
each with its parent writeup's provenance so results can be cited.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import VulnForgeError
from app.repositories.writeup import WriteupRepository
from app.schemas.writeup import RagStats, RetrievalResult, SearchResponse
from app.services.rag.embeddings import get_embedding_provider


class EmbeddingUnavailableError(VulnForgeError):
    """Raised when the embedding backend can't service a query (e.g., rate-limited)."""

    status_code: int = 503
    message: str = "Embedding service is temporarily unavailable (rate limited?). Try again shortly."


class RetrievalService:
    """Semantic search over the writeup corpus."""

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._settings = settings
        self._repo = WriteupRepository(db)
        self._embedder = get_embedding_provider(settings)

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        vuln_class: str | None = None,
        cwe_id: str | None = None,
        tech: str | None = None,
    ) -> SearchResponse:
        """Embed ``query`` and return the top-k most similar chunks."""
        k = top_k or self._settings.rag_default_top_k
        try:
            query_vec = await asyncio.to_thread(self._embedder.embed_query, query)
        except Exception as exc:  # noqa: BLE001 - surface a clean 503 rather than a 500
            raise EmbeddingUnavailableError(
                f"Could not embed the query: {exc}"
            ) from exc
        rows = await self._repo.search(
            query_vec, top_k=k, vuln_class=vuln_class, cwe_id=cwe_id, tech=tech
        )
        results = [
            RetrievalResult(
                writeup_id=writeup.id,
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                similarity=similarity,
                title=writeup.title,
                source=writeup.source,
                source_url=writeup.source_url,
                vuln_class=writeup.vuln_class,
                cwe_id=writeup.cwe_id,
                tech_stack=writeup.tech_stack,
            )
            for chunk, writeup, similarity in rows
        ]
        return SearchResponse(query=query, results=results, provider=self._embedder.name)

    async def stats(self) -> RagStats:
        """Return corpus statistics."""
        s = await self._repo.stats()
        return RagStats(
            total_writeups=s["total_writeups"],
            total_chunks=s["total_chunks"],
            by_source=s["by_source"],
            by_vuln_class=s["by_vuln_class"],
            embedding_model=self._embedder.name,
            embedding_dim=self._settings.rag_embedding_dim,
        )
