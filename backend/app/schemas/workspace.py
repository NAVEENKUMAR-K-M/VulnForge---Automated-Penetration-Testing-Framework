"""
Workspace Pydantic schemas — request/response contracts for workspace endpoints.

Schemas:
    WorkspaceCreate      → Create a new workspace (POST body)
    WorkspaceUpdate      → Partial update (PATCH body)
    WorkspaceResponse    → Full workspace representation (API response)
    WorkspaceSummary     → Lightweight summary for list views
    WorkspaceDashboard   → Aggregated stats for the workspace dashboard
    MemberAddRequest     → Add a member to a workspace (POST body)
    MemberRoleUpdate     → Change a member's role (PATCH body)
    WorkspaceMemberResponse → Member representation in API responses
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models.workspace import WorkspaceMemberRole, WorkspaceStatus
from app.schemas.common import TimestampedResponse, VulnForgeBaseModel


# ── Request Schemas ────────────────────────────────────────────────────────────

class WorkspaceCreate(VulnForgeBaseModel):
    """Payload for creating a new workspace."""

    name: str = Field(
        min_length=1,
        max_length=300,
        description="Short, descriptive engagement name.",
        examples=["Q3 2026 External Pentest"],
    )
    description: str | None = Field(
        default=None,
        description="Extended scope and objectives description.",
        examples=["Full external attack surface assessment for Acme Corp."],
    )
    client_name: str | None = Field(
        default=None,
        max_length=200,
        description="Name of the client organisation.",
        examples=["Acme Corporation"],
    )
    client_contact: str | None = Field(
        default=None,
        max_length=200,
        description="Primary contact at the client (name or email).",
        examples=["alice@acme.com"],
    )
    start_date: date | None = Field(
        default=None,
        description="Planned engagement start date (ISO 8601 date).",
        examples=["2026-09-01"],
    )
    end_date: date | None = Field(
        default=None,
        description="Planned engagement end date (ISO 8601 date).",
        examples=["2026-09-30"],
    )
    settings: dict = Field(
        default_factory=dict,
        description="Optional workspace-level configuration overrides.",
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        """Strip leading/trailing whitespace from workspace name."""
        return v.strip()

    @model_validator(mode="after")
    def validate_date_range(self) -> "WorkspaceCreate":
        """Validate that end_date is not before start_date.

        Returns:
            WorkspaceCreate: The validated schema instance.

        Raises:
            ValueError: If end_date precedes start_date.
        """
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        return self


class WorkspaceUpdate(VulnForgeBaseModel):
    """Partial update payload for an existing workspace.

    All fields are optional — only provided fields are updated.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=300,
        description="Updated workspace name.",
    )
    description: str | None = Field(
        default=None,
        description="Updated description.",
    )
    client_name: str | None = Field(
        default=None,
        max_length=200,
        description="Updated client name.",
    )
    client_contact: str | None = Field(
        default=None,
        max_length=200,
        description="Updated client contact.",
    )
    status: WorkspaceStatus | None = Field(
        default=None,
        description="Updated lifecycle status.",
    )
    start_date: date | None = Field(
        default=None,
        description="Updated start date.",
    )
    end_date: date | None = Field(
        default=None,
        description="Updated end date.",
    )
    settings: dict | None = Field(
        default=None,
        description="Updated workspace settings (full replacement).",
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        """Strip whitespace from name if provided."""
        return v.strip() if v else v


class MemberAddRequest(VulnForgeBaseModel):
    """Request body for adding a member to a workspace."""

    user_id: UUID = Field(description="UUID of the user to add.")
    role: WorkspaceMemberRole = Field(
        default=WorkspaceMemberRole.VIEWER,
        description="Per-workspace role for the new member.",
    )


class MemberRoleUpdate(VulnForgeBaseModel):
    """Request body for changing a member's workspace role."""

    role: WorkspaceMemberRole = Field(
        description="New per-workspace role for this member.",
    )


# ── Response Schemas ───────────────────────────────────────────────────────────

class WorkspaceMemberResponse(VulnForgeBaseModel):
    """Member entry as returned by the API."""

    id: UUID = Field(description="Membership record UUID.")
    workspace_id: UUID = Field(description="Workspace UUID.")
    user_id: UUID = Field(description="Member user UUID.")
    role: WorkspaceMemberRole = Field(description="Per-workspace role.")
    invited_by_id: UUID | None = Field(description="UUID of the inviting user.")
    joined_at: datetime = Field(description="UTC timestamp when membership was created.")
    user_email: str | None = Field(
        default=None,
        description="Email of the member (loaded via join).",
    )
    user_username: str | None = Field(
        default=None,
        description="Username of the member (loaded via join).",
    )


class WorkspaceResponse(TimestampedResponse):
    """Full workspace representation returned by the API."""

    name: str = Field(description="Workspace name.")
    description: str | None = Field(description="Description.")
    client_name: str | None = Field(description="Client organisation name.")
    client_contact: str | None = Field(description="Client contact.")
    status: WorkspaceStatus = Field(description="Lifecycle status.")
    start_date: date | None = Field(description="Engagement start date.")
    end_date: date | None = Field(description="Engagement end date.")
    is_archived: bool = Field(description="Whether the workspace is archived.")
    owner_id: UUID = Field(description="Owner user UUID.")
    settings: dict = Field(description="Workspace-level configuration.")
    is_editable: bool = Field(description="Whether the workspace accepts new scans/edits.")
    is_overdue: bool = Field(description="Whether the engagement end date has passed.")


class WorkspaceSummary(VulnForgeBaseModel):
    """Lightweight workspace representation for list views.

    Only includes fields needed to render a workspace card in the dashboard.
    """

    id: UUID
    name: str
    client_name: str | None
    status: WorkspaceStatus
    is_archived: bool
    start_date: date | None
    end_date: date | None
    owner_id: UUID
    created_at: datetime
    updated_at: datetime
    scan_count: int = Field(default=0, description="Total scans in this workspace.")
    open_vulnerability_count: int = Field(
        default=0,
        description="Number of open/confirmed vulnerabilities.",
    )
    member_count: int = Field(default=0, description="Number of workspace members.")


# ── Dashboard Schemas ──────────────────────────────────────────────────────────

class ScanStatusSummary(VulnForgeBaseModel):
    """Scan counts broken down by status."""

    total: int = Field(default=0)
    pending: int = Field(default=0)
    running: int = Field(default=0)
    paused: int = Field(default=0)
    completed: int = Field(default=0)
    failed: int = Field(default=0)
    cancelled: int = Field(default=0)


class VulnerabilitySeveritySummary(VulnForgeBaseModel):
    """Vulnerability counts broken down by severity (open/confirmed only)."""

    critical: int = Field(default=0)
    high: int = Field(default=0)
    medium: int = Field(default=0)
    low: int = Field(default=0)
    info: int = Field(default=0)


class VulnerabilityStatusSummary(VulnForgeBaseModel):
    """Vulnerability counts broken down by triage status."""

    open: int = Field(default=0)
    confirmed: int = Field(default=0)
    false_positive: int = Field(default=0)
    mitigated: int = Field(default=0)
    resolved: int = Field(default=0)


class WorkspaceDashboard(VulnForgeBaseModel):
    """Aggregated statistics for the workspace dashboard view.

    Computed server-side in a single repository call to avoid N+1 queries.
    """

    workspace_id: UUID = Field(description="Workspace UUID.")
    workspace_name: str = Field(description="Workspace name.")
    status: WorkspaceStatus = Field(description="Workspace lifecycle status.")
    is_overdue: bool = Field(description="Whether engagement end date has passed.")
    member_count: int = Field(description="Number of workspace members.")
    scans: ScanStatusSummary = Field(description="Scan counts by status.")
    vulnerabilities_by_severity: VulnerabilitySeveritySummary = Field(
        description="Open vulnerability counts by CVSS severity."
    )
    vulnerabilities_by_status: VulnerabilityStatusSummary = Field(
        description="Vulnerability counts by triage status."
    )
    total_vulnerabilities: int = Field(
        description="Total vulnerability count across all statuses."
    )
    last_scan_at: datetime | None = Field(
        description="UTC timestamp of the most recent scan completion."
    )
    risk_score: float = Field(
        description=(
            "Weighted risk score (0–100) computed from open vulnerability severity. "
            "Critical=10, High=5, Medium=2, Low=1, Info=0."
        )
    )
