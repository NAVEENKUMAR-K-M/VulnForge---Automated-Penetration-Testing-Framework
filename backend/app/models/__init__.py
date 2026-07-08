"""
VulnForge ORM models package.

Importing this module guarantees all SQLAlchemy model classes are registered
with the declarative base before Alembic or any code calls
``Base.metadata.create_all()``.

Import Order:
    Base must be imported first to initialize the metadata registry.
    Association tables must be imported before models that reference them
    as ``secondary`` arguments in ``relationship()``.
    All other models are imported in dependency order (referenced → referencing).
"""

from app.models.base import Base, TimestampedBase, TimestampMixin, UUIDPrimaryKeyMixin

# Association tables (no ORM class, just Table objects — must come before
# models that use them as relationship secondaries)
from app.models.associations import report_scans, report_vulnerabilities

# Domain models — in dependency order
from app.models.user import User, UserRole
from app.models.user_session import UserSession
from app.models.target import Target, TargetType
from app.models.target_tag import TargetTag
from app.models.plugin import Plugin, PluginPhase
from app.models.scan import Scan, ScanStatus, ScanType, Priority
from app.models.scan_plugin_execution import ScanPluginExecution, PluginExecutionStatus
from app.models.vulnerability import Vulnerability, VulnerabilitySeverity, VulnerabilityStatus
from app.models.vulnerability_reference import VulnerabilityReference, ReferenceType
from app.models.vulnerability_note import VulnerabilityNote
from app.models.report import Report, ReportFormat, ReportStatus, ReportType
from app.models.audit_log import AuditLog, AuditOutcome
from app.models.workspace import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
    WorkspaceStatus,
)
from app.models.scope import ScopeRule, ScopeRuleType, ScopeDisposition
from app.models.scan_profile import ScanProfile, ScanProfilePlugin, ProfileType
from app.models.asset import DiscoveredAsset, AssetType

__all__ = [
    # Base
    "Base",
    "TimestampedBase",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    # Associations
    "report_scans",
    "report_vulnerabilities",
    # Models & Enums
    "User",
    "UserRole",
    "UserSession",
    "Target",
    "TargetType",
    "TargetTag",
    "Plugin",
    "PluginPhase",
    "Scan",
    "ScanStatus",
    "ScanType",
    "Priority",
    "ScanPluginExecution",
    "PluginExecutionStatus",
    "Vulnerability",
    "VulnerabilitySeverity",
    "VulnerabilityStatus",
    "VulnerabilityReference",
    "ReferenceType",
    "VulnerabilityNote",
    "Report",
    "ReportFormat",
    "ReportStatus",
    "ReportType",
    "AuditLog",
    "AuditOutcome",
    # Workspace
    "Workspace",
    "WorkspaceMember",
    "WorkspaceMemberRole",
    "WorkspaceStatus",
    # Scope
    "ScopeRule",
    "ScopeRuleType",
    "ScopeDisposition",
    # Scan Profiles
    "ScanProfile",
    "ScanProfilePlugin",
    "ProfileType",
    # Assets
    "DiscoveredAsset",
    "AssetType",
]
