"""
Unit tests for Plugin Architecture components (Loader and Registry).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.plugin_base import BasePlugin
from app.core.plugin_loader import PluginLoader
from app.core.plugin_registry import PluginRegistry
from app.models.plugin import Plugin, PluginPhase
from app.schemas.plugin import PluginExecutionResult, PluginManifest


# ── Dummy Plugin for Testing ──────────────────────────────────────────────────

class DummyPlugin(BasePlugin):
    manifest = PluginManifest(
        name="dummy_test",
        display_name="Dummy Test Plugin",
        description="A plugin for testing.",
        version="1.0.0",
        phase=PluginPhase.RECONNAISSANCE,
        default_config={"foo": "bar"},
    )

    async def check_dependencies(self) -> bool:
        return True

    async def execute(self) -> PluginExecutionResult:
        return PluginExecutionResult(success=True, raw_output="dummy output")

    def parse_results(self, raw_output: str) -> list:
        return []


# ── Loader Tests ──────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_plugin_loader_discover():
    loader = PluginLoader()
    
    # We patch _walk_packages to pretend we found a module containing DummyPlugin
    with patch.object(loader, '_walk_packages') as mock_walk:
        # Create a mock module info
        mock_info = MagicMock()
        mock_info.name = "app.plugins.dummy.plugin"
        mock_walk.return_value = [mock_info]

        with patch("importlib.import_module") as mock_import:
            # The mocked module should have our DummyPlugin class
            mock_module = MagicMock()
            mock_module.DummyPlugin = DummyPlugin
            
            # inspect.getmembers needs to find it
            import inspect
            def mock_getmembers(module, predicate):
                return [("DummyPlugin", DummyPlugin)]
            
            with patch("inspect.getmembers", side_effect=mock_getmembers):
                mock_import.return_value = mock_module
                
                plugins = loader.discover_plugins()
                
                assert "dummy_test" in plugins
                assert plugins["dummy_test"] is DummyPlugin


# ── Registry Tests ────────────────────────────────────────────────────────────

@pytest.mark.unit
async def test_plugin_registry_sync_creates_new():
    mock_db = AsyncMock()
    # Mock DB returns empty list for existing plugins
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = []
    mock_db.execute.return_value = mock_result
    
    registry = PluginRegistry(mock_db)
    
    # Mock loader to return our DummyPlugin
    with patch.object(registry._loader, 'discover_plugins', return_value={"dummy_test": DummyPlugin}):
        await registry.sync()
        
        # Should have added one new plugin
        mock_db.add.assert_called_once()
        added_plugin = mock_db.add.call_args[0][0]
        assert added_plugin.name == "dummy_test"
        assert added_plugin.is_enabled is True
        assert added_plugin.default_config == {"foo": "bar"}
        mock_db.flush.assert_called_once()


@pytest.mark.unit
async def test_plugin_registry_sync_updates_existing():
    mock_db = AsyncMock()
    
    # Existing plugin in DB
    existing = Plugin(
        id=uuid.uuid4(),
        name="dummy_test",
        display_name="Old Name",
        description="Old",
        version="0.9.0",
        phase=PluginPhase.RECONNAISSANCE,
        is_enabled=False,  # Intentionally disabled globally
    )
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [existing]
    mock_db.execute.return_value = mock_result
    
    registry = PluginRegistry(mock_db)
    
    with patch.object(registry._loader, 'discover_plugins', return_value={"dummy_test": DummyPlugin}):
        await registry.sync()
        
        mock_db.add.assert_called_once_with(existing)
        # Should have updated properties from manifest
        assert existing.display_name == "Dummy Test Plugin"
        assert existing.version == "1.0.0"
        # Should NOT have overridden is_enabled
        assert existing.is_enabled is False


@pytest.mark.unit
async def test_plugin_registry_sync_disables_missing():
    mock_db = AsyncMock()
    
    # DB has a plugin that is no longer on disk
    missing_plugin = Plugin(
        id=uuid.uuid4(),
        name="missing_plugin",
        is_enabled=True,
    )
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [missing_plugin]
    mock_db.execute.return_value = mock_result
    
    registry = PluginRegistry(mock_db)
    
    # Loader finds nothing
    with patch.object(registry._loader, 'discover_plugins', return_value={}):
        await registry.sync()
        
        # execute should be called twice (select, then update)
        assert mock_db.execute.call_count == 2
        # The second execute should be an update statement
        update_stmt = mock_db.execute.call_args_list[1][0][0]
        # We can verify it's an update statement by compiling it
        assert "UPDATE plugins SET is_enabled" in str(update_stmt).replace("\n", " ")

