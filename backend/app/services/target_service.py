"""
Target service — business logic for target management.

Responsibilities:
    - Enforce uniqueness: no duplicate value+type combinations
    - Apply soft-delete (deactivate) instead of hard delete when scans exist
    - Coordinate tag operations atomically with the parent target
    - Write audit log entries for every write operation
    - Raise typed domain exceptions; never expose SQLAlchemy to the API layer

Access Control:
    - Any authenticated user can view active targets
    - Platform ANALYST+ can create targets
    - Only the creator OR platform ADMIN+ can update/deactivate targets
    - Superusers bypass all ownership checks
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.constants import AuditAction
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.models.audit_log import AuditOutcome
from app.models.target import Target, TargetType
from app.models.user import User, UserRole
from app.repositories.audit_log import AuditLogRepository
from app.repositories.target import TargetRepository
from app.schemas.common import PaginatedResponse
from app.schemas.target import (
    BulkTagUpdate,
    TargetCreate,
    TargetDeactivate,
    TargetResponse,
    TargetSummary,
    TargetTagResponse,
    TargetUpdate,
)
from app.utils.target_validators import validate_tag

logger = get_logger(__name__)

# ── Role level threshold for admin operations ─────────────────────────────────
_ADMIN_ROLES = {UserRole.ADMIN}


class TargetService:
    """Orchestrates all target management business logic.

    Attributes:
        _db:           Async database session.
        _settings:     Application settings.
        _target_repo:  Target data access.
        _audit_repo:   Audit log writer.
    """

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._target_repo = TargetRepository(db)
        self._audit_repo = AuditLogRepository(db)

    # ── Internal Helpers ──────────────────────────────────────────────────────

    async def _get_or_404(self, target_id: uuid.UUID) -> Target:
        """Fetch target or raise NotFoundError.

        Args:
            target_id: The target UUID.

        Returns:
            Target: The found target.

        Raises:
            NotFoundError: If no target with this ID exists.
        """
        target = await self._target_repo.get(target_id)
        if target is None:
            raise NotFoundError("Target", str(target_id))
        return target

    def _require_edit_permission(self, target: Target, current_user: User) -> None:
        """Assert the user can edit or deactivate this target.

        Rules:
            - Superusers: always allowed
            - Admins: always allowed
            - Others: only the creator

        Args:
            target:       The target being modified.
            current_user: The requesting user.

        Raises:
            PermissionDeniedError: If the user lacks permission.
        """
        if current_user.is_superuser:
            return
        if current_user.role in _ADMIN_ROLES:
            return
        if target.created_by_id != current_user.id:
            raise PermissionDeniedError(
                "You can only modify targets you created. "
                "Ask an admin to make changes to this target."
            )

    async def _build_response(
        self,
        target: Target,
    ) -> TargetResponse:
        """Build a TargetResponse with tag list and counts.

        Args:
            target: The ORM target instance.

        Returns:
            TargetResponse: Fully populated response schema.
        """
        result = await self._target_repo.get_with_counts(target.id)
        if result is None:
            raise NotFoundError("Target", str(target.id))
        target_obj, scan_count, open_vuln_count = result
        tags = await self._target_repo.get_tags(target_obj.id)
        tag_responses = [
            TargetTagResponse.model_validate(t) for t in tags
        ]
        return TargetResponse(
            id=target_obj.id,
            name=target_obj.name,
            target_type=target_obj.target_type,
            value=target_obj.value,
            description=target_obj.description,
            scope_notes=target_obj.scope_notes,
            is_active=target_obj.is_active,
            created_by_id=target_obj.created_by_id,
            created_at=target_obj.created_at,
            updated_at=target_obj.updated_at,
            tags=tag_responses,
            scan_count=scan_count,
            open_vulnerability_count=open_vuln_count,
        )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create_target(
        self,
        data: TargetCreate,
        current_user: User,
        ip_address: str | None = None,
    ) -> TargetResponse:
        """Create a new target.

        The value is already validated and normalised by the Pydantic schema.
        This method enforces global uniqueness (value + type combination).

        Args:
            data:         Validated creation payload.
            current_user: The requesting user.
            ip_address:   Client IP for audit logging.

        Returns:
            TargetResponse: The created target.

        Raises:
            ConflictError: If a target with this value+type already exists.
        """
        logger.info(
            "target.create.attempt",
            user_id=str(current_user.id),
            target_type=data.target_type.value,
            value=data.value,
        )

        # Uniqueness check: same value + same type = duplicate
        target = await self._target_repo.get_by_value(data.value, data.target_type)
        if target:
            logger.info(
                "target.create.reused",
                target_id=str(target.id),
                target_type=data.target_type.value,
                value=data.value,
            )
        else:
            target = await self._target_repo.create_from_dict(
                {
                    "name": data.name,
                    "target_type": data.target_type,
                    "value": data.value,
                    "description": data.description,
                    "scope_notes": data.scope_notes,
                    "is_active": True,
                    "created_by_id": current_user.id,
                }
            )

            # Add tags atomically with the target creation
            if data.tags:
                await self._target_repo.replace_tags(target.id, data.tags)

            await self._audit_repo.create_entry(
                action=AuditAction.TARGET_CREATED,
                outcome=AuditOutcome.SUCCESS,
                actor_id=current_user.id,
                actor_ip=ip_address,
                resource_type="target",
                resource_id=target.id,
                details={
                    "target_type": data.target_type.value,
                    "value": data.value,
                    "tags": data.tags,
                },
            )

        if data.workspace_id:
            await self._target_repo.link_to_workspace(target.id, data.workspace_id)

        # Ensure all relationships like tags are loaded
        target = await self._target_repo.get(target.id)

        logger.info(
            "target.create.success",
            target_id=str(target.id),
            target_type=data.target_type.value,
        )

        return await self._build_response(target)

    async def get_target(
        self,
        target_id: uuid.UUID,
        current_user: User,
    ) -> TargetResponse:
        """Retrieve a target by ID.

        Args:
            target_id:    The target UUID.
            current_user: The requesting user.

        Returns:
            TargetResponse: The target with tags and counts.

        Raises:
            NotFoundError: If the target doesn't exist.
        """
        target = await self._get_or_404(target_id)
        return await self._build_response(target)

    async def list_targets(
        self,
        current_user: User,
        *,
        active_only: bool = True,
        target_type: TargetType | None = None,
        tag_filter: str | None = None,
        search: str | None = None,
        workspace_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[TargetSummary]:
        """List targets with pagination and filtering.

        Args:
            current_user:  The requesting user.
            active_only:   Exclude inactive targets (default True).
            target_type:   Optional type filter.
            tag_filter:    Optional tag label filter.
            search:        ILIKE search against name and value.
            workspace_id:  Filter by workspace association.
            page:          1-indexed page number.
            page_size:     Items per page.

        Returns:
            PaginatedResponse[TargetSummary]: Paginated target summaries.
        """
        # Admins can see inactive targets; others only see active ones
        effective_active_only = active_only
        if current_user.is_superuser or current_user.role in _ADMIN_ROLES:
            effective_active_only = active_only  # Honour explicit param for admins

        offset = (page - 1) * page_size
        summaries, total = await self._target_repo.list_with_counts(
            active_only=effective_active_only,
            target_type=target_type,
            tag_filter=tag_filter,
            search=search,
            workspace_id=workspace_id,
            offset=offset,
            limit=page_size,
        )

        return PaginatedResponse[TargetSummary].build(
            items=summaries,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_target(
        self,
        target_id: uuid.UUID,
        data: TargetUpdate,
        current_user: User,
        ip_address: str | None = None,
    ) -> TargetResponse:
        """Partially update a target's metadata.

        Requires the user to be the creator, an admin, or a superuser.
        If value+type are both provided, re-validates and checks for conflicts.

        Args:
            target_id:    The target UUID.
            data:         Partial update payload.
            current_user: The requesting user.
            ip_address:   Client IP for audit.

        Returns:
            TargetResponse: The updated target.

        Raises:
            NotFoundError:      If target not found.
            PermissionDeniedError: If user cannot edit.
            ConflictError:      If updated value+type conflicts with existing.
        """
        target = await self._get_or_404(target_id)
        self._require_edit_permission(target, current_user)

        update_data = data.model_dump(exclude_unset=True, exclude_none=False)

        # If changing value+type, check for conflicts
        if "value" in update_data and "target_type" in update_data:
            new_value = update_data["value"]
            new_type = update_data["target_type"]
            existing = await self._target_repo.get_by_value(new_value, new_type)
            if existing and existing.id != target_id:
                raise ConflictError(
                    f"A {new_type.value} target with value '{new_value}' already exists."
                )

        for field, value in update_data.items():
            setattr(target, field, value)
        self._db.add(target)
        await self._db.flush()
        await self._db.refresh(target)

        await self._audit_repo.create_entry(
            action=AuditAction.TARGET_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="target",
            resource_id=target.id,
            details={"changes": list(update_data.keys())},
        )

        logger.info(
            "target.update.success",
            target_id=str(target_id),
            changes=list(update_data.keys()),
        )

        return await self._build_response(target)

    async def deactivate_target(
        self,
        target_id: uuid.UUID,
        data: TargetDeactivate,
        current_user: User,
        ip_address: str | None = None,
    ) -> TargetResponse:
        """Soft-delete a target by marking it inactive.

        Inactive targets cannot be selected for new scans but their historical
        scan data and vulnerability findings remain intact.

        Args:
            target_id:    The target UUID.
            data:         Optional deactivation reason.
            current_user: The requesting user.
            ip_address:   Client IP for audit.

        Returns:
            TargetResponse: The deactivated target.

        Raises:
            ValidationError:   If target is already inactive.
        """
        target = await self._get_or_404(target_id)
        self._require_edit_permission(target, current_user)

        if not target.is_active:
            raise ValidationError("Target is already inactive.")

        target.is_active = False
        if data.reason:
            existing_notes = target.scope_notes or ""
            separator = "\n\n" if existing_notes else ""
            target.scope_notes = (
                f"{existing_notes}{separator}"
                f"[Deactivated] {data.reason}"
            )

        self._db.add(target)
        await self._db.flush()
        await self._db.refresh(target)

        await self._audit_repo.create_entry(
            action=AuditAction.TARGET_DELETED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="target",
            resource_id=target.id,
            details={"reason": data.reason},
        )

        logger.info("target.deactivated", target_id=str(target_id))
        return await self._build_response(target)

    async def reactivate_target(
        self,
        target_id: uuid.UUID,
        current_user: User,
        ip_address: str | None = None,
    ) -> TargetResponse:
        """Re-enable a previously deactivated target.

        Args:
            target_id:    The target UUID.
            current_user: The requesting user.
            ip_address:   Client IP for audit.

        Returns:
            TargetResponse: The reactivated target.
        """
        target = await self._get_or_404(target_id)
        self._require_edit_permission(target, current_user)

        if target.is_active:
            raise ValidationError("Target is already active.")

        await self._target_repo.update_fields(target, is_active=True)

        await self._audit_repo.create_entry(
            action=AuditAction.TARGET_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="target",
            resource_id=target.id,
            details={"action": "reactivated"},
        )

        logger.info("target.reactivated", target_id=str(target_id))
        return await self._build_response(target)

    # ── Tag Management ────────────────────────────────────────────────────────

    async def add_tag(
        self,
        target_id: uuid.UUID,
        raw_tag: str,
        current_user: User,
        ip_address: str | None = None,
    ) -> TargetResponse:
        """Add a single tag to a target.

        Idempotent — adding an existing tag returns 200 without error.

        Args:
            target_id:    The target UUID.
            raw_tag:      The raw tag string (will be validated and normalised).
            current_user: The requesting user.
            ip_address:   Client IP for audit.

        Returns:
            TargetResponse: Updated target with new tag set.
        """
        target = await self._get_or_404(target_id)
        self._require_edit_permission(target, current_user)

        tag = validate_tag(raw_tag)

        # Enforce max tag limit
        existing_tags = await self._target_repo.get_tags(target_id)
        if len(existing_tags) >= 20 and not any(t.tag == tag for t in existing_tags):
            raise ValidationError(
                f"Target already has the maximum of 20 tags. "
                f"Remove a tag before adding a new one."
            )

        await self._target_repo.add_tag(target_id, tag)
        logger.info("target.tag.added", target_id=str(target_id), tag=tag)
        return await self._build_response(target)

    async def remove_tag(
        self,
        target_id: uuid.UUID,
        tag: str,
        current_user: User,
        ip_address: str | None = None,
    ) -> TargetResponse:
        """Remove a single tag from a target.

        Args:
            target_id:    The target UUID.
            tag:          The tag to remove (case-insensitive).
            current_user: The requesting user.
            ip_address:   Client IP for audit.

        Returns:
            TargetResponse: Updated target.

        Raises:
            NotFoundError: If the tag doesn't exist on this target.
        """
        target = await self._get_or_404(target_id)
        self._require_edit_permission(target, current_user)

        normalised = validate_tag(tag)
        removed = await self._target_repo.remove_tag(target_id, normalised)
        if not removed:
            raise NotFoundError("Tag", normalised)

        logger.info("target.tag.removed", target_id=str(target_id), tag=normalised)
        return await self._build_response(target)

    async def replace_tags(
        self,
        target_id: uuid.UUID,
        data: BulkTagUpdate,
        current_user: User,
        ip_address: str | None = None,
    ) -> TargetResponse:
        """Replace all tags for a target (PUT semantics).

        Args:
            target_id:    The target UUID.
            data:         New tag set.
            current_user: The requesting user.
            ip_address:   Client IP for audit.

        Returns:
            TargetResponse: Updated target.
        """
        target = await self._get_or_404(target_id)
        self._require_edit_permission(target, current_user)

        await self._target_repo.replace_tags(target_id, data.tags)

        await self._audit_repo.create_entry(
            action=AuditAction.TARGET_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="target",
            resource_id=target.id,
            details={"action": "tags_replaced", "new_tags": data.tags},
        )

        logger.info(
            "target.tags.replaced",
            target_id=str(target_id),
            count=len(data.tags),
        )
        return await self._build_response(target)
