"""
Target API router — HTTP endpoints for target management.

Endpoints:
    POST   /targets                         Create target
    GET    /targets                         List targets (paginated + filtered)
    GET    /targets/{id}                    Get target by ID
    PATCH  /targets/{id}                    Update target metadata
    DELETE /targets/{id}                    Deactivate (soft-delete) target
    POST   /targets/{id}/reactivate         Reactivate an inactive target
    PUT    /targets/{id}/tags               Replace entire tag set
    POST   /targets/{id}/tags/{tag}         Add a single tag
    DELETE /targets/{id}/tags/{tag}         Remove a single tag
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request, Response, status

from app.api.deps import (
    CurrentUserDep,
    DatabaseDep,
    SettingsDep,
    get_client_ip,
    require_role,
)
from app.core.constants import API_TARGETS_TAG
from app.models.target import TargetType
from app.models.user import UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.target import (
    BulkTagUpdate,
    TargetCreate,
    TargetDeactivate,
    TargetResponse,
    TargetSummary,
    TargetUpdate,
)
from app.services.target_service import TargetService

router = APIRouter(
    prefix="/targets",
    tags=[API_TARGETS_TAG],
)


# ── Dependency ────────────────────────────────────────────────────────────────

async def get_target_service(
    db: DatabaseDep,
    settings: SettingsDep,
) -> TargetService:
    """Construct and return a TargetService for the current request."""
    return TargetService(db=db, settings=settings)


TargetServiceDep = Annotated[TargetService, Depends(get_target_service)]


# ── Target CRUD ───────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=TargetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new target",
    description=(
        "Register a new scan target. The `value` field is strictly validated "
        "against `target_type`:\n\n"
        "- **host**: Valid IPv4 or IPv6 address (not multicast, not unspecified)\n"
        "- **network**: Valid CIDR notation (min /8 for IPv4, /16 for IPv6)\n"
        "- **url**: HTTP/HTTPS URL with scheme and hostname\n"
        "- **domain**: RFC 1123 hostname, subdomains, or wildcard `*.example.com`\n\n"
        "Invalid values are **rejected at the API layer** — they never touch the database. "
        "Requires platform **analyst** role or higher."
    ),
)
async def create_target(
    request: Request,
    data: TargetCreate,
    current_user: Annotated[object, Depends(require_role(UserRole.ANALYST))],
    svc: TargetServiceDep,
) -> TargetResponse:
    """Create target endpoint."""
    from app.models.user import User
    assert isinstance(current_user, User)
    ip = get_client_ip(request)
    return await svc.create_target(data=data, current_user=current_user, ip_address=ip)


@router.get(
    "",
    response_model=PaginatedResponse[TargetSummary],
    status_code=status.HTTP_200_OK,
    summary="List targets",
    description=(
        "Return a paginated, filterable list of targets. "
        "Supports filtering by type, tag, status, and workspace. "
        "Supports full-text search across name and value fields."
    ),
)
async def list_targets(
    current_user: CurrentUserDep,
    svc: TargetServiceDep,
    active_only: bool = Query(True, description="Exclude inactive targets."),
    target_type: TargetType | None = Query(None, description="Filter by target type."),
    tag: str | None = Query(None, description="Filter by tag label (exact match)."),
    search: str | None = Query(None, description="Search name and value (case-insensitive)."),
    workspace_id: uuid.UUID | None = Query(
        None, description="Filter targets with scans in this workspace."
    ),
    page: int = Query(1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(20, ge=1, le=100, description="Results per page."),
) -> PaginatedResponse[TargetSummary]:
    """List targets endpoint."""
    return await svc.list_targets(
        current_user=current_user,
        active_only=active_only,
        target_type=target_type,
        tag_filter=tag,
        search=search,
        workspace_id=workspace_id,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{target_id}",
    response_model=TargetResponse,
    status_code=status.HTTP_200_OK,
    summary="Get target by ID",
    description="Retrieve full target details including tags, scan count, and open vulnerability count.",
)
async def get_target(
    target_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: TargetServiceDep,
) -> TargetResponse:
    """Get target endpoint."""
    return await svc.get_target(target_id=target_id, current_user=current_user)


@router.patch(
    "/{target_id}",
    response_model=TargetResponse,
    status_code=status.HTTP_200_OK,
    summary="Update target metadata",
    description=(
        "Partially update a target. Only the creator, admins, or superusers may edit. "
        "When updating `value`, `target_type` must also be provided (and vice versa) "
        "since value validity depends on type. The updated value is re-validated."
    ),
)
async def update_target(
    request: Request,
    target_id: uuid.UUID,
    data: TargetUpdate,
    current_user: CurrentUserDep,
    svc: TargetServiceDep,
) -> TargetResponse:
    """Update target endpoint."""
    ip = get_client_ip(request)
    return await svc.update_target(
        target_id=target_id,
        data=data,
        current_user=current_user,
        ip_address=ip,
    )


@router.delete(
    "/{target_id}",
    response_model=TargetResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate (soft-delete) a target",
    description=(
        "Mark a target as inactive. Inactive targets cannot be used in new scans, "
        "but all historical scan data and findings are preserved. "
        "Use `POST /{id}/reactivate` to re-enable."
    ),
)
async def deactivate_target(
    request: Request,
    target_id: uuid.UUID,
    data: TargetDeactivate,
    current_user: CurrentUserDep,
    svc: TargetServiceDep,
) -> TargetResponse:
    """Deactivate target endpoint."""
    ip = get_client_ip(request)
    return await svc.deactivate_target(
        target_id=target_id,
        data=data,
        current_user=current_user,
        ip_address=ip,
    )


@router.post(
    "/{target_id}/reactivate",
    response_model=TargetResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivate an inactive target",
    description="Re-enable a previously deactivated target, making it available for new scans.",
)
async def reactivate_target(
    request: Request,
    target_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: TargetServiceDep,
) -> TargetResponse:
    """Reactivate target endpoint."""
    ip = get_client_ip(request)
    return await svc.reactivate_target(
        target_id=target_id,
        current_user=current_user,
        ip_address=ip,
    )


# ── Tag Management ────────────────────────────────────────────────────────────

@router.put(
    "/{target_id}/tags",
    response_model=TargetResponse,
    status_code=status.HTTP_200_OK,
    summary="Replace all target tags",
    description=(
        "Replace the entire tag set for a target (PUT semantics). "
        "All existing tags are removed and replaced with the provided list. "
        "Pass an empty list `[]` to clear all tags. "
        "Tags are validated and normalised to lowercase."
    ),
)
async def replace_tags(
    request: Request,
    target_id: uuid.UUID,
    data: BulkTagUpdate,
    current_user: CurrentUserDep,
    svc: TargetServiceDep,
) -> TargetResponse:
    """Replace tags endpoint."""
    ip = get_client_ip(request)
    return await svc.replace_tags(
        target_id=target_id,
        data=data,
        current_user=current_user,
        ip_address=ip,
    )


@router.post(
    "/{target_id}/tags/{tag}",
    response_model=TargetResponse,
    status_code=status.HTTP_200_OK,
    summary="Add a single tag",
    description=(
        "Add a single tag to the target. Idempotent — adding an already-existing "
        "tag returns 200 without error. "
        "Tags are normalised to lowercase. Maximum 20 tags per target."
    ),
)
async def add_tag(
    request: Request,
    target_id: uuid.UUID,
    tag: str,
    current_user: CurrentUserDep,
    svc: TargetServiceDep,
) -> TargetResponse:
    """Add tag endpoint."""
    ip = get_client_ip(request)
    return await svc.add_tag(
        target_id=target_id,
        raw_tag=tag,
        current_user=current_user,
        ip_address=ip,
    )


@router.delete(
    "/{target_id}/tags/{tag}",
    response_model=TargetResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove a single tag",
    description="Remove a specific tag from the target. Returns 404 if the tag doesn't exist.",
)
async def remove_tag(
    request: Request,
    target_id: uuid.UUID,
    tag: str,
    current_user: CurrentUserDep,
    svc: TargetServiceDep,
) -> TargetResponse:
    """Remove tag endpoint."""
    ip = get_client_ip(request)
    return await svc.remove_tag(
        target_id=target_id,
        tag=tag,
        current_user=current_user,
        ip_address=ip,
    )
