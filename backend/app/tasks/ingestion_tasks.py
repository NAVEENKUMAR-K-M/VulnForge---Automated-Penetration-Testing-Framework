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
from app.services.rag.sources import get_seed_writeups
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
    try:
        async with factory() as session:
            service = WriteupIngestionService(session, settings)
            result = await service.ingest_batch(get_seed_writeups())
        return {
            "status": "ok",
            "ingested": result.ingested,
            "skipped": result.skipped,
            "chunks": result.chunks,
            "provider": result.provider,
        }
    finally:
        await engine.dispose()
