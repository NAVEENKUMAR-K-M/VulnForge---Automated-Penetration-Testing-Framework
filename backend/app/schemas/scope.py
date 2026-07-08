"""
Scope Pydantic schemas — request/response contracts for scope rule endpoints.

Schemas:
    ScopeRuleCreate     → Create a scope rule (POST body)
    ScopeRuleUpdate     → Partial update (PATCH body)
    ScopeRuleResponse   → Full scope rule API response
    ScopeCheckRequest   → Ad-hoc scope check request body
    ScopeCheckResponse  → Scope check result response
    BulkScopeImport     → Import multiple rules at once
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.core.scope_engine import ScopeVerdict, validate_rule_value
from app.models.scope import ScopeDisposition, ScopeRuleType
from app.schemas.common import TimestampedResponse, VulnForgeBaseModel


# ── Request Schemas ────────────────────────────────────────────────────────────

class ScopeRuleCreate(VulnForgeBaseModel):
    """Payload for creating a new scope rule."""

    rule_type: ScopeRuleType = Field(
        description=(
            "Matching strategy:\n"
            "- **domain**: Exact FQDN match (e.g., `example.com`)\n"
            "- **subdomain**: All subdomains of apex domain (e.g., rule `example.com` "
            "matches `api.example.com`)\n"
            "- **cidr**: IPv4/IPv6 network range (e.g., `10.0.0.0/24`)\n"
            "- **wildcard**: Glob pattern (e.g., `*.dev.example.com`)\n"
            "- **host**: Single IP address (e.g., `192.168.1.100`)"
        ),
        examples=["domain", "cidr", "subdomain"],
    )
    disposition: ScopeDisposition = Field(
        default=ScopeDisposition.ALLOW,
        description=(
            "Whether this rule **allows** or **excludes** matching targets.\n"
            "Exclusions always override allow rules (deny wins)."
        ),
        examples=["allow", "exclude"],
    )
    value: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "The scope boundary value. Must be valid for the declared `rule_type`:\n"
            "- domain/subdomain: domain name (e.g., `example.com`)\n"
            "- cidr: CIDR notation (e.g., `10.0.0.0/24`)\n"
            "- wildcard: glob pattern (e.g., `*.dev.example.com`)\n"
            "- host: IP address (e.g., `192.168.1.100`)"
        ),
        examples=["example.com", "10.0.0.0/24", "*.dev.example.com"],
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Optional note explaining why this scope boundary exists.",
        examples=["Client-authorized external perimeter"],
    )

    @model_validator(mode="after")
    def validate_value_for_type(self) -> "ScopeRuleCreate":
        """Validate and normalise value against its rule_type.

        Returns:
            ScopeRuleCreate: Self with normalised value.

        Raises:
            ValueError: If the value is invalid for the declared rule_type.
        """
        self.value = validate_rule_value(self.rule_type, self.value)
        return self


class ScopeRuleUpdate(VulnForgeBaseModel):
    """Partial update payload for an existing scope rule."""

    description: str | None = Field(
        default=None,
        max_length=500,
        description="Updated description.",
    )
    is_active: bool | None = Field(
        default=None,
        description="Enable or disable the rule without deleting it.",
    )
    disposition: ScopeDisposition | None = Field(
        default=None,
        description="Change rule from ALLOW to EXCLUDE or vice versa.",
    )


class ScopeCheckRequest(VulnForgeBaseModel):
    """Ad-hoc scope check request — test a value against workspace scope."""

    target_value: str = Field(
        min_length=1,
        max_length=2048,
        description=(
            "The target value to check against the workspace's scope rules. "
            "Can be an IP address, domain, CIDR, or URL."
        ),
        examples=["api.example.com", "192.168.1.100", "https://app.example.com"],
    )


class BulkScopeRuleItem(VulnForgeBaseModel):
    """A single item in a bulk scope import."""

    rule_type: ScopeRuleType
    disposition: ScopeDisposition = ScopeDisposition.ALLOW
    value: str = Field(min_length=1, max_length=500)
    description: str | None = None

    @model_validator(mode="after")
    def validate_value(self) -> "BulkScopeRuleItem":
        self.value = validate_rule_value(self.rule_type, self.value)
        return self


class BulkScopeImport(VulnForgeBaseModel):
    """Import multiple scope rules in a single request.

    Rules with duplicate value+type+disposition combinations for this workspace
    are silently skipped (idempotent import).
    """

    rules: list[BulkScopeRuleItem] = Field(
        min_length=1,
        max_length=100,
        description="List of scope rules to import (max 100 per request).",
    )
    replace_existing: bool = Field(
        default=False,
        description=(
            "If True, DELETE all existing active rules before importing. "
            "If False, merge with existing rules (duplicates skipped)."
        ),
    )


# ── Response Schemas ───────────────────────────────────────────────────────────

class ScopeRuleResponse(TimestampedResponse):
    """Full scope rule representation returned by the API."""

    workspace_id: uuid.UUID = Field(description="Parent workspace UUID.")
    rule_type: ScopeRuleType = Field(description="Matching strategy.")
    disposition: ScopeDisposition = Field(description="Allow or exclude.")
    value: str = Field(description="The scope boundary value (normalised).")
    description: str | None = Field(description="Optional rule description.")
    is_active: bool = Field(description="Whether this rule is currently active.")
    created_by_id: uuid.UUID = Field(description="UUID of the user who created this rule.")


class ScopeCheckResponse(VulnForgeBaseModel):
    """Result of a scope check against a workspace's rule set."""

    target_value: str = Field(description="The target value that was checked.")
    verdict: ScopeVerdict = Field(
        description=(
            "Scope check outcome:\n"
            "- **permitted**: Target is in scope — scan may proceed\n"
            "- **denied**: Target is out of scope — scan MUST NOT proceed\n"
            "- **no_scope_defined**: No rules configured — all scans blocked"
        )
    )
    is_permitted: bool = Field(description="True if verdict is 'permitted'.")
    reason: str = Field(description="Human-readable explanation of the verdict.")
    matched_rule_id: uuid.UUID | None = Field(
        default=None,
        description="UUID of the rule that determined the verdict.",
    )
    matched_rule_type: ScopeRuleType | None = Field(
        default=None,
        description="Type of the matched rule.",
    )
    matched_disposition: ScopeDisposition | None = Field(
        default=None,
        description="Disposition of the matched rule.",
    )
    denied_by_exclusion: bool = Field(
        default=False,
        description="True if the denial was caused by an explicit EXCLUDE rule.",
    )


class WorkspaceScopeOverview(VulnForgeBaseModel):
    """Summary of a workspace's current scope configuration."""

    workspace_id: uuid.UUID
    total_rules: int = Field(description="Total number of scope rules (active + inactive).")
    active_allow_rules: int = Field(description="Number of active ALLOW rules.")
    active_exclude_rules: int = Field(description="Number of active EXCLUDE rules.")
    inactive_rules: int = Field(description="Number of disabled rules.")
    has_scope_defined: bool = Field(
        description="True if at least one active ALLOW rule exists."
    )
    rule_type_breakdown: dict[str, int] = Field(
        description="Count of active rules per rule type.",
    )
