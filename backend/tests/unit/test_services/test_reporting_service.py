import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.reporting_service import ReportingService
from app.models.report import ReportFormat

@pytest.mark.asyncio
async def test_generate_report_sync_json():
    # Arrange
    db_mock = AsyncMock()
    settings_mock = MagicMock()
    
    svc = ReportingService(db=db_mock, settings=settings_mock)
    
    # Mock _gather_workspace_data
    svc._gather_workspace_data = AsyncMock()
    
    mock_workspace = MagicMock()
    mock_workspace.name = "Test Workspace"
    
    mock_vuln = MagicMock()
    mock_vuln.title = "Test Vuln"
    mock_vuln.severity.value = "critical"
    mock_vuln.cve_id = "CVE-2023-1234"
    mock_vuln.affected_host = "example.com"
    
    svc._gather_workspace_data.return_value = {
        "workspace": mock_workspace,
        "date": "2026-07-08",
        "assets": [MagicMock(), MagicMock()],
        "vulnerabilities": [mock_vuln],
        "critical_high_count": 1,
        "ports": [],
        "technologies": [],
        "screenshots": []
    }
    
    workspace_id = uuid.uuid4()
    
    # Act
    content, content_type = await svc.generate_report_sync(workspace_id, ReportFormat.JSON)
    
    # Assert
    assert content_type == "application/json"
    assert "Test Workspace" in content
    assert "Test Vuln" in content
    assert "critical" in content

@pytest.mark.asyncio
async def test_generate_report_sync_markdown():
    # Arrange
    db_mock = AsyncMock()
    settings_mock = MagicMock()
    
    svc = ReportingService(db=db_mock, settings=settings_mock)
    svc._gather_workspace_data = AsyncMock()
    
    mock_workspace = MagicMock()
    mock_workspace.name = "Test Workspace"
    
    svc._gather_workspace_data.return_value = {
        "workspace": mock_workspace,
        "date": "2026-07-08",
        "assets": [],
        "vulnerabilities": [],
        "critical_high_count": 0,
        "ports": [],
        "technologies": [],
        "screenshots": []
    }
    
    workspace_id = uuid.uuid4()
    
    # Act
    content, content_type = await svc.generate_report_sync(workspace_id, ReportFormat.MARKDOWN)
    
    # Assert
    assert content_type == "text/markdown"
    assert "Test Workspace" in content
    assert "Executive Summary" in content

@pytest.mark.asyncio
async def test_generate_report_sync_html():
    db_mock = AsyncMock()
    settings_mock = MagicMock()
    
    svc = ReportingService(db=db_mock, settings=settings_mock)
    svc._gather_workspace_data = AsyncMock()
    
    mock_workspace = MagicMock()
    mock_workspace.name = "Test Workspace HTML"
    
    svc._gather_workspace_data.return_value = {
        "workspace": mock_workspace,
        "date": "2026-07-08",
        "assets": [],
        "vulnerabilities": [],
        "critical_high_count": 0,
        "ports": [],
        "technologies": [],
        "screenshots": []
    }
    
    content, content_type = await svc.generate_report_sync(uuid.uuid4(), ReportFormat.HTML)
    assert content_type == "text/html"
    assert "Test Workspace HTML" in content
    assert "<!DOCTYPE html>" in content
