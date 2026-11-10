"""
NVD (National Vulnerability Database) connector.

Pulls recent CVEs from the public NVD CVE API 2.0. NVD data is U.S. government
work (public domain). Without an API key the limit is low (≈5 req/30s), so an
optional ``NVD_API_KEY`` is recommended for larger pulls.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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

_API_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_MAX_PER_PAGE = 2000


class NvdConnector(WriteupConnector):
    """Fetches recent CVEs from the NVD CVE API 2.0."""

    name = "nvd"

    async def fetch(self, limit: int = 50) -> list[WriteupIngestInput]:
        headers = {"User-Agent": "vulnforge-rag"}
        api_key = getattr(self._settings, "nvd_api_key", None)
        if api_key:
            headers["apiKey"] = api_key

        # Constrain to a recent publication window so we get current CVEs
        # (NVD's default order starts at the oldest). Max window is 120 days.
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=120)
        params = {
            "resultsPerPage": min(limit, _MAX_PER_PAGE),
            "startIndex": 0,
            "pubStartDate": start.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "pubEndDate": end.strftime("%Y-%m-%dT%H:%M:%S.000"),
        }
        try:
            async with httpx.AsyncClient(timeout=40) as client:
                resp = await client.get(_API_URL, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise WriteupConnectorError(f"NVD fetch failed: {exc}") from exc

        items: list[WriteupIngestInput] = []
        for entry in data.get("vulnerabilities", []):
            mapped = self._map(entry.get("cve") or {})
            if mapped is not None:
                items.append(mapped)
            if len(items) >= limit:
                break
        logger.info("connector.nvd.fetched", count=len(items))
        return items

    def _map(self, cve: dict[str, Any]) -> WriteupIngestInput | None:
        cve_id = cve.get("id")
        if not cve_id:
            return None
        desc = next(
            (d["value"] for d in cve.get("descriptions", []) if d.get("lang") == "en"),
            "",
        ).strip()
        if not desc:
            return None

        cwe_id = None
        for w in cve.get("weaknesses", []):
            for d in w.get("description", []):
                val = d.get("value", "")
                if val.upper().startswith("CWE-"):
                    cwe_id = val
                    break
            if cwe_id:
                break

        severity = None
        metrics = cve.get("metrics", {})
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if metrics.get(key):
                severity = (metrics[key][0].get("cvssData", {}) or {}).get("baseSeverity")
                break

        return WriteupIngestInput(
            title=f"{cve_id}: {desc[:120]}",
            content=desc,
            source=WriteupSource.OTHER,
            source_url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
            source_ref=cve_id,
            vuln_class=vuln_class_for_cwe(cwe_id),
            cwe_id=cwe_id,
            severity=severity.lower() if severity else None,
            tags=[cve_id, "nvd"],
            published_at=_parse_dt(cve.get("published")),
            metadata={"source": "nvd", "references": cve.get("references", [])},
        )


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
