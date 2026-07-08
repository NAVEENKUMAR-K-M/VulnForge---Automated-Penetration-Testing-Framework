"""
Synchronizes dynamically loaded plugins with the database.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.plugin_loader import PluginLoader
from app.models.plugin import Plugin

logger = get_logger(__name__)


class PluginRegistry:
    """Manages the synchronization between on-disk plugins and the `plugins` DB table.

    Attributes:
        _db (AsyncSession): The database session.
        _loader (PluginLoader): The plugin discovery utility.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._loader = PluginLoader()

    async def sync(self) -> None:
        """Discover local plugins and synchronize their state to the database.

        Algorithm:
        1. Discover all valid BasePlugin subclasses on disk.
        2. Query all existing plugins from the database.
        3. For each discovered plugin:
           - If it doesn't exist in DB, create it.
           - If it does exist, update its metadata (version, config, etc.) and ensure it's enabled.
        4. For each DB plugin NOT found on disk:
           - Mark it as disabled (`is_enabled=False`) to prevent scan dispatch failures.
        """
        logger.info("Starting plugin registry synchronization")
        
        discovered_classes = self._loader.discover_plugins()
        discovered_names = set(discovered_classes.keys())

        # Fetch all existing plugins from the database
        stmt = select(Plugin)
        result = await self._db.execute(stmt)
        existing_plugins: dict[str, Plugin] = {p.name: p for p in result.scalars().all()}
        existing_names = set(existing_plugins.keys())

        # 1. Update existing or Create new
        for name, cls in discovered_classes.items():
            manifest = cls.get_manifest()
            module_path = f"{cls.__module__}.{cls.__name__}"
            
            if name in existing_plugins:
                # Update existing
                db_plugin = existing_plugins[name]
                db_plugin.display_name = manifest.display_name
                db_plugin.description = manifest.description
                db_plugin.version = manifest.version
                db_plugin.phase = manifest.phase
                db_plugin.default_config = manifest.default_config
                db_plugin.plugin_metadata = manifest.plugin_metadata
                db_plugin.module_path = module_path
                # We do NOT force is_enabled=True here, because an admin might have intentionally
                # disabled a plugin globally. We only flip it if we were restoring it from missing.
                self._db.add(db_plugin)
                logger.debug("Updated existing plugin in registry", name=name)
            else:
                # Create new
                new_plugin = Plugin(
                    name=manifest.name,
                    display_name=manifest.display_name,
                    description=manifest.description,
                    version=manifest.version,
                    phase=manifest.phase,
                    is_enabled=True,
                    is_builtin=True,  # All dynamically loaded local plugins are "builtin"
                    module_path=module_path,
                    default_config=manifest.default_config,
                    plugin_metadata=manifest.plugin_metadata,
                )
                self._db.add(new_plugin)
                logger.info("Registered new plugin", name=name)

        # 2. Disable missing plugins
        missing_names = existing_names - discovered_names
        if missing_names:
            logger.warning("Disabling missing plugins not found on disk", missing=list(missing_names))
            disable_stmt = (
                update(Plugin)
                .where(Plugin.name.in_(missing_names))
                .values(is_enabled=False)
            )
            await self._db.execute(disable_stmt)

        await self._db.flush()
        logger.info("Plugin registry synchronization complete", 
                    total_discovered=len(discovered_names),
                    total_missing=len(missing_names))
