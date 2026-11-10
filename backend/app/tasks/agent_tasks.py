"""
Agent execution task.

Processes an agent run's actions in order. APPROVED actions execute (passive
recon autonomously; active ones only once a human approved them); the first
PROPOSED action still awaiting approval halts the run (status
AWAITING_APPROVAL). Scope is re-validated against each action's target before it
runs — an out-of-scope action is hard-failed, never executed.

Plugin actions reuse the Phase-1 plugin runner so findings land under the run's
backing scan. The RAG action performs a read-only retrieval.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.plugin_loader import PluginLoader
from app.core.scope_engine import check_scope
from app.models.agent_run import AgentAction, AgentActionState, AgentRun, AgentRunStatus
from app.models.plugin import Plugin
from app.models.scan import Scan, ScanStatus
from app.models.target import Target
from app.repositories.scope import ScopeRepository
from app.services.agent.tools import RAG_TOOL
from app.tasks.celery_app import celery_app
from app.tasks.scan_tasks import _run_one_plugin

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(name="vulnforge.run_agent")
def run_agent(run_id: str) -> dict[str, Any]:
    """Celery entry point — advance an agent run as far as autonomy allows."""
    return asyncio.run(_execute_agent(run_id))


async def _execute_agent(run_id: str) -> dict[str, Any]:
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url, pool_pre_ping=True,
        connect_args={"server_settings": {"jit": "off"}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    log = logger.bind(run_id=run_id)

    try:
        run_pk = uuid.UUID(run_id)

        async with factory() as session:
            run = await session.get(AgentRun, run_pk)
            if run is None:
                return {"run_id": run_id, "status": "not_found"}
            target = await session.get(Target, run.target_id)
            workspace_id = run.workspace_id
            scan_pk = run.scan_id
            target_id = run.target_id
            target_value = target.value if target else None
            action_ids = [
                a.id
                for a in (
                    await session.execute(
                        select(AgentAction)
                        .where(AgentAction.run_id == run_pk)
                        .order_by(AgentAction.step_index)
                    )
                ).scalars().all()
            ]
            # name -> plugin_id for building the plugin runner payload
            plugin_map = {
                name: pid
                for pid, name in (
                    await session.execute(select(Plugin.id, Plugin.name))
                ).all()
            }

        if target_value is None:
            await _finalize_run(factory, run_pk, AgentRunStatus.FAILED, "Target no longer exists.")
            return {"run_id": run_id, "status": "failed"}

        loaded = PluginLoader().discover_plugins()

        for action_id in action_ids:
            # Re-read the action fresh (state may have changed via approvals).
            async with factory() as session:
                action = await session.get(AgentAction, action_id)
                state = action.state
                tool_name = action.tool_name
                tier = action.tier
                params = dict(action.params or {})

            if state in (
                AgentActionState.EXECUTED, AgentActionState.FAILED,
                AgentActionState.SKIPPED, AgentActionState.REJECTED,
            ):
                continue

            if state == AgentActionState.PROPOSED:
                # Hit an un-approved active action — halt and wait for a human.
                await _finalize_run(factory, run_pk, AgentRunStatus.AWAITING_APPROVAL)
                log.info("agent.awaiting_approval", action=tool_name)
                return {"run_id": run_id, "status": "awaiting_approval"}

            # state == APPROVED → execute, but re-check scope first (defense in depth).
            async with factory() as session:
                rules = await ScopeRepository(session).get_rules_for_workspace(
                    workspace_id, active_only=False
                )
            verdict = check_scope(target_value, rules)
            if not verdict.is_permitted:
                await _finish_action(
                    factory, action_id, AgentActionState.FAILED,
                    scope_verdict=verdict.verdict.value,
                    error=f"Scope denied: {verdict.reason}",
                )
                log.warning("agent.action_scope_denied", action=tool_name)
                continue

            await _execute_action(
                factory=factory, action_id=action_id, tool_name=tool_name,
                params=params, scan_pk=scan_pk, workspace_id=workspace_id,
                target_id=target_id, target_value=target_value, loaded=loaded,
                plugin_map=plugin_map, verdict=verdict.verdict.value, settings=settings, log=log,
            )

        # All actions processed with none left awaiting approval → done.
        await _finalize_run(factory, run_pk, AgentRunStatus.COMPLETED)
        await _complete_backing_scan(factory, scan_pk)
        log.info("agent.completed")
        return {"run_id": run_id, "status": "completed"}

    except Exception as exc:  # noqa: BLE001
        logger.exception("agent.unhandled_error", run_id=run_id)
        try:
            await _finalize_run(factory, uuid.UUID(run_id), AgentRunStatus.FAILED, str(exc))
        except Exception:  # noqa: BLE001
            pass
        return {"run_id": run_id, "status": "failed"}
    finally:
        await engine.dispose()


async def _execute_action(
    *, factory, action_id, tool_name, params, scan_pk, workspace_id, target_id,
    target_value, loaded, plugin_map, verdict, settings, log,
) -> None:
    if tool_name == RAG_TOOL:
        await _run_rag_action(factory, action_id, params, settings, verdict, log)
        return

    plugin_id = plugin_map.get(tool_name)
    if plugin_id is None or tool_name not in loaded:
        await _finish_action(
            factory, action_id, AgentActionState.SKIPPED,
            scope_verdict=verdict, error="Tool not available on this host.",
        )
        return

    if scan_pk is None:
        await _finish_action(
            factory, action_id, AgentActionState.FAILED,
            scope_verdict=verdict, error="No backing scan to anchor findings.",
        )
        return

    outcome = await _run_one_plugin(
        factory=factory, scan_pk=scan_pk, workspace_id=workspace_id,
        target_id=target_id, target_value=target_value,
        resolved_plugin={"name": tool_name, "plugin_id": str(plugin_id), "config": {}},
        loaded=loaded, log=log,
    )
    state_map = {
        "executed": AgentActionState.EXECUTED,
        "skipped": AgentActionState.SKIPPED,
        "failed": AgentActionState.FAILED,
    }
    summary_map = {
        "executed": "Executed; findings recorded under the run's scan.",
        "skipped": "Tool is not available on this host; skipped.",
        "failed": "Tool ran but did not complete successfully.",
    }
    await _finish_action(
        factory, action_id,
        state_map.get(outcome, AgentActionState.FAILED),
        scope_verdict=verdict,
        summary=summary_map.get(outcome),
    )


async def _run_rag_action(factory, action_id, params, settings, verdict, log) -> None:
    try:
        from app.services.rag.retrieval_service import RetrievalService

        async with factory() as session:
            result = await RetrievalService(session, settings).search(
                params.get("query", ""), top_k=3
            )
        titles = "; ".join(r.title for r in result.results) or "no matches"
        await _finish_action(
            factory, action_id, AgentActionState.EXECUTED,
            scope_verdict=verdict,
            summary=f"Retrieved {len(result.results)} related writeup(s): {titles}",
        )
    except Exception as exc:  # noqa: BLE001 - retrieval is best-effort
        await _finish_action(
            factory, action_id, AgentActionState.EXECUTED,
            scope_verdict=verdict,
            summary=f"Retrieval unavailable ({exc}).",
        )


async def _finish_action(
    factory, action_id: uuid.UUID, state: AgentActionState, *,
    scope_verdict: str | None = None, summary: str | None = None, error: str | None = None,
) -> None:
    async with factory() as session:
        action = await session.get(AgentAction, action_id)
        if action is None:
            return
        action.state = state
        if scope_verdict is not None:
            action.scope_verdict = scope_verdict
        if summary is not None:
            action.result_summary = summary
        if error is not None:
            action.error_message = error
        await session.commit()


async def _finalize_run(
    factory, run_pk: uuid.UUID, status: AgentRunStatus, error: str | None = None
) -> None:
    async with factory() as session:
        run = await session.get(AgentRun, run_pk)
        if run is None:
            return
        run.status = status
        if error is not None:
            run.error_message = error
        await session.commit()


async def _complete_backing_scan(factory, scan_pk: uuid.UUID | None) -> None:
    if scan_pk is None:
        return
    async with factory() as session:
        scan = await session.get(Scan, scan_pk)
        if scan is not None and not scan.is_terminal:
            scan.status = ScanStatus.COMPLETED
            scan.completed_at = _utcnow()
            await session.commit()
