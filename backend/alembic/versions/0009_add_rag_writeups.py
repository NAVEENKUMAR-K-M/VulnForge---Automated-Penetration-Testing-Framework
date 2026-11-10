"""Add RAG writeup corpus (pgvector) — writeups + writeup_chunks.

Revision ID: 0009_add_rag_writeups
Revises: 30cec625e23c
Create Date: 2026-11-10 00:00:00.000000+00:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_add_rag_writeups"
down_revision: Union[str, None] = "30cec625e23c"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None

# Must match settings.rag_embedding_dim (voyage-3.5-lite @ 1024).
EMBEDDING_DIM = 1024


def upgrade() -> None:
    # pgvector extension (image: pgvector/pgvector:pg15)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    writeup_source = postgresql.ENUM(
        "hackerone", "bugcrowd", "github", "blog", "manual", "other",
        name="writeup_source_enum",
        create_type=False,
    )
    writeup_source.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "writeups",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("source", writeup_source, server_default="other", nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("vuln_class", sa.String(length=100), nullable=True),
        sa.Column("cwe_id", sa.String(length=32), nullable=True),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("tech_stack", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("char_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_writeups"),
        sa.UniqueConstraint("content_hash", name="uq_writeups_content_hash"),
    )
    op.create_index("ix_writeups_source", "writeups", ["source"])
    op.create_index("ix_writeups_source_ref", "writeups", ["source_ref"])
    op.create_index("ix_writeups_vuln_class", "writeups", ["vuln_class"])
    op.create_index("ix_writeups_cwe_id", "writeups", ["cwe_id"])

    op.create_table(
        "writeup_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("writeup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.ForeignKeyConstraint(["writeup_id"], ["writeups.id"], name="fk_writeup_chunks_writeup", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_writeup_chunks"),
        sa.UniqueConstraint("writeup_id", "chunk_index", name="uq_writeup_chunks_pair"),
    )
    op.create_index("ix_writeup_chunks_writeup_id", "writeup_chunks", ["writeup_id"])
    # Approximate-nearest-neighbour index for cosine similarity search.
    op.create_index(
        "ix_writeup_chunks_embedding_hnsw",
        "writeup_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_writeup_chunks_embedding_hnsw", table_name="writeup_chunks")
    op.drop_index("ix_writeup_chunks_writeup_id", table_name="writeup_chunks")
    op.drop_table("writeup_chunks")
    op.drop_index("ix_writeups_cwe_id", table_name="writeups")
    op.drop_index("ix_writeups_vuln_class", table_name="writeups")
    op.drop_index("ix_writeups_source_ref", table_name="writeups")
    op.drop_index("ix_writeups_source", table_name="writeups")
    op.drop_table("writeups")
    op.execute("DROP TYPE IF EXISTS writeup_source_enum")
