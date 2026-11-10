"""Unit tests for the LLM provider abstraction."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.llm.cli_provider import CliProvider
from app.services.llm.provider import (
    LLMUnavailableError,
    NullProvider,
    get_llm_provider,
)


def _settings(**overrides):
    s = get_settings().model_copy(update=overrides)
    return s


class TestFactory:
    def test_cli_selected(self) -> None:
        p = get_llm_provider(_settings(llm_provider="cli"))
        assert isinstance(p, CliProvider)

    def test_none_selected(self) -> None:
        assert isinstance(get_llm_provider(_settings(llm_provider="none")), NullProvider)

    def test_unknown_falls_back_to_null(self) -> None:
        assert isinstance(get_llm_provider(_settings(llm_provider="wat")), NullProvider)


class TestNullProvider:
    async def test_generate_raises(self) -> None:
        with pytest.raises(LLMUnavailableError):
            await NullProvider().generate("hi")


class TestCliProvider:
    async def test_missing_binary_raises(self) -> None:
        p = CliProvider(_settings(llm_cli_command="vf_nonexistent_bin_xyz", llm_cli_args=""))
        with pytest.raises(LLMUnavailableError):
            await p.generate("hello")

    def test_args_split_and_name(self) -> None:
        p = CliProvider(_settings(llm_cli_command="claude", llm_cli_args="-p --foo"))
        assert p.name == "cli:claude"
        assert p._args == ["-p", "--foo"]
