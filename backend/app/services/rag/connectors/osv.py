"""
OSV.dev connector.

OSV has no "recent vulns" list endpoint — it's queried per package — so this
connector sweeps a curated set of widely-used packages across ecosystems and
collects their vulnerabilities (deduplicated within the batch). OSV data is open
(CC-BY-4.0). Many records are GHSA-sourced, so content-hash dedupe naturally
merges any overlap with the github_advisories source.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.core.logging import get_logger
from app.models.writeup import WriteupSource
from app.schemas.writeup import WriteupIngestInput
from app.services.rag.connectors.base import (
    WriteupConnector,
    WriteupConnectorError,
    vuln_class_for_cwe,
)

logger = get_logger(__name__)

_API_URL = "https://api.osv.dev/v1/query"

# A small, broad set of popular packages to sweep. Extend as needed.
_CURATED_PACKAGES: list[tuple[str, str]] = [
    ("PyPI", "django"), ("PyPI", "flask"), ("PyPI", "requests"), ("PyPI", "pyyaml"),
    ("npm", "lodash"), ("npm", "express", ), ("npm", "axios"), ("npm", "next"),
    ("Go", "github.com/gin-gonic/gin"), ("Maven", "org.springframework:spring-core"),
    ("RubyGems", "rails"), ("Packagist", "laravel/framework"),
]


class OsvConnector(WriteupConnector):
    """Sweeps OSV.dev for vulns in a curated package set."""

    name = "osv"

    async def fetch(self, limit: int = 50) -> list[WriteupIngestInput]:
        items: list[WriteupIngestInput] = []
        seen: set[str] = set()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                for ecosystem, name in _CURATED_PACKAGES:
                    if len(items) >= limit:
                        break
                    resp = await client.post(
                        _API_URL,
                        json={"package": {"ecosystem": ecosystem, "name": name}},
                        headers={"User-Agent": "vulnforge-rag"},
                    )
                    if resp.status_code != 200:
                        continue
                    for vuln in resp.json().get("vulns", []):
                        vid = vuln.get("id")
                        if not vid or vid in seen:
                            continue
                        seen.add(vid)
                        mapped = self._map(vuln, ecosystem, name)
                        if mapped is not None:
                            items.append(mapped)
                            if len(items) >= limit:
                                break
        except httpx.HTTPError as exc:
            raise WriteupConnectorError(f"OSV fetch failed: {exc}") from exc

        logger.info("connector.osv.fetched", count=len(items))
        return items

    def _map(self, vuln: dict[str, Any], ecosystem: str, package: str) -> WriteupIngestInput | None:
        vid = vuln.get("id")
        summary = (vuln.get("summary") or "").strip()
        details = (vuln.get("details") or "").strip()
        content = "\n\n".join(p for p in (summary, details) if p)
        if not content:
            return None

        db = vuln.get("database_specific", {}) or {}
        cwe_ids = db.get("cwe_ids") or []
        cwe_id = cwe_ids[0] if cwe_ids else None
        aliases = vuln.get("aliases") or []
        cve = next((a for a in aliases if a.startswith("CVE-")), None)

        return WriteupIngestInput(
            title=summary or vid or "OSV vulnerability",
            content=content,
            source=WriteupSource.OTHER,
            source_url=f"https://osv.dev/vulnerability/{vid}",
            source_ref=vid,
            summary=summary or None,
            vuln_class=vuln_class_for_cwe(cwe_id),
            cwe_id=cwe_id,
            severity=db.get("severity"),
            tech_stack=[ecosystem.lower(), package],
            tags=[t for t in (vid, cve, "osv") if t],
            published_at=_parse_dt(vuln.get("published")),
            metadata={"source": "osv", "ecosystem": ecosystem, "references": vuln.get("references", [])},
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
