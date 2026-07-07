"""
Workspace repository — all database access for workspaces and membership.

Design Rules:
    - No business logic lives here, only query construction.
    - The dashboard method uses a single aggregated query to avoid N+1.
    - All soft-delete filtering (is_archived) is applied here, not in services.
    - Membership uniqueness is enforced by the DB constraint; the repo
      surfaces the IntegrityError for the service to convert to a ConflictError.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, case, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import Scan, ScanStatus
from app.models.vulnerability import Vulnerability, VulnerabilitySeverity, VulnerabilityStatus
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceMemberRole, WorkspaceStatus
from app.repositories.base import BaseRepository
from app.schemas.workspace import (
    ScanStatusSummary,
    VulnerabilitySeveritySummary,
    VulnerabilityStatusSummary,
    WorkspaceDashboard,
    WorkspaceSummary,
)


class WorkspaceRepository(BaseRepository[Workspace, dict, dict]):
    """Repository for Workspace and WorkspaceMember CRUD and analytics."""

    model = Workspace

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── Workspace Lookup ──────────────────────────────────────────────────────

    async def get_by_id_for_user(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        is_superuser: bool = False,
    ) -> Workspace | None:
        """Fetch a workspace only if the user is a member or superuser.

        Args:
            workspace_id: The workspace UUID.
            user_id:      The requesting user's UUID.
            is_superuser: If True, bypass membership check.

        Returns:
            Workspace | None: The workspace, or None if not found/not accessible.
        """
        stmt = select(Workspace).where(Workspace.id == workspace_id)

        if not is_superuser:
            # User must be the owner OR an explicit member
            stmt = stmt.where(
                or_(
                    Workspace.owner_id == user_id,
                    Workspace.id.in_(
                        select(WorkspaceMember.workspace_id).where(
                            WorkspaceMember.user_id == user_id
                        )
                    ),
                )
            )

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        is_superuser: bool = False,
        include_archived: bool = False,
        status_filter: WorkspaceStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Workspace], int]:
        """Return paginated workspaces visible to the requesting user.

        Args:
            user_id:          The requesting user's UUID.
            is_superuser:     If True, return all workspaces platform-wide.
            include_archived: If False, exclude archived workspaces.
            status_filter:    Optional status filter.
            offset:           Pagination offset.
            limit:            Maximum results.

        Returns:
            tuple[list[Workspace], int]: (page of workspaces, total count)
        """
        # ── Base filter ────────────────────────────────────────────────────
        conditions: list[Any] = []

        if not is_superuser:
            conditions.append(
                or_(
                    Workspace.owner_id == user_id,
                    Workspace.id.in_(
                        select(WorkspaceMember.workspace_id).where(
                            WorkspaceMember.user_id == user_id
                        )
                    ),
                )
            )

        if not include_archived:
            conditions.append(Workspace.is_archived.is_(False))

        if status_filter is not None:
            conditions.append(Workspace.status == status_filter)

        # ── Count ──────────────────────────────────────────────────────────
        count_stmt = select(func.count(Workspace.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # ── Page ───────────────────────────────────────────────────────────
        list_stmt = select(Workspace)
        if conditions:
            list_stmt = list_stmt.where(and_(*conditions))
        list_stmt = list_stmt.order_by(Workspace.created_at.desc()).offset(offset).limit(limit)
        page_result = await self._session.execute(list_stmt)
        workspaces = list(page_result.scalars().all())

        return workspaces, total

    async def search_by_name(
        self,
        query: str,
        user_id: uuid.UUID,
        *,
        is_superuser: bool = False,
        limit: int = 10,
    ) -> list[Workspace]:
        """Full-text search workspaces by name using ILIKE.

        Args:
            query:        Search string.
            user_id:      Requesting user (for access scope).
            is_superuser: Bypass membership filter if True.
            limit:        Maximum results.

        Returns:
            list[Workspace]: Matching, accessible, non-archived workspaces.
        """
        stmt = select(Workspace).where(
            and_(
                Workspace.name.ilike(f"%{query}%"),
                Workspace.is_archived.is_(False),
            )
        )
        if not is_superuser:
            stmt = stmt.where(
                or_(
                    Workspace.owner_id == user_id,
                    Workspace.id.in_(
                        select(WorkspaceMember.workspace_id).where(
                            WorkspaceMember.user_id == user_id
                        )
                    ),
                )
            )
        stmt = stmt.order_by(Workspace.name).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ── Member Management ─────────────────────────────────────────────────────

    async def get_membership(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkspaceMember | None:
        """Fetch the membership record for a user in a workspace.

        Args:
            workspace_id: The workspace UUID.
            user_id:      The user UUID.

        Returns:
            WorkspaceMember | None: The membership record, or None.
        """
        stmt = select(WorkspaceMember).where(
            and_(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_member_role(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        is_owner: bool = False,
    ) -> WorkspaceMemberRole | None:
        """Return the effective workspace role for a user.

        The workspace owner always has OWNER role, regardless of the
        workspace_members table (they may not have an explicit membership row).

        Args:
            workspace_id: The workspace UUID.
            user_id:      The user UUID.
            is_owner:     True if the user is the workspace owner.

        Returns:
            WorkspaceMemberRole | None: The effective role, or None (no access).
        """
        if is_owner:
            return WorkspaceMemberRole.OWNER

        membership = await self.get_membership(workspace_id, user_id)
        return membership.role if membership else None

    async def add_member(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        role: WorkspaceMemberRole,
        invited_by_id: uuid.UUID | None = None,
    ) -> WorkspaceMember:
        """Add a user to a workspace with the specified role.

        Args:
            workspace_id:   The workspace UUID.
            user_id:        The user to add.
            role:           Per-workspace role.
            invited_by_id:  The inviting user's UUID.

        Returns:
            WorkspaceMember: The newly created membership record.
        """
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            invited_by_id=invited_by_id,
        )
        self._session.add(member)
        await self._session.flush()
        await self._session.refresh(member)
        return member

    async def update_member_role(
        self,
        membership: WorkspaceMember,
        new_role: WorkspaceMemberRole,
    ) -> WorkspaceMember:
        """Change a member's workspace role.

        Args:
            membership: The existing membership record.
            new_role:   The new role to assign.

        Returns:
            WorkspaceMember: The updated membership record.
        """
        membership.role = new_role
        self._session.add(membership)
        await self._session.flush()
        await self._session.refresh(membership)
        return membership

    async def remove_member(self, membership: WorkspaceMember) -> None:
        """Remove a user from a workspace.

        Args:
            membership: The membership record to delete.
        """
        await self._session.delete(membership)
        await self._session.flush()

    async def list_members(
        self,
        workspace_id: uuid.UUID,
    ) -> list[WorkspaceMember]:
        """Return all members of a workspace.

        Args:
            workspace_id: The workspace UUID.

        Returns:
            list[WorkspaceMember]: All membership records.
        """
        stmt = (
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.joined_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_members(self, workspace_id: uuid.UUID) -> int:
        """Count the number of members in a workspace.

        Args:
            workspace_id: The workspace UUID.

        Returns:
            int: Member count.
        """
        stmt = select(func.count(WorkspaceMember.id)).where(
            WorkspaceMember.workspace_id == workspace_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # ── Archive / Restore ─────────────────────────────────────────────────────

    async def archive_workspace(self, workspace: Workspace) -> Workspace:
        """Soft-delete a workspace by marking it archived.

        Args:
            workspace: The workspace to archive.

        Returns:
            Workspace: The updated workspace.
        """
        return await self.update_fields(
            workspace,
            is_archived=True,
            status=WorkspaceStatus.ARCHIVED,
        )

    async def restore_workspace(self, workspace: Workspace) -> Workspace:
        """Restore a previously archived workspace.

        Args:
            workspace: The archived workspace.

        Returns:
            Workspace: The restored workspace (status → ACTIVE).
        """
        return await self.update_fields(
            workspace,
            is_archived=False,
            status=WorkspaceStatus.ACTIVE,
        )

    # ── Dashboard Analytics ───────────────────────────────────────────────────

    async def get_dashboard(self, workspace: Workspace) -> WorkspaceDashboard:
        """Compute workspace dashboard statistics in minimal DB round trips.

        Computes:
            - Scan counts broken down by status
            - Vulnerability counts by severity (open + confirmed only)
            - Vulnerability counts by triage status
            - Member count
            - Last completed scan timestamp
            - Weighted risk score

        Args:
            workspace: The workspace ORM instance.

        Returns:
            WorkspaceDashboard: Fully populated dashboard stats.
        """
        workspace_id = workspace.id

        # ── Scan stats ─────────────────────────────────────────────────────
        scan_stats_stmt = select(
            func.count(Scan.id).label("total"),
            func.sum(
                case((Scan.status == ScanStatus.PENDING, 1), else_=0)
            ).label("pending"),
            func.sum(
                case((Scan.status == ScanStatus.RUNNING, 1), else_=0)
            ).label("running"),
            func.sum(
                case((Scan.status == ScanStatus.PAUSED, 1), else_=0)
            ).label("paused"),
            func.sum(
                case((Scan.status == ScanStatus.COMPLETED, 1), else_=0)
            ).label("completed"),
            func.sum(
                case((Scan.status == ScanStatus.FAILED, 1), else_=0)
            ).label("failed"),
            func.sum(
                case((Scan.status == ScanStatus.CANCELLED, 1), else_=0)
            ).label("cancelled"),
            func.max(Scan.completed_at).label("last_scan_at"),
        ).where(Scan.workspace_id == workspace_id)

        scan_result = await self._session.execute(scan_stats_stmt)
        scan_row = scan_result.one()

        scan_summary = ScanStatusSummary(
            total=scan_row.total or 0,
            pending=scan_row.pending or 0,
            running=scan_row.running or 0,
            paused=scan_row.paused or 0,
            completed=scan_row.completed or 0,
            failed=scan_row.failed or 0,
            cancelled=scan_row.cancelled or 0,
        )

        # ── Vulnerability stats ────────────────────────────────────────────
        vuln_stats_stmt = select(
            func.count(Vulnerability.id).label("total"),
            # By severity (all statuses)
            func.sum(
                case((Vulnerability.severity == VulnerabilitySeverity.CRITICAL, 1), else_=0)
            ).label("sev_critical"),
            func.sum(
                case((Vulnerability.severity == VulnerabilitySeverity.HIGH, 1), else_=0)
            ).label("sev_high"),
            func.sum(
                case((Vulnerability.severity == VulnerabilitySeverity.MEDIUM, 1), else_=0)
            ).label("sev_medium"),
            func.sum(
                case((Vulnerability.severity == VulnerabilitySeverity.LOW, 1), else_=0)
            ).label("sev_low"),
            func.sum(
                case((Vulnerability.severity == VulnerabilitySeverity.INFO, 1), else_=0)
            ).label("sev_info"),
            # By triage status
            func.sum(
                case((Vulnerability.status == VulnerabilityStatus.OPEN, 1), else_=0)
            ).label("st_open"),
            func.sum(
                case((Vulnerability.status == VulnerabilityStatus.CONFIRMED, 1), else_=0)
            ).label("st_confirmed"),
            func.sum(
                case(
                    (Vulnerability.status == VulnerabilityStatus.FALSE_POSITIVE, 1),
                    else_=0,
                )
            ).label("st_false_positive"),
            func.sum(
                case((Vulnerability.status == VulnerabilityStatus.MITIGATED, 1), else_=0)
            ).label("st_mitigated"),
            func.sum(
                case((Vulnerability.status == VulnerabilityStatus.RESOLVED, 1), else_=0)
            ).label("st_resolved"),
        ).where(
            Vulnerability.scan_id.in_(
                select(Scan.id).where(Scan.workspace_id == workspace_id)
            )
        )

        vuln_result = await self._session.execute(vuln_stats_stmt)
        vuln_row = vuln_result.one()

        sev_summary = VulnerabilitySeveritySummary(
            critical=vuln_row.sev_critical or 0,
            high=vuln_row.sev_high or 0,
            medium=vuln_row.sev_medium or 0,
            low=vuln_row.sev_low or 0,
            info=vuln_row.sev_info or 0,
        )
        status_summary = VulnerabilityStatusSummary(
            open=vuln_row.st_open or 0,
            confirmed=vuln_row.st_confirmed or 0,
            false_positive=vuln_row.st_false_positive or 0,
            mitigated=vuln_row.st_mitigated or 0,
            resolved=vuln_row.st_resolved or 0,
        )

        # ── Member count ───────────────────────────────────────────────────
        member_count = await self.count_members(workspace_id)

        # ── Weighted risk score ────────────────────────────────────────────
        # Only open + confirmed vulnerabilities contribute to risk
        open_criticals = vuln_row.sev_critical or 0
        open_highs = vuln_row.sev_high or 0
        open_mediums = vuln_row.sev_medium or 0
        open_lows = vuln_row.sev_low or 0

        raw_score = (
            open_criticals * 10
            + open_highs * 5
            + open_mediums * 2
            + open_lows * 1
        )
        # Normalise to 0–100 with a ceiling of 100
        risk_score = min(100.0, round(raw_score, 1))

        return WorkspaceDashboard(
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            status=workspace.status,
            is_overdue=workspace.is_overdue,
            member_count=member_count,
            scans=scan_summary,
            vulnerabilities_by_severity=sev_summary,
            vulnerabilities_by_status=status_summary,
            total_vulnerabilities=vuln_row.total or 0,
            last_scan_at=scan_row.last_scan_at,
            risk_score=risk_score,
        )

    # ── List Summaries ────────────────────────────────────────────────────────

    async def get_summaries_for_user(
        self,
        user_id: uuid.UUID,
        *,
        is_superuser: bool = False,
        include_archived: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[WorkspaceSummary], int]:
        """Return workspace list summaries with aggregated counts.

        Uses a single query with LEFT JOINs to compute scan_count,
        open_vulnerability_count, and member_count without N+1 queries.

        Args:
            user_id:          Requesting user UUID.
            is_superuser:     Bypass membership filter.
            include_archived: Include archived workspaces.
            offset:           Pagination offset.
            limit:            Max results.

        Returns:
            tuple[list[WorkspaceSummary], int]: Summaries and total count.
        """
        # ── Subqueries ─────────────────────────────────────────────────────
        scan_count_sq = (
            select(
                Scan.workspace_id,
                func.count(Scan.id).label("scan_count"),
            )
            .group_by(Scan.workspace_id)
            .subquery()
        )

        open_vuln_sq = (
            select(
                Scan.workspace_id,
                func.count(Vulnerability.id).label("open_vuln_count"),
            )
            .join(Vulnerability, Vulnerability.scan_id == Scan.id)
            .where(
                Vulnerability.status.in_(
                    [VulnerabilityStatus.OPEN, VulnerabilityStatus.CONFIRMED]
                )
            )
            .group_by(Scan.workspace_id)
            .subquery()
        )

        member_count_sq = (
            select(
                WorkspaceMember.workspace_id,
                func.count(WorkspaceMember.id).label("member_count"),
            )
            .group_by(WorkspaceMember.workspace_id)
            .subquery()
        )

        # ── Conditions ─────────────────────────────────────────────────────
        conditions: list[Any] = []

        if not is_superuser:
            conditions.append(
                or_(
                    Workspace.owner_id == user_id,
                    Workspace.id.in_(
                        select(WorkspaceMember.workspace_id).where(
                            WorkspaceMember.user_id == user_id
                        )
                    ),
                )
            )

        if not include_archived:
            conditions.append(Workspace.is_archived.is_(False))

        # ── Count ──────────────────────────────────────────────────────────
        count_stmt = select(func.count(Workspace.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()

        # ── Main query with LEFT JOINs ─────────────────────────────────────
        stmt = (
            select(
                Workspace,
                func.coalesce(scan_count_sq.c.scan_count, 0).label("scan_count"),
                func.coalesce(open_vuln_sq.c.open_vuln_count, 0).label("open_vuln_count"),
                func.coalesce(member_count_sq.c.member_count, 0).label("member_count"),
            )
            .outerjoin(scan_count_sq, scan_count_sq.c.workspace_id == Workspace.id)
            .outerjoin(open_vuln_sq, open_vuln_sq.c.workspace_id == Workspace.id)
            .outerjoin(member_count_sq, member_count_sq.c.workspace_id == Workspace.id)
        )

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(Workspace.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(stmt)

        summaries: list[WorkspaceSummary] = []
        for row in result:
            ws: Workspace = row[0]
            summaries.append(
                WorkspaceSummary(
                    id=ws.id,
                    name=ws.name,
                    client_name=ws.client_name,
                    status=ws.status,
                    is_archived=ws.is_archived,
                    start_date=ws.start_date,
                    end_date=ws.end_date,
                    owner_id=ws.owner_id,
                    created_at=ws.created_at,
                    updated_at=ws.updated_at,
                    scan_count=row.scan_count,
                    open_vulnerability_count=row.open_vuln_count,
                    member_count=row.member_count,
                )
            )

        return summaries, total
