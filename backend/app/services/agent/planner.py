"""
Agent planner.

Produces the ordered plan of actions for a run. An LLM may **select and order**
tools when one is configured, but every choice passes through hard guardrails:

    - Only tools in the registry are allowed (invented names are dropped).
    - The target is fixed by the run — the LLM never chooses targets.
    - Tiers come from the registry, so the LLM cannot downgrade an ACTIVE tool to
      skip the approval gate: active tools are always PROPOSED regardless.

If no LLM is available (or its output is unusable), planning falls back to a
deterministic plan: passive recon → RAG lookup → active plugins (proposed).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.models.agent_run import ActionTier
from app.services.agent.tools import RAG_TOOL, AgentTool

logger = get_logger(__name__)

_PLANNER_SYSTEM = (
    "You plan an authorized security assessment. Choose ONLY from the provided "
    "tools — never invent tools or targets. Prefer passive reconnaissance before "
    "active scanning. Respond with ONLY a JSON array of tool names, in order."
)


@dataclass
class PlannedAction:
    tool_name: str
    tier: ActionTier
    params: dict[str, Any]
    rationale: str


def _params_for(tool: AgentTool, target_value: str) -> dict[str, Any]:
    return {"query": target_value} if tool.kind == "rag" else {}


async def plan_actions(
    target_value: str, tools: dict[str, AgentTool], llm: Any | None = None
) -> list[PlannedAction]:
    """Return the ordered plan. Uses the LLM when available, else deterministic."""
    if llm is not None:
        try:
            planned = await _llm_plan(target_value, tools, llm)
            if planned:
                logger.info("agent.plan.llm", steps=len(planned))
                return planned
        except Exception as exc:  # noqa: BLE001 - any failure → deterministic
            logger.info("agent.plan.llm_fallback", reason=str(exc))
    return _deterministic_plan(target_value, tools)


async def _llm_plan(
    target_value: str, tools: dict[str, AgentTool], llm: Any
) -> list[PlannedAction]:
    tool_lines = "\n".join(
        f"- {t.name} ({t.tier.value}): {t.description}" for t in tools.values()
    )
    prompt = (
        f"Target: {target_value}\n\nAvailable tools:\n{tool_lines}\n\n"
        "Return a JSON array of tool names to run, in order."
    )
    text = await llm.generate(prompt, system=_PLANNER_SYSTEM)
    names = _parse_tool_list(text)

    # Guardrails: keep only known tools, in order, without duplicates.
    seen: set[str] = set()
    plan: list[PlannedAction] = []
    for name in names:
        if name not in tools or name in seen:
            continue
        seen.add(name)
        tool = tools[name]  # tier comes from the registry, not the LLM
        plan.append(
            PlannedAction(
                tool_name=name,
                tier=tool.tier,
                params=_params_for(tool, target_value),
                rationale=f"Planner selected {name}: {tool.description}",
            )
        )
    return plan


def _parse_tool_list(text: str) -> list[str]:
    """Extract a JSON array of strings from (possibly noisy) LLM output."""
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    return [str(x) for x in data if isinstance(x, str)]


def _deterministic_plan(
    target_value: str, tools: dict[str, AgentTool]
) -> list[PlannedAction]:
    """Passive recon → RAG lookup → active plugins (proposed)."""
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
