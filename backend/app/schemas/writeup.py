"""
Pydantic schemas for the RAG knowledge base — writeup ingestion, retrieval
results, and corpus stats.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.writeup import WriteupSource
from app.schemas.common import TimestampedResponse, VulnForgeBaseModel


class WriteupIngestInput(VulnForgeBaseModel):
    """A single raw writeup to ingest (normalised → chunked → embedded)."""

    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, description="Full writeup text to chunk + embed.")
    source: WriteupSource = Field(default=WriteupSource.OTHER)
    source_url: str | None = Field(default=None, max_length=1000)
    source_ref: str | None = Field(default=None, max_length=255)
    summary: str | None = Field(default=None)
    vuln_class: str | None = Field(default=None, max_length=100)
    cwe_id: str | None = Field(default=None, max_length=32)
    severity: str | None = Field(default=None, max_length=32)
    tech_stack: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    published_at: datetime | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WriteupResponse(TimestampedResponse):
    """A writeup record (without chunk bodies)."""

    source: WriteupSource
    source_url: str | None
    source_ref: str | None
    title: str
    summary: str | None
    vuln_class: str | None
    cwe_id: str | None
    severity: str | None
    tech_stack: list[str]
    tags: list[str]
    published_at: datetime | None
    char_count: int


class RetrievalResult(VulnForgeBaseModel):
    """One retrieved chunk with its parent writeup's provenance."""

    writeup_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    content: str
    similarity: float = Field(description="Cosine similarity in [−1, 1]; higher is closer.")
    title: str
    source: WriteupSource
    source_url: str | None
    vuln_class: str | None
    cwe_id: str | None
    tech_stack: list[str]


class SearchResponse(VulnForgeBaseModel):
    """Retrieval response envelope."""

    query: str
    results: list[RetrievalResult]
    provider: str = Field(description="Embedding model used for the query.")


class IngestResult(VulnForgeBaseModel):
    """Outcome of an ingestion batch."""

    ingested: int = Field(description="New writeups embedded + stored.")
    skipped: int = Field(description="Duplicates skipped (already in corpus).")
    chunks: int = Field(description="Total chunks embedded in this batch.")
    provider: str


class RagStats(VulnForgeBaseModel):
    """Corpus statistics."""

    total_writeups: int
    total_chunks: int
    by_source: dict[str, int]
    by_vuln_class: dict[str, int]
    embedding_model: str
    embedding_dim: int
