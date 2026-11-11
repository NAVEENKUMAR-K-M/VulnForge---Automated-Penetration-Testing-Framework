"""Unit tests for the shared web auth helpers (static creds + form login)."""

import pytest

from app.plugins.reconnaissance.web_crawler.crawler import apply_auth, make_client


def test_make_client_applies_static_headers_and_cookies():
    client = make_client(
        timeout=5, verify_tls=False, user_agent="UA",
        auth={"headers": {"Authorization": "Bearer t0ken"}, "cookies": {"session": "abc"}},
    )
    try:
        assert client.headers["authorization"] == "Bearer t0ken"
        assert client.headers["user-agent"] == "UA"
        assert client.cookies.get("session") == "abc"
    finally:
        pass  # client is not opened; nothing to close


def test_make_client_without_auth_is_fine():
    client = make_client(timeout=5, verify_tls=False, user_agent="UA", auth=None)
    assert client.headers["user-agent"] == "UA"


@pytest.mark.asyncio
async def test_apply_auth_noop_without_login_url():
    client = make_client(timeout=5, verify_tls=False, user_agent="UA", auth=None)
    async with client:
        assert await apply_auth(client, None) is False
        assert await apply_auth(client, {}) is False
        assert await apply_auth(client, {"headers": {"x": "y"}}) is False  # static-only, no login
