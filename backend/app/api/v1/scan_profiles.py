"""
Scan Profile API router — HTTP endpoints for profile management.

Endpoints:
    GET    /profiles                           List profiles
    POST   /profiles                           Create profile
    GET    /profiles/{id}                      Get profile by ID
    PATCH  /profiles/{id}                      Update profile metadata
    DELETE /profiles/{id}                      Delete profile
    POST   /profiles/{id}/clone                Clone profile
    GET    /profiles/{id}/plugins              List profile plugins
    POST   /profiles/{id}/plugins              Add plugin to profile
    PATCH  /profiles/{id}/plugins/{plugin_id}  Update plugin in profile
    DELETE /profiles/{id}/plugins/{plugin_id}  Remove plugin from profile
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
from app.core.constants import API_PROFILES_TAG
from app.models.scan_profile import ProfileType
from app.models.user import UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.scan_profile import (
    ProfilePluginAdd,
    ScanProfileClone,
    ScanProfileCreate,
    ScanProfilePluginResponse,
    ScanProfilePluginUpdate,
    ScanProfileResponse,
    ScanProfileSummary,
    ScanProfileUpdate,
)
from app.services.scan_profile_service import ScanProfileService

router = APIRouter(
    prefix="/profiles",
    tags=[API_PROFILES_TAG],
)


# ── Dependency ────────────────────────────────────────────────────────────────

async def get_profile_service(
    db: DatabaseDep, settings: SettingsDep
) -> ScanProfileService:
    """Construct and return a ScanProfileService."""
    return ScanProfileService(db=db, settings=settings)


ProfileServiceDep = Annotated[ScanProfileService, Depends(get_profile_service)]


# ── Profile CRUD ──────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=PaginatedResponse[ScanProfileSummary],
    status_code=status.HTTP_200_OK,
    summary="List scan profiles",
    description=(
        "Return paginated scan profiles. "
        "By default includes builtin profiles and platform-wide custom profiles. "
        "Filter by workspace to include workspace-scoped profiles. "
        "Builtin profiles are listed first, then custom profiles alphabetically."
    ),
)
async def list_profiles(
    current_user: CurrentUserDep,
    svc: ProfileServiceDep,
    workspace_id: uuid.UUID | None = Query(
        None, description="Include profiles for this workspace."
    ),
    active_only: bool = Query(True, description="Exclude inactive profiles."),
    profile_type: ProfileType | None = Query(None, description="Filter by type."),
    search: str | None = Query(None, description="Search by name."),
    include_builtin: bool = Query(True, description="Include system builtin profiles."),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ScanProfileSummary]:
    return await svc.list_profiles(
        current_user=current_user,
        workspace_id=workspace_id,
        active_only=active_only,
        profile_type=profile_type,
        search=search,
        include_builtin=include_builtin,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=ScanProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a scan profile",
    description=(
        "Create a new custom scan profile. "
        "Optionally specify an initial plugin set with per-plugin config overrides. "
        "For standard configurations, prefer **cloning** a builtin profile. "
        "Requires platform **Analyst** role or higher."
    ),
)
async def create_profile(
    request: Request,
    data: ScanProfileCreate,
    current_user: Annotated[object, Depends(require_role(UserRole.ANALYST))],
    svc: ProfileServiceDep,
) -> ScanProfileResponse:
    from app.models.user import User
    assert isinstance(current_user, User)
    ip = get_client_ip(request)
    return await svc.create_profile(data=data, current_user=current_user, ip_address=ip)


@router.get(
    "/{profile_id}",
    response_model=ScanProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get profile by ID",
    description=(
        "Return full profile details including all plugin entries with "
        "their enable state, execution order, and config overrides."
    ),
)
async def get_profile(
    profile_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: ProfileServiceDep,
) -> ScanProfileResponse:
    return await svc.get_profile(profile_id=profile_id, current_user=current_user)


@router.patch(
    "/{profile_id}",
    response_model=ScanProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update profile metadata",
    description=(
        "Partially update a custom profile's name, description, scan type, "
        "priority, timeout, tags, or active state. "
        "**Builtin profiles cannot be updated** — clone them first."
    ),
)
async def update_profile(
    request: Request,
    profile_id: uuid.UUID,
    data: ScanProfileUpdate,
    current_user: CurrentUserDep,
    svc: ProfileServiceDep,
) -> ScanProfileResponse:
    ip = get_client_ip(request)
    return await svc.update_profile(
        profile_id=profile_id,
        data=data,
        current_user=current_user,
        ip_address=ip,
    )


@router.delete(
    "/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a profile",
    description=(
        "Permanently delete a custom profile. "
        "**Builtin profiles cannot be deleted.** "
        "The operation deletes all associated plugin entries."
    ),
)
async def delete_profile(
    request: Request,
    profile_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: ProfileServiceDep,
) -> Response:
    ip = get_client_ip(request)
    await svc.delete_profile(
        profile_id=profile_id, current_user=current_user, ip_address=ip
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{profile_id}/clone",
    response_model=ScanProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Clone a profile",
    description=(
        "Clone any profile (builtin or custom) into a new **Custom** profile. "
        "All plugin entries and config overrides are copied to the clone. "
        "The clone is fully editable. Use this to customise a builtin profile "
        "for a specific engagement."
    ),
)
async def clone_profile(
    request: Request,
    profile_id: uuid.UUID,
    data: ScanProfileClone,
    current_user: CurrentUserDep,
    svc: ProfileServiceDep,
) -> ScanProfileResponse:
    ip = get_client_ip(request)
    return await svc.clone_profile(
        profile_id=profile_id,
        data=data,
        current_user=current_user,
        ip_address=ip,
    )


# ── Plugin Management ─────────────────────────────────────────────────────────

@router.post(
    "/{profile_id}/plugins",
    response_model=ScanProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Add plugin to profile",
    description=(
        "Add a plugin to the profile with optional enable state, "
        "execution order, and config overrides. "
        "Idempotent — adding an already-present plugin returns 200. "
        "Requires edit permission on the profile."
    ),
)
async def add_plugin(
    request: Request,
    profile_id: uuid.UUID,
    data: ProfilePluginAdd,
    current_user: CurrentUserDep,
    svc: ProfileServiceDep,
) -> ScanProfileResponse:
    ip = get_client_ip(request)
    return await svc.add_plugin(
        profile_id=profile_id, data=data, current_user=current_user, ip_address=ip
    )


@router.patch(
    "/{profile_id}/plugins/{plugin_id}",
    response_model=ScanProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update plugin in profile",
    description=(
        "Update a plugin entry within a profile. "
        "Can change `is_enabled`, `execution_order`, or `config_override`. "
        "Use `is_enabled=false` to disable a plugin without removing it. "
        "`config_override` replaces the existing override entirely."
    ),
)
async def update_plugin(
    request: Request,
    profile_id: uuid.UUID,
    plugin_id: uuid.UUID,
    data: ScanProfilePluginUpdate,
    current_user: CurrentUserDep,
    svc: ProfileServiceDep,
) -> ScanProfileResponse:
    ip = get_client_ip(request)
    return await svc.update_plugin(
        profile_id=profile_id,
        plugin_id=plugin_id,
        data=data,
        current_user=current_user,
        ip_address=ip,
    )


@router.delete(
    "/{profile_id}/plugins/{plugin_id}",
    response_model=ScanProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove plugin from profile",
    description=(
        "Remove a plugin from the profile entirely. "
        "Use PATCH with `is_enabled=false` to disable without removing. "
        "Returns 404 if the plugin is not in this profile."
    ),
)
async def remove_plugin(
    request: Request,
    profile_id: uuid.UUID,
    plugin_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: ProfileServiceDep,
) -> ScanProfileResponse:
    ip = get_client_ip(request)
    return await svc.remove_plugin(
        profile_id=profile_id,
        plugin_id=plugin_id,
        current_user=current_user,
        ip_address=ip,
    )
