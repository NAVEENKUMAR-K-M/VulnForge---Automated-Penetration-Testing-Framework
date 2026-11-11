"""
Target value validators — enforce authorized scope of penetration tests.

Every target value is validated before it touches the database.  Invalid
values are rejected with a descriptive error at the schema layer, long before
any scan can be created.

Supported Target Types and Their Validation Rules:
    HOST    → Valid IPv4 or IPv6 address (not loopback, not multicast)
    NETWORK → Valid IPv4 or IPv6 CIDR notation (/0 to /32 for v4, /0 to /128 for v6)
    URL     → Well-formed HTTP/HTTPS URL with a valid hostname
    DOMAIN  → RFC 1123 hostname (can be bare domain, subdomain, or wildcard *.domain)

Security Rationale:
    Rejecting invalid targets at validation time prevents:
        - Accidental scanning of unintended assets
        - Injection attacks via malformed values passed to CLI tools
        - Ambiguous values that tools interpret differently

Design:
    All validators return the *normalised* value on success and raise
    ``ValueError`` on failure.  Pydantic field validators call these directly.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse


# ── Domain Validation ─────────────────────────────────────────────────────────

# RFC 1123 label: starts/ends with alphanumeric, may contain hyphens, max 63 chars
_LABEL_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$")

# Wildcard prefix pattern (only leading *. is allowed)
_WILDCARD_RE = re.compile(r"^\*\..+")


def validate_domain(value: str) -> str:
    """Validate and normalise a domain or subdomain target value.

    Accepts:
        - Bare domains: ``example.com``
        - Subdomains:   ``api.example.com``, ``dev.api.example.com``
        - Wildcards:    ``*.example.com`` (only leading ``*.`` prefix)

    Rejects:
        - IP addresses (use TargetType.HOST instead)
        - URLs with schemes (use TargetType.URL instead)
        - Labels exceeding 63 characters
        - Total length exceeding 253 characters
        - Invalid characters
        - Single-label names (e.g., ``localhost``)
        - Labels starting or ending with hyphens

    Args:
        value: The raw domain string.

    Returns:
        str: The normalised (lowercased, stripped) domain.

    Raises:
        ValueError: If the domain is invalid.
    """
    normalised = value.strip().lower()

    if not normalised:
        raise ValueError("Domain value cannot be empty.")

    # Reject anything that looks like a URL (has a scheme)
    if "://" in normalised:
        raise ValueError(
            f"'{value}' looks like a URL. Use target_type='url' instead."
        )

    # Handle wildcard prefix
    domain_to_check = normalised
    if _WILDCARD_RE.match(normalised):
        domain_to_check = normalised[2:]  # Strip the leading '*.'

    # Must not be a bare IP address
    try:
        ipaddress.ip_address(domain_to_check)
        raise ValueError(
            f"'{value}' is an IP address. Use target_type='host' instead."
        )
    except ValueError as exc:
        if "is an IP address" in str(exc):
            raise

    # Total length
    if len(domain_to_check) > 253:
        raise ValueError(
            f"Domain '{value}' exceeds maximum length of 253 characters."
        )

    labels = domain_to_check.split(".")
    if len(labels) < 2:
        raise ValueError(
            f"'{value}' is a single-label name. Must include at least one dot "
            f"(e.g., 'example.com')."
        )

    for label in labels:
        if not label:
            raise ValueError(f"Domain '{value}' contains an empty label (double dot).")
        if len(label) > 63:
            raise ValueError(
                f"Label '{label}' in domain '{value}' exceeds 63 characters."
            )
        if not _LABEL_RE.match(label):
            raise ValueError(
                f"Label '{label}' in domain '{value}' contains invalid characters. "
                f"Labels must start and end with alphanumeric characters and may "
                f"only contain hyphens between them."
            )

    return normalised


# ── IPv4/IPv6 Host Validation ─────────────────────────────────────────────────

def validate_host(value: str) -> str:
    """Validate and normalise a single IPv4 or IPv6 address.

    Accepts:
        - IPv4: ``192.168.1.100``, ``10.0.0.1``
        - IPv6: ``2001:db8::1``, ``::1`` (loopback allowed with warning context)

    Rejects:
        - CIDR notation (use TargetType.NETWORK instead)
        - Hostnames/domains (use TargetType.DOMAIN instead)
        - Multicast addresses (224.0.0.0/4, ff00::/8)
        - Unspecified addresses (0.0.0.0, ::)

    Args:
        value: The raw IP address string.

    Returns:
        str: The normalised (compressed) IP address string.

    Raises:
        ValueError: If the value is not a valid IP address.
    """
    stripped = value.strip()

    if not stripped:
        raise ValueError("Host value cannot be empty.")

    # Reject CIDR notation
    if "/" in stripped:
        raise ValueError(
            f"'{value}' looks like a network range. Use target_type='network' instead."
        )

    try:
        addr = ipaddress.ip_address(stripped)
    except ValueError:
        raise ValueError(
            f"'{value}' is not a valid IPv4 or IPv6 address. "
            f"For domains, use target_type='domain'. "
            f"For URLs, use target_type='url'."
        )

    if addr.is_multicast:
        raise ValueError(
            f"'{value}' is a multicast address and cannot be a scan target."
        )

    if addr.is_unspecified:
        raise ValueError(
            f"'{value}' is the unspecified address and cannot be a scan target."
        )

    # Return the compressed canonical form (handles IPv6 abbreviation)
    return str(addr)


# ── CIDR Network Validation ───────────────────────────────────────────────────

def validate_network(value: str) -> str:
    """Validate and normalise a CIDR network range.

    Accepts:
        - IPv4 CIDR:  ``10.0.0.0/24``, ``192.168.0.0/16``
        - IPv6 CIDR:  ``2001:db8::/32``
        - Host CIDR:  ``192.168.1.1/32`` (single host expressed as CIDR)

    Rejects:
        - Addresses without prefix length
        - Multicast ranges
        - Prefix lengths that imply the entire internet (/0) — these are
          rejected as they would represent an unauthorized global scan.

    Args:
        value: The raw CIDR string.

    Returns:
        str: The normalised network in canonical form (host bits zeroed).

    Raises:
        ValueError: If the value is not valid CIDR notation.
    """
    stripped = value.strip()

    if not stripped:
        raise ValueError("Network value cannot be empty.")

    if "/" not in stripped:
        raise ValueError(
            f"'{value}' is missing a prefix length. "
            f"Network targets must be in CIDR notation (e.g., '10.0.0.0/24'). "
            f"For a single host, use target_type='host'."
        )

    try:
        # strict=False: allows host bits to be set (e.g., 192.168.1.5/24 → 192.168.1.0/24)
        network = ipaddress.ip_network(stripped, strict=False)
    except ValueError:
        raise ValueError(
            f"'{value}' is not valid CIDR notation. "
            f"Examples: '10.0.0.0/24', '192.168.0.0/16', '2001:db8::/32'."
        )

    if network.is_multicast:
        raise ValueError(
            f"'{value}' is a multicast network and cannot be a scan target."
        )

    # Reject /0 prefixes — scanning the entire internet is never authorized
    if network.prefixlen == 0:
        raise ValueError(
            f"Prefix length /0 covers the entire internet and is not a valid scan target."
        )

    # Warn on very large ranges — /8 or larger for IPv4 is unusual
    if isinstance(network, ipaddress.IPv4Network) and network.prefixlen < 8:
        raise ValueError(
            f"IPv4 prefix /{network.prefixlen} covers {network.num_addresses:,} addresses. "
            f"Prefix length must be /8 or smaller for IPv4 targets."
        )

    if isinstance(network, ipaddress.IPv6Network) and network.prefixlen < 16:
        raise ValueError(
            f"IPv6 prefix /{network.prefixlen} is too broad to be a valid scan target. "
            f"Prefix length must be /16 or larger for IPv6 targets."
        )

    # Return the canonical network address (host bits zeroed)
    return str(network)


# ── URL Validation ────────────────────────────────────────────────────────────

_VALID_SCHEMES = {"http", "https"}


def validate_url(value: str) -> str:
    """Validate and normalise an HTTP/HTTPS URL target.

    Accepts:
        - ``https://app.example.com``
        - ``http://192.168.1.100:8080/admin``
        - ``https://api.example.com/v1``

    Rejects:
        - Non-HTTP schemes (ftp, file, etc.)
        - URLs without a hostname
        - Malformed URLs that fail urlparse

    Args:
        value: The raw URL string.

    Returns:
        str: The validated (stripped) URL. Scheme is lowercased.

    Raises:
        ValueError: If the URL is not a valid HTTP/HTTPS URL.
    """
    stripped = value.strip()

    if not stripped:
        raise ValueError("URL value cannot be empty.")

    # Auto-add scheme if missing to help urlparse work correctly
    if "://" not in stripped:
        raise ValueError(
            f"'{value}' is missing a URL scheme. "
            f"Include 'http://' or 'https://' (e.g., 'https://example.com')."
        )

    try:
        parsed = urlparse(stripped)
    except Exception:
        raise ValueError(f"'{value}' could not be parsed as a URL.")

    scheme = parsed.scheme.lower()
    if scheme not in _VALID_SCHEMES:
        raise ValueError(
            f"URL scheme '{scheme}' is not supported. "
            f"Only 'http' and 'https' are allowed scan targets."
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(
            f"'{value}' does not contain a valid hostname."
        )

    if len(stripped) > 2048:
        raise ValueError("URL exceeds maximum length of 2048 characters.")

    # Reconstruct with the lowercased scheme. urlparse already lowercases
    # parsed.scheme, so a replace() of that against the original (possibly
    # upper-case) text would silently no-op; rebuild from the part after "://".
    normalised = f"{scheme}://{stripped.split('://', 1)[1]}"
    return normalised


# ── Tag Validation ────────────────────────────────────────────────────────────

_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9\-_]{0,48}[a-z0-9]$|^[a-z0-9]$")


def validate_tag(value: str) -> str:
    """Validate and normalise a single target tag.

    Tags are lowercase, alphanumeric labels used to categorise targets.
    Valid characters: lowercase letters, digits, hyphens, underscores.
    Length: 1–50 characters.

    Args:
        value: The raw tag string.

    Returns:
        str: The normalised (lowercased, stripped) tag.

    Raises:
        ValueError: If the tag is invalid.
    """
    normalised = value.strip().lower()

    if not normalised:
        raise ValueError("Tag cannot be empty.")

    if len(normalised) > 50:
        raise ValueError(
            f"Tag '{value}' exceeds maximum length of 50 characters."
        )

    if not _TAG_RE.match(normalised):
        raise ValueError(
            f"Tag '{normalised}' contains invalid characters. "
            f"Tags must be lowercase alphanumeric and may contain hyphens "
            f"and underscores (e.g., 'production', 'web-app', 'internal_api')."
        )

    return normalised


# ── Unified Dispatcher ────────────────────────────────────────────────────────

def validate_target_value(target_type: str, value: str) -> str:
    """Validate a target value against its declared type.

    This is the single entry point called by the Pydantic schema validator.
    It dispatches to the appropriate type-specific validator.

    Args:
        target_type: One of 'host', 'network', 'url', 'domain'.
        value:       The raw target value string.

    Returns:
        str: The normalised, validated value.

    Raises:
        ValueError: If the value is invalid for the declared type.
    """
    validators = {
        "host": validate_host,
        "network": validate_network,
        "url": validate_url,
        "domain": validate_domain,
    }

    validator = validators.get(target_type.lower())
    if validator is None:
        raise ValueError(
            f"Unknown target type '{target_type}'. "
            f"Must be one of: host, network, url, domain."
        )

    return validator(value)
