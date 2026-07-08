"""
Scope Engine — determines whether a target is authorized for scanning.

This is the security-critical component of VulnForge.  It is called before
EVERY scan dispatch to ensure no scan runs against an out-of-scope target.

Architecture:
    The engine operates on a list of ``ScopeRule`` ORM objects fetched from
    the database.  It evaluates each rule against the target value and returns
    a ``ScopeCheckResult`` describing the verdict and the matched rule.

Algorithm (deny-wins):
    1. Evaluate ALL active EXCLUDE rules against the target.
       If ANY exclusion matches → DENIED (out of scope).
    2. Evaluate ALL active ALLOW rules against the target.
       If ANY allowance matches → PERMITTED (in scope).
    3. If no allow rule matches → DENIED (implicit deny / default-deny).

This default-deny posture means an unconfigured workspace with zero scope
rules CANNOT run any scans — the operator must explicitly define scope before
scanning is permitted.

Rule Matching Semantics:
    DOMAIN:    Exact case-insensitive match of the normalised FQDN.
               "example.com" matches "example.com" — NOT "api.example.com".

    SUBDOMAIN: Matches any subdomain of the given apex domain.
               Rule value "example.com" matches "api.example.com",
               "dev.api.example.com" — NOT "example.com" itself.
               For the apex + all subdomains, use both a DOMAIN and SUBDOMAIN rule.

    CIDR:      The target IP address must be contained in the CIDR network.
               Works for both IPv4 (10.0.0.0/24) and IPv6 (2001:db8::/32).
               If the target is a URL or domain, IPs are NOT extracted from DNS
               (no DNS resolution at scope-check time for security/speed).

    WILDCARD:  Python fnmatch semantics. '*' matches any sequence of characters
               within a single domain label only when used in a label position.
               Full glob applied to the lowercased target value.
               Example: "*.dev.example.com" matches "api.dev.example.com"
                        but NOT "api.staging.dev.example.com" (multiple levels).
               For multi-level wildcards use "**.example.com".

    HOST:      Exact IP address match (normalised via ipaddress module).
               "192.168.1.1" matches "192.168.1.1" — not any range.

Target normalisation:
    Before matching, all target values are lowercased and stripped.
    URLs are decomposed to their hostname for domain/subdomain/cidr/host checks.
    Port numbers are stripped from hostnames.

Security Invariants:
    - The engine NEVER performs DNS lookups (no SSRF risk, no latency).
    - The engine is PURE (no side effects, no I/O) — all rules are pre-loaded.
    - Exclusions ALWAYS override allowances — there is no ordering dependency.
    - An empty rule set → implicit DENY ALL.
"""

from __future__ import annotations

import fnmatch
import ipaddress
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse

from app.models.scope import ScopeDisposition, ScopeRule, ScopeRuleType


# ── Result Types ──────────────────────────────────────────────────────────────

class ScopeVerdict(str, Enum):
    """The outcome of a scope check.

    Values:
        PERMITTED:     Target is explicitly in scope — scan may proceed.
        DENIED:        Target is out of scope — scan MUST NOT proceed.
        NO_SCOPE_DEFINED: No active scope rules exist for this workspace.
                       Scans are blocked until scope is configured.
    """

    PERMITTED = "permitted"
    DENIED = "denied"
    NO_SCOPE_DEFINED = "no_scope_defined"


@dataclass(frozen=True)
class ScopeCheckResult:
    """Immutable result of a scope check operation.

    Attributes:
        verdict:         The scope check outcome.
        target_value:    The normalised target value that was checked.
        matched_rule_id: UUID of the rule that determined the verdict (str).
        matched_rule_type: The type of the matched rule.
        matched_disposition: The disposition of the matched rule.
        reason:          Human-readable explanation of the verdict.
        denied_by_exclusion: True if verdict is DENIED due to an exclusion rule.
    """

    verdict: ScopeVerdict
    target_value: str
    matched_rule_id: str | None = None
    matched_rule_type: ScopeRuleType | None = None
    matched_disposition: ScopeDisposition | None = None
    reason: str = ""
    denied_by_exclusion: bool = False

    @property
    def is_permitted(self) -> bool:
        """Return True if the target is in scope."""
        return self.verdict == ScopeVerdict.PERMITTED

    @property
    def is_denied(self) -> bool:
        """Return True if the target is out of scope."""
        return self.verdict in (ScopeVerdict.DENIED, ScopeVerdict.NO_SCOPE_DEFINED)


# ── Normalisation Helpers ─────────────────────────────────────────────────────

def _extract_hostname(value: str) -> str:
    """Extract the hostname from a URL or return the value unchanged.

    For CIDR/HOST rules, the target must already be an IP.  For domain-based
    rules, URLs are decomposed to their hostname.

    Args:
        value: The target value (may be URL, IP, CIDR, or domain).

    Returns:
        str: Lowercase hostname or IP string, port stripped.
    """
    stripped = value.strip().lower()
    if "://" in stripped:
        try:
            parsed = urlparse(stripped)
            host = parsed.hostname or stripped
            return host
        except Exception:
            return stripped
    # Strip port if present (e.g., "example.com:8080" → "example.com")
    if ":" in stripped and not stripped.startswith("["):
        # Could be IPv6 or host:port — only strip port for non-IPv6
        try:
            ipaddress.ip_address(stripped)
            return stripped  # It's a plain IPv6 address
        except ValueError:
            parts = stripped.rsplit(":", 1)
            if parts[-1].isdigit():
                return parts[0]
    return stripped


def _normalise_target(value: str) -> str:
    """Normalise a target value for matching.

    Returns lowercase, stripped value with URL decomposed to hostname.

    Args:
        value: Raw target value.

    Returns:
        str: Normalised value.
    """
    return _extract_hostname(value)


def _is_ip_address(value: str) -> bool:
    """Return True if value is a valid IPv4 or IPv6 address.

    Args:
        value: The string to test.

    Returns:
        bool: True if parseable as an IP address.
    """
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


# ── Per-Rule Matching Functions ───────────────────────────────────────────────

def _match_domain(rule_value: str, target: str) -> bool:
    """Exact domain match (case-insensitive, normalised).

    Args:
        rule_value: Normalised rule value (e.g., "example.com").
        target:     Normalised target value.

    Returns:
        bool: True if target exactly equals the rule domain.
    """
    return target == rule_value.strip().lower()


def _match_subdomain(rule_value: str, target: str) -> bool:
    """Match any subdomain of the rule's apex domain.

    SUBDOMAIN("example.com") matches "api.example.com" and
    "dev.api.example.com" but NOT "example.com" itself.

    Args:
        rule_value: The apex domain (e.g., "example.com").
        target:     The target domain to check.

    Returns:
        bool: True if target is a subdomain of rule_value.
    """
    apex = rule_value.strip().lower()
    # Target must end with ".{apex}" and have at least one more label
    suffix = f".{apex}"
    return target.endswith(suffix) and len(target) > len(suffix)


def _match_cidr(rule_value: str, target: str) -> bool:
    """Check if target IP is contained in the CIDR network.

    If target is not an IP address (e.g., it's a domain name or URL),
    this check returns False immediately — the engine never does DNS
    resolution.

    Args:
        rule_value: CIDR string (e.g., "10.0.0.0/24").
        target:     The target value (should be an IP for CIDR rules).

    Returns:
        bool: True if target IP is within the CIDR network.
    """
    if not _is_ip_address(target):
        return False
    try:
        network = ipaddress.ip_network(rule_value.strip(), strict=False)
        addr = ipaddress.ip_address(target)
        return addr in network
    except ValueError:
        return False


def _match_wildcard(rule_value: str, target: str) -> bool:
    """Match using Python fnmatch glob pattern.

    Pattern is applied to the full lowercased target value.
    '*' in a pattern matches any sequence of characters (fnmatch semantics).

    Common patterns:
        *.example.com        → any single-level subdomain
        **.example.com       → any multi-level subdomain
        api-*.example.com    → api-v1.example.com, api-v2.example.com
        10.0.0.*             → any host in 10.0.0.0/24 (less preferred — use CIDR)

    Args:
        rule_value: Glob pattern string.
        target:     Normalised target value.

    Returns:
        bool: True if target matches the pattern.
    """
    pattern = rule_value.strip().lower()
    return fnmatch.fnmatch(target, pattern)


def _match_host(rule_value: str, target: str) -> bool:
    """Exact IP address match (normalised via ipaddress module).

    Both values are parsed through ``ipaddress.ip_address()`` to handle
    IPv6 abbreviation differences (e.g., "::1" vs "0:0:0:0:0:0:0:1").

    Args:
        rule_value: The scope rule IP address.
        target:     The target IP to check.

    Returns:
        bool: True if they are the same IP address.
    """
    if not _is_ip_address(target):
        return False
    try:
        rule_ip = ipaddress.ip_address(rule_value.strip())
        target_ip = ipaddress.ip_address(target)
        return rule_ip == target_ip
    except ValueError:
        return False


# ── Rule Matcher Dispatcher ───────────────────────────────────────────────────

_MATCHERS = {
    ScopeRuleType.DOMAIN: _match_domain,
    ScopeRuleType.SUBDOMAIN: _match_subdomain,
    ScopeRuleType.CIDR: _match_cidr,
    ScopeRuleType.WILDCARD: _match_wildcard,
    ScopeRuleType.HOST: _match_host,
}


def _rule_matches(rule: ScopeRule, normalised_target: str) -> bool:
    """Evaluate a single scope rule against a normalised target value.

    Args:
        rule:              The scope rule to evaluate.
        normalised_target: The lowercased, stripped, hostname-extracted target.

    Returns:
        bool: True if the rule matches the target.
    """
    matcher = _MATCHERS.get(rule.rule_type)
    if matcher is None:
        return False
    return matcher(rule.value, normalised_target)


# ── Public API ────────────────────────────────────────────────────────────────

def check_scope(
    target_value: str,
    rules: list[ScopeRule],
) -> ScopeCheckResult:
    """Determine whether a target is in scope given a set of workspace rules.

    This is the primary entry point called by the scan service before
    every scan dispatch.  It is pure (no I/O) — all rules must be
    pre-loaded from the database by the caller.

    Algorithm:
        1. Filter to active rules only.
        2. If no active rules → NO_SCOPE_DEFINED (implicit deny).
        3. Normalise the target value.
        4. Check all EXCLUDE rules first — if any match → DENIED.
        5. Check all ALLOW rules — if any match → PERMITTED.
        6. No ALLOW match → DENIED (implicit deny).

    Args:
        target_value: The target value to check (IP, domain, URL, CIDR).
        rules:        All ScopeRule records for the workspace (active and inactive).

    Returns:
        ScopeCheckResult: Immutable result with verdict, matched rule, and reason.

    Examples:
        >>> from app.core.scope_engine import check_scope
        >>> result = check_scope("api.example.com", workspace_rules)
        >>> if not result.is_permitted:
        ...     raise ScopeViolationError(result.reason)
    """
    active_rules = [r for r in rules if r.is_active]

    # ── No rules → implicit deny ──────────────────────────────────────────
    if not active_rules:
        return ScopeCheckResult(
            verdict=ScopeVerdict.NO_SCOPE_DEFINED,
            target_value=target_value,
            reason=(
                "No active scope rules are defined for this workspace. "
                "Configure at least one ALLOW rule before running scans."
            ),
        )

    normalised = _normalise_target(target_value)

    # Separate rules by disposition
    exclude_rules = [r for r in active_rules if r.disposition == ScopeDisposition.EXCLUDE]
    allow_rules = [r for r in active_rules if r.disposition == ScopeDisposition.ALLOW]

    # ── Step 1: Check exclusions (deny wins) ──────────────────────────────
    for rule in exclude_rules:
        if _rule_matches(rule, normalised):
            return ScopeCheckResult(
                verdict=ScopeVerdict.DENIED,
                target_value=target_value,
                matched_rule_id=str(rule.id),
                matched_rule_type=rule.rule_type,
                matched_disposition=ScopeDisposition.EXCLUDE,
                reason=(
                    f"Target '{target_value}' is explicitly excluded by "
                    f"{rule.rule_type.value} rule '{rule.value}'."
                ),
                denied_by_exclusion=True,
            )

    # ── Step 2: Check allowances ──────────────────────────────────────────
    for rule in allow_rules:
        if _rule_matches(rule, normalised):
            return ScopeCheckResult(
                verdict=ScopeVerdict.PERMITTED,
                target_value=target_value,
                matched_rule_id=str(rule.id),
                matched_rule_type=rule.rule_type,
                matched_disposition=ScopeDisposition.ALLOW,
                reason=(
                    f"Target '{target_value}' is in scope via "
                    f"{rule.rule_type.value} rule '{rule.value}'."
                ),
            )

    # ── Step 3: Default deny ──────────────────────────────────────────────
    return ScopeCheckResult(
        verdict=ScopeVerdict.DENIED,
        target_value=target_value,
        reason=(
            f"Target '{target_value}' does not match any ALLOW rule in this workspace. "
            f"Add a scope rule that covers this target to permit scanning."
        ),
    )


def check_scope_bulk(
    target_values: list[str],
    rules: list[ScopeRule],
) -> dict[str, ScopeCheckResult]:
    """Check multiple target values against the same rule set.

    Useful for pre-flight validation of scan batches without repeated
    database round-trips.

    Args:
        target_values: List of target values to check.
        rules:         Active scope rules for the workspace.

    Returns:
        dict[str, ScopeCheckResult]: Maps each target_value to its result.
    """
    return {value: check_scope(value, rules) for value in target_values}


def validate_rule_value(rule_type: ScopeRuleType, value: str) -> str:
    """Validate a scope rule value against its declared type.

    Called at the schema layer to reject invalid rule values before they
    reach the database.

    Args:
        rule_type: The scope rule type.
        value:     The raw value to validate.

    Returns:
        str: The normalised, validated value.

    Raises:
        ValueError: If the value is invalid for the declared rule_type.
    """
    from app.utils.target_validators import (
        validate_domain,
        validate_host,
        validate_network,
    )

    stripped = value.strip().lower()

    if not stripped:
        raise ValueError("Scope rule value cannot be empty.")

    if rule_type == ScopeRuleType.DOMAIN:
        return validate_domain(stripped)

    elif rule_type == ScopeRuleType.SUBDOMAIN:
        # Same syntax as domain — value is the apex domain
        return validate_domain(stripped)

    elif rule_type == ScopeRuleType.CIDR:
        return validate_network(stripped)

    elif rule_type == ScopeRuleType.HOST:
        return validate_host(stripped)

    elif rule_type == ScopeRuleType.WILDCARD:
        # Wildcards can contain *, ., -, alphanumerics, and underscores
        import re
        pattern = re.compile(r"^[\w\*\.\-]+$")
        if not pattern.match(stripped):
            raise ValueError(
                f"Wildcard pattern '{value}' contains invalid characters. "
                f"Allowed: alphanumerics, dots, hyphens, underscores, asterisks."
            )
        if len(stripped) > 250:
            raise ValueError("Wildcard pattern exceeds maximum length of 250 characters.")
        if not ("." in stripped or "*" in stripped):
            raise ValueError(
                f"Wildcard pattern '{value}' must contain at least one '.' or '*'."
            )
        return stripped

    raise ValueError(f"Unknown rule_type '{rule_type}'.")
