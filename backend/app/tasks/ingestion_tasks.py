"""
Writeup ingestion task (beat-scheduled).

Runs the ingestion pipeline over the configured sources. Gated by
``rag_ingest_enabled`` so the schedule is inert until an operator turns it on
(and a Voyage key is usually configured first). Like the scan task, it owns its
own async engine so asyncpg stays bound to this task's event loop.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.rag.ingestion_service import WriteupIngestionService
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="vulnforge.ingest_writeups")
def ingest_writeups() -> dict[str, Any]:
    """Celery entry point — ingest configured writeup sources."""
    return asyncio.run(_run_ingestion())


async def _run_ingestion() -> dict[str, Any]:
    settings = get_settings()
    if not settings.rag_ingest_enabled:
        logger.info("ingest.disabled")
        return {"status": "disabled"}

    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"server_settings": {"jit": "off"}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    sources = [s.strip() for s in settings.rag_ingest_sources.split(",") if s.strip()]
    totals = {"ingested": 0, "skipped": 0, "chunks": 0}
    per_source: dict[str, Any] = {}
    try:
        async with factory() as session:
            service = WriteupIngestionService(session, settings)
            for source in sources:
                try:
                    result = await service.ingest_from_source(source, limit=settings.rag_ingest_limit)
                except Exception as exc:  # noqa: BLE001 - one bad source shouldn't abort the rest
                    logger.exception("ingest.source_failed", source=source)
                    per_source[source] = {"error": str(exc)}
                    continue
                totals["ingested"] += result.ingested
                totals["skipped"] += result.skipped
                totals["chunks"] += result.chunks
                per_source[source] = {
                    "ingested": result.ingested,
                    "skipped": result.skipped,
                    "chunks": result.chunks,
                }
        return {"status": "ok", "sources": per_source, **totals}
    finally:
        await engine.dispose()
