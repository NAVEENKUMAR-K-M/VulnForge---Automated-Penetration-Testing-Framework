"""
Writeup and WriteupChunk ORM models — the RAG knowledge corpus.

A ``Writeup`` is a single public, disclosed bug-bounty report / PoC / research
article ingested into VulnForge's knowledge base.  Its text is split into
``WriteupChunk`` rows, each carrying a pgvector embedding for semantic search.

These are **global reference data** — deliberately NOT workspace-scoped.  The
corpus is shared across all workspaces; only retrieval *results* become
workspace-relevant when combined with a workspace's recon context.  Every
writeup keeps its ``source_url`` so retrieved context can always be cited.

Dedupe: ``content_hash`` (sha256 of normalised content) is unique, so re-running
ingestion over an already-seen report is a no-op.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.models.base import TimestampedBase

if TYPE_CHECKING:
    pass

# Embedding dimensionality is fixed at import from settings — commit to one model.
_EMBEDDING_DIM = get_settings().rag_embedding_dim


class WriteupSource(str, enum.Enum):
    """Origin platform of a writeup (used for provenance and filtering)."""

    HACKERONE = "hackerone"
    BUGCROWD = "bugcrowd"
    GITHUB = "github"
    BLOG = "blog"
    MANUAL = "manual"
    OTHER = "other"


class Writeup(TimestampedBase):
    """A single disclosed writeup / PoC in the knowledge corpus."""

    __tablename__ = "writeups"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_writeups_content_hash"),
    )

    source: Mapped[WriteupSource] = mapped_column(
        Enum(WriteupSource, values_callable=lambda obj: [e.value for e in obj], name="writeup_source_enum"),
        nullable=False,
        default=WriteupSource.OTHER,
        server_default=WriteupSource.OTHER.value,
        index=True,
        doc="Origin platform of this writeup.",
    )
    source_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        doc="Canonical public URL — used to cite retrieved context.",
    )
    source_ref: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        doc="External identifier on the source platform (e.g., report id).",
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Human-readable writeup title.",
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional short summary of the writeup.",
    )
    vuln_class: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        doc="Vulnerability class (e.g., 'sqli', 'xss', 'idor', 'ssrf').",
    )
    cwe_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        doc="CWE identifier (e.g., 'CWE-89') if known.",
    )
    severity: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        doc="Reported severity as free text (platforms vary).",
    )
    tech_stack: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        doc="Technologies/products the writeup concerns (e.g., ['jenkins', 'laravel']).",
    )
    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        doc="Free-form searchable labels.",
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the writeup was originally published/disclosed.",
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="sha256 of normalised content — dedupe key.",
    )
    char_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        doc="Length of the ingested content in characters.",
    )
    writeup_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        doc="Arbitrary extra metadata from the source.",
    )

    chunks: Mapped[list[WriteupChunk]] = relationship(
        "WriteupChunk",
        back_populates="writeup",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="WriteupChunk.chunk_index",
    )


class WriteupChunk(TimestampedBase):
    """A single embedded chunk of a writeup, searchable by vector similarity."""

    __tablename__ = "writeup_chunks"
    __table_args__ = (
        UniqueConstraint("writeup_id", "chunk_index", name="uq_writeup_chunks_pair"),
    )

    writeup_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("writeups.id", ondelete="CASCADE", name="fk_writeup_chunks_writeup"),
        nullable=False,
        index=True,
        doc="FK to the parent writeup.",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="0-based position of this chunk within the writeup.",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="The chunk's text.",
    )
    char_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        doc="Length of this chunk in characters.",
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(_EMBEDDING_DIM),
        nullable=True,
        doc="pgvector embedding of this chunk (cosine space).",
    )

    writeup: Mapped[Writeup] = relationship(
        "Writeup",
        back_populates="chunks",
        lazy="select",
    )
