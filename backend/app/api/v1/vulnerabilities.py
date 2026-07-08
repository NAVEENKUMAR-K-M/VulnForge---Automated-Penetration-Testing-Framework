"""
API Router for Vulnerabilities.
"""

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_db, get_settings
from app.models.user import User
from app.models.vulnerability import VulnerabilityStatus
from app.schemas.common import PaginatedResponse
from app.schemas.vulnerability import VulnerabilityResponse
from app.services.vulnerability_service import VulnerabilityService

router = APIRouter()


@router.get(
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}},
    "/workspaces/{workspace_id}/vulnerabilities",
    response_model=PaginatedResponse[VulnerabilityResponse],
    summary="List vulnerabilities in a workspace",
)
async def list_vulnerabilities(
    workspace_id: uuid.UUID,
    target_id: uuid.UUID | None = Query(None, description="Filter by target"),
    scan_id: uuid.UUID | None = Query(None, description="Filter by scan"),
    severity: str | None = Query(None, description="Filter by severity level"),
    status: VulnerabilityStatus | None = Query(None, description="Filter by workflow status"),
    search: str | None = Query(None, description="Search title and description"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
    settings=Depends(get_settings),
) -> PaginatedResponse[VulnerabilityResponse]:
    """Retrieve all vulnerabilities in the specified workspace."""
    svc = VulnerabilityService(db, settings)
    # Convert skip/limit to page/page_size for the service
    page = (skip // limit) + 1
    return await svc.list_vulnerabilities(
        workspace_id=workspace_id,
        current_user=current_user,
        target_id=target_id,
        scan_id=scan_id,
        severity=severity,
        status=status,
        search=search,
        page=page,
        page_size=limit,
    )
