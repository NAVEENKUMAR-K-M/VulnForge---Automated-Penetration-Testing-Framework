"""
RAG API router — search the writeup corpus, view stats, and (admin) ingest.

The corpus is global (not workspace-scoped), so these endpoints are not under a
workspace prefix. Search/stats require authentication; ingestion requires a
superuser.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status

from app.api.deps import (
    CurrentUserDep,
    DatabaseDep,
    SettingsDep,
    require_superuser,
)
from app.schemas.writeup import IngestResult, RagStats, SearchResponse, WriteupIngestInput
from app.services.rag.connectors import AVAILABLE_CONNECTORS
from app.services.rag.ingestion_service import WriteupIngestionService
from app.services.rag.retrieval_service import RetrievalService
from app.services.rag.sources import get_seed_writeups

router = APIRouter(prefix="/rag", tags=["rag"])


async def get_retrieval_service(db: DatabaseDep, settings: SettingsDep) -> RetrievalService:
    return RetrievalService(db=db, settings=settings)


async def get_ingestion_service(db: DatabaseDep, settings: SettingsDep) -> WriteupIngestionService:
    return WriteupIngestionService(db=db, settings=settings)


RetrievalServiceDep = Annotated[RetrievalService, Depends(get_retrieval_service)]
IngestionServiceDep = Annotated[WriteupIngestionService, Depends(get_ingestion_service)]


@router.get(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search the writeup knowledge base",
    description=(
        "Semantic search over disclosed-writeup chunks, returned with provenance "
        "(title + source URL) and an optional metadata filter."
    ),
)
async def search_writeups(
    current_user: CurrentUserDep,
    svc: RetrievalServiceDep,
    q: str = Query(..., min_length=1, description="Natural-language query / recon context."),
    top_k: int | None = Query(None, ge=1, le=50, description="Max results."),
    vuln_class: str | None = Query(None, description="Filter by vulnerability class."),
    cwe_id: str | None = Query(None, description="Filter by CWE id."),
    tech: str | None = Query(None, description="Filter by a technology in tech_stack."),
) -> SearchResponse:
    return await svc.search(q, top_k=top_k, vuln_class=vuln_class, cwe_id=cwe_id, tech=tech)


@router.get(
    "/stats",
    response_model=RagStats,
    status_code=status.HTTP_200_OK,
    summary="Corpus statistics",
)
async def rag_stats(current_user: CurrentUserDep, svc: RetrievalServiceDep) -> RagStats:
    return await svc.stats()


@router.get(
    "/sources",
    status_code=status.HTTP_200_OK,
    summary="List available writeup source connectors",
)
async def list_sources(current_user: CurrentUserDep) -> dict[str, list[str]]:
    return {"sources": sorted(AVAILABLE_CONNECTORS)}


@router.post(
    "/ingest/seed",
    response_model=IngestResult,
    status_code=status.HTTP_200_OK,
    summary="Ingest the built-in seed corpus (admin)",
    description="Embed and store the bundled seed writeups. Idempotent via content-hash dedupe.",
)
async def ingest_seed(
    _su: Annotated[object, Depends(require_superuser())],
    svc: IngestionServiceDep,
) -> IngestResult:
    return await svc.ingest_batch(get_seed_writeups())


@router.post(
    "/ingest/source",
    response_model=IngestResult,
    status_code=status.HTTP_200_OK,
    summary="Ingest from a named source connector (admin)",
    description=(
        "Fetch writeups from a public source connector (e.g. 'github_advisories') "
        "and embed them. Deduplicated by content hash. See GET /rag/sources."
    ),
)
async def ingest_source(
    _su: Annotated[object, Depends(require_superuser())],
    svc: IngestionServiceDep,
    source: str = Query(..., description="Connector name, e.g. 'github_advisories'."),
    limit: int = Query(50, ge=1, le=500, description="Max writeups to fetch."),
) -> IngestResult:
    return await svc.ingest_from_source(source, limit=limit)


@router.post(
    "/writeups",
    response_model=IngestResult,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a custom batch of writeups (admin)",
    description="Embed and store caller-supplied writeups. Deduplicated by content hash.",
)
async def ingest_writeups(
    _su: Annotated[object, Depends(require_superuser())],
    svc: IngestionServiceDep,
    items: list[WriteupIngestInput] = Body(..., description="Writeups to ingest."),
) -> IngestResult:
    return await svc.ingest_batch(items)
