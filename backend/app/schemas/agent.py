"""Pydantic schemas for the orchestrator agent."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.agent_run import ActionTier, AgentActionState, AgentRunStatus
from app.schemas.common import TimestampedResponse, VulnForgeBaseModel


class AgentRunCreate(VulnForgeBaseModel):
    """Request body to start an agent run."""

    target_id: uuid.UUID = Field(description="Target to assess. Must be in workspace scope.")
    name: str | None = Field(default=None, max_length=300)
    objective: str | None = Field(
        default=None, description="Optional free-text objective for the run."
    )


class AgentActionResponse(TimestampedResponse):
    run_id: uuid.UUID
    step_index: int
    tool_name: str
    target_value: str
    tier: ActionTier
    state: AgentActionState
    params: dict[str, Any]
    rationale: str | None
    scope_verdict: str | None
    result_summary: str | None
    error_message: str | None


class AgentRunResponse(TimestampedResponse):
    name: str
    objective: str | None
    status: AgentRunStatus
    workspace_id: uuid.UUID
    target_id: uuid.UUID
    scan_id: uuid.UUID | None
    error_message: str | None


class AgentRunDetail(AgentRunResponse):
    actions: list[AgentActionResponse] = Field(default_factory=list)


class AgentRunSummary(VulnForgeBaseModel):
    id: uuid.UUID
    name: str
    status: AgentRunStatus
    target_id: uuid.UUID
    workspace_id: uuid.UUID
    created_at: datetime
