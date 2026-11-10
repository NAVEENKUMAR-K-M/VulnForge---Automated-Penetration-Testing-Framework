"""
LLM provider interface + factory.

Generation is kept behind one small interface so the backend is swappable: the
default is a CLI subprocess (Claude/Codex CLI), but an API-SDK provider could be
dropped in via config without touching the reporting service or the agent.

Callers must handle ``LLMUnavailableError`` and degrade gracefully (e.g. the
reporting service falls back to a deterministic, data-derived summary when no
CLI is configured).
"""

from __future__ import annotations

import abc

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMUnavailableError(Exception):
    """Raised when the configured LLM backend cannot produce a response."""


class LLMProvider(abc.ABC):
    """Interface for text generation."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Short identifier of the backend (for logging/metadata)."""

    @abc.abstractmethod
    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        """Generate a completion for ``prompt``. Raises ``LLMUnavailableError``."""


class NullProvider(LLMProvider):
    """A provider that never generates — forces callers to their fallback."""

    @property
    def name(self) -> str:
        return "none"

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        raise LLMUnavailableError("LLM generation is disabled (llm_provider='none').")


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Return the configured LLM provider."""
    provider = (settings.llm_provider or "cli").lower()
    if provider == "cli":
        # Imported lazily to avoid importing subprocess machinery when unused.
        from app.services.llm.cli_provider import CliProvider

        return CliProvider(settings)
    if provider in ("none", "null", "disabled"):
        return NullProvider()
    logger.warning("llm.unknown_provider", provider=provider)
    return NullProvider()
