"""
Assets API router.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import CurrentUserDep, DatabaseDep, get_client_ip
from app.core.constants import API_ASSETS_TAG
from app.models.asset import AssetType
from app.schemas.asset import AssetResponse
from app.schemas.common import PaginatedResponse
from app.services.asset_service import AssetService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/assets",
    tags=[API_ASSETS_TAG],
)


async def get_asset_service(db: DatabaseDep) -> AssetService:
    return AssetService(db=db)


AssetServiceDep = Annotated[AssetService, Depends(get_asset_service)]


@router.get(
    "",
    response_model=PaginatedResponse[AssetResponse],
    status_code=status.HTTP_200_OK,
    summary="List discovered assets",
)
async def list_assets(
    workspace_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: AssetServiceDep,
    target_id: uuid.UUID | None = Query(None),
    asset_type: AssetType | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[AssetResponse]:
    return await svc.list_assets(
        workspace_id=workspace_id,
        current_user=current_user,
        target_id=target_id,
        asset_type=asset_type,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an asset",
)
async def delete_asset(
    workspace_id: uuid.UUID,
    asset_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: AssetServiceDep,
) -> Response:
    await svc.delete_asset(
        workspace_id=workspace_id,
        asset_id=asset_id,
        current_user=current_user,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
