"""Unit tests for agent tool tiering and planning (the safety-critical logic)."""

from __future__ import annotations

from app.models.agent_run import ActionTier
from app.models.plugin import PluginPhase
from app.services.agent.planner import plan_actions
from app.services.agent.tools import RAG_TOOL, AgentTool, tier_for_phase


class TestTiering:
    def test_recon_is_passive(self) -> None:
        assert tier_for_phase(PluginPhase.RECONNAISSANCE) == ActionTier.PASSIVE

    def test_vuln_scanning_is_active(self) -> None:
        assert tier_for_phase(PluginPhase.VULNERABILITY_SCANNING) == ActionTier.ACTIVE

    def test_exploitation_is_active(self) -> None:
        assert tier_for_phase(PluginPhase.EXPLOITATION) == ActionTier.ACTIVE
        assert tier_for_phase(PluginPhase.POST_EXPLOITATION) == ActionTier.ACTIVE


def _tools() -> dict[str, AgentTool]:
    return {
        "nmap": AgentTool("nmap", ActionTier.PASSIVE, "plugin", "port scan"),
        "httpx": AgentTool("httpx", ActionTier.PASSIVE, "plugin", "probe"),
        "nuclei": AgentTool("nuclei", ActionTier.ACTIVE, "plugin", "vuln scan"),
        RAG_TOOL: AgentTool(RAG_TOOL, ActionTier.PASSIVE, "rag", "retrieve"),
    }


class TestPlanner:
    def test_passive_before_active(self) -> None:
        plan = plan_actions("example.com", _tools())
        tiers = [p.tier for p in plan]
        # all passive steps precede the first active step
        first_active = next(i for i, t in enumerate(tiers) if t == ActionTier.ACTIVE)
        assert all(t == ActionTier.PASSIVE for t in tiers[:first_active])

    def test_active_tools_are_proposed_tier(self) -> None:
        plan = plan_actions("example.com", _tools())
        active = [p for p in plan if p.tier == ActionTier.ACTIVE]
        assert [p.tool_name for p in active] == ["nuclei"]

    def test_rag_step_included_with_query(self) -> None:
        plan = plan_actions("example.com", _tools())
        rag = [p for p in plan if p.tool_name == RAG_TOOL]
        assert len(rag) == 1
        assert rag[0].params["query"] == "example.com"
        assert rag[0].tier == ActionTier.PASSIVE

    def test_all_plugins_represented(self) -> None:
        plan = plan_actions("example.com", _tools())
        names = {p.tool_name for p in plan}
        assert {"nmap", "httpx", "nuclei", RAG_TOOL} <= names
