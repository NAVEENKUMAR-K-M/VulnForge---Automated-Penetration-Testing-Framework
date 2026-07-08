"""
Dynamic plugin discovery and loading.

Scans the `plugins/` directory for Python modules containing classes that 
inherit from `BasePlugin`. 
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Iterator

from app.core.logging import get_logger
from app.core.plugin_base import BasePlugin

logger = get_logger(__name__)


class PluginLoader:
    """Discovers and loads BasePlugin subclasses from a given package directory.

    Attributes:
        plugin_package (str): The base Python package path to scan (e.g., 'app.plugins').
        plugin_dir (Path): The filesystem path corresponding to the package.
    """

    def __init__(self, plugin_package: str = "app.plugins") -> None:
        self.plugin_package = plugin_package
        # Resolve the package name to an absolute filesystem path.
        # Assuming app/plugins is relative to this file's parent's parent.
        base_dir = Path(__file__).resolve().parent.parent
        self.plugin_dir = base_dir / "plugins"

    def discover_plugins(self) -> dict[str, type[BasePlugin]]:
        """Scan the plugins directory and return a map of all discovered BasePlugin classes.

        Returns:
            dict[str, type[BasePlugin]]: Mapping of plugin_name to the Plugin Class.
        """
        if not self.plugin_dir.exists() or not self.plugin_dir.is_dir():
            logger.warning("Plugin directory does not exist", path=str(self.plugin_dir))
            return {}

        plugins: dict[str, type[BasePlugin]] = {}

        # Recursively find all modules within the plugins package
        for module_info in self._walk_packages():
            try:
                module = importlib.import_module(module_info.name)
                
                # Inspect the module for classes that subclass BasePlugin
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # Check if it's a subclass of BasePlugin (and not BasePlugin itself)
                    if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                        # Ensure it has a valid manifest
                        try:
                            manifest = obj.get_manifest()
                            if manifest.name in plugins:
                                logger.error(
                                    "Duplicate plugin name discovered", 
                                    name=manifest.name, 
                                    existing=str(plugins[manifest.name]),
                                    new=str(obj)
                                )
                                continue
                            
                            plugins[manifest.name] = obj
                            logger.debug("Discovered plugin", name=manifest.name, class_name=obj.__name__)
                        except NotImplementedError as e:
                            logger.warning(
                                "Skipping plugin missing valid manifest", 
                                class_name=obj.__name__, 
                                module=module_info.name,
                                error=str(e)
                            )
            except Exception as e:
                logger.error("Failed to load plugin module", module=module_info.name, error=str(e))

        logger.info("Plugin discovery complete", count=len(plugins))
        return plugins

    def _walk_packages(self) -> Iterator[pkgutil.ModuleInfo]:
        """Recursively walk the plugin package using pkgutil."""
        # We need the path as a list of strings for pkgutil
        paths = [str(self.plugin_dir)]
        prefix = f"{self.plugin_package}."
        
        # yield modules in the root plugins package too if any
        for info in pkgutil.iter_modules(paths, prefix):
            yield info
            if info.ispkg:
                # If it's a subpackage (e.g., app.plugins.reconnaissance), walk it
                sub_path = [str(self.plugin_dir / info.name.split('.')[-1])]
                yield from pkgutil.walk_packages(sub_path, info.name + ".")
