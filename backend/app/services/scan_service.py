"""
Scan Service — orchestrates scan creation, scope enforcement, plugin
resolution, and Celery dispatch.

Design notes:
    - ``Scan`` has no ``profile_id`` FK, so the concrete plugin set is resolved
      at creation time (from a profile, or by PTES phase for the scan_type) and
      persisted on ``Scan.configuration["resolved_plugins"]``.  The Celery task
      reads that list — no extra migration required.
    - The row is committed BEFORE dispatch so the worker never races a
      not-yet-visible scan.
    - Scope is enforced here (default-deny) before a scan is ever created; the
      task re-checks as defense in depth.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.exceptions import NotFoundError, ScopeViolationError, ValidationError
from app.core.logging import get_logger
from app.core.scope_engine import check_scope
from app.models.plugin import Plugin, PluginPhase
from app.models.scan import Priority, Scan, ScanStatus, ScanType
from app.models.scan_profile import ScanProfile, ScanProfilePlugin
from app.models.target import Target
from app.models.user import User
from app.repositories.scope import ScopeRepository
from app.schemas.common import PaginatedResponse
from app.schemas.scan import ScanCreate, ScanResponse, ScanSummary
from app.services.workspace_service import WorkspaceService

logger = get_logger(__name__)


# Which plugin phases run for each scan type when no profile is supplied.
# FULL deliberately excludes EXPLOITATION — intrusive phases are opt-in.
_SCAN_TYPE_PHASES: dict[ScanType, list[PluginPhase]] = {
    ScanType.RECONNAISSANCE: [PluginPhase.RECONNAISSANCE],
    ScanType.VULNERABILITY: [PluginPhase.VULNERABILITY_SCANNING],
    ScanType.EXPLOITATION: [PluginPhase.EXPLOITATION],
    ScanType.FULL: [PluginPhase.RECONNAISSANCE, PluginPhase.VULNERABILITY_SCANNING],
}


class ScanService:
    """Business logic for creating and managing scans."""

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._workspace_svc = WorkspaceService(db, settings)
        self._scope_repo = ScopeRepository(db)

    # ── Create + dispatch ──────────────────────────────────────────────────────

    async def create_scan(
        self,
        workspace_id: uuid.UUID,
        data: ScanCreate,
        current_user: User,
    ) -> ScanResponse:
        """Validate scope, resolve plugins, persist, and dispatch a scan."""
        # Access control — raises NotFoundError if the user can't see the workspace.
        await self._workspace_svc.get_workspace(workspace_id, current_user)

        target = await self._db.get(Target, data.target_id)
        if target is None or not target.is_active:
            raise NotFoundError("Target", str(data.target_id))

        # ── Scope enforcement (default-deny) ──────────────────────────────────
        rules = await self._scope_repo.get_rules_for_workspace(
            workspace_id, active_only=False
        )
        scope_result = check_scope(target.value, rules)
        if not scope_result.is_permitted:
            logger.warning(
                "scan.scope_denied",
                workspace_id=str(workspace_id),
                target=target.value,
                reason=scope_result.reason,
            )
            raise ScopeViolationError(scope_result.reason)

        resolved = await self._resolve_plugins(data, workspace_id)
        if not resolved:
            raise ValidationError(
                "No enabled plugins resolved for this scan. "
                "Add plugins to the profile or enable plugins for this scan type."
            )

        scan = Scan(
            name=data.name,
            description=data.description,
            status=ScanStatus.PENDING,
            target_id=target.id,
            created_by_id=current_user.id,
            workspace_id=workspace_id,
            scan_type=data.scan_type,
            priority=data.priority or Priority.MEDIUM,
            configuration={**(data.configuration or {}), "resolved_plugins": resolved},
        )
        self._db.add(scan)
        # Commit BEFORE dispatch so the worker can always see the row.
        await self._db.commit()
        await self._db.refresh(scan)

        self._dispatch(scan)
        await self._db.commit()
        await self._db.refresh(scan)

        logger.info(
            "scan.created",
            scan_id=str(scan.id),
            workspace_id=str(workspace_id),
            plugins=len(resolved),
            celery_task_id=scan.celery_task_id,
        )
        return ScanResponse.model_validate(scan)

    def _dispatch(self, scan: Scan) -> None:
        """Enqueue the scan task. On broker failure, mark the scan FAILED."""
        try:
            from app.tasks.scan_tasks import run_scan

            task = run_scan.delay(str(scan.id))
            scan.celery_task_id = task.id
        except Exception as exc:  # noqa: BLE001 - broker may be unreachable
            logger.error("scan.dispatch_failed", scan_id=str(scan.id), error=str(exc))
            scan.status = ScanStatus.FAILED
            scan.error_message = f"Failed to enqueue scan task: {exc}"

    async def _resolve_plugins(
        self, data: ScanCreate, workspace_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        """Resolve the concrete plugin set for this scan.

        From a profile (respecting per-plugin enable + config overrides and
        execution order), or by PTES phase for the scan_type.
        """
        if data.profile_id is not None:
            profile = await self._db.get(
                ScanProfile,
                data.profile_id,
                options=[
                    selectinload(ScanProfile.profile_plugins).selectinload(
                        ScanProfilePlugin.plugin
                    )
                ],
            )
            if profile is None:
                raise NotFoundError("ScanProfile", str(data.profile_id))

            entries = sorted(
                (pp for pp in profile.profile_plugins if pp.is_enabled),
                key=lambda pp: pp.execution_order,
            )
            resolved: list[dict[str, Any]] = []
            for pp in entries:
                plugin = pp.plugin
                if plugin is None or not plugin.is_enabled:
                    continue
                resolved.append(
                    {
                        "plugin_id": str(plugin.id),
                        "name": plugin.name,
                        "config": {**(plugin.default_config or {}), **(pp.config_override or {})},
                    }
                )
            return resolved

        phases = _SCAN_TYPE_PHASES.get(data.scan_type, [])
        if not phases:
            return []
        stmt = select(Plugin).where(
            Plugin.is_enabled.is_(True), Plugin.phase.in_(phases)
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        return [
            {"plugin_id": str(p.id), "name": p.name, "config": dict(p.default_config or {})}
            for p in rows
        ]

    # ── Read ────────────────────────────────────────────────────────────────────

    async def list_scans(
        self,
        workspace_id: uuid.UUID,
        current_user: User,
        *,
        status_filter: ScanStatus | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[ScanSummary]:
        await self._workspace_svc.get_workspace(workspace_id, current_user)

        conditions: list[Any] = [Scan.workspace_id == workspace_id]
        if status_filter is not None:
            conditions.append(Scan.status == status_filter)

        count_stmt = select(func.count(Scan.id)).where(and_(*conditions))
        total = (await self._db.execute(count_stmt)).scalar_one()

        offset = (page - 1) * page_size
        stmt = (
            select(Scan)
            .where(and_(*conditions))
            .order_by(Scan.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        items = [ScanSummary.model_validate(s) for s in rows]
        return PaginatedResponse[ScanSummary].build(
            items=items, total=total, page=page, page_size=page_size
        )

    async def get_scan(
        self, workspace_id: uuid.UUID, scan_id: uuid.UUID, current_user: User
    ) -> ScanResponse:
        await self._workspace_svc.get_workspace(workspace_id, current_user)
        scan = await self._db.get(Scan, scan_id)
        if scan is None or scan.workspace_id != workspace_id:
            raise NotFoundError("Scan", str(scan_id))
        return ScanResponse.model_validate(scan)

    async def cancel_scan(
        self, workspace_id: uuid.UUID, scan_id: uuid.UUID, current_user: User
    ) -> ScanResponse:
        await self._workspace_svc.get_workspace(workspace_id, current_user)
        scan = await self._db.get(Scan, scan_id)
        if scan is None or scan.workspace_id != workspace_id:
            raise NotFoundError("Scan", str(scan_id))
        if scan.is_terminal:
            raise ValidationError("Scan is already in a terminal state.")

        if scan.celery_task_id:
            try:
                from app.tasks.celery_app import celery_app

                celery_app.control.revoke(scan.celery_task_id, terminate=True)
            except Exception as exc:  # noqa: BLE001 - revoke is best-effort
                logger.warning(
                    "scan.revoke_failed", scan_id=str(scan_id), error=str(exc)
                )

        scan.status = ScanStatus.CANCELLED
        await self._db.commit()
        await self._db.refresh(scan)
        logger.info("scan.cancelled", scan_id=str(scan_id))
        return ScanResponse.model_validate(scan)
