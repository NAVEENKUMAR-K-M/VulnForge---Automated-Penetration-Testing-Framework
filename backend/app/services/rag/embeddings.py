"""
Embedding providers for the RAG knowledge base.

Two implementations behind one interface:
    - ``VoyageEmbeddingProvider``: real embeddings via the Voyage AI API. Used
      when a ``VOYAGE_API_KEY`` is configured. Distinguishes document vs. query
      input types (Voyage embeds them differently for better retrieval).
    - ``FakeEmbeddingProvider``: deterministic, hash-seeded unit vectors with no
      network calls — for dev, offline work, and tests. Same text → same vector,
      so similarity is stable (if not semantically meaningful).

``get_embedding_provider(settings)`` picks Voyage when the provider is "voyage"
AND a key is present, otherwise falls back to fake (logging a warning). Commit
to one model + dimension up front: changing either means re-embedding the whole
corpus.
"""

from __future__ import annotations

import abc
import hashlib
import math

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingProvider(abc.ABC):
    """Interface for turning text into fixed-dimension vectors."""

    def __init__(self, dimension: int) -> None:
        self.dimension = dimension

    @abc.abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents (corpus text)."""

    @abc.abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a single search query."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Short identifier of the backing model (for logging/metadata)."""


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic, offline embedder. NOT semantically meaningful."""

    def __init__(self, dimension: int) -> None:
        super().__init__(dimension)

    @property
    def name(self) -> str:
        return "fake-deterministic"

    def _embed_one(self, text: str) -> list[float]:
        # Seed a simple PRNG from the text hash and emit a unit vector.
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        vec: list[float] = []
        x = seed or 1
        for _ in range(self.dimension):
            # xorshift-ish deterministic sequence
            x ^= (x << 13) & 0xFFFFFFFFFFFFFFFF
            x ^= x >> 7
            x ^= (x << 17) & 0xFFFFFFFFFFFFFFFF
            vec.append(((x % 2000) / 1000.0) - 1.0)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)


# Message markers used to tell a persistent *quota exhaustion* apart from a
# transient *rate limit* (3 RPM). We only fail over to the next key on the
# former — a transient 429 should retry on the same key, not burn the fallback.
_RATE_LIMIT_MARKERS = ("rpm", "tpm", "per minute", "rate limit")
_EXHAUSTION_MARKERS = ("quota", "exceeded your", "insufficient", "out of credit", "free token")


def _is_exhaustion(exc: Exception) -> bool:
    """Heuristic: True if the error looks like free-token/quota exhaustion."""
    msg = str(exc).lower()
    if any(m in msg for m in _RATE_LIMIT_MARKERS):
        return False
    return any(m in msg for m in _EXHAUSTION_MARKERS)


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Voyage AI embeddings with ordered multi-key failover.

    Keys are tried in order starting from the first non-exhausted one. When a key
    reports quota/free-token exhaustion, we advance to the next key (persisted on
    this instance) and retry. Transient 3 RPM rate limits are handled by the
    SDK's own backoff (``max_retries``) on the *same* key — they never consume
    the fallback.
    """

    def __init__(self, api_keys: list[str], model: str, dimension: int) -> None:
        super().__init__(dimension)
        import voyageai  # imported lazily so the dep is optional at import time

        if not api_keys:
            raise ValueError("At least one Voyage API key is required.")
        self._clients = [voyageai.Client(api_key=k, max_retries=6) for k in api_keys]
        self._model = model
        self._active = 0  # index of the current (non-exhausted) key

    @property
    def name(self) -> str:
        if len(self._clients) == 1:
            return self._model
        return f"{self._model} (key {self._active + 1}/{len(self._clients)})"

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        last_exc: Exception | None = None
        for i in range(self._active, len(self._clients)):
            try:
                result = self._clients[i].embed(
                    texts,
                    model=self._model,
                    input_type=input_type,
                    output_dimension=self.dimension,
                )
                self._active = i  # stick here until this key is exhausted
                return [list(e) for e in result.embeddings]
            except Exception as exc:  # noqa: BLE001 - classify then decide failover
                last_exc = exc
                if _is_exhaustion(exc) and i + 1 < len(self._clients):
                    logger.warning("embeddings.voyage_key_exhausted", key_index=i)
                    self._active = i + 1
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed(texts, "document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query")[0]


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Return the configured embedding provider.

    Voyage when ``rag_embedding_provider == 'voyage'`` and a key is present;
    otherwise the deterministic fake embedder (with a warning).
    """
    dim = settings.rag_embedding_dim
    keys = [k for k in (settings.voyage_api_key, settings.voyage_api_key_fallback) if k]
    if settings.rag_embedding_provider == "voyage" and keys:
        try:
            return VoyageEmbeddingProvider(
                api_keys=keys,
                model=settings.rag_embedding_model,
                dimension=dim,
            )
        except Exception as exc:  # noqa: BLE001 - fall back rather than crash ingestion
            logger.warning("embeddings.voyage_init_failed", error=str(exc))

    logger.warning(
        "embeddings.using_fake",
        reason="no voyage key or provider=fake",
        dimension=dim,
    )
    return FakeEmbeddingProvider(dimension=dim)
