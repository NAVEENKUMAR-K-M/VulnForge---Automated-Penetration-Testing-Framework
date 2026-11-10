"""Unit tests for NVD/OSV/WSTG/curated connector mapping (no network)."""

from __future__ import annotations

from app.core.config import get_settings
from app.models.writeup import WriteupSource
from app.services.rag.connectors.curated import CuratedConnector
from app.services.rag.connectors.nvd import NvdConnector
from app.services.rag.connectors.osv import OsvConnector
from app.services.rag.connectors.wstg import _first_heading


def _s():
    return get_settings()


class TestNvdMapping:
    def test_maps_cve(self) -> None:
        cve = {
            "id": "CVE-2026-1234",
            "descriptions": [{"lang": "en", "value": "SSRF in the import feature."}],
            "weaknesses": [{"description": [{"value": "CWE-918"}]}],
            "metrics": {"cvssMetricV31": [{"cvssData": {"baseSeverity": "CRITICAL"}}]},
            "published": "2026-05-01T00:00:00.000",
        }
        item = NvdConnector(_s())._map(cve)
        assert item is not None
        assert item.cwe_id == "CWE-918"
        assert item.vuln_class == "ssrf"
        assert item.severity == "critical"
        assert item.source_url.endswith("CVE-2026-1234")
        assert "CVE-2026-1234" in item.tags

    def test_no_description_skipped(self) -> None:
        assert NvdConnector(_s())._map({"id": "CVE-X", "descriptions": []}) is None


class TestOsvMapping:
    def test_maps_vuln(self) -> None:
        vuln = {
            "id": "GHSA-aaaa-bbbb-cccc",
            "summary": "SQL injection in example",
            "details": "Longer markdown details here.",
            "database_specific": {"cwe_ids": ["CWE-89"], "severity": "HIGH"},
            "aliases": ["CVE-2026-9999"],
            "published": "2026-01-02T00:00:00Z",
        }
        item = OsvConnector(_s())._map(vuln, "PyPI", "example")
        assert item is not None
        assert item.vuln_class == "sqli"
        assert item.tech_stack == ["pypi", "example"]
        assert "CVE-2026-9999" in item.tags
        assert item.source_url.endswith("GHSA-aaaa-bbbb-cccc")

    def test_empty_skipped(self) -> None:
        assert OsvConnector(_s())._map({"id": "x"}, "npm", "y") is None


class TestCuratedMapping:
    def test_maps_entry(self) -> None:
        entry = {
            "title": "IDOR checklist",
            "content": "step by step",
            "vuln_class": "idor",
            "cwe_id": "CWE-639",
            "tech_stack": ["api"],
        }
        item = CuratedConnector(_s())._map(entry)
        assert item is not None
        assert item.source is WriteupSource.MANUAL
        assert item.vuln_class == "idor"

    def test_missing_fields_skipped(self) -> None:
        assert CuratedConnector(_s())._map({"title": "x"}) is None
        assert CuratedConnector(_s())._map({"content": "x"}) is None


class TestWstgHeading:
    def test_extracts_first_h1(self) -> None:
        assert _first_heading("intro\n\n# Testing for XSS\n\nbody") == "Testing for XSS"

    def test_none_when_no_heading(self) -> None:
        assert _first_heading("no heading here\n## sub only") is None
