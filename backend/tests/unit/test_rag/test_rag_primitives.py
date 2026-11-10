"""Unit tests for RAG primitives: chunking, hashing, and the fake embedder."""

from __future__ import annotations

import math

import pytest

from app.services.rag.chunking import chunk_text, content_hash, normalise_content
from app.services.rag.embeddings import FakeEmbeddingProvider


class TestChunking:
    def test_empty_returns_no_chunks(self) -> None:
        assert chunk_text("", chunk_size=100, overlap=10) == []
        assert chunk_text("   \n\n  ", chunk_size=100, overlap=10) == []

    def test_short_text_single_chunk(self) -> None:
        chunks = chunk_text("a short writeup", chunk_size=100, overlap=10)
        assert chunks == ["a short writeup"]

    def test_long_text_is_split_with_overlap(self) -> None:
        text = "sentence. " * 200  # 2000 chars
        chunks = chunk_text(text, chunk_size=400, overlap=80)
        assert len(chunks) > 1
        assert all(len(c) <= 400 for c in chunks)

    def test_overlap_clamped_when_ge_chunk_size(self) -> None:
        # overlap >= chunk_size must not loop forever
        chunks = chunk_text("word " * 100, chunk_size=50, overlap=100)
        assert len(chunks) >= 1


class TestContentHash:
    def test_deterministic(self) -> None:
        assert content_hash("hello world") == content_hash("hello world")

    def test_whitespace_normalised(self) -> None:
        # Horizontal whitespace runs collapse; identical logical content hashes equal.
        assert content_hash("a\t\tb   c") == content_hash("a b c")

    def test_different_content_differs(self) -> None:
        assert content_hash("sqli") != content_hash("xss")

    def test_normalise_collapses_blank_lines(self) -> None:
        assert normalise_content("a\n\n\n\n\nb") == "a\n\nb"


class TestFakeEmbedder:
    def test_dimension(self) -> None:
        emb = FakeEmbeddingProvider(256)
        assert len(emb.embed_query("x")) == 256

    def test_deterministic(self) -> None:
        emb = FakeEmbeddingProvider(128)
        assert emb.embed_query("sql injection") == emb.embed_query("sql injection")

    def test_unit_norm(self) -> None:
        emb = FakeEmbeddingProvider(128)
        v = emb.embed_query("payload")
        assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-6)

    def test_distinct_inputs_differ(self) -> None:
        emb = FakeEmbeddingProvider(128)
        assert emb.embed_query("a") != emb.embed_query("b")

    def test_embed_documents_batches(self) -> None:
        emb = FakeEmbeddingProvider(64)
        out = emb.embed_documents(["one", "two", "three"])
        assert len(out) == 3
        assert all(len(v) == 64 for v in out)
        assert emb.embed_documents([]) == []
