"""
OWASP Web Security Testing Guide (WSTG) connector — the *methodology* source.

Pulls the WSTG testing chapters (markdown) from the public OWASP/wstg GitHub
repo. WSTG is licensed CC-BY-SA 4.0 (redistributable with attribution). Unlike
the advisory/CVE sources, these describe *how to test for* each bug class — the
hunting methodology that advisories don't capture. Uses ``GITHUB_TOKEN`` for a
higher rate limit if set.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.logging import get_logger
from app.models.writeup import WriteupSource
from app.schemas.writeup import WriteupIngestInput
from app.services.rag.connectors.base import WriteupConnector, WriteupConnectorError

logger = get_logger(__name__)

_CONTENTS_API = (
    "https://api.github.com/repos/OWASP/wstg/contents/"
    "document/4-Web_Application_Security_Testing"
)


class WstgConnector(WriteupConnector):
    """Fetches OWASP WSTG testing chapters as methodology writeups."""

    name = "wstg"

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/vnd.github+json", "User-Agent": "vulnforge-rag"}
        token = getattr(self._settings, "github_token", None)
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    async def fetch(self, limit: int = 50) -> list[WriteupIngestInput]:
        items: list[WriteupIngestInput] = []
        try:
            async with httpx.AsyncClient(timeout=30, headers=self._headers()) as client:
                files = await self._walk(client, _CONTENTS_API, limit)
                for entry, category in files:
                    if len(items) >= limit:
                        break
                    raw = await client.get(entry["download_url"])
                    if raw.status_code != 200 or not raw.text.strip():
                        continue
                    items.append(self._map(entry, category, raw.text))
        except httpx.HTTPError as exc:
            raise WriteupConnectorError(f"WSTG fetch failed: {exc}") from exc

        logger.info("connector.wstg.fetched", count=len(items))
        return items

    async def _walk(
        self, client: httpx.AsyncClient, url: str, limit: int, category: str = ""
    ) -> list[tuple[dict[str, Any], str]]:
        """Recursively collect markdown file entries, tagged by top category."""
        resp = await client.get(url)
        resp.raise_for_status()
        out: list[tuple[dict[str, Any], str]] = []
        for entry in resp.json():
            if len(out) >= limit:
                break
            if entry["type"] == "dir":
                cat = category or entry["name"]
                out.extend(await self._walk(client, entry["url"], limit - len(out), cat))
            elif entry["type"] == "file" and entry["name"].lower().endswith(".md"):
                if entry["name"].lower() == "readme.md":
                    continue
                out.append((entry, category))
        return out

    def _map(self, entry: dict[str, Any], category: str, markdown: str) -> WriteupIngestInput:
        title = _first_heading(markdown) or entry["name"].replace(".md", "").replace("_", " ")
        cat_label = category.split("-", 1)[-1].replace("_", " ") if category else "WSTG"
        return WriteupIngestInput(
            title=f"WSTG: {title}",
            content=markdown,
            source=WriteupSource.OTHER,
            source_url=entry.get("html_url"),
            source_ref=entry["name"],
            summary=f"OWASP WSTG methodology — {cat_label}",
            tags=["methodology", "owasp-wstg", category] if category else ["methodology", "owasp-wstg"],
            metadata={"source": "owasp-wstg", "category": category, "license": "CC-BY-SA-4.0"},
        )


def _first_heading(markdown: str) -> str | None:
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return None
