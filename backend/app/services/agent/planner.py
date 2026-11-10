"""
Agent planner.

Produces the ordered plan of actions for a run. Tool *selection* is
deterministic and bounded — the agent never invents arbitrary tools or targets,
which keeps it inside the scope-gated, approval-gated rails. An LLM (when
configured) is used only to phrase the rationale, never to choose what runs.

Plan shape for a target:
    1. All passive recon plugins (auto-approved).
    2. A passive RAG lookup for context.
    3. Each active plugin as a PROPOSED step (requires human approval).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.agent_run import ActionTier
from app.services.agent.tools import RAG_TOOL, AgentTool


@dataclass
class PlannedAction:
    tool_name: str
    tier: ActionTier
    params: dict[str, Any]
    rationale: str


def plan_actions(target_value: str, tools: dict[str, AgentTool]) -> list[PlannedAction]:
    """Return the ordered, deterministic plan for assessing ``target_value``."""
    passive_plugins = sorted(
        (t for t in tools.values() if t.kind == "plugin" and t.tier == ActionTier.PASSIVE),
        key=lambda t: t.name,
    )
    active_plugins = sorted(
        (t for t in tools.values() if t.kind == "plugin" and t.tier == ActionTier.ACTIVE),
        key=lambda t: t.name,
    )

    plan: list[PlannedAction] = []
    for tool in passive_plugins:
        plan.append(
            PlannedAction(
                tool_name=tool.name,
                tier=ActionTier.PASSIVE,
                params={},
                rationale=f"Passive reconnaissance with {tool.name} to map the attack surface.",
            )
        )
    if RAG_TOOL in tools:
        plan.append(
            PlannedAction(
                tool_name=RAG_TOOL,
                tier=ActionTier.PASSIVE,
                params={"query": target_value},
                rationale="Retrieve related disclosed writeups to inform follow-up testing.",
            )
        )
    for tool in active_plugins:
        plan.append(
            PlannedAction(
                tool_name=tool.name,
                tier=ActionTier.ACTIVE,
                params={},
                rationale=(
                    f"Active scanning with {tool.name} actively probes the target and "
                    f"requires explicit human approval before it runs."
                ),
            )
        )
    return plan
