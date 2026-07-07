"""
Application-wide constants and enumerations.

All values that would otherwise be magic numbers or inline strings are
defined here so they have a single source of truth and show up in IDE
autocomplete.

Design:
    Values that are environment-configurable belong in ``core/config.py``.
    Values that are fixed regardless of deployment belong here.
"""

from __future__ import annotations

# ── Token Types ───────────────────────────────────────────────────────────────

ACCESS_TOKEN_TYPE: str = "access"
"""JWT ``type`` claim value for access tokens."""

REFRESH_TOKEN_BYTES: int = 32
"""Number of random bytes used to generate refresh tokens (256-bit entropy)."""

PASSWORD_RESET_TOKEN_BYTES: int = 32
"""Number of random bytes for password reset tokens (256-bit entropy)."""

PASSWORD_RESET_EXPIRY_MINUTES: int = 15
"""Password reset tokens expire after this many minutes."""

# ── HTTP Headers ──────────────────────────────────────────────────────────────

AUTHORIZATION_HEADER: str = "Authorization"
BEARER_PREFIX: str = "Bearer "

# ── Audit Log Actions ─────────────────────────────────────────────────────────
# Dot-notation action strings written to the audit_logs table.

class AuditAction:
    """Namespace for audit log action identifiers."""

    # Auth
    USER_REGISTERED: str = "user.registered"
    USER_LOGIN_SUCCESS: str = "user.login.success"
    USER_LOGIN_FAILED: str = "user.login.failed"
    USER_LOCKED: str = "user.locked"
    USER_LOGOUT: str = "user.logout"
    USER_LOGOUT_ALL: str = "user.logout_all"
    TOKEN_REFRESHED: str = "token.refreshed"
    TOKEN_REFRESH_FAILED: str = "token.refresh.failed"
    PASSWORD_RESET_REQUESTED: str = "user.password_reset.requested"
    PASSWORD_RESET_COMPLETED: str = "user.password_reset.completed"

    # Users
    USER_CREATED: str = "user.created"
    USER_UPDATED: str = "user.updated"
    USER_DELETED: str = "user.deleted"

    # Targets
    TARGET_CREATED: str = "target.created"
    TARGET_UPDATED: str = "target.updated"
    TARGET_DELETED: str = "target.deleted"

    # Scans
    SCAN_CREATED: str = "scan.created"
    SCAN_STARTED: str = "scan.started"
    SCAN_COMPLETED: str = "scan.completed"
    SCAN_FAILED: str = "scan.failed"
    SCAN_CANCELLED: str = "scan.cancelled"

    # Vulnerabilities
    VULN_STATUS_CHANGED: str = "vulnerability.status_changed"
    VULN_VERIFIED: str = "vulnerability.verified"

    # Reports
    REPORT_CREATED: str = "report.created"
    REPORT_DOWNLOADED: str = "report.downloaded"

    # Workspaces
    WORKSPACE_CREATED: str = "workspace.created"
    WORKSPACE_UPDATED: str = "workspace.updated"
    WORKSPACE_ARCHIVED: str = "workspace.archived"
    WORKSPACE_RESTORED: str = "workspace.restored"
    WORKSPACE_DELETED: str = "workspace.deleted"
    WORKSPACE_MEMBER_ADDED: str = "workspace.member.added"
    WORKSPACE_MEMBER_REMOVED: str = "workspace.member.removed"
    WORKSPACE_MEMBER_ROLE_CHANGED: str = "workspace.member.role_changed"


# ── Role Hierarchy ────────────────────────────────────────────────────────────

ROLE_HIERARCHY: dict[str, int] = {
    "viewer": 0,
    "analyst": 1,
    "admin": 2,
}
"""
Maps role name to numeric privilege level.
Higher number = more privilege.
Used by the RBAC dependency to check role sufficiency.
"""

# ── Pagination ────────────────────────────────────────────────────────────────

DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100

# ── CVSS Severity Thresholds ──────────────────────────────────────────────────
# Based on CVSS v3.1 specification

CVSS_CRITICAL_THRESHOLD: float = 9.0
CVSS_HIGH_THRESHOLD: float = 7.0
CVSS_MEDIUM_THRESHOLD: float = 4.0
CVSS_LOW_THRESHOLD: float = 0.1

# ── Misc ──────────────────────────────────────────────────────────────────────

API_HEALTH_TAG: str = "health"
API_AUTH_TAG: str = "authentication"
API_USERS_TAG: str = "users"
API_TARGETS_TAG: str = "targets"
API_SCANS_TAG: str = "scans"
API_VULNERABILITIES_TAG: str = "vulnerabilities"
API_REPORTS_TAG: str = "reports"
API_PLUGINS_TAG: str = "plugins"
API_WORKSPACES_TAG: str = "workspaces"
