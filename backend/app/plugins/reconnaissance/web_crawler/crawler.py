"""
Shared same-host crawl routine used by the Web Crawler plugin and the active
web scanner. Returns plain dicts so callers map them to their own schemas.
"""

from __future__ import annotations

import re
import time
from collections import deque
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse, urlsplit

import httpx

_LINK_RE = re.compile(r"""(?:href|src|action)\s*=\s*["']([^"'#\s>]+)""", re.IGNORECASE)
_FORM_RE = re.compile(r"<form\b([^>]*)>(.*?)</form>", re.IGNORECASE | re.DOTALL)
_METHOD_RE = re.compile(r"""method\s*=\s*["']?([a-zA-Z]+)""", re.IGNORECASE)
_ACTION_RE = re.compile(r"""action\s*=\s*["']([^"']*)""", re.IGNORECASE)
_FIELD_RE = re.compile(
    r"""<(?:input|select|textarea)\b[^>]*\bname\s*=\s*["']([^"']+)""", re.IGNORECASE
)
_BODY_CAP = 20_000
_VALID_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"}


def canon(url: str, *, drop_query: bool = False) -> str:
    """Canonicalize a URL: drop the fragment, normalize an empty path to '/'."""
    s = urlsplit(url)._replace(fragment="")
    if drop_query:
        s = s._replace(query="")
    if s.path == "":
        s = s._replace(path="/")
    return s.geturl()


def normalize_base(target: str) -> str:
    t = target.strip()
    if "://" not in t:
        t = f"http://{t}"
    return t.rstrip("/")


def make_client(
    *, timeout: float, verify_tls: bool, user_agent: str,
    auth: dict[str, Any] | None = None, follow_redirects: bool = True,
) -> httpx.AsyncClient:
    """Build an httpx client, carrying any static auth (headers + cookies).

    ``auth`` may contain ``headers`` and ``cookies`` dicts (applied to every
    request) and form-login fields consumed by :func:`apply_auth`.
    """
    headers: dict[str, str] = {"User-Agent": user_agent}
    cookies: dict[str, str] | None = None
    if auth:
        headers.update({str(k): str(v) for k, v in (auth.get("headers") or {}).items()})
        cookies = {str(k): str(v) for k, v in (auth.get("cookies") or {}).items()} or None
    return httpx.AsyncClient(
        follow_redirects=follow_redirects, timeout=timeout, verify=verify_tls,
        headers=headers, cookies=cookies,
    )


async def apply_auth(client: httpx.AsyncClient, auth: dict[str, Any] | None) -> bool:
    """Perform a form login if configured, so session cookies stick to ``client``.

    ``auth`` shape (all optional): ``login_url``, ``login_method`` (POST),
    ``login_data`` (the credentials/fields to submit). Returns True if a login
    request was attempted and did not error. Static headers/cookies are applied
    at client creation, so no login request is needed for those.
    """
    if not auth or not auth.get("login_url"):
        return False
    method = str(auth.get("login_method") or "POST").upper()
    data = {**(auth.get("login_data") or {})}
    try:
        if method == "GET":
            await client.get(auth["login_url"], params=data)
        else:
            await client.request(method, auth["login_url"], data=data)
        return True
    except Exception:  # noqa: BLE001 - a failed login must not abort the scan
        return False


async def crawl_site(
    target: str,
    *,
    max_pages: int = 60,
    max_depth: int = 3,
    timeout: float = 10.0,
    verify_tls: bool = False,
    user_agent: str = "VulnForge-Crawler/1.0",
    auth: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Spider ``target`` (same host only) and return (endpoints, transactions).

    Endpoints are ``{method, url, status_code, content_type, parameters}`` where
    each parameter is ``{name, location, example}``. Transactions are captured
    GET fetches with response metadata and a body snippet.
    """
    base = normalize_base(target)
    base_host = urlparse(base).netloc

    endpoints: dict[tuple[str, str], dict[str, Any]] = {}
    transactions: list[dict[str, Any]] = []
    visited: set[str] = set()
    frontier: deque[tuple[str, int]] = deque([(base, 0)])

    def _add_endpoint(method: str, url: str, params: list[dict[str, str]],
                      status: int | None = None, content_type: str | None = None) -> None:
        clean = canon(url)
        entry = endpoints.setdefault(
            (method, clean),
            {"method": method, "url": clean, "parameters": {}, "status_code": status, "content_type": content_type},
        )
        if status is not None:
            entry["status_code"] = status
        if content_type is not None:
            entry["content_type"] = content_type
        for p in params:
            entry["parameters"][(p["name"], p["location"])] = p

    async with make_client(
        timeout=timeout, verify_tls=verify_tls, user_agent=user_agent, auth=auth,
    ) as client:
        await apply_auth(client, auth)
        while frontier and len(visited) < max_pages:
            url, depth = frontier.popleft()
            norm = canon(url)
            if norm in visited:
                continue
            visited.add(norm)

            started = time.monotonic()
            try:
                resp = await client.get(url)
            except Exception:  # noqa: BLE001 - a dead link must not abort the crawl
                continue
            elapsed = int((time.monotonic() - started) * 1000)

            body = resp.text or ""
            ctype = resp.headers.get("content-type", "")
            q_params = [
                {"name": name, "location": "query", "example": (vals[0] if vals else "")}
                for name, vals in parse_qs(urlsplit(url).query).items()
            ]
            _add_endpoint("GET", url, q_params, status=resp.status_code, content_type=ctype.split(";")[0] or None)

            transactions.append({
                "method": "GET", "url": str(resp.url), "status_code": resp.status_code,
                "response_headers": dict(resp.headers), "response_body": body[:_BODY_CAP],
                "duration_ms": elapsed, "endpoint_url": canon(url, drop_query=True),
            })

            if "html" not in ctype.lower():
                continue

            if depth < max_depth:
                for raw in _LINK_RE.findall(body):
                    nxt = urljoin(str(resp.url), raw)
                    pr = urlparse(nxt)
                    if pr.scheme not in ("http", "https") or pr.netloc != base_host:
                        continue
                    clean = canon(nxt)
                    if clean not in visited:
                        frontier.append((clean, depth + 1))

            for attrs, inner in _FORM_RE.findall(body):
                m = _METHOD_RE.search(attrs)
                method = (m.group(1).upper() if m else "GET")
                if method not in _VALID_METHODS:
                    method = "GET"
                a = _ACTION_RE.search(attrs)
                action = urljoin(str(resp.url), a.group(1)) if (a and a.group(1)) else str(resp.url)
                if urlparse(action).netloc != base_host:
                    continue
                loc = "body" if method != "GET" else "query"
                fields = [{"name": n, "location": loc, "example": ""} for n in _FIELD_RE.findall(inner)]
                _add_endpoint(method, action, fields)

    out_endpoints = [
        {"method": e["method"], "url": e["url"], "status_code": e["status_code"],
         "content_type": e["content_type"], "parameters": list(e["parameters"].values())}
        for e in endpoints.values()
    ]
    return out_endpoints, transactions
