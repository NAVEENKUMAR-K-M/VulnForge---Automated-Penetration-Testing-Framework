"""
Agent tool registry.

Each discovered plugin becomes an agent-callable tool, plus a passive
``rag_search`` tool. A tool's **intrusiveness tier** is derived from the plugin
phase and governs autonomy: PASSIVE (reconnaissance) runs autonomously, ACTIVE
(vulnerability scanning, exploitation, post-exploitation) must be approved by a
human before it runs.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.core.plugin_loader import PluginLoader
from app.models.agent_run import ActionTier
from app.models.plugin import PluginPhase

logger = get_logger(__name__)

RAG_TOOL = "rag_search"


def tier_for_phase(phase: PluginPhase) -> ActionTier:
    """Reconnaissance is passive; everything else is active (needs approval)."""
    return ActionTier.PASSIVE if phase == PluginPhase.RECONNAISSANCE else ActionTier.ACTIVE


@dataclass(frozen=True)
class AgentTool:
    name: str
    tier: ActionTier
    kind: str  # "plugin" | "rag"
    description: str


def build_tool_registry() -> dict[str, AgentTool]:
    """Build the available tool set from on-disk plugins + the RAG tool."""
    tools: dict[str, AgentTool] = {}
    for name, cls in PluginLoader().discover_plugins().items():
        try:
            manifest = cls.get_manifest()
        except Exception:  # noqa: BLE001
            continue
        tools[name] = AgentTool(
            name=name,
            tier=tier_for_phase(manifest.phase),
            kind="plugin",
            description=manifest.description,
        )
    tools[RAG_TOOL] = AgentTool(
        name=RAG_TOOL,
        tier=ActionTier.PASSIVE,
        kind="rag",
        description="Retrieve related disclosed writeups for context (read-only).",
    )
    return tools
