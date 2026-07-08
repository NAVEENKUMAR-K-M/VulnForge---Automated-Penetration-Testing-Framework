"""
Unit tests for the AssetService and Repository deduplication logic.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.asset import AssetType
from app.schemas.asset import AssetCreate
from app.services.asset_service import AssetService


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(mock_db: AsyncMock) -> AssetService:
    svc = AssetService(mock_db)
    svc._repo = AsyncMock()
    svc._workspace_svc = AsyncMock()
    return svc


@pytest.mark.unit
async def test_ingest_assets_calls_repo(service: AssetService) -> None:
    workspace_id = uuid.uuid4()
    target_id = uuid.uuid4()
    scan_id = uuid.uuid4()
    
    assets = [
        AssetCreate(asset_type=AssetType.DOMAIN, value="api.example.com", source_tool="subfinder"),
        AssetCreate(asset_type=AssetType.DOMAIN, value="dev.example.com", source_tool="amass"),
    ]
    
    service._repo.ingest_assets.return_value = 2
    
    result = await service.ingest_assets(workspace_id, target_id, scan_id, assets)
    
    assert result == 2
    service._repo.ingest_assets.assert_called_once_with(
        workspace_id=workspace_id,
        target_id=target_id,
        scan_id=scan_id,
        assets=assets,
    )


@pytest.mark.unit
async def test_list_assets_enforces_rbac(service: AssetService) -> None:
    workspace_id = uuid.uuid4()
    user = MagicMock(id=uuid.uuid4())
    
    # Mock repo to return empty list
    service._repo.list_assets.return_value = ([], 0)
    
    await service.list_assets(workspace_id, user)
    
    # Should have called workspace service to check membership
    service._workspace_svc.assert_membership.assert_called_once_with(
        workspace_id=workspace_id, user_id=user.id
    )
