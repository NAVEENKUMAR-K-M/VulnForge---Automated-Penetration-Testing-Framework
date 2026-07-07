"""
Workspace service — business logic for workspace management.

Responsibilities:
    - Enforce workspace access control (ownership, membership, role checks)
    - Coordinate repository calls for multi-step operations
    - Write audit log entries for every security-significant action
    - Raise typed domain exceptions for all error conditions
    - Never expose raw SQLAlchemy to the API layer

Access Control Model:
    Platform admins/superusers: can see and manage all workspaces.
    Workspace OWNER: full control within the workspace.
    Workspace MEMBER: create scans, triage findings.
    Workspace VIEWER: read-only access.
    Non-members: no visibility (workspace doesn't exist from their POV).
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AuditAction
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.models.audit_log import AuditOutcome
from app.models.user import User
from app.models.workspace import WorkspaceMemberRole, WorkspaceStatus
from app.repositories.audit_log import AuditLogRepository
from app.repositories.user import UserRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.workspace import (
    MemberAddRequest,
    MemberRoleUpdate,
    WorkspaceCreate,
    WorkspaceDashboard,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceSummary,
    WorkspaceUpdate,
)

logger = get_logger(__name__)

# ── Workspace member role hierarchy (higher = more privilege) ─────────────────
_MEMBER_ROLE_LEVEL: dict[WorkspaceMemberRole, int] = {
    WorkspaceMemberRole.VIEWER: 0,
    WorkspaceMemberRole.MEMBER: 1,
    WorkspaceMemberRole.OWNER: 2,
}


class WorkspaceService:
    """Orchestrates all workspace management business logic.

    Attributes:
        _db:            Async database session.
        _settings:      Application settings.
        _workspace_repo: Workspace data access.
        _user_repo:     User data access (for member validation).
        _audit_repo:    Audit log writer.
    """

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._workspace_repo = WorkspaceRepository(db)
        self._user_repo = UserRepository(db)
        self._audit_repo = AuditLogRepository(db)

    # ── Internal Helpers ──────────────────────────────────────────────────────

    async def _get_workspace_or_404(
        self,
        workspace_id: uuid.UUID,
        current_user: User,
    ):
        """Fetch a workspace or raise NotFoundError.

        Uses membership-scoped access — non-members get 404 (not 403) to
        prevent workspace existence disclosure.

        Args:
            workspace_id:  The workspace UUID.
            current_user:  The requesting user.

        Returns:
            Workspace: The accessible workspace.

        Raises:
            NotFoundError: If workspace doesn't exist or user has no access.
        """
        workspace = await self._workspace_repo.get_by_id_for_user(
            workspace_id=workspace_id,
            user_id=current_user.id,
            is_superuser=current_user.is_superuser,
        )
        if workspace is None:
            raise NotFoundError("Workspace", str(workspace_id))
        return workspace

    def _get_effective_role(
        self,
        workspace,
        current_user: User,
        membership,
    ) -> WorkspaceMemberRole | None:
        """Determine the user's effective role in the workspace.

        Owners always get OWNER role. Superusers get OWNER role.

        Args:
            workspace:    The workspace ORM instance.
            current_user: The requesting user.
            membership:   The user's WorkspaceMember record (may be None).

        Returns:
            WorkspaceMemberRole | None: Effective role or None for no access.
        """
        if current_user.is_superuser or workspace.owner_id == current_user.id:
            return WorkspaceMemberRole.OWNER
        return membership.role if membership else None

    def _require_workspace_role(
        self,
        effective_role: WorkspaceMemberRole | None,
        minimum: WorkspaceMemberRole,
        action: str = "perform this action",
    ) -> None:
        """Assert the user has at least the minimum required workspace role.

        Args:
            effective_role: The user's current role.
            minimum:        The minimum role required.
            action:         Human-readable action name for error messages.

        Raises:
            PermissionDeniedError: If effective_role < minimum.
        """
        if effective_role is None:
            raise PermissionDeniedError()
        user_level = _MEMBER_ROLE_LEVEL.get(effective_role, -1)
        required_level = _MEMBER_ROLE_LEVEL.get(minimum, 999)
        if user_level < required_level:
            raise PermissionDeniedError(
                f"Workspace {minimum.value} role required to {action}."
            )

    # ── Workspace CRUD ────────────────────────────────────────────────────────

    async def create_workspace(
        self,
        data: WorkspaceCreate,
        current_user: User,
        ip_address: str | None = None,
    ) -> WorkspaceResponse:
        """Create a new workspace.

        The creating user is automatically assigned as the workspace owner
        AND receives an explicit OWNER membership record.

        Args:
            data:         Validated workspace creation payload.
            current_user: The user creating the workspace.
            ip_address:   Client IP for audit logging.

        Returns:
            WorkspaceResponse: The created workspace.
        """
        logger.info(
            "workspace.create.attempt",
            user_id=str(current_user.id),
            name=data.name,
        )

        workspace = await self._workspace_repo.create_from_dict(
            {
                "name": data.name,
                "description": data.description,
                "client_name": data.client_name,
                "client_contact": data.client_contact,
                "start_date": data.start_date,
                "end_date": data.end_date,
                "settings": data.settings,
                "owner_id": current_user.id,
                "status": WorkspaceStatus.ACTIVE,
                "is_archived": False,
            }
        )

        # Auto-add owner as explicit OWNER member (simplifies permission checks)
        await self._workspace_repo.add_member(
            workspace_id=workspace.id,
            user_id=current_user.id,
            role=WorkspaceMemberRole.OWNER,
            invited_by_id=None,
        )

        await self._audit_repo.create_entry(
            action=AuditAction.WORKSPACE_CREATED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="workspace",
            resource_id=workspace.id,
            details={"name": workspace.name, "client_name": workspace.client_name},
        )

        logger.info(
            "workspace.create.success",
            workspace_id=str(workspace.id),
            name=workspace.name,
        )

        return WorkspaceResponse.model_validate(workspace)

    async def get_workspace(
        self,
        workspace_id: uuid.UUID,
        current_user: User,
    ) -> WorkspaceResponse:
        """Retrieve a workspace by ID.

        Args:
            workspace_id:  The workspace UUID.
            current_user:  The requesting user.

        Returns:
            WorkspaceResponse: The workspace.

        Raises:
            NotFoundError: If workspace doesn't exist or user has no access.
        """
        workspace = await self._get_workspace_or_404(workspace_id, current_user)
        return WorkspaceResponse.model_validate(workspace)

    async def list_workspaces(
        self,
        current_user: User,
        *,
        include_archived: bool = False,
        status_filter: WorkspaceStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ):
        """List workspaces visible to the current user with pagination.

        Args:
            current_user:     The requesting user.
            include_archived: Include archived workspaces.
            status_filter:    Optional status filter.
            page:             1-indexed page number.
            page_size:        Items per page.

        Returns:
            PaginatedResponse[WorkspaceSummary]: Paginated workspace summaries.
        """
        from app.schemas.common import PaginatedResponse

        offset = (page - 1) * page_size
        summaries, total = await self._workspace_repo.get_summaries_for_user(
            user_id=current_user.id,
            is_superuser=current_user.is_superuser,
            include_archived=include_archived,
            offset=offset,
            limit=page_size,
        )

        return PaginatedResponse[WorkspaceSummary].build(
            items=summaries,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_workspace(
        self,
        workspace_id: uuid.UUID,
        data: WorkspaceUpdate,
        current_user: User,
        ip_address: str | None = None,
    ) -> WorkspaceResponse:
        """Update a workspace's metadata.

        Requires OWNER role within the workspace.

        Args:
            workspace_id:  The workspace UUID.
            data:          Partial update payload.
            current_user:  The requesting user.
            ip_address:    Client IP for audit logging.

        Returns:
            WorkspaceResponse: The updated workspace.

        Raises:
            NotFoundError:      If workspace not accessible.
            PermissionDeniedError: If user is not an OWNER.
            ValidationError:    If archiving is attempted via update (use archive endpoint).
        """
        workspace = await self._get_workspace_or_404(workspace_id, current_user)
        membership = await self._workspace_repo.get_membership(workspace_id, current_user.id)
        effective_role = self._get_effective_role(workspace, current_user, membership)
        self._require_workspace_role(effective_role, WorkspaceMemberRole.OWNER, "update this workspace")

        # Prevent status transition to ARCHIVED via update (use archive endpoint)
        if data.status == WorkspaceStatus.ARCHIVED:
            raise ValidationError(
                "Use the DELETE /workspaces/{id} endpoint to archive a workspace."
            )

        update_data = data.model_dump(exclude_unset=True, exclude_none=False)
        if update_data:
            for field, value in update_data.items():
                if value is not None or field in ("description", "client_name", "client_contact"):
                    setattr(workspace, field, value)
            self._db.add(workspace)
            await self._db.flush()
            await self._db.refresh(workspace)

        await self._audit_repo.create_entry(
            action=AuditAction.WORKSPACE_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="workspace",
            resource_id=workspace.id,
            details={"changes": list(update_data.keys())},
        )

        logger.info(
            "workspace.update.success",
            workspace_id=str(workspace_id),
            changes=list(update_data.keys()),
        )

        return WorkspaceResponse.model_validate(workspace)

    async def archive_workspace(
        self,
        workspace_id: uuid.UUID,
        current_user: User,
        ip_address: str | None = None,
    ) -> WorkspaceResponse:
        """Soft-delete (archive) a workspace.

        Requires OWNER role. Archives the workspace — does not hard-delete.
        All scans, findings, and reports remain intact.

        Args:
            workspace_id:  The workspace UUID.
            current_user:  The requesting user.
            ip_address:    Client IP for audit logging.

        Returns:
            WorkspaceResponse: The archived workspace.
        """
        workspace = await self._get_workspace_or_404(workspace_id, current_user)
        membership = await self._workspace_repo.get_membership(workspace_id, current_user.id)
        effective_role = self._get_effective_role(workspace, current_user, membership)
        self._require_workspace_role(effective_role, WorkspaceMemberRole.OWNER, "archive this workspace")

        if workspace.is_archived:
            raise ValidationError("Workspace is already archived.")

        workspace = await self._workspace_repo.archive_workspace(workspace)

        await self._audit_repo.create_entry(
            action=AuditAction.WORKSPACE_ARCHIVED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="workspace",
            resource_id=workspace.id,
        )

        logger.info("workspace.archived", workspace_id=str(workspace_id))
        return WorkspaceResponse.model_validate(workspace)

    async def restore_workspace(
        self,
        workspace_id: uuid.UUID,
        current_user: User,
        ip_address: str | None = None,
    ) -> WorkspaceResponse:
        """Restore a previously archived workspace.

        Args:
            workspace_id:  The workspace UUID.
            current_user:  The requesting user.
            ip_address:    Client IP for audit logging.

        Returns:
            WorkspaceResponse: The restored workspace.
        """
        # Must query with include_archived to find it
        workspace = await self._workspace_repo.get(workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace", str(workspace_id))

        if not workspace.is_archived:
            raise ValidationError("Workspace is not archived.")

        membership = await self._workspace_repo.get_membership(workspace_id, current_user.id)
        effective_role = self._get_effective_role(workspace, current_user, membership)
        self._require_workspace_role(effective_role, WorkspaceMemberRole.OWNER, "restore this workspace")

        workspace = await self._workspace_repo.restore_workspace(workspace)

        await self._audit_repo.create_entry(
            action=AuditAction.WORKSPACE_RESTORED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="workspace",
            resource_id=workspace.id,
        )

        logger.info("workspace.restored", workspace_id=str(workspace_id))
        return WorkspaceResponse.model_validate(workspace)

    # ── Dashboard ─────────────────────────────────────────────────────────────

    async def get_dashboard(
        self,
        workspace_id: uuid.UUID,
        current_user: User,
    ) -> WorkspaceDashboard:
        """Return aggregated dashboard statistics for a workspace.

        Args:
            workspace_id:  The workspace UUID.
            current_user:  The requesting user.

        Returns:
            WorkspaceDashboard: Full aggregated stats.
        """
        workspace = await self._get_workspace_or_404(workspace_id, current_user)
        return await self._workspace_repo.get_dashboard(workspace)

    # ── Member Management ─────────────────────────────────────────────────────

    async def list_members(
        self,
        workspace_id: uuid.UUID,
        current_user: User,
    ) -> list[WorkspaceMemberResponse]:
        """List all members of a workspace.

        Requires at least VIEWER role.

        Args:
            workspace_id:  The workspace UUID.
            current_user:  The requesting user.

        Returns:
            list[WorkspaceMemberResponse]: All membership records.
        """
        workspace = await self._get_workspace_or_404(workspace_id, current_user)
        members = await self._workspace_repo.list_members(workspace_id)

        responses: list[WorkspaceMemberResponse] = []
        for m in members:
            # Load user email + username for display
            user = await self._user_repo.get(m.user_id)
            responses.append(
                WorkspaceMemberResponse(
                    id=m.id,
                    workspace_id=m.workspace_id,
                    user_id=m.user_id,
                    role=m.role,
                    invited_by_id=m.invited_by_id,
                    joined_at=m.joined_at,
                    user_email=user.email if user else None,
                    user_username=user.username if user else None,
                )
            )
        return responses

    async def add_member(
        self,
        workspace_id: uuid.UUID,
        data: MemberAddRequest,
        current_user: User,
        ip_address: str | None = None,
    ) -> WorkspaceMemberResponse:
        """Add a user to the workspace.

        Requires OWNER role. The invited user must exist and be active.
        Cannot add the workspace owner (they are already implicitly an OWNER).

        Args:
            workspace_id:  The workspace UUID.
            data:          Member add request with user_id and role.
            current_user:  The requesting user.
            ip_address:    Client IP for audit logging.

        Returns:
            WorkspaceMemberResponse: The new membership record.

        Raises:
            PermissionDeniedError: If current user lacks OWNER role.
            NotFoundError:         If invited user doesn't exist.
            ConflictError:         If user is already a member.
            ValidationError:       If trying to add the workspace owner.
        """
        workspace = await self._get_workspace_or_404(workspace_id, current_user)
        membership = await self._workspace_repo.get_membership(workspace_id, current_user.id)
        effective_role = self._get_effective_role(workspace, current_user, membership)
        self._require_workspace_role(effective_role, WorkspaceMemberRole.OWNER, "manage members")

        # Validate invited user
        invited_user = await self._user_repo.get(data.user_id)
        if invited_user is None or not invited_user.is_active:
            raise NotFoundError("User", str(data.user_id))

        if workspace.owner_id == data.user_id:
            raise ValidationError("The workspace owner is already an implicit OWNER member.")

        # Check for existing membership
        existing = await self._workspace_repo.get_membership(workspace_id, data.user_id)
        if existing is not None:
            raise ConflictError(
                f"User '{invited_user.username}' is already a member of this workspace."
            )

        try:
            member = await self._workspace_repo.add_member(
                workspace_id=workspace_id,
                user_id=data.user_id,
                role=data.role,
                invited_by_id=current_user.id,
            )
        except IntegrityError as exc:
            raise ConflictError("User is already a member of this workspace.") from exc

        await self._audit_repo.create_entry(
            action=AuditAction.WORKSPACE_MEMBER_ADDED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="workspace",
            resource_id=workspace_id,
            details={
                "invited_user_id": str(data.user_id),
                "role": data.role.value,
            },
        )

        logger.info(
            "workspace.member.added",
            workspace_id=str(workspace_id),
            user_id=str(data.user_id),
            role=data.role.value,
        )

        return WorkspaceMemberResponse(
            id=member.id,
            workspace_id=member.workspace_id,
            user_id=member.user_id,
            role=member.role,
            invited_by_id=member.invited_by_id,
            joined_at=member.joined_at,
            user_email=invited_user.email,
            user_username=invited_user.username,
        )

    async def update_member_role(
        self,
        workspace_id: uuid.UUID,
        target_user_id: uuid.UUID,
        data: MemberRoleUpdate,
        current_user: User,
        ip_address: str | None = None,
    ) -> WorkspaceMemberResponse:
        """Change a member's workspace role.

        Requires OWNER role. Cannot change the workspace owner's role.

        Args:
            workspace_id:      The workspace UUID.
            target_user_id:    The member whose role to change.
            data:              New role.
            current_user:      The requesting user.
            ip_address:        Client IP for audit logging.

        Returns:
            WorkspaceMemberResponse: The updated membership.
        """
        workspace = await self._get_workspace_or_404(workspace_id, current_user)
        membership = await self._workspace_repo.get_membership(workspace_id, current_user.id)
        effective_role = self._get_effective_role(workspace, current_user, membership)
        self._require_workspace_role(effective_role, WorkspaceMemberRole.OWNER, "change member roles")

        if workspace.owner_id == target_user_id:
            raise ValidationError("Cannot change the workspace owner's role.")

        target_membership = await self._workspace_repo.get_membership(workspace_id, target_user_id)
        if target_membership is None:
            raise NotFoundError("WorkspaceMember", str(target_user_id))

        old_role = target_membership.role
        updated = await self._workspace_repo.update_member_role(target_membership, data.role)

        await self._audit_repo.create_entry(
            action=AuditAction.WORKSPACE_MEMBER_ROLE_CHANGED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="workspace",
            resource_id=workspace_id,
            details={
                "target_user_id": str(target_user_id),
                "old_role": old_role.value,
                "new_role": data.role.value,
            },
        )

        user = await self._user_repo.get(target_user_id)
        return WorkspaceMemberResponse(
            id=updated.id,
            workspace_id=updated.workspace_id,
            user_id=updated.user_id,
            role=updated.role,
            invited_by_id=updated.invited_by_id,
            joined_at=updated.joined_at,
            user_email=user.email if user else None,
            user_username=user.username if user else None,
        )

    async def remove_member(
        self,
        workspace_id: uuid.UUID,
        target_user_id: uuid.UUID,
        current_user: User,
        ip_address: str | None = None,
    ) -> None:
        """Remove a user from a workspace.

        An OWNER can remove any member. A MEMBER can remove themselves (leave).

        Args:
            workspace_id:     The workspace UUID.
            target_user_id:   The user to remove.
            current_user:     The requesting user.
            ip_address:       Client IP for audit logging.

        Raises:
            PermissionDeniedError: If current user lacks permission to remove.
            ValidationError:       If trying to remove the workspace owner.
        """
        workspace = await self._get_workspace_or_404(workspace_id, current_user)

        if workspace.owner_id == target_user_id:
            raise ValidationError(
                "Cannot remove the workspace owner. Transfer ownership first."
            )

        membership = await self._workspace_repo.get_membership(workspace_id, current_user.id)
        effective_role = self._get_effective_role(workspace, current_user, membership)

        # Owners can remove anyone; members can only remove themselves
        is_self_removal = target_user_id == current_user.id
        if not is_self_removal:
            self._require_workspace_role(
                effective_role, WorkspaceMemberRole.OWNER, "remove other members"
            )

        target_membership = await self._workspace_repo.get_membership(workspace_id, target_user_id)
        if target_membership is None:
            raise NotFoundError("WorkspaceMember", str(target_user_id))

        await self._workspace_repo.remove_member(target_membership)

        await self._audit_repo.create_entry(
            action=AuditAction.WORKSPACE_MEMBER_REMOVED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="workspace",
            resource_id=workspace_id,
            details={
                "removed_user_id": str(target_user_id),
                "self_removal": is_self_removal,
            },
        )

        logger.info(
            "workspace.member.removed",
            workspace_id=str(workspace_id),
            user_id=str(target_user_id),
        )
