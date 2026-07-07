"""
Workspace API router — HTTP endpoints for workspace management.

Endpoints:
    POST   /workspaces                           Create workspace
    GET    /workspaces                           List workspaces (paginated)
    GET    /workspaces/{id}                      Get workspace by ID
    PATCH  /workspaces/{id}                      Update workspace
    DELETE /workspaces/{id}                      Archive workspace (soft-delete)
    POST   /workspaces/{id}/restore              Restore archived workspace
    GET    /workspaces/{id}/dashboard            Workspace dashboard statistics
    GET    /workspaces/{id}/members              List workspace members
    POST   /workspaces/{id}/members              Add member
    PATCH  /workspaces/{id}/members/{user_id}    Update member role
    DELETE /workspaces/{id}/members/{user_id}    Remove member
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import (
    CurrentUserDep,
    DatabaseDep,
    SettingsDep,
    get_client_ip,
    require_role,
)
from app.core.constants import API_WORKSPACES_TAG
from app.models.user import UserRole
from app.models.workspace import WorkspaceStatus
from app.schemas.common import MessageResponse, PaginatedResponse
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
from app.services.workspace_service import WorkspaceService

router = APIRouter(
    prefix="/workspaces",
    tags=[API_WORKSPACES_TAG],
)


# ── Dependency ────────────────────────────────────────────────────────────────

async def get_workspace_service(db: DatabaseDep, settings: SettingsDep) -> WorkspaceService:
    """Construct and return a WorkspaceService for the current request."""
    return WorkspaceService(db=db, settings=settings)


WorkspaceServiceDep = Annotated[WorkspaceService, Depends(get_workspace_service)]


# ── Workspace CRUD ────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
    description=(
        "Create a new workspace/engagement. The creating user is automatically "
        "assigned as the workspace **owner**. "
        "Requires at least the **analyst** platform role."
    ),
)
async def create_workspace(
    request: Request,
    data: WorkspaceCreate,
    current_user: Annotated[object, Depends(require_role(UserRole.ANALYST))],
    svc: WorkspaceServiceDep,
) -> WorkspaceResponse:
    """Create workspace endpoint."""
    from app.models.user import User
    assert isinstance(current_user, User)
    ip = get_client_ip(request)
    return await svc.create_workspace(data=data, current_user=current_user, ip_address=ip)


@router.get(
    "",
    response_model=PaginatedResponse[WorkspaceSummary],
    status_code=status.HTTP_200_OK,
    summary="List workspaces",
    description=(
        "Return a paginated list of workspaces the current user can access. "
        "Platform admins and superusers see all workspaces. "
        "Use `include_archived=true` to include archived workspaces."
    ),
)
async def list_workspaces(
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
    include_archived: bool = Query(False, description="Include archived workspaces."),
    status_filter: WorkspaceStatus | None = Query(None, description="Filter by status."),
    page: int = Query(1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Results per page."),
) -> PaginatedResponse[WorkspaceSummary]:
    """List workspaces endpoint."""
    return await svc.list_workspaces(
        current_user=current_user,
        include_archived=include_archived,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get workspace by ID",
    description=(
        "Retrieve full workspace details. Returns 404 if the workspace doesn't "
        "exist **or** the user has no membership (prevents existence disclosure)."
    ),
)
async def get_workspace(
    workspace_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> WorkspaceResponse:
    """Get workspace endpoint."""
    return await svc.get_workspace(workspace_id=workspace_id, current_user=current_user)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update workspace metadata",
    description=(
        "Partially update workspace metadata. Requires **OWNER** role in the workspace. "
        "Use the `DELETE /{id}` endpoint to archive the workspace — setting "
        "`status=archived` here is rejected."
    ),
)
async def update_workspace(
    request: Request,
    workspace_id: uuid.UUID,
    data: WorkspaceUpdate,
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> WorkspaceResponse:
    """Update workspace endpoint."""
    ip = get_client_ip(request)
    return await svc.update_workspace(
        workspace_id=workspace_id,
        data=data,
        current_user=current_user,
        ip_address=ip,
    )


@router.delete(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive (soft-delete) a workspace",
    description=(
        "Soft-delete the workspace by archiving it. "
        "All data (scans, findings, reports) is preserved. "
        "Requires **OWNER** role. Use `POST /{id}/restore` to undo."
    ),
)
async def archive_workspace(
    request: Request,
    workspace_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> WorkspaceResponse:
    """Archive workspace endpoint."""
    ip = get_client_ip(request)
    return await svc.archive_workspace(
        workspace_id=workspace_id,
        current_user=current_user,
        ip_address=ip,
    )


@router.post(
    "/{workspace_id}/restore",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore an archived workspace",
    description=(
        "Restore a previously archived workspace back to **ACTIVE** status. "
        "Requires **OWNER** role or superuser."
    ),
)
async def restore_workspace(
    request: Request,
    workspace_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> WorkspaceResponse:
    """Restore workspace endpoint."""
    ip = get_client_ip(request)
    return await svc.restore_workspace(
        workspace_id=workspace_id,
        current_user=current_user,
        ip_address=ip,
    )


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get(
    "/{workspace_id}/dashboard",
    response_model=WorkspaceDashboard,
    status_code=status.HTTP_200_OK,
    summary="Workspace dashboard statistics",
    description=(
        "Return aggregated engagement statistics for the workspace dashboard: "
        "scan counts by status, vulnerability counts by severity and triage status, "
        "member count, last scan timestamp, and a weighted risk score (0–100)."
    ),
)
async def get_workspace_dashboard(
    workspace_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> WorkspaceDashboard:
    """Dashboard endpoint."""
    return await svc.get_dashboard(workspace_id=workspace_id, current_user=current_user)


# ── Member Management ─────────────────────────────────────────────────────────

@router.get(
    "/{workspace_id}/members",
    response_model=list[WorkspaceMemberResponse],
    status_code=status.HTTP_200_OK,
    summary="List workspace members",
    description="Return all members of the workspace including their per-workspace roles.",
)
async def list_workspace_members(
    workspace_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> list[WorkspaceMemberResponse]:
    """List members endpoint."""
    return await svc.list_members(workspace_id=workspace_id, current_user=current_user)


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member to the workspace",
    description=(
        "Add an existing platform user to this workspace with the specified role. "
        "Requires **OWNER** role in the workspace. "
        "The user must already have an active platform account."
    ),
)
async def add_workspace_member(
    request: Request,
    workspace_id: uuid.UUID,
    data: MemberAddRequest,
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> WorkspaceMemberResponse:
    """Add member endpoint."""
    ip = get_client_ip(request)
    return await svc.add_member(
        workspace_id=workspace_id,
        data=data,
        current_user=current_user,
        ip_address=ip,
    )


@router.patch(
    "/{workspace_id}/members/{target_user_id}",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a member's workspace role",
    description=(
        "Change a workspace member's per-workspace role. "
        "Requires **OWNER** role. Cannot change the workspace owner's role."
    ),
)
async def update_member_role(
    request: Request,
    workspace_id: uuid.UUID,
    target_user_id: uuid.UUID,
    data: MemberRoleUpdate,
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> WorkspaceMemberResponse:
    """Update member role endpoint."""
    ip = get_client_ip(request)
    return await svc.update_member_role(
        workspace_id=workspace_id,
        target_user_id=target_user_id,
        data=data,
        current_user=current_user,
        ip_address=ip,
    )


@router.delete(
    "/{workspace_id}/members/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from the workspace",
    description=(
        "Remove a user from the workspace. "
        "**Owners** can remove any member. "
        "**Members** can only remove themselves (leave the workspace). "
        "Cannot remove the workspace owner."
    ),
)
async def remove_workspace_member(
    request: Request,
    workspace_id: uuid.UUID,
    target_user_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: WorkspaceServiceDep,
) -> Response:
    """Remove member endpoint."""
    ip = get_client_ip(request)
    await svc.remove_member(
        workspace_id=workspace_id,
        target_user_id=target_user_id,
        current_user=current_user,
        ip_address=ip,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
