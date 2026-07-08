"""
Asset repository for data access and deduplication upserts.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import AssetType, DiscoveredAsset
from app.repositories.base import BaseRepository
from app.schemas.asset import AssetCreate


class AssetRepository(BaseRepository[DiscoveredAsset, dict, dict]):
    """Data access for DiscoveredAssets."""

    model = DiscoveredAsset

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def ingest_assets(
        self,
        workspace_id: uuid.UUID,
        target_id: uuid.UUID,
        scan_id: uuid.UUID,
        assets: list[AssetCreate],
    ) -> int:
        """Upsert a batch of assets, deduplicating by (workspace, value, type).

        If the asset already exists in the workspace, we append the new source_tool
        to its `source_tools` array and update the `updated_at` timestamp.

        Args:
            workspace_id: The workspace UUID.
            target_id:    The target UUID.
            scan_id:      The scan UUID reporting the assets.
            assets:       List of AssetCreate schemas.

        Returns:
            int: Number of items processed.
        """
        if not assets:
            return 0

        # Build list of dicts for bulk insert
        values = []
        for a in assets:
            values.append({
                "workspace_id": workspace_id,
                "target_id": target_id,
                "scan_id": scan_id,
                "asset_type": a.asset_type,
                "value": a.value,
                "source_tools": [a.source_tool],
                "metadata": a.metadata,
            })

        # Create the PostgreSQL insert statement
        stmt = insert(DiscoveredAsset).values(values)

        # On conflict (duplicate workspace_id, value, asset_type)
        # We want to merge the new source_tool into the existing source_tools JSONB array.
        # PostgreSQL JSONB operator '||' concatenates arrays.
        # But we need to ensure uniqueness within the array (no duplicate tool names).
        # We can do this using a subquery or by extracting elements, 
        # but a simpler approach since we use Postgres is to append, 
        # then rely on a service-level background dedup or just allow small duplicates, 
        # or use a raw SQL function.
        # A robust way using Postgres: 
        # source_tools = (
        #    SELECT jsonb_agg(DISTINCT elem)
        #    FROM jsonb_array_elements(discovered_assets.source_tools || EXCLUDED.source_tools) elem
        # )
        
        merge_tools_expr = func.coalesce(
            select(func.jsonb_agg(func.distinct(text("elem"))))
            .select_from(func.jsonb_array_elements(
                DiscoveredAsset.source_tools.op('||')(stmt.excluded.source_tools)
            ).alias("elem")).scalar_subquery(),
            stmt.excluded.source_tools
        )

        update_stmt = stmt.on_conflict_do_update(
            constraint="uq_discovered_assets_workspace_value_type",
            set_={
                "source_tools": merge_tools_expr,
                "metadata": DiscoveredAsset.metadata_dict.op('||')(stmt.excluded.metadata),
                "updated_at": func.now(),
                # We do not override scan_id because scan_id tracks the *first* scan that found it.
            }
        )

        await self._session.execute(update_stmt)
        await self._session.flush()
        return len(assets)

    async def list_assets(
        self,
        workspace_id: uuid.UUID,
        target_id: uuid.UUID | None = None,
        asset_type: AssetType | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[DiscoveredAsset], int]:
        """Paginated list of active assets for a workspace."""
        conditions: list[Any] = [
            DiscoveredAsset.workspace_id == workspace_id,
            DiscoveredAsset.is_active.is_(True),
        ]
        
        if target_id:
            conditions.append(DiscoveredAsset.target_id == target_id)
        
        if asset_type:
            conditions.append(DiscoveredAsset.asset_type == asset_type)
            
        if search:
            conditions.append(DiscoveredAsset.value.ilike(f"%{search}%"))
            
        count_stmt = select(func.count(DiscoveredAsset.id)).where(and_(*conditions))
        total = (await self._session.execute(count_stmt)).scalar_one()
        
        stmt = select(DiscoveredAsset).where(and_(*conditions)).order_by(
            DiscoveredAsset.value
        ).offset(offset).limit(limit)
        
        result = await self._session.execute(stmt)
        return list(result.scalars().all()), total
