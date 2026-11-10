"""
Text normalisation, hashing, and chunking for writeup ingestion.

Chunking is a simple character sliding window with overlap — deterministic and
dependency-free.  Chunk size/overlap come from settings and must stay fixed once
the corpus is embedded (changing them means re-embedding).
"""

from __future__ import annotations

import hashlib
import re

_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")


def normalise_content(text: str) -> str:
    """Collapse runs of whitespace and excess blank lines; strip ends.

    Normalisation makes the content hash stable against trivial formatting
    differences so dedupe works across re-ingests.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANKLINES_RE.sub("\n\n", text)
    return text.strip()


def content_hash(text: str) -> str:
    """Return the sha256 hex digest of normalised text (dedupe key)."""
    return hashlib.sha256(normalise_content(text).encode("utf-8")).hexdigest()


def chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping character windows.

    Prefers to break on a paragraph/sentence boundary near the window end so
    chunks don't cut mid-word where possible.
    """
    text = normalise_content(text)
    if not text:
        return []
    if overlap >= chunk_size:
        overlap = chunk_size // 4

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            # Try to end on a nearby boundary within the last 20% of the window.
            window = text[start:end]
            boundary = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if boundary > int(chunk_size * 0.8):
                end = start + boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks
