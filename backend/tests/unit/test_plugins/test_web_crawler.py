"""Unit tests for the Web Crawler plugin's result parsing."""

import json

from app.models.web import HttpMethod, ParameterLocation
from app.plugins.reconnaissance.web_crawler.plugin import WebCrawlerPlugin


def _plugin() -> WebCrawlerPlugin:
    return WebCrawlerPlugin(config={}, target="http://t")


def test_parse_results_maps_endpoints_and_transactions():
    raw = json.dumps({
        "endpoints": [
            {
                "method": "POST", "url": "http://t/login", "status_code": None,
                "content_type": None,
                "parameters": [
                    {"name": "username", "location": "body", "example": ""},
                    {"name": "password", "location": "body", "example": ""},
                ],
            },
            {"method": "GET", "url": "http://t/search", "status_code": 200, "content_type": "text/html",
             "parameters": [{"name": "q", "location": "query", "example": "x"}]},
        ],
        "transactions": [
            {"method": "GET", "url": "http://t/", "status_code": 200,
             "response_headers": {"x": "y"}, "response_body": "hi", "duration_ms": 12,
             "endpoint_url": "http://t/"},
        ],
    })
    parsed = _plugin().parse_results(raw)

    assert len(parsed.endpoints) == 2
    login = next(e for e in parsed.endpoints if e.url.endswith("/login"))
    assert login.method is HttpMethod.POST
    assert {p.name for p in login.parameters} == {"username", "password"}
    assert login.parameters[0].location is ParameterLocation.BODY

    assert len(parsed.transactions) == 1
    assert parsed.transactions[0].status_code == 200
    assert parsed.transactions[0].endpoint_url == "http://t/"


def test_parse_results_handles_empty_and_malformed():
    assert _plugin().parse_results("") == _plugin().parse_results("")
    assert _plugin().parse_results("not json").endpoints == []
    # A malformed endpoint row is skipped, valid ones kept.
    raw = json.dumps({"endpoints": [{"nope": 1}, {"method": "GET", "url": "http://t/ok"}]})
    parsed = _plugin().parse_results(raw)
    assert [e.url for e in parsed.endpoints] == ["http://t/ok"]
