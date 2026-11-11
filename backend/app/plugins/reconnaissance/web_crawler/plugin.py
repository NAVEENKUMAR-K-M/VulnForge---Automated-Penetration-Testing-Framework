"""
Web Crawler plugin for VulnForge.

A bounded, same-host async spider (Python httpx — no external binary) that maps
an application's request surface: pages, links and HTML forms. It emits
HttpEndpoint records (with their query/body parameters) and HttpTransaction
evidence, which downstream active testers (DAST, the agent) consume.

Safety: stays on the target host, obeys page/depth caps and per-request
timeouts. The scan engine has already scope-checked the target before this runs.
"""

from __future__ import annotations

import json

from app.core.plugin_base import BasePlugin
from app.models.plugin import PluginPhase
from app.models.web import HttpMethod, ParameterLocation, TransactionSource
from app.plugins.reconnaissance.web_crawler.crawler import crawl_site
from app.schemas.plugin import ParsedResults, PluginExecutionResult, PluginManifest
from app.schemas.web import EndpointParameter, HttpEndpointCreate, HttpTransactionCreate


class WebCrawlerPlugin(BasePlugin):
    """Maps the web request surface and captures evidence."""

    manifest = PluginManifest(
        name="web_crawler",
        display_name="Web Crawler",
        description="Spiders a web application to map endpoints, parameters and forms.",
        version="1.0.0",
        phase=PluginPhase.RECONNAISSANCE,
        default_config={
            "max_pages": 60,
            "max_depth": 3,
            "timeout": 10,
            "verify_tls": False,
            "user_agent": "VulnForge-Crawler/1.0",
        },
        plugin_metadata={"author": "VulnForge", "requires": "python-httpx"},
    )

    async def check_dependencies(self) -> bool:
        return True  # pure-Python (httpx is a core dependency)

    async def execute(self) -> PluginExecutionResult:
        try:
            endpoints, transactions = await crawl_site(
                self.target,
                max_pages=int(self.config.get("max_pages", 60)),
                max_depth=int(self.config.get("max_depth", 3)),
                timeout=float(self.config.get("timeout", 10)),
                verify_tls=bool(self.config.get("verify_tls", False)),
                user_agent=str(self.config.get("user_agent", "VulnForge-Crawler/1.0")),
            )
        except Exception as exc:  # noqa: BLE001
            return PluginExecutionResult(success=False, raw_output="", error_message=str(exc))

        self.logger.info("crawl.done", endpoints=len(endpoints), transactions=len(transactions))
        return PluginExecutionResult(
            success=True, raw_output=json.dumps({"endpoints": endpoints, "transactions": transactions})
        )

    def parse_results(self, raw_output: str) -> ParsedResults:
        try:
            data = json.loads(raw_output) if raw_output else {}
        except json.JSONDecodeError:
            return ParsedResults()

        endpoints: list[HttpEndpointCreate] = []
        for e in data.get("endpoints", []):
            try:
                endpoints.append(HttpEndpointCreate(
                    method=HttpMethod(e.get("method", "GET")),
                    url=e["url"],
                    status_code=e.get("status_code"),
                    content_type=e.get("content_type"),
                    source_tool=self.manifest.name,
                    parameters=[
                        EndpointParameter(
                            name=p["name"],
                            location=ParameterLocation(p.get("location", "query")),
                            example=p.get("example") or None,
                        )
                        for p in e.get("parameters", [])
                    ],
                ))
            except Exception:  # noqa: BLE001 - skip malformed rows, keep the rest
                continue

        transactions: list[HttpTransactionCreate] = []
        for t in data.get("transactions", []):
            try:
                transactions.append(HttpTransactionCreate(
                    source=TransactionSource.CRAWLER,
                    method=HttpMethod(t.get("method", "GET")),
                    url=t["url"],
                    status_code=t.get("status_code"),
                    response_headers=t.get("response_headers", {}),
                    response_body=t.get("response_body"),
                    duration_ms=t.get("duration_ms"),
                    endpoint_url=t.get("endpoint_url"),
                ))
            except Exception:  # noqa: BLE001
                continue

        return ParsedResults(endpoints=endpoints, transactions=transactions)
