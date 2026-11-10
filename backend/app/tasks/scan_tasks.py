"""
Scan execution task.

``run_scan`` is the Celery entry point.  It is a synchronous Celery task that
drives an async orchestration coroutine via ``asyncio.run``.  The coroutine
owns its own async engine for the duration of the scan, so asyncpg connections
stay bound to this task's event loop (the FastAPI engine lives in a different
process and must not be reused here).

Execution flow per scan:
    1. Mark scan RUNNING, record ``started_at``.
    2. Re-validate the target against the workspace scope rules (defense in
       depth — the API already checked at creation, but scope may have changed).
    3. For each resolved plugin: load the class, check dependencies, execute,
       parse, and persist assets + vulnerabilities.  Each plugin gets a
       ``ScanPluginExecution`` row for per-plugin observability.
    4. Mark scan COMPLETED (or FAILED if nothing ran).

Plugins whose class is missing on disk or whose CLI dependency is unavailable
are SKIPPED gracefully rather than failing the whole scan.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.plugin_loader import PluginLoader
from app.core.scope_engine import check_scope
from app.models.scan import Scan, ScanStatus
from app.models.scan_plugin_execution import PluginExecutionStatus, ScanPluginExecution
from app.models.target import Target
from app.repositories.asset import AssetRepository
from app.repositories.scope import ScopeRepository
from app.repositories.vulnerability import VulnerabilityRepository
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(bind=True, name="vulnforge.run_scan")
def run_scan(self, scan_id: str) -> dict[str, Any]:  # noqa: ANN001 - Celery self
    """Celery entry point — runs the async scan orchestration to completion."""
    return asyncio.run(_execute_scan(scan_id))


async def _execute_scan(scan_id: str) -> dict[str, Any]:
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"server_settings": {"jit": "off"}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    log = logger.bind(scan_id=scan_id)

    try:
        scan_pk = uuid.UUID(scan_id)

        # ── 1. Load scan + target, transition to RUNNING ──────────────────────
        async with factory() as session:
            scan = await session.get(Scan, scan_pk)
            if scan is None:
                log.warning("scan.not_found")
                return {"scan_id": scan_id, "status": "not_found"}

            target = await session.get(Target, scan.target_id)
            if target is None:
                scan.status = ScanStatus.FAILED
                scan.error_message = "Target no longer exists."
                scan.completed_at = _utcnow()
                await session.commit()
                return {"scan_id": scan_id, "status": "failed", "reason": "target_missing"}

            # Capture primitives so we can use them after the session closes.
            workspace_id = scan.workspace_id
            target_id = target.id
            target_value = target.value
            resolved: list[dict[str, Any]] = list(
                (scan.configuration or {}).get("resolved_plugins", [])
            )

            scan.status = ScanStatus.RUNNING
            scan.started_at = _utcnow()
            await session.commit()

        # ── 2. Scope re-validation (deny-wins, default-deny) ──────────────────
        async with factory() as session:
            scope_repo = ScopeRepository(session)
            rules = (
                await scope_repo.get_rules_for_workspace(workspace_id, active_only=False)
                if workspace_id is not None
                else []
            )
        scope_result = check_scope(target_value, rules)
        if not scope_result.is_permitted:
            await _finalize_scan(
                factory, scan_pk, ScanStatus.FAILED,
                error=f"Scope denied: {scope_result.reason}",
            )
            log.warning("scan.scope_denied", reason=scope_result.reason)
            return {"scan_id": scan_id, "status": "failed", "reason": "scope_denied"}

        # ── 3. Execute resolved plugins ───────────────────────────────────────
        loaded = PluginLoader().discover_plugins()
        ran_any = False
        for rp in resolved:
            outcome = await _run_one_plugin(
                factory=factory,
                scan_pk=scan_pk,
                workspace_id=workspace_id,
                target_id=target_id,
                target_value=target_value,
                resolved_plugin=rp,
                loaded=loaded,
                log=log,
            )
            ran_any = ran_any or outcome == "executed"

        # ── 4. Finalize ───────────────────────────────────────────────────────
        final = ScanStatus.COMPLETED if (ran_any or not resolved) else ScanStatus.FAILED
        error = None if final is ScanStatus.COMPLETED else "No plugin executed successfully."
        await _finalize_scan(factory, scan_pk, final, error=error)
        log.info("scan.finished", status=final.value, plugins=len(resolved))
        return {"scan_id": scan_id, "status": final.value, "plugins": len(resolved)}

    except Exception as exc:  # noqa: BLE001 - last-resort guard so the worker never crashes silently
        logger.exception("scan.unhandled_error", scan_id=scan_id)
        try:
            await _finalize_scan(factory, uuid.UUID(scan_id), ScanStatus.FAILED, error=str(exc))
        except Exception:  # noqa: BLE001
            logger.exception("scan.finalize_failed", scan_id=scan_id)
        return {"scan_id": scan_id, "status": "failed", "reason": "unhandled_error"}
    finally:
        await engine.dispose()


async def _run_one_plugin(
    *,
    factory: async_sessionmaker,
    scan_pk: uuid.UUID,
    workspace_id: uuid.UUID | None,
    target_id: uuid.UUID,
    target_value: str,
    resolved_plugin: dict[str, Any],
    loaded: dict[str, Any],
    log: Any,
) -> str:
    """Execute a single resolved plugin.

    Returns one of: "executed" (ran successfully), "skipped" (tool/class not
    available), or "failed" (ran but errored).
    """
    name = resolved_plugin.get("name", "")
    plugin_id_raw = resolved_plugin.get("plugin_id")
    config = resolved_plugin.get("config", {}) or {}
    plog = log.bind(plugin=name)

    # Create the execution record up front for observability.
    async with factory() as session:
        spe = ScanPluginExecution(
            scan_id=scan_pk,
            plugin_id=uuid.UUID(str(plugin_id_raw)),
            status=PluginExecutionStatus.RUNNING,
            configuration=config,
            started_at=_utcnow(),
        )
        session.add(spe)
        await session.commit()
        await session.refresh(spe)
        spe_id = spe.id

    plugin_cls = loaded.get(name)
    if plugin_cls is None:
        await _finish_execution(
            factory, spe_id, PluginExecutionStatus.SKIPPED,
            error="Plugin class not found on disk.",
        )
        plog.warning("plugin.missing")
        return "skipped"

    try:
        plugin = plugin_cls(config=config, target=target_value)

        if not await plugin.check_dependencies():
            await _finish_execution(
                factory, spe_id, PluginExecutionStatus.SKIPPED,
                error="Plugin dependencies are not available on this host.",
            )
            plog.warning("plugin.deps_missing")
            return "skipped"

        result = await plugin.execute()
        if not result.success:
            await _finish_execution(
                factory, spe_id, PluginExecutionStatus.FAILED,
                raw_output=result.raw_output, error=result.error_message,
            )
            plog.warning("plugin.failed", error=result.error_message)
            return "failed"

        parsed = plugin.parse_results(result.raw_output)

        # Persist findings in a dedicated session/transaction.
        async with factory() as session:
            if parsed.assets and workspace_id is not None:
                await AssetRepository(session).ingest_assets(
                    workspace_id=workspace_id,
                    target_id=target_id,
                    scan_id=scan_pk,
                    assets=parsed.assets,
                )
            if parsed.vulnerabilities:
                await VulnerabilityRepository(session).ingest_vulnerabilities(
                    target_id=target_id,
                    scan_id=scan_pk,
                    plugin_execution_id=spe_id,
                    vulnerabilities=parsed.vulnerabilities,
                )
            await session.commit()

        await _finish_execution(
            factory, spe_id, PluginExecutionStatus.COMPLETED, raw_output=result.raw_output,
        )
        plog.info(
            "plugin.completed",
            assets=len(parsed.assets),
            vulnerabilities=len(parsed.vulnerabilities),
        )
        return "executed"

    except Exception as exc:  # noqa: BLE001 - isolate plugin failures from the scan
        logger.exception("plugin.exception", plugin=name)
        await _finish_execution(
            factory, spe_id, PluginExecutionStatus.FAILED, error=str(exc),
        )
        return "failed"


async def _finish_execution(
    factory: async_sessionmaker,
    spe_id: uuid.UUID,
    status: PluginExecutionStatus,
    *,
    raw_output: str | None = None,
    error: str | None = None,
) -> None:
    async with factory() as session:
        spe = await session.get(ScanPluginExecution, spe_id)
        if spe is None:
            return
        spe.status = status
        spe.completed_at = _utcnow()
        if raw_output is not None:
            spe.raw_output = raw_output
        if error is not None:
            spe.error_message = error
        await session.commit()


async def _finalize_scan(
    factory: async_sessionmaker,
    scan_pk: uuid.UUID,
    status: ScanStatus,
    *,
    error: str | None = None,
) -> None:
    async with factory() as session:
        scan = await session.get(Scan, scan_pk)
        if scan is None:
            return
        scan.status = status
        scan.completed_at = _utcnow()
        if error is not None:
            scan.error_message = error
        await session.commit()
