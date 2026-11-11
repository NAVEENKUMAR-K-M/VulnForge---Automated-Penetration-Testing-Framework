"""
Unit tests for target validators.

Tests every valid and invalid case for each validator function.
No database — pure Python.

Markers: @pytest.mark.unit
"""

from __future__ import annotations

import pytest

from app.utils.target_validators import (
    validate_domain,
    validate_host,
    validate_network,
    validate_tag,
    validate_target_value,
    validate_url,
)


# ── Host Validator ────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestValidateHost:
    """Tests for validate_host()."""

    # Valid cases
    def test_valid_ipv4(self) -> None:
        assert validate_host("192.168.1.100") == "192.168.1.100"

    def test_valid_ipv4_leading_trailing_whitespace(self) -> None:
        assert validate_host("  10.0.0.1  ") == "10.0.0.1"

    def test_valid_ipv4_private(self) -> None:
        assert validate_host("172.16.0.1") == "172.16.0.1"

    def test_valid_ipv6_full(self) -> None:
        assert validate_host("2001:0db8:0000:0000:0000:0000:0000:0001") == "2001:db8::1"

    def test_valid_ipv6_compressed(self) -> None:
        assert validate_host("2001:db8::1") == "2001:db8::1"

    def test_valid_ipv6_loopback(self) -> None:
        # Loopback is valid (pentesters may test internal services)
        assert validate_host("::1") == "::1"

    # Invalid cases
    def test_rejects_cidr_notation(self) -> None:
        with pytest.raises(ValueError, match="network"):
            validate_host("192.168.1.0/24")

    def test_rejects_multicast_ipv4(self) -> None:
        with pytest.raises(ValueError, match="multicast"):
            validate_host("224.0.0.1")

    def test_rejects_multicast_ipv6(self) -> None:
        with pytest.raises(ValueError, match="multicast"):
            validate_host("ff02::1")

    def test_rejects_unspecified_ipv4(self) -> None:
        with pytest.raises(ValueError, match="unspecified"):
            validate_host("0.0.0.0")

    def test_rejects_unspecified_ipv6(self) -> None:
        with pytest.raises(ValueError, match="unspecified"):
            validate_host("::")

    def test_rejects_domain_name(self) -> None:
        with pytest.raises(ValueError):
            validate_host("example.com")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            validate_host("")

    def test_rejects_url(self) -> None:
        with pytest.raises(ValueError):
            validate_host("https://192.168.1.1")


# ── Network Validator ─────────────────────────────────────────────────────────

@pytest.mark.unit
class TestValidateNetwork:
    """Tests for validate_network()."""

    # Valid cases
    def test_valid_ipv4_cidr(self) -> None:
        assert validate_network("10.0.0.0/24") == "10.0.0.0/24"

    def test_valid_ipv4_host_bits_zeroed(self) -> None:
        # Host bits stripped → canonical form
        assert validate_network("192.168.1.5/24") == "192.168.1.0/24"

    def test_valid_ipv4_slash32(self) -> None:
        assert validate_network("192.168.1.1/32") == "192.168.1.1/32"

    def test_valid_ipv4_slash8(self) -> None:
        assert validate_network("10.0.0.0/8") == "10.0.0.0/8"

    def test_valid_ipv6_cidr(self) -> None:
        assert validate_network("2001:db8::/32") == "2001:db8::/32"

    def test_valid_ipv6_slash16(self) -> None:
        assert validate_network("2001::/16") == "2001::/16"

    def test_strips_whitespace(self) -> None:
        assert validate_network(" 10.0.0.0/16 ") == "10.0.0.0/16"

    # Invalid cases
    def test_rejects_no_prefix(self) -> None:
        with pytest.raises(ValueError, match="prefix length"):
            validate_network("192.168.1.0")

    def test_rejects_slash0_ipv4(self) -> None:
        with pytest.raises(ValueError, match="entire internet"):
            validate_network("0.0.0.0/0")

    def test_rejects_small_prefix_ipv4(self) -> None:
        # /7 is too broad — IPv4 targets must be /8 or smaller
        with pytest.raises(ValueError, match=r"/8 or smaller"):
            validate_network("10.0.0.0/7")

    def test_rejects_small_prefix_ipv6(self) -> None:
        with pytest.raises(ValueError, match="too broad"):
            validate_network("2001::/15")

    def test_rejects_multicast_range(self) -> None:
        with pytest.raises(ValueError, match="multicast"):
            validate_network("224.0.0.0/8")

    def test_rejects_garbage(self) -> None:
        with pytest.raises(ValueError):
            validate_network("not-a-cidr")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            validate_network("")


# ── URL Validator ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestValidateUrl:
    """Tests for validate_url()."""

    # Valid cases
    def test_valid_https(self) -> None:
        assert validate_url("https://example.com") == "https://example.com"

    def test_valid_http(self) -> None:
        assert validate_url("http://192.168.1.1:8080") == "http://192.168.1.1:8080"

    def test_valid_with_path(self) -> None:
        result = validate_url("https://app.example.com/api/v1")
        assert result == "https://app.example.com/api/v1"

    def test_valid_with_query_string(self) -> None:
        result = validate_url("https://example.com/search?q=test&page=1")
        assert "example.com" in result

    def test_lowercases_scheme(self) -> None:
        result = validate_url("HTTPS://example.com")
        assert result.startswith("https://")

    def test_strips_whitespace(self) -> None:
        result = validate_url("  https://example.com  ")
        assert result == "https://example.com"

    # Invalid cases
    def test_rejects_missing_scheme(self) -> None:
        with pytest.raises(ValueError, match="scheme"):
            validate_url("example.com")

    def test_rejects_ftp_scheme(self) -> None:
        with pytest.raises(ValueError, match="not supported"):
            validate_url("ftp://example.com")

    def test_rejects_file_scheme(self) -> None:
        with pytest.raises(ValueError, match="not supported"):
            validate_url("file:///etc/passwd")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            validate_url("")


# ── Domain Validator ──────────────────────────────────────────────────────────

@pytest.mark.unit
class TestValidateDomain:
    """Tests for validate_domain()."""

    # Valid cases
    def test_valid_bare_domain(self) -> None:
        assert validate_domain("example.com") == "example.com"

    def test_valid_subdomain(self) -> None:
        assert validate_domain("api.example.com") == "api.example.com"

    def test_valid_deep_subdomain(self) -> None:
        assert validate_domain("dev.api.internal.example.com") == "dev.api.internal.example.com"

    def test_valid_wildcard(self) -> None:
        assert validate_domain("*.example.com") == "*.example.com"

    def test_normalises_to_lowercase(self) -> None:
        assert validate_domain("Example.COM") == "example.com"

    def test_strips_whitespace(self) -> None:
        assert validate_domain("  example.com  ") == "example.com"

    def test_valid_numeric_tld(self) -> None:
        # Technically valid RFC 1123
        assert validate_domain("example.io") == "example.io"

    def test_valid_hyphenated_label(self) -> None:
        assert validate_domain("my-service.example.com") == "my-service.example.com"

    # Invalid cases
    def test_rejects_single_label(self) -> None:
        with pytest.raises(ValueError, match="single-label"):
            validate_domain("localhost")

    def test_rejects_ip_address(self) -> None:
        with pytest.raises(ValueError, match="IP address"):
            validate_domain("192.168.1.1")

    def test_rejects_url_with_scheme(self) -> None:
        with pytest.raises(ValueError, match="URL"):
            validate_domain("https://example.com")

    def test_rejects_label_starting_with_hyphen(self) -> None:
        with pytest.raises(ValueError):
            validate_domain("-example.com")

    def test_rejects_label_ending_with_hyphen(self) -> None:
        with pytest.raises(ValueError):
            validate_domain("example-.com")

    def test_rejects_label_too_long(self) -> None:
        long_label = "a" * 64
        with pytest.raises(ValueError, match="63 characters"):
            validate_domain(f"{long_label}.com")

    def test_rejects_double_dot(self) -> None:
        with pytest.raises(ValueError, match="empty label"):
            validate_domain("example..com")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            validate_domain("")


# ── Tag Validator ─────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestValidateTag:
    """Tests for validate_tag()."""

    def test_valid_simple_tag(self) -> None:
        assert validate_tag("production") == "production"

    def test_valid_hyphenated(self) -> None:
        assert validate_tag("web-app") == "web-app"

    def test_valid_underscored(self) -> None:
        assert validate_tag("internal_api") == "internal_api"

    def test_normalises_to_lowercase(self) -> None:
        assert validate_tag("Production") == "production"

    def test_strips_whitespace(self) -> None:
        assert validate_tag("  external  ") == "external"

    def test_single_char(self) -> None:
        assert validate_tag("a") == "a"

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            validate_tag("")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError, match="50 characters"):
            validate_tag("a" * 51)

    def test_rejects_special_chars(self) -> None:
        with pytest.raises(ValueError, match="invalid characters"):
            validate_tag("bad@tag")

    def test_rejects_spaces_inside(self) -> None:
        with pytest.raises(ValueError):
            validate_tag("has space")

    def test_rejects_leading_hyphen(self) -> None:
        with pytest.raises(ValueError):
            validate_tag("-starts-with-hyphen")


# ── Dispatcher ────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestDispatcher:
    """Tests for validate_target_value() dispatcher."""

    def test_dispatches_host(self) -> None:
        assert validate_target_value("host", "10.0.0.1") == "10.0.0.1"

    def test_dispatches_network(self) -> None:
        assert validate_target_value("network", "10.0.0.0/24") == "10.0.0.0/24"

    def test_dispatches_url(self) -> None:
        assert validate_target_value("url", "https://example.com") == "https://example.com"

    def test_dispatches_domain(self) -> None:
        assert validate_target_value("domain", "example.com") == "example.com"

    def test_rejects_unknown_type(self) -> None:
        with pytest.raises(ValueError, match="Unknown target type"):
            validate_target_value("invalid_type", "example.com")

    def test_case_insensitive_type(self) -> None:
        assert validate_target_value("HOST", "10.0.0.1") == "10.0.0.1"
        assert validate_target_value("DOMAIN", "example.com") == "example.com"
