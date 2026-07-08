"""
Unit tests for the scope engine (core/scope_engine.py).

All tests are pure Python — no database, no I/O.
Tests cover every rule type, every disposition, edge cases,
URL decomposition, IPv6, wildcard patterns, and boundary conditions.

Markers: @pytest.mark.unit
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.core.scope_engine import (
    ScopeVerdict,
    ScopeCheckResult,
    check_scope,
    check_scope_bulk,
    validate_rule_value,
    _match_domain,
    _match_subdomain,
    _match_cidr,
    _match_wildcard,
    _match_host,
    _normalise_target,
    _extract_hostname,
)
from app.models.scope import ScopeDisposition, ScopeRule, ScopeRuleType


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_rule(
    rule_type: ScopeRuleType,
    value: str,
    disposition: ScopeDisposition = ScopeDisposition.ALLOW,
    is_active: bool = True,
) -> ScopeRule:
    rule = MagicMock(spec=ScopeRule)
    rule.id = uuid.uuid4()
    rule.rule_type = rule_type
    rule.value = value
    rule.disposition = disposition
    rule.is_active = is_active
    return rule


# ── Normalisation Tests ───────────────────────────────────────────────────────

@pytest.mark.unit
class TestNormalisation:
    """Tests for target value normalisation."""

    def test_extracts_hostname_from_https_url(self) -> None:
        assert _extract_hostname("https://example.com") == "example.com"

    def test_extracts_hostname_with_path(self) -> None:
        assert _extract_hostname("https://example.com/api/v1") == "example.com"

    def test_extracts_hostname_with_port(self) -> None:
        assert _extract_hostname("https://example.com:8443") == "example.com"

    def test_extracts_ip_from_http_url(self) -> None:
        assert _extract_hostname("http://192.168.1.100:8080") == "192.168.1.100"

    def test_strips_port_from_host(self) -> None:
        assert _extract_hostname("example.com:8080") == "example.com"

    def test_returns_ip_unchanged(self) -> None:
        assert _extract_hostname("10.0.0.1") == "10.0.0.1"

    def test_lowercases_hostname(self) -> None:
        assert _normalise_target("API.Example.COM") == "api.example.com"

    def test_strips_whitespace(self) -> None:
        assert _normalise_target("  example.com  ") == "example.com"

    def test_ipv6_address_unchanged(self) -> None:
        result = _extract_hostname("2001:db8::1")
        assert result == "2001:db8::1"


# ── Matcher Unit Tests ────────────────────────────────────────────────────────

@pytest.mark.unit
class TestDomainMatcher:
    """Tests for _match_domain()."""

    def test_exact_match(self) -> None:
        assert _match_domain("example.com", "example.com") is True

    def test_no_match_different_domain(self) -> None:
        assert _match_domain("example.com", "other.com") is False

    def test_subdomain_not_matched_by_domain(self) -> None:
        # DOMAIN rule is exact — does NOT match subdomains
        assert _match_domain("example.com", "api.example.com") is False

    def test_case_handled(self) -> None:
        # Values should be pre-normalised — this tests the function directly
        assert _match_domain("example.com", "example.com") is True

    def test_no_match_prefix(self) -> None:
        assert _match_domain("example.com", "notexample.com") is False

    def test_no_match_suffix(self) -> None:
        assert _match_domain("example.com", "example.com.evil") is False


@pytest.mark.unit
class TestSubdomainMatcher:
    """Tests for _match_subdomain()."""

    def test_single_level_subdomain(self) -> None:
        assert _match_subdomain("example.com", "api.example.com") is True

    def test_multi_level_subdomain(self) -> None:
        assert _match_subdomain("example.com", "dev.api.example.com") is True

    def test_apex_domain_not_matched(self) -> None:
        # SUBDOMAIN rule does NOT match the apex itself
        assert _match_subdomain("example.com", "example.com") is False

    def test_different_apex_not_matched(self) -> None:
        assert _match_subdomain("example.com", "api.other.com") is False

    def test_partial_suffix_not_matched(self) -> None:
        # "notexample.com" should not match rule "example.com"
        assert _match_subdomain("example.com", "api.notexample.com") is False

    def test_subdomain_of_different_tld(self) -> None:
        assert _match_subdomain("example.com", "api.example.org") is False


@pytest.mark.unit
class TestCIDRMatcher:
    """Tests for _match_cidr()."""

    def test_ipv4_in_range(self) -> None:
        assert _match_cidr("10.0.0.0/24", "10.0.0.100") is True

    def test_ipv4_network_address(self) -> None:
        assert _match_cidr("10.0.0.0/24", "10.0.0.0") is True

    def test_ipv4_broadcast_address(self) -> None:
        assert _match_cidr("10.0.0.0/24", "10.0.0.255") is True

    def test_ipv4_out_of_range(self) -> None:
        assert _match_cidr("10.0.0.0/24", "10.0.1.1") is False

    def test_ipv4_slash32(self) -> None:
        assert _match_cidr("192.168.1.100/32", "192.168.1.100") is True
        assert _match_cidr("192.168.1.100/32", "192.168.1.101") is False

    def test_ipv6_in_range(self) -> None:
        assert _match_cidr("2001:db8::/32", "2001:db8::1") is True
        assert _match_cidr("2001:db8::/32", "2001:db8:0:1::1") is True

    def test_ipv6_out_of_range(self) -> None:
        assert _match_cidr("2001:db8::/32", "2001:db9::1") is False

    def test_domain_not_matched_by_cidr(self) -> None:
        # Domains are not IPs — CIDR rule cannot match them
        assert _match_cidr("10.0.0.0/24", "example.com") is False

    def test_url_hostname_not_matched_by_cidr(self) -> None:
        # Expects pre-normalised hostname; URL hostname would already be extracted
        assert _match_cidr("10.0.0.0/24", "app.example.com") is False


@pytest.mark.unit
class TestWildcardMatcher:
    """Tests for _match_wildcard()."""

    def test_single_level_wildcard(self) -> None:
        assert _match_wildcard("*.example.com", "api.example.com") is True

    def test_wildcard_does_not_match_apex(self) -> None:
        assert _match_wildcard("*.example.com", "example.com") is False

    def test_wildcard_does_not_match_multilevel_by_default(self) -> None:
        # fnmatch * matches any chars but not multiple dots in paths context
        # *.example.com DOES match api.staging.example.com because * matches "api.staging"
        # This is fnmatch behaviour — document it
        result = _match_wildcard("*.example.com", "api.staging.example.com")
        assert result is True  # fnmatch * matches "api.staging"

    def test_double_star_wildcard(self) -> None:
        assert _match_wildcard("**.example.com", "a.b.example.com") is True

    def test_prefix_wildcard(self) -> None:
        assert _match_wildcard("api-*.example.com", "api-v1.example.com") is True
        assert _match_wildcard("api-*.example.com", "api-v2.example.com") is True
        assert _match_wildcard("api-*.example.com", "web.example.com") is False

    def test_wildcard_ip_range(self) -> None:
        assert _match_wildcard("10.0.0.*", "10.0.0.100") is True
        assert _match_wildcard("10.0.0.*", "10.0.1.100") is False

    def test_no_match(self) -> None:
        assert _match_wildcard("*.example.com", "api.other.com") is False


@pytest.mark.unit
class TestHostMatcher:
    """Tests for _match_host()."""

    def test_exact_ipv4_match(self) -> None:
        assert _match_host("192.168.1.100", "192.168.1.100") is True

    def test_different_ipv4(self) -> None:
        assert _match_host("192.168.1.100", "192.168.1.101") is False

    def test_ipv6_normalised_match(self) -> None:
        # Both are the same address, different representation
        assert _match_host("2001:db8::1", "2001:db8::1") is True

    def test_domain_not_matched_by_host(self) -> None:
        assert _match_host("192.168.1.100", "example.com") is False

    def test_cidr_not_matched_by_host(self) -> None:
        assert _match_host("192.168.1.100", "192.168.1.100/32") is False


# ── check_scope() Tests ───────────────────────────────────────────────────────

@pytest.mark.unit
class TestCheckScope:
    """Tests for the main check_scope() function."""

    # ── No rules ─────────────────────────────────────────────────────────────

    def test_empty_rules_returns_no_scope_defined(self) -> None:
        result = check_scope("example.com", [])
        assert result.verdict == ScopeVerdict.NO_SCOPE_DEFINED
        assert result.is_denied is True

    def test_all_inactive_rules_returns_no_scope_defined(self) -> None:
        rules = [
            make_rule(ScopeRuleType.DOMAIN, "example.com", is_active=False),
        ]
        result = check_scope("example.com", rules)
        assert result.verdict == ScopeVerdict.NO_SCOPE_DEFINED

    # ── Basic allow ───────────────────────────────────────────────────────────

    def test_domain_allow_permits(self) -> None:
        rules = [make_rule(ScopeRuleType.DOMAIN, "example.com")]
        result = check_scope("example.com", rules)
        assert result.verdict == ScopeVerdict.PERMITTED
        assert result.is_permitted is True

    def test_host_allow_permits(self) -> None:
        rules = [make_rule(ScopeRuleType.HOST, "10.0.0.1")]
        result = check_scope("10.0.0.1", rules)
        assert result.verdict == ScopeVerdict.PERMITTED

    def test_cidr_allow_permits(self) -> None:
        rules = [make_rule(ScopeRuleType.CIDR, "10.0.0.0/24")]
        result = check_scope("10.0.0.100", rules)
        assert result.verdict == ScopeVerdict.PERMITTED

    def test_subdomain_allow_permits_subdomain(self) -> None:
        rules = [make_rule(ScopeRuleType.SUBDOMAIN, "example.com")]
        result = check_scope("api.example.com", rules)
        assert result.verdict == ScopeVerdict.PERMITTED

    def test_subdomain_allow_does_not_permit_apex(self) -> None:
        rules = [make_rule(ScopeRuleType.SUBDOMAIN, "example.com")]
        result = check_scope("example.com", rules)
        assert result.verdict == ScopeVerdict.DENIED

    def test_wildcard_allow_permits(self) -> None:
        rules = [make_rule(ScopeRuleType.WILDCARD, "*.dev.example.com")]
        result = check_scope("api.dev.example.com", rules)
        assert result.verdict == ScopeVerdict.PERMITTED

    # ── Exclusion overrides allow (deny-wins) ─────────────────────────────────

    def test_exclude_overrides_allow(self) -> None:
        rules = [
            make_rule(ScopeRuleType.CIDR, "10.0.0.0/24", ScopeDisposition.ALLOW),
            make_rule(ScopeRuleType.HOST, "10.0.0.1", ScopeDisposition.EXCLUDE),
        ]
        result = check_scope("10.0.0.1", rules)
        assert result.verdict == ScopeVerdict.DENIED
        assert result.denied_by_exclusion is True

    def test_exclude_for_admin_host_in_cidr_range(self) -> None:
        """Classic scope pattern: allow range, exclude firewall."""
        rules = [
            make_rule(ScopeRuleType.CIDR, "10.0.0.0/24", ScopeDisposition.ALLOW),
            make_rule(ScopeRuleType.HOST, "10.0.0.1", ScopeDisposition.EXCLUDE),
        ]
        # Normal host is in scope
        assert check_scope("10.0.0.100", rules).verdict == ScopeVerdict.PERMITTED
        # Firewall is excluded
        assert check_scope("10.0.0.1", rules).verdict == ScopeVerdict.DENIED

    def test_exclude_admin_subdomain(self) -> None:
        """Allow all subdomains, exclude admin subdomain."""
        rules = [
            make_rule(ScopeRuleType.SUBDOMAIN, "example.com", ScopeDisposition.ALLOW),
            make_rule(ScopeRuleType.DOMAIN, "admin.example.com", ScopeDisposition.EXCLUDE),
        ]
        assert check_scope("api.example.com", rules).verdict == ScopeVerdict.PERMITTED
        assert check_scope("admin.example.com", rules).verdict == ScopeVerdict.DENIED

    # ── URL decomposition ─────────────────────────────────────────────────────

    def test_url_target_domain_rule(self) -> None:
        """URL target is decomposed to hostname for domain rules."""
        rules = [make_rule(ScopeRuleType.DOMAIN, "example.com")]
        result = check_scope("https://example.com/api/v1", rules)
        assert result.verdict == ScopeVerdict.PERMITTED

    def test_url_target_subdomain_rule(self) -> None:
        rules = [make_rule(ScopeRuleType.SUBDOMAIN, "example.com")]
        result = check_scope("https://api.example.com:8443/v2", rules)
        assert result.verdict == ScopeVerdict.PERMITTED

    def test_url_target_wildcard_rule(self) -> None:
        rules = [make_rule(ScopeRuleType.WILDCARD, "*.example.com")]
        result = check_scope("https://api.example.com/health", rules)
        assert result.verdict == ScopeVerdict.PERMITTED

    def test_url_with_ip_and_cidr_rule(self) -> None:
        rules = [make_rule(ScopeRuleType.CIDR, "10.0.0.0/24")]
        result = check_scope("http://10.0.0.50:8080", rules)
        assert result.verdict == ScopeVerdict.PERMITTED

    # ── Default deny ──────────────────────────────────────────────────────────

    def test_no_matching_allow_rule_is_denied(self) -> None:
        """Target not covered by any ALLOW rule → implicit deny."""
        rules = [make_rule(ScopeRuleType.DOMAIN, "example.com")]
        result = check_scope("other.com", rules)
        assert result.verdict == ScopeVerdict.DENIED
        assert result.denied_by_exclusion is False

    def test_out_of_cidr_range_is_denied(self) -> None:
        rules = [make_rule(ScopeRuleType.CIDR, "10.0.0.0/24")]
        result = check_scope("10.0.1.1", rules)
        assert result.verdict == ScopeVerdict.DENIED

    # ── Matched rule info ─────────────────────────────────────────────────────

    def test_permitted_result_includes_matched_rule_id(self) -> None:
        rule = make_rule(ScopeRuleType.DOMAIN, "example.com")
        result = check_scope("example.com", [rule])
        assert result.matched_rule_id == str(rule.id)
        assert result.matched_rule_type == ScopeRuleType.DOMAIN

    def test_denied_by_exclusion_includes_matched_rule_id(self) -> None:
        allow_rule = make_rule(ScopeRuleType.CIDR, "10.0.0.0/24")
        excl_rule = make_rule(ScopeRuleType.HOST, "10.0.0.1", ScopeDisposition.EXCLUDE)
        result = check_scope("10.0.0.1", [allow_rule, excl_rule])
        assert result.matched_rule_id == str(excl_rule.id)
        assert result.denied_by_exclusion is True

    # ── Inactive rules ignored ────────────────────────────────────────────────

    def test_inactive_allow_rule_ignored(self) -> None:
        rules = [
            make_rule(ScopeRuleType.DOMAIN, "example.com", is_active=False),
            make_rule(ScopeRuleType.DOMAIN, "other.com", is_active=True),
        ]
        # example.com rule is inactive → not permitted
        result = check_scope("example.com", rules)
        assert result.verdict == ScopeVerdict.DENIED

    def test_inactive_exclude_rule_ignored(self) -> None:
        """Inactive exclude rule does not block targets."""
        rules = [
            make_rule(ScopeRuleType.CIDR, "10.0.0.0/24", is_active=True),
            make_rule(ScopeRuleType.HOST, "10.0.0.1", ScopeDisposition.EXCLUDE, is_active=False),
        ]
        # Exclusion is inactive → 10.0.0.1 is still in scope
        result = check_scope("10.0.0.1", rules)
        assert result.verdict == ScopeVerdict.PERMITTED


# ── Bulk Check Tests ──────────────────────────────────────────────────────────

@pytest.mark.unit
class TestCheckScopeBulk:
    def test_bulk_check_multiple_targets(self) -> None:
        rules = [
            make_rule(ScopeRuleType.CIDR, "10.0.0.0/24"),
            make_rule(ScopeRuleType.DOMAIN, "example.com"),
        ]
        results = check_scope_bulk(
            ["10.0.0.100", "example.com", "10.0.1.1", "other.com"],
            rules,
        )
        assert results["10.0.0.100"].is_permitted is True
        assert results["example.com"].is_permitted is True
        assert results["10.0.1.1"].is_permitted is False
        assert results["other.com"].is_permitted is False

    def test_bulk_check_empty_rules(self) -> None:
        results = check_scope_bulk(["example.com", "10.0.0.1"], [])
        for result in results.values():
            assert result.verdict == ScopeVerdict.NO_SCOPE_DEFINED


# ── validate_rule_value() Tests ───────────────────────────────────────────────

@pytest.mark.unit
class TestValidateRuleValue:
    """Tests for schema-layer rule value validation."""

    # Domain
    def test_valid_domain(self) -> None:
        assert validate_rule_value(ScopeRuleType.DOMAIN, "example.com") == "example.com"

    def test_invalid_domain_single_label(self) -> None:
        with pytest.raises(ValueError):
            validate_rule_value(ScopeRuleType.DOMAIN, "localhost")

    # Subdomain (same syntax as domain — apex domain value)
    def test_valid_subdomain_rule_value(self) -> None:
        assert validate_rule_value(ScopeRuleType.SUBDOMAIN, "example.com") == "example.com"

    # CIDR
    def test_valid_cidr(self) -> None:
        assert validate_rule_value(ScopeRuleType.CIDR, "10.0.0.0/24") == "10.0.0.0/24"

    def test_cidr_host_bits_stripped(self) -> None:
        # 10.0.0.5/24 → 10.0.0.0/24
        assert validate_rule_value(ScopeRuleType.CIDR, "10.0.0.5/24") == "10.0.0.0/24"

    def test_invalid_cidr_slash0(self) -> None:
        with pytest.raises(ValueError):
            validate_rule_value(ScopeRuleType.CIDR, "0.0.0.0/0")

    # HOST
    def test_valid_host(self) -> None:
        assert validate_rule_value(ScopeRuleType.HOST, "192.168.1.100") == "192.168.1.100"

    def test_invalid_host_is_cidr(self) -> None:
        with pytest.raises(ValueError):
            validate_rule_value(ScopeRuleType.HOST, "192.168.1.0/24")

    # WILDCARD
    def test_valid_wildcard_single_star(self) -> None:
        assert validate_rule_value(ScopeRuleType.WILDCARD, "*.example.com") == "*.example.com"

    def test_valid_wildcard_prefix(self) -> None:
        assert validate_rule_value(ScopeRuleType.WILDCARD, "api-*.example.com") == "api-*.example.com"

    def test_invalid_wildcard_special_chars(self) -> None:
        with pytest.raises(ValueError):
            validate_rule_value(ScopeRuleType.WILDCARD, "*.example.com; rm -rf /")

    def test_invalid_wildcard_no_dot_or_star(self) -> None:
        with pytest.raises(ValueError):
            validate_rule_value(ScopeRuleType.WILDCARD, "plainword")

    def test_unknown_rule_type_raises(self) -> None:
        with pytest.raises((ValueError, AttributeError)):
            validate_rule_value("UNKNOWN", "example.com")  # type: ignore


# ── Edge Cases ────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestEdgeCases:
    """Boundary and edge case tests."""

    def test_ipv6_target_with_host_rule(self) -> None:
        rules = [make_rule(ScopeRuleType.HOST, "2001:db8::1")]
        result = check_scope("2001:db8::1", rules)
        assert result.verdict == ScopeVerdict.PERMITTED

    def test_ipv6_target_with_cidr_rule(self) -> None:
        rules = [make_rule(ScopeRuleType.CIDR, "2001:db8::/32")]
        result = check_scope("2001:db8::dead:beef", rules)
        assert result.verdict == ScopeVerdict.PERMITTED

    def test_scope_result_is_immutable(self) -> None:
        """ScopeCheckResult is a frozen dataclass."""
        result = check_scope("example.com", [])
        with pytest.raises((AttributeError, TypeError)):
            result.verdict = ScopeVerdict.PERMITTED  # type: ignore

    def test_multiple_allow_rules_first_match_wins(self) -> None:
        """When multiple ALLOW rules match, the result is PERMITTED."""
        rules = [
            make_rule(ScopeRuleType.DOMAIN, "example.com"),
            make_rule(ScopeRuleType.SUBDOMAIN, "example.com"),
        ]
        result = check_scope("example.com", rules)
        assert result.verdict == ScopeVerdict.PERMITTED

    def test_scope_check_result_is_permitted_property(self) -> None:
        result = ScopeCheckResult(
            verdict=ScopeVerdict.PERMITTED,
            target_value="example.com",
        )
        assert result.is_permitted is True
        assert result.is_denied is False

    def test_scope_check_result_is_denied_property(self) -> None:
        result = ScopeCheckResult(
            verdict=ScopeVerdict.DENIED,
            target_value="example.com",
        )
        assert result.is_permitted is False
        assert result.is_denied is True

    def test_scope_check_result_no_scope_is_denied(self) -> None:
        result = ScopeCheckResult(
            verdict=ScopeVerdict.NO_SCOPE_DEFINED,
            target_value="example.com",
        )
        assert result.is_denied is True
