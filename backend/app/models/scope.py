"""
ScopeRule ORM model — authorized scanning boundaries per workspace.

Architecture:
    Every workspace has a set of ScopeRules defining what is in-scope for
    scanning.  Before any scan is dispatched, the scope engine evaluates the
    target value against the workspace's rules.  A scan is ONLY allowed if at
    least one rule ALLOWS it and no exclusion rule DENIES it.

    The dual-list model (allow + exclude) follows the standard pentest scope
    document pattern:
        "All hosts in 10.0.0.0/24 EXCEPT 10.0.0.1 (the firewall)"
        "All subdomains of example.com EXCEPT admin.example.com"

Rule Types:
    DOMAIN       → Exact domain match (e.g., example.com)
    SUBDOMAIN    → All subdomains of a domain (e.g., *.example.com logic)
    CIDR         → IPv4/IPv6 network range (e.g., 10.0.0.0/24)
    WILDCARD     → Glob-style pattern (e.g., *.dev.example.com, api-*.example.com)
    HOST         → Single IPv4/IPv6 address (e.g., 192.168.1.100)

Rule Disposition:
    ALLOW        → Target matching this rule is in scope
    EXCLUDE      → Target matching this rule is explicitly out of scope
                   (exclusions override allowances — deny wins)
"""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase

if TYPE_CHECKING:
    from app.models.workspace import Workspace
    from app.models.user import User


# ── Enumerations ──────────────────────────────────────────────────────────────

class ScopeRuleType(str, enum.Enum):
    """Classification of a scope rule entry.

    Values:
        DOMAIN:    Exact domain match — only this specific FQDN is in scope.
                   Example: ``example.com`` matches ``example.com`` exactly;
                   does NOT match ``sub.example.com``.
        SUBDOMAIN: All subdomains of a domain, but NOT the apex domain itself.
                   Example: ``example.com`` matches ``api.example.com``,
                   ``dev.api.example.com`` but NOT ``example.com``.
        CIDR:      IPv4 or IPv6 CIDR network range.
                   Example: ``10.0.0.0/24`` matches any host in that range.
        WILDCARD:  Glob-style shell pattern (``fnmatch`` semantics).
                   Example: ``*.dev.example.com``, ``api-*.example.com``.
        HOST:      Single IP address (no prefix). Exact match only.
                   Example: ``192.168.1.100``.
    """

    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    CIDR = "cidr"
    WILDCARD = "wildcard"
    HOST = "host"


class ScopeDisposition(str, enum.Enum):
    """Whether this rule allows or excludes a target.

    Values:
        ALLOW:   Target matching this rule is in scope.
        EXCLUDE: Target matching this rule is explicitly out of scope.
                 Exclusions always override allow rules (deny wins).
    """

    ALLOW = "allow"
    EXCLUDE = "exclude"


# ── Model ─────────────────────────────────────────────────────────────────────

class ScopeRule(TimestampedBase):
    """ORM model for the ``scope_rules`` table.

    A ScopeRule is a single entry in a workspace's authorized scope definition.
    The scope engine evaluates ALL rules for a workspace to determine whether
    a given target value is in scope before dispatching a scan.

    Attributes:
        workspace_id:  FK to the workspace this rule belongs to.
        rule_type:     The matching strategy (domain, subdomain, cidr, etc.).
        disposition:   ALLOW or EXCLUDE.
        value:         The scope rule value (domain name, CIDR, host, pattern).
        description:   Optional human-readable note about why this rule exists.
        is_active:     Soft-disable without deleting the rule.
        created_by_id: FK to the user who created this rule.
    """

    __tablename__ = "scope_rules"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "rule_type",
            "disposition",
            "value",
            name="uq_scope_rules_workspace_type_value",
        ),
        CheckConstraint(
            "char_length(trim(value)) > 0",
            name="ck_scope_rules_value_nonempty",
        ),
        Index("idx_scope_rules_workspace_id", "workspace_id"),
        Index("idx_scope_rules_disposition", "disposition"),
        Index(
            "idx_scope_rules_active",
            "workspace_id",
            "is_active",
            postgresql_where=text("is_active = TRUE"),
        ),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "workspaces.id",
            ondelete="CASCADE",
            name="fk_scope_rules_workspace",
        ),
        nullable=False,
        doc="FK to the workspace this rule is scoped to.",
    )
    rule_type: Mapped[ScopeRuleType] = mapped_column(
        Enum(ScopeRuleType, name="scope_rule_type_enum"),
        nullable=False,
        doc="Matching strategy for this scope rule.",
    )
    disposition: Mapped[ScopeDisposition] = mapped_column(
        Enum(ScopeDisposition, name="scope_disposition_enum"),
        nullable=False,
        default=ScopeDisposition.ALLOW,
        server_default=ScopeDisposition.ALLOW.value,
        doc="Whether this rule allows or excludes the matched target.",
    )
    value: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc=(
            "The scope boundary value. Interpretation depends on rule_type:\n"
            "  DOMAIN/SUBDOMAIN: domain name (e.g., 'example.com')\n"
            "  CIDR: network in CIDR notation (e.g., '10.0.0.0/24')\n"
            "  WILDCARD: glob pattern (e.g., '*.dev.example.com')\n"
            "  HOST: single IP address (e.g., '192.168.1.100')"
        ),
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional human-readable note explaining this scope boundary.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("TRUE"),
        doc="Soft-disable flag. Inactive rules are ignored by the scope engine.",
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_scope_rules_users"),
        nullable=False,
        index=True,
        doc="FK to the user who created this scope rule.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="scope_rules",
        lazy="select",
    )
    created_by: Mapped[User] = relationship(
        "User",
        foreign_keys=[created_by_id],
        lazy="select",
    )
