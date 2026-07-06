"""
AuditLog repository — append-only write layer for the audit trail.

Design:
    AuditLog is intentionally write-only from the application layer.
    The ``create_entry`` method is the single insertion point.
    Read access (for audit review UIs) goes through a separate admin
    endpoint that queries this repo directly.

    Because the table is partitioned, we use ``INSERT`` rather than
    ORM-level ``session.add()`` to avoid any potential confusion with
    SQLAlchemy's identity map and partition routing.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, AuditOutcome
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog, dict, dict]):
    """Append-only repository for the partitioned ``audit_logs`` table."""

    model = AuditLog

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_entry(
        self,
        *,
        action: str,
        outcome: AuditOutcome,
        actor_id: uuid.UUID | None = None,
        actor_ip: str | None = None,
        resource_type: str | None = None,
        resource_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Insert a new audit log entry.

        This is the ONLY method through which audit log entries are created.
        It is called by services after every security-significant action.

        Args:
            action:        Dot-notation action identifier (e.g., 'user.login.success').
            outcome:       success | failure.
            actor_id:      UUID of the acting user (None for unauthenticated events).
            actor_ip:      Client IP address.
            resource_type: Type of entity acted upon (e.g., 'scan').
            resource_id:   UUID of the entity acted upon.
            details:       Action-specific context payload.

        Returns:
            AuditLog: The created audit log entry.
        """
        return await self.create_from_dict(
            {
                "action": action,
                "outcome": outcome,
                "actor_id": actor_id,
                "actor_ip": actor_ip,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": details or {},
            }
        )

    async def get_entries_for_resource(
        self,
        resource_type: str,
        resource_id: uuid.UUID,
        limit: int = 50,
    ) -> list[AuditLog]:
        """Retrieve audit log entries for a specific resource.

        Args:
            resource_type: The entity type (e.g., 'scan', 'vulnerability').
            resource_id:   The entity's UUID.
            limit:         Maximum entries to return.

        Returns:
            list[AuditLog]: Audit entries ordered by most recent first.
        """
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_entries_for_actor(
        self,
        actor_id: uuid.UUID,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Retrieve recent audit entries for a specific user.

        Args:
            actor_id: The user's UUID.
            limit:    Maximum entries to return.

        Returns:
            list[AuditLog]: Audit entries ordered by most recent first.
        """
        stmt = (
            select(AuditLog)
            .where(AuditLog.actor_id == actor_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
