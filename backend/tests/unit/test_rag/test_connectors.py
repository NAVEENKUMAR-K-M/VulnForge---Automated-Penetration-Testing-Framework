"""Unit tests for source connectors (mapping only — no network)."""

from __future__ import annotations

from app.core.config import get_settings
from app.models.writeup import WriteupSource
from app.services.rag.connectors.base import vuln_class_for_cwe
from app.services.rag.connectors.github_advisories import GitHubAdvisoryConnector

_SAMPLE_ADVISORY = {
    "ghsa_id": "GHSA-xxxx-yyyy-zzzz",
    "cve_id": "CVE-2026-0001",
    "summary": "SQL injection in example package search",
    "description": "A detailed description of the root cause, impact, and fix.",
    "severity": "high",
    "html_url": "https://github.com/advisories/GHSA-xxxx-yyyy-zzzz",
    "published_at": "2026-05-01T12:00:00Z",
    "withdrawn_at": None,
    "cwes": [{"cwe_id": "CWE-89", "name": "SQL Injection"}],
    "references": [{"url": "https://example.com/ref"}],
    "vulnerabilities": [
        {"package": {"ecosystem": "npm", "name": "example-pkg"}},
        {"package": {"ecosystem": "npm", "name": "example-pkg"}},
    ],
}


class TestCweMapping:
    def test_known_cwe(self) -> None:
        assert vuln_class_for_cwe("CWE-89") == "sqli"
        assert vuln_class_for_cwe("cwe-79") == "xss"
        assert vuln_class_for_cwe("CWE-918") == "ssrf"

    def test_unknown_or_none(self) -> None:
        assert vuln_class_for_cwe("CWE-99999") is None
        assert vuln_class_for_cwe(None) is None


class TestGitHubAdvisoryMapping:
    def _conn(self) -> GitHubAdvisoryConnector:
        return GitHubAdvisoryConnector(get_settings())

    def test_maps_core_fields(self) -> None:
        item = self._conn()._map(_SAMPLE_ADVISORY)
        assert item is not None
        assert item.source is WriteupSource.GITHUB
        assert item.source_url.endswith("GHSA-xxxx-yyyy-zzzz")
        assert item.source_ref == "GHSA-xxxx-yyyy-zzzz"
        assert item.cwe_id == "CWE-89"
        assert item.vuln_class == "sqli"
        assert item.severity == "high"
        assert "CVE-2026-0001" in item.tags
        assert item.published_at is not None

    def test_tech_stack_deduped(self) -> None:
        item = self._conn()._map(_SAMPLE_ADVISORY)
        assert item is not None
        # ecosystem + package name, no duplicates
        assert item.tech_stack == ["npm", "example-pkg"]

    def test_withdrawn_skipped(self) -> None:
        advisory = {**_SAMPLE_ADVISORY, "withdrawn_at": "2026-06-01T00:00:00Z"}
        assert self._conn()._map(advisory) is None

    def test_empty_content_skipped(self) -> None:
        advisory = {**_SAMPLE_ADVISORY, "summary": "", "description": ""}
        assert self._conn()._map(advisory) is None
