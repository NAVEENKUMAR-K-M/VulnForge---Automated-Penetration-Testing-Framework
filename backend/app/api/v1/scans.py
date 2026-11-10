"""
Scan API router — create, list, inspect, and cancel scans.

Endpoints (workspace-scoped):
    POST   /workspaces/{workspace_id}/scans              Create + dispatch a scan
    GET    /workspaces/{workspace_id}/scans              List scans
    GET    /workspaces/{workspace_id}/scans/{scan_id}    Get scan detail
    POST   /workspaces/{workspace_id}/scans/{scan_id}/cancel  Cancel a scan

Scope is enforced in the service (default-deny) before any scan is created.
Creating or cancelling a scan requires the platform **Analyst** role or higher.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    CurrentUserDep,
    DatabaseDep,
    SettingsDep,
    require_role,
)
from app.models.scan import ScanStatus
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.scan import ScanCreate, ScanResponse, ScanSummary
from app.services.scan_service import ScanService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/scans",
    tags=["scans"],
)


async def get_scan_service(db: DatabaseDep, settings: SettingsDep) -> ScanService:
    """Construct a ScanService."""
    return ScanService(db=db, settings=settings)


ScanServiceDep = Annotated[ScanService, Depends(get_scan_service)]


@router.post(
    "",
    response_model=ScanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and dispatch a scan",
    description=(
        "Validate the target against the workspace scope (default-deny), "
        "resolve the plugin set (from a profile or by scan type), persist the "
        "scan, and enqueue it for background execution. Requires **Analyst** role."
    ),
)
async def create_scan(
    workspace_id: uuid.UUID,
    data: ScanCreate,
    current_user: Annotated[object, Depends(require_role(UserRole.ANALYST))],
    svc: ScanServiceDep,
) -> ScanResponse:
    assert isinstance(current_user, User)
    return await svc.create_scan(workspace_id=workspace_id, data=data, current_user=current_user)


@router.get(
    "",
    response_model=PaginatedResponse[ScanSummary],
    status_code=status.HTTP_200_OK,
    summary="List scans",
    description="Return paginated scans for the workspace, newest first.",
)
async def list_scans(
    workspace_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: ScanServiceDep,
    status_filter: ScanStatus | None = Query(None, alias="status", description="Filter by status."),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[ScanSummary]:
    return await svc.list_scans(
        workspace_id=workspace_id,
        current_user=current_user,
        status_filter=status_filter,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{scan_id}",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Get scan detail",
)
async def get_scan(
    workspace_id: uuid.UUID,
    scan_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: ScanServiceDep,
) -> ScanResponse:
    return await svc.get_scan(
        workspace_id=workspace_id, scan_id=scan_id, current_user=current_user
    )


@router.post(
    "/{scan_id}/cancel",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a scan",
    description="Revoke the running task and mark the scan cancelled. Requires **Analyst** role.",
)
async def cancel_scan(
    workspace_id: uuid.UUID,
    scan_id: uuid.UUID,
    current_user: Annotated[object, Depends(require_role(UserRole.ANALYST))],
    svc: ScanServiceDep,
) -> ScanResponse:
    assert isinstance(current_user, User)
    return await svc.cancel_scan(
        workspace_id=workspace_id, scan_id=scan_id, current_user=current_user
    )
