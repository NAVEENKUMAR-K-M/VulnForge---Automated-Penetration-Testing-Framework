"""
CLI-subprocess LLM provider.

Invokes a local agent CLI (Claude Code's ``claude``, OpenAI's ``codex``, or any
command that reads a prompt on stdin and prints a completion on stdout). The
prompt is fed via **stdin** (never interpolated into the argv) to avoid any
shell/argument injection. Uses ``asyncio.create_subprocess_exec`` with a hard
timeout, mirroring the plugin subprocess idiom.

Config:
    llm_cli_command : the binary (default "claude")
    llm_cli_args    : space-separated extra args (default "-p" for print mode)
    llm_cli_timeout : seconds before the call is killed

If the binary is missing or errors, raises ``LLMUnavailableError`` so the caller
can fall back.
"""

from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.core.logging import get_logger
from app.services.llm.provider import LLMProvider, LLMUnavailableError

logger = get_logger(__name__)


class CliProvider(LLMProvider):
    """Generates via a local CLI subprocess."""

    def __init__(self, settings: Settings) -> None:
        self._command = settings.llm_cli_command
        self._args = [a for a in (settings.llm_cli_args or "").split(" ") if a]
        self._timeout = settings.llm_cli_timeout

    @property
    def name(self) -> str:
        return f"cli:{self._command}"

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        full = f"{system.strip()}\n\n{prompt}" if system else prompt
        cmd = [self._command, *self._args]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise LLMUnavailableError(
                f"LLM CLI '{self._command}' not found. Set LLM_CLI_COMMAND or LLM_PROVIDER=none."
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise LLMUnavailableError(f"Failed to launch LLM CLI: {exc}") from exc

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(full.encode("utf-8")), timeout=self._timeout
            )
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise LLMUnavailableError(
                f"LLM CLI timed out after {self._timeout}s."
            ) from exc

        if proc.returncode != 0:
            raise LLMUnavailableError(
                f"LLM CLI exited {proc.returncode}: {stderr.decode(errors='replace')[:200]}"
            )

        text = stdout.decode(errors="replace").strip()
        if not text:
            raise LLMUnavailableError("LLM CLI returned empty output.")
        return text
