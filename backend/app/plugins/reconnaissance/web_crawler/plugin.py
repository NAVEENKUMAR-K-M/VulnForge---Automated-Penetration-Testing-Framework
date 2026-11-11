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
import re
import time
from collections import deque
from typing import Any
from urllib.parse import urljoin, urlparse, urlsplit, parse_qs

import httpx

from app.core.plugin_base import BasePlugin
from app.models.plugin import PluginPhase
from app.models.web import HttpMethod, ParameterLocation, TransactionSource
from app.schemas.plugin import ParsedResults, PluginExecutionResult, PluginManifest
from app.schemas.web import EndpointParameter, HttpEndpointCreate, HttpTransactionCreate

_LINK_RE = re.compile(r"""(?:href|src|action)\s*=\s*["']([^"'#\s>]+)""", re.IGNORECASE)
_FORM_RE = re.compile(r"<form\b([^>]*)>(.*?)</form>", re.IGNORECASE | re.DOTALL)
_METHOD_RE = re.compile(r"""method\s*=\s*["']?([a-zA-Z]+)""", re.IGNORECASE)
_ACTION_RE = re.compile(r"""action\s*=\s*["']([^"']*)""", re.IGNORECASE)
_FIELD_RE = re.compile(
    r"""<(?:input|select|textarea)\b[^>]*\bname\s*=\s*["']([^"']+)""", re.IGNORECASE
)
_BODY_CAP = 20_000


def _canon(url: str, *, drop_query: bool = False) -> str:
    """Canonicalize a URL: drop the fragment, normalize an empty path to '/'."""
    s = urlsplit(url)._replace(fragment="")
    if drop_query:
        s = s._replace(query="")
    if s.path == "":
        s = s._replace(path="/")
    return s.geturl()


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

    def _base_url(self) -> str:
        t = self.target.strip()
        if "://" not in t:
            t = f"http://{t}"
        return t.rstrip("/")

    async def execute(self) -> PluginExecutionResult:
        base = self._base_url()
        base_host = urlparse(base).netloc
        max_pages = int(self.config.get("max_pages", 60))
        max_depth = int(self.config.get("max_depth", 3))
        timeout = float(self.config.get("timeout", 10))
        verify = bool(self.config.get("verify_tls", False))
        ua = str(self.config.get("user_agent", "VulnForge-Crawler/1.0"))

        endpoints: dict[tuple[str, str], dict[str, Any]] = {}
        transactions: list[dict[str, Any]] = []
        visited: set[str] = set()
        frontier: deque[tuple[str, int]] = deque([(base, 0)])

        def _add_endpoint(method: str, url: str, params: list[dict[str, str]],
                          status: int | None = None, content_type: str | None = None) -> None:
            clean = _canon(url)
            key = (method, clean)
            entry = endpoints.setdefault(key, {
                "method": method, "url": clean, "parameters": {},
                "status_code": status, "content_type": content_type,
            })
            if status is not None:
                entry["status_code"] = status
            if content_type is not None:
                entry["content_type"] = content_type
            for p in params:
                entry["parameters"][(p["name"], p["location"])] = p

        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=timeout, verify=verify,
                headers={"User-Agent": ua},
            ) as client:
                while frontier and len(visited) < max_pages:
                    url, depth = frontier.popleft()
                    norm = _canon(url)
                    if norm in visited:
                        continue
                    visited.add(norm)

                    started = time.monotonic()
                    try:
                        resp = await client.get(url)
                    except Exception as exc:  # noqa: BLE001 - a dead link must not abort the crawl
                        self.logger.debug("crawl.fetch_failed", url=url, error=str(exc))
                        continue
                    elapsed = int((time.monotonic() - started) * 1000)

                    body = resp.text or ""
                    ctype = resp.headers.get("content-type", "")

                    # Endpoint for the fetched URL (query params become parameters).
                    q_params = [
                        {"name": name, "location": ParameterLocation.QUERY.value, "example": (vals[0] if vals else "")}
                        for name, vals in parse_qs(urlsplit(url).query).items()
                    ]
                    _add_endpoint("GET", url, q_params, status=resp.status_code, content_type=ctype.split(";")[0] or None)

                    transactions.append({
                        "method": "GET", "url": str(resp.url),
                        "status_code": resp.status_code,
                        "response_headers": dict(resp.headers),
                        "response_body": body[:_BODY_CAP],
                        "duration_ms": elapsed,
                        "endpoint_url": _canon(url, drop_query=True),
                    })

                    if "html" not in ctype.lower():
                        continue

                    # Follow in-scope links.
                    if depth < max_depth:
                        for raw in _LINK_RE.findall(body):
                            nxt = urljoin(str(resp.url), raw)
                            if urlparse(nxt).scheme not in ("http", "https"):
                                continue
                            if urlparse(nxt).netloc != base_host:
                                continue
                            clean = _canon(nxt)
                            if clean not in visited:
                                frontier.append((clean, depth + 1))

                    # Parse forms into endpoints with their input parameters.
                    for attrs, inner in _FORM_RE.findall(body):
                        m = _METHOD_RE.search(attrs)
                        method = (m.group(1).upper() if m else "GET")
                        if method not in HttpMethod.__members__:
                            method = "GET"
                        a = _ACTION_RE.search(attrs)
                        action = urljoin(str(resp.url), a.group(1)) if (a and a.group(1)) else str(resp.url)
                        if urlparse(action).netloc != base_host:
                            continue
                        loc = ParameterLocation.BODY.value if method != "GET" else ParameterLocation.QUERY.value
                        fields = [{"name": n, "location": loc, "example": ""} for n in _FIELD_RE.findall(inner)]
                        _add_endpoint(method, action, fields)
        except Exception as exc:  # noqa: BLE001
            return PluginExecutionResult(success=False, raw_output="", error_message=str(exc))

        # Flatten the parameter maps for serialization.
        out_endpoints = []
        for e in endpoints.values():
            out_endpoints.append({
                "method": e["method"], "url": e["url"],
                "status_code": e["status_code"], "content_type": e["content_type"],
                "parameters": list(e["parameters"].values()),
            })

        payload = json.dumps({"endpoints": out_endpoints, "transactions": transactions})
        self.logger.info("crawl.done", pages=len(visited), endpoints=len(out_endpoints))
        return PluginExecutionResult(success=True, raw_output=payload)

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
