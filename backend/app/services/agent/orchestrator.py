"""
Agent orchestrator service.

Starts and steers agent runs under two hard safety controls:
    1. Scope gate (default-deny): the target is validated against workspace scope
       before a run is ever created, and re-validated per action at execution.
    2. Approval gate: passive/recon actions are auto-approved and execute
       autonomously; active/intrusive actions are PROPOSED and only run after a
       human approves them.

Every decision is recorded on the AgentAction rows (the primary audit trail) and
mirrored, best-effort, into the append-only ``audit_logs``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.exceptions import NotFoundError, ScopeViolationError, ValidationError
from app.core.logging import get_logger
from app.core.scope_engine import check_scope
from app.models.agent_run import (
    ActionTier,
    AgentAction,
    AgentActionState,
    AgentRun,
    AgentRunStatus,
)
from app.models.audit_log import AuditOutcome
from app.models.scan import Scan, ScanStatus, ScanType
from app.models.target import Target
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.repositories.scope import ScopeRepository
from app.schemas.agent import (
    AgentActionResponse,
    AgentRunCreate,
    AgentRunDetail,
    AgentRunResponse,
    AgentRunSummary,
)
from app.schemas.common import PaginatedResponse
from app.services.agent.planner import plan_actions
from app.services.agent.tools import build_tool_registry
from app.services.llm.provider import get_llm_provider
from app.services.workspace_service import WorkspaceService

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AgentOrchestrator:
    """Starts agent runs and processes approvals."""

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._workspace_svc = WorkspaceService(db, settings)
        self._scope_repo = ScopeRepository(db)
        self._audit = AuditLogRepository(db)

    # ── Start ───────────────────────────────────────────────────────────────────

    async def start_run(
        self, workspace_id: uuid.UUID, data: AgentRunCreate, current_user: User
    ) -> AgentRunResponse:
        await self._workspace_svc.get_workspace(workspace_id, current_user)

        target = await self._db.get(Target, data.target_id)
        if target is None or not target.is_active:
            raise NotFoundError("Target", str(data.target_id))

        # Scope gate (default-deny) before anything is created.
        rules = await self._scope_repo.get_rules_for_workspace(workspace_id, active_only=False)
        scope_result = check_scope(target.value, rules)
        if not scope_result.is_permitted:
            await self._write_audit(
                current_user, "agent.run.denied", None,
                AuditOutcome.FAILURE, {"target": target.value, "reason": scope_result.reason},
            )
            raise ScopeViolationError(scope_result.reason)

        # Backing scan anchors any findings into the normal pipeline.
        scan = Scan(
            name=f"Agent: {data.name or target.value}",
            description="Backing scan for an orchestrator agent run.",
            status=ScanStatus.RUNNING,
            target_id=target.id,
            created_by_id=current_user.id,
            workspace_id=workspace_id,
            scan_type=ScanType.FULL,
            started_at=_utcnow(),
            configuration={"agent": True},
        )
        self._db.add(scan)
        await self._db.flush()

        run = AgentRun(
            name=data.name or f"Agent run on {target.value}",
            objective=data.objective,
            status=AgentRunStatus.RUNNING,
            workspace_id=workspace_id,
            target_id=target.id,
            scan_id=scan.id,
            created_by_id=current_user.id,
        )
        self._db.add(run)
        await self._db.flush()

        tools = build_tool_registry()
        planned = await plan_actions(target.value, tools, llm=get_llm_provider(self._settings))
        has_approved = has_proposed = False
        for i, pa in enumerate(planned):
            auto = pa.tier == ActionTier.PASSIVE
            has_approved = has_approved or auto
            has_proposed = has_proposed or (not auto)
            self._db.add(
                AgentAction(
                    run_id=run.id,
                    step_index=i,
                    tool_name=pa.tool_name,
                    target_value=target.value,
                    tier=pa.tier,
                    state=AgentActionState.APPROVED if auto else AgentActionState.PROPOSED,
                    params=pa.params,
                    rationale=pa.rationale,
                )
            )

        if not has_approved and has_proposed:
            run.status = AgentRunStatus.AWAITING_APPROVAL

        await self._db.commit()
        await self._write_audit(
            current_user, "agent.run.created", run.id, AuditOutcome.SUCCESS,
            {"target": target.value, "planned_actions": len(planned)},
        )

        if has_approved:
            self._dispatch(run.id)

        await self._db.refresh(run)
        logger.info("agent.run_started", run_id=str(run.id), actions=len(planned))
        return AgentRunResponse.model_validate(run)

    # ── Approve / reject ────────────────────────────────────────────────────────

    async def approve_action(
        self, workspace_id: uuid.UUID, run_id: uuid.UUID, action_id: uuid.UUID, current_user: User
    ) -> AgentRunDetail:
        run = await self._get_run_or_404(run_id, workspace_id, current_user)
        action = await self._db.get(AgentAction, action_id)
        if action is None or action.run_id != run.id:
            raise NotFoundError("AgentAction", str(action_id))
        if action.state != AgentActionState.PROPOSED:
            raise ValidationError("Action is not awaiting approval.")

        action.state = AgentActionState.APPROVED
        run.status = AgentRunStatus.RUNNING
        await self._db.commit()
        await self._write_audit(
            current_user, "agent.action.approved", action.id, AuditOutcome.SUCCESS,
            {"tool": action.tool_name, "tier": action.tier.value},
        )
        self._dispatch(run.id)
        return await self.get_run(workspace_id, run_id, current_user)

    async def reject_action(
        self, workspace_id: uuid.UUID, run_id: uuid.UUID, action_id: uuid.UUID, current_user: User
    ) -> AgentRunDetail:
        run = await self._get_run_or_404(run_id, workspace_id, current_user)
        action = await self._db.get(AgentAction, action_id)
        if action is None or action.run_id != run.id:
            raise NotFoundError("AgentAction", str(action_id))
        if action.state != AgentActionState.PROPOSED:
            raise ValidationError("Action is not awaiting approval.")

        action.state = AgentActionState.REJECTED
        await self._db.commit()
        await self._write_audit(
            current_user, "agent.action.rejected", action.id, AuditOutcome.SUCCESS,
            {"tool": action.tool_name},
        )
        # Re-dispatch so the run continues past the rejected step (or completes).
        self._dispatch(run.id)
        return await self.get_run(workspace_id, run_id, current_user)

    # ── Read ────────────────────────────────────────────────────────────────────

    async def get_run(
        self, workspace_id: uuid.UUID, run_id: uuid.UUID, current_user: User
    ) -> AgentRunDetail:
        run = await self._get_run_or_404(run_id, workspace_id, current_user, with_actions=True)
        detail = AgentRunDetail.model_validate(run)
        detail.actions = [AgentActionResponse.model_validate(a) for a in run.actions]
        return detail

    async def list_runs(
        self, workspace_id: uuid.UUID, current_user: User, *, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse[AgentRunSummary]:
        await self._workspace_svc.get_workspace(workspace_id, current_user)
        base = select(AgentRun).where(AgentRun.workspace_id == workspace_id)
        total = (
            await self._db.execute(
                select(func.count(AgentRun.id)).where(AgentRun.workspace_id == workspace_id)
            )
        ).scalar_one()
        rows = (
            await self._db.execute(
                base.order_by(AgentRun.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return PaginatedResponse[AgentRunSummary].build(
            items=[AgentRunSummary.model_validate(r) for r in rows],
            total=total, page=page, page_size=page_size,
        )

    async def get_pending(
        self, workspace_id: uuid.UUID, run_id: uuid.UUID, current_user: User
    ) -> list[AgentActionResponse]:
        run = await self._get_run_or_404(run_id, workspace_id, current_user)
        rows = (
            await self._db.execute(
                select(AgentAction).where(
                    and_(
                        AgentAction.run_id == run.id,
                        AgentAction.state == AgentActionState.PROPOSED,
                    )
                ).order_by(AgentAction.step_index)
            )
        ).scalars().all()
        return [AgentActionResponse.model_validate(a) for a in rows]

    # ── Helpers ─────────────────────────────────────────────────────────────────

    async def _get_run_or_404(
        self,
        run_id: uuid.UUID,
        workspace_id: uuid.UUID,
        current_user: User,
        *,
        with_actions: bool = False,
    ) -> AgentRun:
        await self._workspace_svc.get_workspace(workspace_id, current_user)
        opts = [selectinload(AgentRun.actions)] if with_actions else []
        run = await self._db.get(AgentRun, run_id, options=opts)
        if run is None or run.workspace_id != workspace_id:
            raise NotFoundError("AgentRun", str(run_id))
        return run

    def _dispatch(self, run_id: uuid.UUID) -> None:
        try:
            from app.tasks.agent_tasks import run_agent

            run_agent.delay(str(run_id))
        except Exception as exc:  # noqa: BLE001 - broker may be down
            logger.error("agent.dispatch_failed", run_id=str(run_id), error=str(exc))

    async def _write_audit(
        self,
        user: User,
        action: str,
        resource_id: uuid.UUID | None,
        outcome: AuditOutcome,
        details: dict[str, Any],
    ) -> None:
        """Best-effort mirror into audit_logs (AgentAction rows are authoritative)."""
        try:
            await self._audit.create_entry(
                action=action,
                outcome=outcome,
                actor_id=user.id,
                resource_type="agent_run",
                resource_id=resource_id,
                details=details,
            )
            await self._db.commit()
        except Exception:  # noqa: BLE001
            logger.info("agent.audit_skipped", action=action)
