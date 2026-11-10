"""
Agent API router — start agent runs, inspect them, and approve/reject the
intrusive actions the agent proposes.

Safety model: starting a run scope-checks the target (default-deny); passive
recon runs autonomously while active actions wait as PROPOSED until a human
approves them here. Starting a run and approving/rejecting actions require the
platform **Analyst** role.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUserDep, DatabaseDep, SettingsDep, require_role
from app.models.user import User, UserRole
from app.schemas.agent import (
    AgentActionResponse,
    AgentRunCreate,
    AgentRunDetail,
    AgentRunResponse,
    AgentRunSummary,
)
from app.schemas.common import PaginatedResponse
from app.services.agent.orchestrator import AgentOrchestrator

router = APIRouter(prefix="/workspaces/{workspace_id}/agent", tags=["agent"])


async def get_orchestrator(db: DatabaseDep, settings: SettingsDep) -> AgentOrchestrator:
    return AgentOrchestrator(db=db, settings=settings)


OrchestratorDep = Annotated[AgentOrchestrator, Depends(get_orchestrator)]


@router.post(
    "/runs",
    response_model=AgentRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start an agent run",
    description=(
        "Scope-check the target (default-deny), plan the assessment, and begin. "
        "Passive recon runs autonomously; active actions are proposed for approval. "
        "Requires **Analyst** role."
    ),
)
async def start_run(
    workspace_id: uuid.UUID,
    data: AgentRunCreate,
    current_user: Annotated[object, Depends(require_role(UserRole.ANALYST))],
    svc: OrchestratorDep,
) -> AgentRunResponse:
    assert isinstance(current_user, User)
    return await svc.start_run(workspace_id=workspace_id, data=data, current_user=current_user)


@router.get(
    "/runs",
    response_model=PaginatedResponse[AgentRunSummary],
    summary="List agent runs",
)
async def list_runs(
    workspace_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: OrchestratorDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[AgentRunSummary]:
    return await svc.list_runs(
        workspace_id=workspace_id, current_user=current_user, page=page, page_size=page_size
    )


@router.get(
    "/runs/{run_id}",
    response_model=AgentRunDetail,
    summary="Get an agent run with its actions",
)
async def get_run(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: OrchestratorDep,
) -> AgentRunDetail:
    return await svc.get_run(workspace_id=workspace_id, run_id=run_id, current_user=current_user)


@router.get(
    "/runs/{run_id}/pending",
    response_model=list[AgentActionResponse],
    summary="List actions awaiting approval",
)
async def pending_actions(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: CurrentUserDep,
    svc: OrchestratorDep,
) -> list[AgentActionResponse]:
    return await svc.get_pending(workspace_id=workspace_id, run_id=run_id, current_user=current_user)


@router.post(
    "/runs/{run_id}/actions/{action_id}/approve",
    response_model=AgentRunDetail,
    summary="Approve a proposed (active) action",
)
async def approve_action(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    action_id: uuid.UUID,
    current_user: Annotated[object, Depends(require_role(UserRole.ANALYST))],
    svc: OrchestratorDep,
) -> AgentRunDetail:
    assert isinstance(current_user, User)
    return await svc.approve_action(
        workspace_id=workspace_id, run_id=run_id, action_id=action_id, current_user=current_user
    )


@router.post(
    "/runs/{run_id}/actions/{action_id}/reject",
    response_model=AgentRunDetail,
    summary="Reject a proposed (active) action",
)
async def reject_action(
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    action_id: uuid.UUID,
    current_user: Annotated[object, Depends(require_role(UserRole.ANALYST))],
    svc: OrchestratorDep,
) -> AgentRunDetail:
    assert isinstance(current_user, User)
    return await svc.reject_action(
        workspace_id=workspace_id, run_id=run_id, action_id=action_id, current_user=current_user
    )
