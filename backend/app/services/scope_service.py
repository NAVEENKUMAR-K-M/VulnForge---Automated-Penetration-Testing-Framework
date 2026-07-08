"""
Scope service — business logic for workspace scope management.

Key Responsibilities:
    1. CRUD for ScopeRule records within a workspace
    2. Pre-scan scope check: validate target is in scope before dispatch
    3. Bulk import with optional replace semantics
    4. Workspace scope overview for the UI

Access Control:
    - Workspace OWNER/MEMBER: read scope, check scope
    - Workspace OWNER: create, update, delete scope rules, bulk import
    - Superuser: all operations on all workspaces
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AuditAction
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ScopeViolationError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.scope_engine import ScopeCheckResult, ScopeVerdict, check_scope
from app.models.audit_log import AuditOutcome
from app.models.scope import ScopeDisposition, ScopeRule, ScopeRuleType
from app.models.user import User
from app.models.workspace import WorkspaceMemberRole
from app.repositories.audit_log import AuditLogRepository
from app.repositories.scope import ScopeRepository
from app.repositories.workspace import WorkspaceRepository
from app.schemas.scope import (
    BulkScopeImport,
    ScopeCheckRequest,
    ScopeCheckResponse,
    ScopeRuleCreate,
    ScopeRuleResponse,
    ScopeRuleUpdate,
    WorkspaceScopeOverview,
)

logger = get_logger(__name__)


class ScopeService:
    """Orchestrates all scope rule management and pre-scan scope validation.

    Attributes:
        _db:             Async database session.
        _settings:       Application settings.
        _scope_repo:     Scope rule data access.
        _workspace_repo: Workspace access (for membership/permission checks).
        _audit_repo:     Audit log writer.
    """

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._scope_repo = ScopeRepository(db)
        self._workspace_repo = WorkspaceRepository(db)
        self._audit_repo = AuditLogRepository(db)

    # ── Internal Helpers ──────────────────────────────────────────────────────

    async def _get_workspace_or_404(self, workspace_id: uuid.UUID, user: User):
        """Fetch workspace with membership-scoped access.

        Args:
            workspace_id: The workspace UUID.
            user:         The requesting user.

        Returns:
            Workspace: The accessible workspace.

        Raises:
            NotFoundError: If workspace not found or user has no access.
        """
        ws = await self._workspace_repo.get_by_id_for_user(
            workspace_id=workspace_id,
            user_id=user.id,
            is_superuser=user.is_superuser,
        )
        if ws is None:
            raise NotFoundError("Workspace", str(workspace_id))
        return ws

    async def _get_effective_role(
        self,
        workspace_id: uuid.UUID,
        workspace,
        user: User,
    ) -> WorkspaceMemberRole | None:
        """Return the user's effective workspace role.

        Args:
            workspace_id: The workspace UUID.
            workspace:    The workspace ORM object.
            user:         The requesting user.

        Returns:
            WorkspaceMemberRole | None: Effective role.
        """
        if user.is_superuser or workspace.owner_id == user.id:
            return WorkspaceMemberRole.OWNER
        membership = await self._workspace_repo.get_membership(workspace_id, user.id)
        return membership.role if membership else None

    def _require_owner(
        self,
        effective_role: WorkspaceMemberRole | None,
        action: str = "manage scope rules",
    ) -> None:
        """Assert the user has OWNER role.

        Args:
            effective_role: The user's effective workspace role.
            action:         Human-readable action for error message.

        Raises:
            PermissionDeniedError: If role is not OWNER.
        """
        if effective_role != WorkspaceMemberRole.OWNER:
            raise PermissionDeniedError(
                f"Workspace OWNER role required to {action}."
            )

    async def _get_rule_or_404(
        self, rule_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> ScopeRule:
        """Fetch a rule scoped to a workspace or raise NotFoundError.

        Args:
            rule_id:      The rule UUID.
            workspace_id: The workspace UUID.

        Returns:
            ScopeRule: The found rule.

        Raises:
            NotFoundError: If rule not found in this workspace.
        """
        rule = await self._scope_repo.get_rule_for_workspace(rule_id, workspace_id)
        if rule is None:
            raise NotFoundError("ScopeRule", str(rule_id))
        return rule

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create_rule(
        self,
        workspace_id: uuid.UUID,
        data: ScopeRuleCreate,
        current_user: User,
        ip_address: str | None = None,
    ) -> ScopeRuleResponse:
        """Create a new scope rule for a workspace.

        Args:
            workspace_id:  The workspace UUID.
            data:          Validated rule creation payload.
            current_user:  The requesting user.
            ip_address:    Client IP for audit logging.

        Returns:
            ScopeRuleResponse: The created rule.

        Raises:
            ConflictError: If an identical rule already exists.
        """
        ws = await self._get_workspace_or_404(workspace_id, current_user)
        role = await self._get_effective_role(workspace_id, ws, current_user)
        self._require_owner(role)

        # Conflict check
        existing = await self._scope_repo.find_duplicate(
            workspace_id=workspace_id,
            rule_type=data.rule_type,
            disposition=data.disposition,
            value=data.value,
        )
        if existing:
            raise ConflictError(
                f"A {data.disposition.value} rule for "
                f"'{data.value}' ({data.rule_type.value}) already exists in this workspace."
            )

        rule = await self._scope_repo.create_from_dict(
            {
                "workspace_id": workspace_id,
                "rule_type": data.rule_type,
                "disposition": data.disposition,
                "value": data.value,
                "description": data.description,
                "is_active": True,
                "created_by_id": current_user.id,
            }
        )

        await self._audit_repo.create_entry(
            action=AuditAction.SCOPE_RULE_CREATED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="scope_rule",
            resource_id=rule.id,
            details={
                "workspace_id": str(workspace_id),
                "rule_type": data.rule_type.value,
                "disposition": data.disposition.value,
                "value": data.value,
            },
        )

        logger.info(
            "scope_rule.created",
            workspace_id=str(workspace_id),
            rule_type=data.rule_type.value,
            disposition=data.disposition.value,
            value=data.value,
        )

        return ScopeRuleResponse.model_validate(rule)

    async def list_rules(
        self,
        workspace_id: uuid.UUID,
        current_user: User,
        *,
        active_only: bool = True,
        disposition: ScopeDisposition | None = None,
        rule_type: ScopeRuleType | None = None,
    ) -> list[ScopeRuleResponse]:
        """List all scope rules for a workspace.

        Args:
            workspace_id:  The workspace UUID.
            current_user:  The requesting user.
            active_only:   Exclude inactive rules.
            disposition:   Optional disposition filter.
            rule_type:     Optional type filter.

        Returns:
            list[ScopeRuleResponse]: Matching rules.
        """
        await self._get_workspace_or_404(workspace_id, current_user)

        rules = await self._scope_repo.get_rules_for_workspace(
            workspace_id=workspace_id,
            active_only=active_only,
            disposition=disposition,
            rule_type=rule_type,
        )
        return [ScopeRuleResponse.model_validate(r) for r in rules]

    async def get_rule(
        self,
        workspace_id: uuid.UUID,
        rule_id: uuid.UUID,
        current_user: User,
    ) -> ScopeRuleResponse:
        """Fetch a single scope rule.

        Args:
            workspace_id:  The workspace UUID.
            rule_id:       The rule UUID.
            current_user:  The requesting user.

        Returns:
            ScopeRuleResponse: The rule.
        """
        await self._get_workspace_or_404(workspace_id, current_user)
        rule = await self._get_rule_or_404(rule_id, workspace_id)
        return ScopeRuleResponse.model_validate(rule)

    async def update_rule(
        self,
        workspace_id: uuid.UUID,
        rule_id: uuid.UUID,
        data: ScopeRuleUpdate,
        current_user: User,
        ip_address: str | None = None,
    ) -> ScopeRuleResponse:
        """Partially update a scope rule.

        Allows toggling is_active, changing description, or flipping disposition.
        The rule value and type cannot be changed — delete and recreate instead.

        Args:
            workspace_id:  The workspace UUID.
            rule_id:       The rule UUID.
            data:          Partial update payload.
            current_user:  The requesting user.
            ip_address:    Client IP for audit logging.

        Returns:
            ScopeRuleResponse: The updated rule.
        """
        ws = await self._get_workspace_or_404(workspace_id, current_user)
        role = await self._get_effective_role(workspace_id, ws, current_user)
        self._require_owner(role, "update scope rules")

        rule = await self._get_rule_or_404(rule_id, workspace_id)

        update_data = data.model_dump(exclude_unset=True, exclude_none=False)
        for field_name, value in update_data.items():
            setattr(rule, field_name, value)
        self._db.add(rule)
        await self._db.flush()
        await self._db.refresh(rule)

        await self._audit_repo.create_entry(
            action=AuditAction.SCOPE_RULE_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="scope_rule",
            resource_id=rule.id,
            details={"changes": list(update_data.keys())},
        )

        return ScopeRuleResponse.model_validate(rule)

    async def delete_rule(
        self,
        workspace_id: uuid.UUID,
        rule_id: uuid.UUID,
        current_user: User,
        ip_address: str | None = None,
    ) -> None:
        """Permanently delete a scope rule.

        Use is_active=False for soft-disable; use DELETE for permanent removal.

        Args:
            workspace_id:  The workspace UUID.
            rule_id:       The rule UUID.
            current_user:  The requesting user.
            ip_address:    Client IP for audit logging.
        """
        ws = await self._get_workspace_or_404(workspace_id, current_user)
        role = await self._get_effective_role(workspace_id, ws, current_user)
        self._require_owner(role, "delete scope rules")

        rule = await self._get_rule_or_404(rule_id, workspace_id)

        await self._session_delete(rule)

        await self._audit_repo.create_entry(
            action=AuditAction.SCOPE_RULE_DELETED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="scope_rule",
            resource_id=rule_id,
            details={
                "value": rule.value,
                "rule_type": rule.rule_type.value,
                "disposition": rule.disposition.value,
            },
        )
        logger.info("scope_rule.deleted", rule_id=str(rule_id))

    async def _session_delete(self, rule: ScopeRule) -> None:
        await self._db.delete(rule)
        await self._db.flush()

    # ── Bulk Import ───────────────────────────────────────────────────────────

    async def bulk_import(
        self,
        workspace_id: uuid.UUID,
        data: BulkScopeImport,
        current_user: User,
        ip_address: str | None = None,
    ) -> list[ScopeRuleResponse]:
        """Import multiple scope rules at once.

        If replace_existing=True, all existing rules are deleted first.
        Duplicate rules (same type+disposition+value) are silently skipped.

        Args:
            workspace_id:  The workspace UUID.
            data:          Bulk import payload.
            current_user:  The requesting user.
            ip_address:    Client IP for audit logging.

        Returns:
            list[ScopeRuleResponse]: The created rules.
        """
        ws = await self._get_workspace_or_404(workspace_id, current_user)
        role = await self._get_effective_role(workspace_id, ws, current_user)
        self._require_owner(role, "import scope rules")

        deleted_count = 0
        if data.replace_existing:
            deleted_count = await self._scope_repo.delete_all_for_workspace(workspace_id)

        rules_data = [
            {
                "rule_type": item.rule_type,
                "disposition": item.disposition,
                "value": item.value,
                "description": item.description,
                "is_active": True,
                "created_by_id": current_user.id,
            }
            for item in data.rules
        ]

        created = await self._scope_repo.bulk_create(
            workspace_id=workspace_id,
            rules_data=rules_data,
        )

        await self._audit_repo.create_entry(
            action=AuditAction.SCOPE_RULES_BULK_IMPORTED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="workspace",
            resource_id=workspace_id,
            details={
                "imported": len(created),
                "skipped_duplicates": len(data.rules) - len(created),
                "deleted_existing": deleted_count,
                "replace_existing": data.replace_existing,
            },
        )

        logger.info(
            "scope_rules.bulk_imported",
            workspace_id=str(workspace_id),
            imported=len(created),
        )

        return [ScopeRuleResponse.model_validate(r) for r in created]

    # ── Scope Check ───────────────────────────────────────────────────────────

    async def check_scope(
        self,
        workspace_id: uuid.UUID,
        request: ScopeCheckRequest,
        current_user: User,
    ) -> ScopeCheckResponse:
        """Ad-hoc scope check — test a value against the workspace's rules.

        This is the same check that runs before every scan. Exposes it as an
        API endpoint so operators can validate their scope configuration
        interactively before running scans.

        Args:
            workspace_id:  The workspace UUID.
            request:       The scope check request with target_value.
            current_user:  The requesting user.

        Returns:
            ScopeCheckResponse: The scope check verdict and explanation.
        """
        await self._get_workspace_or_404(workspace_id, current_user)

        rules = await self._scope_repo.get_rules_for_workspace(
            workspace_id=workspace_id,
            active_only=True,
        )

        result = check_scope(request.target_value, rules)

        return ScopeCheckResponse(
            target_value=result.target_value,
            verdict=result.verdict,
            is_permitted=result.is_permitted,
            reason=result.reason,
            matched_rule_id=(
                uuid.UUID(result.matched_rule_id)
                if result.matched_rule_id else None
            ),
            matched_rule_type=result.matched_rule_type,
            matched_disposition=result.matched_disposition,
            denied_by_exclusion=result.denied_by_exclusion,
        )

    async def assert_target_in_scope(
        self,
        workspace_id: uuid.UUID,
        target_value: str,
    ) -> ScopeCheckResult:
        """Assert a target is in scope before dispatching a scan.

        This is called by the Scan service — NOT an HTTP endpoint.
        Raises ScopeViolationError if the target is out of scope.

        Args:
            workspace_id:  The workspace UUID.
            target_value:  The target value to check.

        Returns:
            ScopeCheckResult: The permitted result (if not raising).

        Raises:
            ScopeViolationError: If target is out of scope.
        """
        rules = await self._scope_repo.get_rules_for_workspace(
            workspace_id=workspace_id,
            active_only=True,
        )

        result = check_scope(target_value, rules)

        if result.is_denied:
            logger.warning(
                "scope.violation",
                workspace_id=str(workspace_id),
                target=target_value,
                verdict=result.verdict.value,
                reason=result.reason,
            )
            raise ScopeViolationError(result.reason)

        logger.debug(
            "scope.permitted",
            workspace_id=str(workspace_id),
            target=target_value,
            matched_rule=result.matched_rule_id,
        )
        return result

    # ── Overview ──────────────────────────────────────────────────────────────

    async def get_overview(
        self,
        workspace_id: uuid.UUID,
        current_user: User,
    ) -> WorkspaceScopeOverview:
        """Return scope configuration overview for a workspace.

        Args:
            workspace_id:  The workspace UUID.
            current_user:  The requesting user.

        Returns:
            WorkspaceScopeOverview: Aggregated scope stats.
        """
        await self._get_workspace_or_404(workspace_id, current_user)
        return await self._scope_repo.get_overview(workspace_id)
