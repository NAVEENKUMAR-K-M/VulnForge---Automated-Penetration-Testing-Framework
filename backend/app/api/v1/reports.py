"""
API Router for Reporting Engine.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import PlainTextResponse

from app.api.deps import CurrentUserDep, DatabaseDep, SettingsDep
from app.models.report import ReportFormat
from app.services.reporting_service import ReportingService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/reports",
    tags=["reports"],
)


def get_reporting_service(db: DatabaseDep, settings: SettingsDep) -> ReportingService:
    return ReportingService(db=db, settings=settings)


ReportingServiceDep = Annotated[ReportingService, Depends(get_reporting_service)]


@router.post(
    "/generate",
    summary="Generate a comprehensive security report",
    description=(
        "Synchronously generates a professional assessment report "
        "aggregating all vulnerabilities, targets, discovered assets, "
        "and metadata (ports, technologies, screenshots) for a given workspace. "
        "Requires the caller to be a member or owner of the workspace."
    ),
    responses={
        200: {"description": "The generated report file (PDF, HTML, JSON, or Markdown)."},
        400: {"description": "Invalid format specified."},
        403: {"description": "Not enough permissions to access this workspace."},
        404: {"description": "Workspace not found."},
    },
)
async def generate_report(
    workspace_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: ReportingServiceDep,
    format: ReportFormat = Query(ReportFormat.HTML, description="Format to generate"),
):
    """Generate a workspace assessment report on the fly."""
    
    # Check permissions using the service internally (or do it here)
    await svc._workspace_svc.get_workspace(workspace_id=workspace_id, current_user=current_user)
    
    content, content_type = await svc.generate_report_sync(
        workspace_id=workspace_id,
        format=format
    )
    
    # Define file extension and disposition
    ext = format.value
    if format == ReportFormat.MARKDOWN:
        ext = "md"
        
    filename = f"vulnforge-report-{workspace_id.hex[:8]}.{ext}"
    
    # Return appropriately typed response
    if isinstance(content, bytes):
        return Response(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    else:
        # For text-based formats (HTML, Markdown, JSON)
        return PlainTextResponse(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
