"""
Writeup ingestion service — normalise → dedupe → chunk → embed → upsert.

Embedding calls are offloaded to a worker thread so a Voyage network round-trip
never blocks the event loop.  Dedupe is by content hash: re-ingesting an
already-seen writeup is a no-op (no re-embed), which keeps the Voyage budget
bounded.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.repositories.writeup import WriteupRepository
from app.schemas.writeup import IngestResult, WriteupIngestInput
from app.services.rag.chunking import chunk_text, content_hash, normalise_content
from app.services.rag.connectors import get_connector
from app.services.rag.embeddings import get_embedding_provider

logger = get_logger(__name__)


class WriteupIngestionService:
    """Ingest raw writeups into the embedded corpus."""

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._repo = WriteupRepository(db)
        self._embedder = get_embedding_provider(settings)

    async def ingest_one(self, item: WriteupIngestInput) -> tuple[bool, int]:
        """Ingest a single writeup. Returns ``(ingested?, n_chunks)``.

        Does not commit — the caller commits the batch.
        """
        chash = content_hash(item.content)
        if await self._repo.get_by_hash(chash) is not None:
            return (False, 0)

        chunks = chunk_text(
            item.content,
            chunk_size=self._settings.rag_chunk_size,
            overlap=self._settings.rag_chunk_overlap,
        )
        if not chunks:
            return (False, 0)

        embeddings = await asyncio.to_thread(self._embedder.embed_documents, chunks)

        chunk_rows = [
            {
                "chunk_index": i,
                "content": content,
                "char_count": len(content),
                "embedding": embedding,
            }
            for i, (content, embedding) in enumerate(zip(chunks, embeddings))
        ]
        data = {
            "source": item.source,
            "source_url": item.source_url,
            "source_ref": item.source_ref,
            "title": item.title,
            "summary": item.summary,
            "vuln_class": item.vuln_class,
            "cwe_id": item.cwe_id,
            "severity": item.severity,
            "tech_stack": item.tech_stack,
            "tags": item.tags,
            "published_at": item.published_at,
            "content_hash": chash,
            "char_count": len(normalise_content(item.content)),
            "writeup_metadata": item.metadata,
        }
        await self._repo.create_writeup(data, chunk_rows)
        return (True, len(chunks))

    async def ingest_from_source(self, source: str, limit: int = 50) -> IngestResult:
        """Fetch writeups from a named connector and ingest them."""
        connector = get_connector(source, self._settings)
        items = await connector.fetch(limit=limit)
        logger.info("ingest.source_fetched", source=source, fetched=len(items))
        return await self.ingest_batch(items)

    async def ingest_batch(self, items: list[WriteupIngestInput]) -> IngestResult:
        """Ingest a batch, committing once at the end."""
        ingested = skipped = total_chunks = 0
        for item in items:
            try:
                ok, n = await self.ingest_one(item)
            except Exception:  # noqa: BLE001 - one bad writeup shouldn't abort the batch
                logger.exception("ingest.item_failed", title=item.title)
                skipped += 1
                continue
            if ok:
                ingested += 1
                total_chunks += n
            else:
                skipped += 1

        await self._db.commit()
        logger.info(
            "ingest.batch_done",
            ingested=ingested,
            skipped=skipped,
            chunks=total_chunks,
            provider=self._embedder.name,
        )
        return IngestResult(
            ingested=ingested,
            skipped=skipped,
            chunks=total_chunks,
            provider=self._embedder.name,
        )
