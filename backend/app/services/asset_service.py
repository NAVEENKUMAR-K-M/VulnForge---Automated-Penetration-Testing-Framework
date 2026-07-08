"""
Asset Service — business logic for Asset Management.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models.asset import AssetType, DiscoveredAsset
from app.models.user import User
from app.repositories.asset import AssetRepository
from app.schemas.asset import AssetCreate, AssetResponse
from app.schemas.common import PaginatedResponse
from app.services.workspace_service import WorkspaceService


class AssetService:
    """Orchestrates asset management and deduplication."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AssetRepository(db)
        self._workspace_svc = WorkspaceService(db)

    async def ingest_assets(
        self,
        workspace_id: uuid.UUID,
        target_id: uuid.UUID,
        scan_id: uuid.UUID,
        assets: list[AssetCreate],
    ) -> int:
        """Ingest a batch of discovered assets.
        
        Called internally by the Scan Engine. Bypasses user RBAC since 
        the scan itself has already been authorized.
        """
        if not assets:
            return 0
        return await self._repo.ingest_assets(
            workspace_id=workspace_id,
            target_id=target_id,
            scan_id=scan_id,
            assets=assets,
        )

    async def list_assets(
        self,
        workspace_id: uuid.UUID,
        current_user: User,
        target_id: uuid.UUID | None = None,
        asset_type: AssetType | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[AssetResponse]:
        """List active assets in a workspace (requires VIEWER)."""
        await self._workspace_svc.assert_membership(
            workspace_id=workspace_id, user_id=current_user.id
        )

        offset = (page - 1) * page_size
        assets, total = await self._repo.list_assets(
            workspace_id=workspace_id,
            target_id=target_id,
            asset_type=asset_type,
            search=search,
            offset=offset,
            limit=page_size,
        )

        responses = [
            AssetResponse(
                id=a.id,
                workspace_id=a.workspace_id,
                target_id=a.target_id,
                scan_id=a.scan_id,
                asset_type=a.asset_type,
                value=a.value,
                source_tools=a.source_tools,
                is_active=a.is_active,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in assets
        ]

        return PaginatedResponse[AssetResponse].build(
            items=responses, total=total, page=page, page_size=page_size
        )

    async def delete_asset(
        self,
        workspace_id: uuid.UUID,
        asset_id: uuid.UUID,
        current_user: User,
    ) -> None:
        """Soft-delete an asset (requires ANALYST)."""
        member = await self._workspace_svc.assert_membership(
            workspace_id=workspace_id, user_id=current_user.id
        )
        if not member.role.can_write():
            raise PermissionDeniedError(
                "Only Analysts or Owners can delete assets."
            )

        asset = await self._repo.get_by_id(asset_id)
        if not asset or asset.workspace_id != workspace_id:
            raise NotFoundError("DiscoveredAsset", str(asset_id))

        asset.is_active = False
        self._db.add(asset)
        await self._db.flush()
