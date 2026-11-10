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


class FakeLLM:
    def __init__(self, response: str, *, raises: bool = False) -> None:
        self._response = response
        self._raises = raises

    @property
    def name(self) -> str:
        return "fake"

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        if self._raises:
            raise RuntimeError("boom")
        return self._response


class TestDeterministicPlanner:
    async def test_passive_before_active(self) -> None:
        plan = await plan_actions("example.com", _tools())
        tiers = [p.tier for p in plan]
        first_active = next(i for i, t in enumerate(tiers) if t == ActionTier.ACTIVE)
        assert all(t == ActionTier.PASSIVE for t in tiers[:first_active])

    async def test_active_tools_are_active_tier(self) -> None:
        plan = await plan_actions("example.com", _tools())
        active = [p for p in plan if p.tier == ActionTier.ACTIVE]
        assert [p.tool_name for p in active] == ["nuclei"]

    async def test_rag_step_included_with_query(self) -> None:
        plan = await plan_actions("example.com", _tools())
        rag = [p for p in plan if p.tool_name == RAG_TOOL]
        assert len(rag) == 1 and rag[0].params["query"] == "example.com"


class TestLlmPlannerGuardrails:
    async def test_invalid_tools_dropped_and_tiers_preserved(self) -> None:
        llm = FakeLLM('["nmap", "evil_tool", "nuclei"]')
        plan = await plan_actions("example.com", _tools(), llm=llm)
        names = [p.tool_name for p in plan]
        assert names == ["nmap", "nuclei"]           # invented tool dropped
        tiers = {p.tool_name: p.tier for p in plan}
        assert tiers["nuclei"] == ActionTier.ACTIVE  # LLM cannot downgrade the tier

    async def test_unusable_output_falls_back_to_deterministic(self) -> None:
        llm = FakeLLM("I cannot help with that.")
        plan = await plan_actions("example.com", _tools(), llm=llm)
        # deterministic plan includes every tool
        assert {"nmap", "httpx", "nuclei", RAG_TOOL} <= {p.tool_name for p in plan}

    async def test_llm_error_falls_back(self) -> None:
        llm = FakeLLM("", raises=True)
        plan = await plan_actions("example.com", _tools(), llm=llm)
        assert {"nmap", "nuclei"} <= {p.tool_name for p in plan}
