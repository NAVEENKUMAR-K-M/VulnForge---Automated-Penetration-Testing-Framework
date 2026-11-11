"""Unit tests for the Active Web Scanner's result parsing + detection builders."""

import json

from app.models.vulnerability import VulnerabilitySeverity
from app.models.web import TransactionSource
from app.plugins.vulnerability_scanning.web_active_scan.plugin import WebActiveScanPlugin


def _plugin() -> WebActiveScanPlugin:
    return WebActiveScanPlugin(config={}, target="http://t")


def test_parse_results_builds_vulns_and_evidence():
    raw = json.dumps({
        "findings": [
            {
                "title": "SQL Injection (error-based) in `id` parameter",
                "description": "db error surfaced",
                "severity": "critical", "cwe_id": "CWE-89",
                "affected_host": "t", "affected_path": "/item",
                "proof_of_concept": "GET /item?id=1'", "remediation": "params",
            },
        ],
        "evidence": [
            {"method": "GET", "url": "http://t/item?id=1'", "status_code": 500,
             "response_headers": {}, "response_body": "SQL error", "duration_ms": 9,
             "notes": "SQLi", "endpoint_url": "http://t/item"},
        ],
    })
    parsed = _plugin().parse_results(raw)

    assert len(parsed.vulnerabilities) == 1
    v = parsed.vulnerabilities[0]
    assert v.severity is VulnerabilitySeverity.CRITICAL
    assert v.cwe_id == "CWE-89"
    assert v.affected_path == "/item"

    assert len(parsed.transactions) == 1
    assert parsed.transactions[0].source is TransactionSource.DAST
    assert parsed.transactions[0].status_code == 500


def test_parse_results_skips_malformed_and_empty():
    assert _plugin().parse_results("").vulnerabilities == []
    assert _plugin().parse_results("junk").vulnerabilities == []
    raw = json.dumps({"findings": [{"bad": 1}, {
        "title": "x", "description": "y", "severity": "low"}]})
    parsed = _plugin().parse_results(raw)
    assert [v.title for v in parsed.vulnerabilities] == ["x"]
