"""
GitHub Advisory Database connector.

Pulls reviewed global security advisories from the public GitHub REST API
(https://api.github.com/advisories). The GitHub Advisory Database is licensed
CC-BY 4.0, so entries are redistributable with attribution — we keep each
advisory's canonical ``html_url`` as provenance.

Each advisory carries a real, human-written description (root cause, impact,
remediation), a CWE, a severity, a CVE, and the affected ecosystems/packages —
which map cleanly onto the Writeup schema for tech-stack-filtered retrieval.

An optional ``GITHUB_TOKEN`` raises the rate limit from 60 to 5000 req/hr.
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

_API_URL = "https://api.github.com/advisories"
_PER_PAGE = 100


class GitHubAdvisoryConnector(WriteupConnector):
    """Fetches reviewed advisories from the GitHub Advisory Database."""

    name = "github_advisories"

    async def fetch(self, limit: int = 50) -> list[WriteupIngestInput]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "vulnforge-rag",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = getattr(self._settings, "github_token", None)
        if token:
            headers["Authorization"] = f"Bearer {token}"

        items: list[WriteupIngestInput] = []
        url: str | None = _API_URL
        params: dict[str, Any] | None = {
            "per_page": min(limit, _PER_PAGE),
            "type": "reviewed",
            "sort": "published",
            "direction": "desc",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                while url and len(items) < limit:
                    resp = await client.get(url, params=params, headers=headers)
                    if resp.status_code == 403 and resp.headers.get("x-ratelimit-remaining") == "0":
                        raise WriteupConnectorError(
                            "GitHub API rate limit exceeded. Set GITHUB_TOKEN for a higher limit."
                        )
                    resp.raise_for_status()
                    for advisory in resp.json():
                        mapped = self._map(advisory)
                        if mapped is not None:
                            items.append(mapped)
                            if len(items) >= limit:
                                break
                    # Follow pagination via the Link header; params only on the first call.
                    url = resp.links.get("next", {}).get("url")
                    params = None
        except httpx.HTTPError as exc:
            raise WriteupConnectorError(f"GitHub advisories fetch failed: {exc}") from exc

        logger.info("connector.github_advisories.fetched", count=len(items))
        return items

    def _map(self, advisory: dict[str, Any]) -> WriteupIngestInput | None:
        if advisory.get("withdrawn_at"):
            return None
        summary = (advisory.get("summary") or "").strip()
        description = (advisory.get("description") or "").strip()
        content = description or summary
        if not content:
            return None

        cwes = advisory.get("cwes") or []
        cwe_id = cwes[0].get("cwe_id") if cwes else None

        vulns = advisory.get("vulnerabilities") or []
        tech: list[str] = []
        for v in vulns:
            pkg = v.get("package") or {}
            for key in ("ecosystem", "name"):
                val = pkg.get(key)
                if val and val not in tech:
                    tech.append(val)

        cve_id = advisory.get("cve_id")
        ghsa_id = advisory.get("ghsa_id")
        tags = [t for t in (cve_id, ghsa_id) if t]

        published_at = _parse_dt(advisory.get("published_at"))

        return WriteupIngestInput(
            title=summary or ghsa_id or "GitHub Security Advisory",
            content=content,
            source=WriteupSource.GITHUB,
            source_url=advisory.get("html_url"),
            source_ref=ghsa_id,
            summary=summary or None,
            vuln_class=vuln_class_for_cwe(cwe_id),
            cwe_id=cwe_id,
            severity=advisory.get("severity"),
            tech_stack=tech,
            tags=tags,
            published_at=published_at,
            metadata={
                "cve_id": cve_id,
                "ghsa_id": ghsa_id,
                "references": advisory.get("references") or [],
                "cvss": advisory.get("cvss"),
                "license": "CC-BY-4.0 (GitHub Advisory Database)",
            },
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
