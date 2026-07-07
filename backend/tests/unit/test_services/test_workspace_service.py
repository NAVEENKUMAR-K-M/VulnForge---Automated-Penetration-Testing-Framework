"""
Unit tests for WorkspaceService.

All tests use mocked repositories — no real DB required.
Business logic (access control, audit writing, role enforcement) is
verified in isolation from SQL implementation.

Markers: @pytest.mark.unit
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.models.user import User, UserRole
from app.models.workspace import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
    WorkspaceStatus,
)
from app.schemas.workspace import (
    MemberAddRequest,
    MemberRoleUpdate,
    WorkspaceCreate,
    WorkspaceUpdate,
)
from app.services.workspace_service import WorkspaceService


# ── Test Helpers ──────────────────────────────────────────────────────────────

def make_settings() -> MagicMock:
    return MagicMock()


def make_user(
    *,
    role: UserRole = UserRole.ANALYST,
    is_superuser: bool = False,
    is_active: bool = True,
    user_id: uuid.UUID | None = None,
) -> User:
    u = MagicMock(spec=User)
    u.id = user_id or uuid.uuid4()
    u.email = "test@vulnforge.local"
    u.username = "testuser"
    u.role = role
    u.is_superuser = is_superuser
    u.is_active = is_active
    return u


def make_workspace(
    owner_id: uuid.UUID,
    *,
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE,
    is_archived: bool = False,
    name: str = "Test Engagement",
    workspace_id: uuid.UUID | None = None,
) -> Workspace:
    ws = MagicMock(spec=Workspace)
    ws.id = workspace_id or uuid.uuid4()
    ws.name = name
    ws.description = "Test workspace"
    ws.client_name = "Acme Corp"
    ws.client_contact = "alice@acme.com"
    ws.status = status
    ws.is_archived = is_archived
    ws.owner_id = owner_id
    ws.settings = {}
    ws.start_date = None
    ws.end_date = None
    ws.is_editable = not is_archived and status == WorkspaceStatus.ACTIVE
    ws.is_overdue = False
    return ws


def make_membership(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    role: WorkspaceMemberRole = WorkspaceMemberRole.MEMBER,
) -> WorkspaceMember:
    m = MagicMock(spec=WorkspaceMember)
    m.id = uuid.uuid4()
    m.workspace_id = workspace_id
    m.user_id = user_id
    m.role = role
    m.invited_by_id = None
    m.joined_at = MagicMock()
    return m


def make_service(
    owner: User,
    workspace: Workspace | None = None,
    membership: WorkspaceMember | None = None,
) -> tuple[WorkspaceService, MagicMock, MagicMock, MagicMock]:
    """Build WorkspaceService with fully mocked repos."""
    db = AsyncMock()
    svc = WorkspaceService(db=db, settings=make_settings())

    svc._workspace_repo = AsyncMock()
    svc._user_repo = AsyncMock()
    svc._audit_repo = AsyncMock()

    if workspace:
        svc._workspace_repo.get_by_id_for_user.return_value = workspace
        svc._workspace_repo.get.return_value = workspace

    if membership:
        svc._workspace_repo.get_membership.return_value = membership
    else:
        svc._workspace_repo.get_membership.return_value = None

    svc._audit_repo.create_entry.return_value = MagicMock()

    return svc, svc._workspace_repo, svc._user_repo, svc._audit_repo


# ── Tests: Create Workspace ───────────────────────────────────────────────────

@pytest.mark.unit
class TestCreateWorkspace:
    @pytest.mark.asyncio
    async def test_create_workspace_success(self) -> None:
        """Analyst can create a workspace."""
        owner = make_user(role=UserRole.ANALYST)
        svc, ws_repo, _, audit_repo = make_service(owner)

        new_ws = make_workspace(owner_id=owner.id)
        ws_repo.create_from_dict.return_value = new_ws
        ws_repo.add_member.return_value = make_membership(new_ws.id, owner.id, WorkspaceMemberRole.OWNER)

        data = WorkspaceCreate(
            name="Q3 External Pentest",
            client_name="Acme Corp",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )

        result = await svc.create_workspace(data=data, current_user=owner)

        ws_repo.create_from_dict.assert_called_once()
        ws_repo.add_member.assert_called_once_with(
            workspace_id=new_ws.id,
            user_id=owner.id,
            role=WorkspaceMemberRole.OWNER,
            invited_by_id=None,
        )
        audit_repo.create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_workspace_invalid_dates_raises(self) -> None:
        """end_date before start_date raises a Pydantic validation error."""
        with pytest.raises(Exception):  # pydantic ValidationError
            WorkspaceCreate(
                name="Bad Dates",
                start_date=date(2026, 9, 30),
                end_date=date(2026, 9, 1),  # Before start
            )


# ── Tests: Get Workspace ──────────────────────────────────────────────────────

@pytest.mark.unit
class TestGetWorkspace:
    @pytest.mark.asyncio
    async def test_get_workspace_success(self) -> None:
        """Member can retrieve workspace by ID."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id)
        svc, _, _, _ = make_service(owner, workspace=ws)

        result = await svc.get_workspace(workspace_id=ws.id, current_user=owner)
        assert result.id == ws.id

    @pytest.mark.asyncio
    async def test_get_workspace_not_found_raises(self) -> None:
        """Non-member gets 404 (not 403) to prevent existence disclosure."""
        user = make_user()
        svc, ws_repo, _, _ = make_service(user)
        ws_repo.get_by_id_for_user.return_value = None

        with pytest.raises(NotFoundError):
            await svc.get_workspace(workspace_id=uuid.uuid4(), current_user=user)


# ── Tests: Update Workspace ───────────────────────────────────────────────────

@pytest.mark.unit
class TestUpdateWorkspace:
    @pytest.mark.asyncio
    async def test_owner_can_update_workspace(self) -> None:
        """Workspace owner can update metadata."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id)
        membership = make_membership(ws.id, owner.id, WorkspaceMemberRole.OWNER)
        svc, ws_repo, _, audit_repo = make_service(owner, workspace=ws, membership=membership)

        ws_repo.get_membership.return_value = membership

        data = WorkspaceUpdate(name="Updated Name")
        result = await svc.update_workspace(ws.id, data, owner)

        audit_repo.create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_member_cannot_update_workspace(self) -> None:
        """Non-owner member cannot update workspace metadata."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id)
        other_user = make_user()
        membership = make_membership(ws.id, other_user.id, WorkspaceMemberRole.MEMBER)

        svc, ws_repo, _, _ = make_service(other_user, workspace=ws, membership=membership)
        ws_repo.get_by_id_for_user.return_value = ws
        ws_repo.get_membership.return_value = membership

        data = WorkspaceUpdate(name="Should Fail")

        with pytest.raises(PermissionDeniedError):
            await svc.update_workspace(ws.id, data, other_user)

    @pytest.mark.asyncio
    async def test_archive_via_update_raises_validation_error(self) -> None:
        """Setting status=archived via update raises ValidationError."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id)
        membership = make_membership(ws.id, owner.id, WorkspaceMemberRole.OWNER)
        svc, ws_repo, _, _ = make_service(owner, workspace=ws, membership=membership)
        ws_repo.get_membership.return_value = membership

        data = WorkspaceUpdate(status=WorkspaceStatus.ARCHIVED)

        with pytest.raises(ValidationError):
            await svc.update_workspace(ws.id, data, owner)


# ── Tests: Archive / Restore ──────────────────────────────────────────────────

@pytest.mark.unit
class TestArchiveRestore:
    @pytest.mark.asyncio
    async def test_owner_can_archive_workspace(self) -> None:
        """Workspace owner can archive their workspace."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id, is_archived=False)
        membership = make_membership(ws.id, owner.id, WorkspaceMemberRole.OWNER)
        svc, ws_repo, _, audit_repo = make_service(owner, workspace=ws, membership=membership)
        ws_repo.get_membership.return_value = membership

        archived_ws = make_workspace(owner_id=owner.id, is_archived=True, status=WorkspaceStatus.ARCHIVED)
        ws_repo.archive_workspace.return_value = archived_ws

        result = await svc.archive_workspace(ws.id, owner)

        ws_repo.archive_workspace.assert_called_once_with(ws)
        audit_repo.create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_archiving_already_archived_raises(self) -> None:
        """Archiving an already-archived workspace raises ValidationError."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id, is_archived=True)
        membership = make_membership(ws.id, owner.id, WorkspaceMemberRole.OWNER)
        svc, ws_repo, _, _ = make_service(owner, workspace=ws, membership=membership)
        ws_repo.get_membership.return_value = membership

        with pytest.raises(ValidationError):
            await svc.archive_workspace(ws.id, owner)

    @pytest.mark.asyncio
    async def test_owner_can_restore_workspace(self) -> None:
        """Workspace owner can restore an archived workspace."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id, is_archived=True, status=WorkspaceStatus.ARCHIVED)
        membership = make_membership(ws.id, owner.id, WorkspaceMemberRole.OWNER)
        svc, ws_repo, _, audit_repo = make_service(owner, workspace=ws, membership=membership)
        ws_repo.get_membership.return_value = membership

        restored = make_workspace(owner_id=owner.id, is_archived=False, status=WorkspaceStatus.ACTIVE)
        ws_repo.restore_workspace.return_value = restored

        await svc.restore_workspace(ws.id, owner)

        ws_repo.restore_workspace.assert_called_once_with(ws)

    @pytest.mark.asyncio
    async def test_restoring_non_archived_raises(self) -> None:
        """Restoring a non-archived workspace raises ValidationError."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id, is_archived=False)
        membership = make_membership(ws.id, owner.id, WorkspaceMemberRole.OWNER)
        svc, ws_repo, _, _ = make_service(owner, workspace=ws, membership=membership)
        ws_repo.get_membership.return_value = membership

        with pytest.raises(ValidationError):
            await svc.restore_workspace(ws.id, owner)


# ── Tests: Member Management ──────────────────────────────────────────────────

@pytest.mark.unit
class TestMemberManagement:
    @pytest.mark.asyncio
    async def test_owner_can_add_member(self) -> None:
        """Workspace owner can add a new member."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id)
        owner_membership = make_membership(ws.id, owner.id, WorkspaceMemberRole.OWNER)
        svc, ws_repo, user_repo, audit_repo = make_service(
            owner, workspace=ws, membership=owner_membership
        )
        ws_repo.get_membership.side_effect = [owner_membership, None]  # owner check, then target check

        new_user = make_user(role=UserRole.ANALYST)
        user_repo.get.return_value = new_user

        new_member = make_membership(ws.id, new_user.id, WorkspaceMemberRole.VIEWER)
        ws_repo.add_member.return_value = new_member

        data = MemberAddRequest(user_id=new_user.id, role=WorkspaceMemberRole.VIEWER)
        result = await svc.add_member(ws.id, data, owner)

        ws_repo.add_member.assert_called_once()
        audit_repo.create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_owner_cannot_add_member(self) -> None:
        """Member without OWNER role cannot add new members."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id)
        regular_user = make_user()
        member_membership = make_membership(ws.id, regular_user.id, WorkspaceMemberRole.MEMBER)
        svc, ws_repo, _, _ = make_service(
            regular_user, workspace=ws, membership=member_membership
        )
        ws_repo.get_by_id_for_user.return_value = ws
        ws_repo.get_membership.return_value = member_membership

        data = MemberAddRequest(user_id=uuid.uuid4(), role=WorkspaceMemberRole.VIEWER)

        with pytest.raises(PermissionDeniedError):
            await svc.add_member(ws.id, data, regular_user)

    @pytest.mark.asyncio
    async def test_adding_duplicate_member_raises_conflict(self) -> None:
        """Adding an already-member user raises ConflictError."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id)
        existing_user = make_user()
        owner_membership = make_membership(ws.id, owner.id, WorkspaceMemberRole.OWNER)
        existing_membership = make_membership(ws.id, existing_user.id, WorkspaceMemberRole.VIEWER)

        svc, ws_repo, user_repo, _ = make_service(
            owner, workspace=ws, membership=owner_membership
        )
        # First call returns owner membership, second returns existing member
        ws_repo.get_membership.side_effect = [owner_membership, existing_membership]
        user_repo.get.return_value = existing_user

        data = MemberAddRequest(user_id=existing_user.id, role=WorkspaceMemberRole.MEMBER)

        with pytest.raises(ConflictError):
            await svc.add_member(ws.id, data, owner)

    @pytest.mark.asyncio
    async def test_member_can_leave_workspace(self) -> None:
        """A member can remove themselves (leave) without OWNER role."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id)
        member_user = make_user()
        member_membership = make_membership(ws.id, member_user.id, WorkspaceMemberRole.MEMBER)

        svc, ws_repo, _, audit_repo = make_service(
            member_user, workspace=ws, membership=member_membership
        )
        ws_repo.get_membership.return_value = member_membership

        # Self-removal should succeed
        await svc.remove_member(ws.id, member_user.id, member_user)

        ws_repo.remove_member.assert_called_once_with(member_membership)

    @pytest.mark.asyncio
    async def test_cannot_remove_workspace_owner(self) -> None:
        """Attempting to remove the workspace owner raises ValidationError."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id)
        svc, _, _, _ = make_service(owner, workspace=ws)

        with pytest.raises(ValidationError):
            await svc.remove_member(ws.id, owner.id, owner)

    @pytest.mark.asyncio
    async def test_owner_can_change_member_role(self) -> None:
        """Workspace owner can change a member's role."""
        owner = make_user()
        ws = make_workspace(owner_id=owner.id)
        target_user = make_user()
        owner_membership = make_membership(ws.id, owner.id, WorkspaceMemberRole.OWNER)
        target_membership = make_membership(ws.id, target_user.id, WorkspaceMemberRole.VIEWER)

        svc, ws_repo, user_repo, audit_repo = make_service(
            owner, workspace=ws, membership=owner_membership
        )
        ws_repo.get_membership.side_effect = [owner_membership, target_membership]
        user_repo.get.return_value = target_user

        updated_membership = make_membership(ws.id, target_user.id, WorkspaceMemberRole.MEMBER)
        ws_repo.update_member_role.return_value = updated_membership

        data = MemberRoleUpdate(role=WorkspaceMemberRole.MEMBER)
        result = await svc.update_member_role(ws.id, target_user.id, data, owner)

        ws_repo.update_member_role.assert_called_once_with(
            target_membership, WorkspaceMemberRole.MEMBER
        )
        audit_repo.create_entry.assert_called_once()


# ── Tests: Superuser Bypass ───────────────────────────────────────────────────

@pytest.mark.unit
class TestSuperuserBypass:
    @pytest.mark.asyncio
    async def test_superuser_can_access_any_workspace(self) -> None:
        """Superuser can access workspaces they are not a member of."""
        other_owner = make_user()
        ws = make_workspace(owner_id=other_owner.id)
        superuser = make_user(is_superuser=True)

        svc, ws_repo, _, _ = make_service(superuser, workspace=ws)
        # No membership for superuser — but they can still access
        ws_repo.get_membership.return_value = None

        result = await svc.get_workspace(ws.id, superuser)
        assert result.id == ws.id

    @pytest.mark.asyncio
    async def test_superuser_can_archive_any_workspace(self) -> None:
        """Superuser can archive any workspace regardless of membership."""
        other_owner = make_user()
        ws = make_workspace(owner_id=other_owner.id)
        superuser = make_user(is_superuser=True)

        svc, ws_repo, _, audit_repo = make_service(superuser, workspace=ws)
        ws_repo.get_membership.return_value = None  # No membership
        archived = make_workspace(other_owner.id, is_archived=True, status=WorkspaceStatus.ARCHIVED)
        ws_repo.archive_workspace.return_value = archived

        await svc.archive_workspace(ws.id, superuser)
        ws_repo.archive_workspace.assert_called_once()
