"""
Scope repository — database access for ScopeRule records.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scope import ScopeDisposition, ScopeRule, ScopeRuleType
from app.repositories.base import BaseRepository
from app.schemas.scope import WorkspaceScopeOverview


class ScopeRepository(BaseRepository[ScopeRule, dict, dict]):
    """Repository for ScopeRule data access."""

    model = ScopeRule

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── Lookup ────────────────────────────────────────────────────────────────

    async def get_rules_for_workspace(
        self,
        workspace_id: uuid.UUID,
        *,
        active_only: bool = True,
        disposition: ScopeDisposition | None = None,
        rule_type: ScopeRuleType | None = None,
    ) -> list[ScopeRule]:
        """Fetch all scope rules for a workspace.

        Used by both the API (list endpoint) and the scope engine (pre-scan check).

        Args:
            workspace_id: The workspace UUID.
            active_only:  If True, only return active rules.
            disposition:  Optional filter by ALLOW or EXCLUDE.
            rule_type:    Optional filter by rule type.

        Returns:
            list[ScopeRule]: Matching scope rules ordered by disposition, type, value.
        """
        conditions: list[Any] = [ScopeRule.workspace_id == workspace_id]

        if active_only:
            conditions.append(ScopeRule.is_active.is_(True))

        if disposition is not None:
            conditions.append(ScopeRule.disposition == disposition)

        if rule_type is not None:
            conditions.append(ScopeRule.rule_type == rule_type)

        stmt = (
            select(ScopeRule)
            .where(and_(*conditions))
            .order_by(
                ScopeRule.disposition,
                ScopeRule.rule_type,
                ScopeRule.value,
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def find_duplicate(
        self,
        workspace_id: uuid.UUID,
        rule_type: ScopeRuleType,
        disposition: ScopeDisposition,
        value: str,
    ) -> ScopeRule | None:
        """Find an existing rule with the same workspace+type+disposition+value.

        Args:
            workspace_id: The workspace UUID.
            rule_type:    The rule type.
            disposition:  The rule disposition.
            value:        The normalised rule value.

        Returns:
            ScopeRule | None: The existing rule if it exists.
        """
        stmt = select(ScopeRule).where(
            and_(
                ScopeRule.workspace_id == workspace_id,
                ScopeRule.rule_type == rule_type,
                ScopeRule.disposition == disposition,
                ScopeRule.value == value,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_rule_for_workspace(
        self,
        rule_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> ScopeRule | None:
        """Fetch a specific rule, scoped to a workspace.

        Prevents accessing rules from other workspaces by always filtering
        on workspace_id alongside rule id.

        Args:
            rule_id:      The rule UUID.
            workspace_id: The workspace UUID.

        Returns:
            ScopeRule | None
        """
        stmt = select(ScopeRule).where(
            and_(
                ScopeRule.id == rule_id,
                ScopeRule.workspace_id == workspace_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ── Bulk Operations ───────────────────────────────────────────────────────

    async def delete_all_for_workspace(self, workspace_id: uuid.UUID) -> int:
        """Delete all scope rules for a workspace.

        Used by bulk import with replace_existing=True.

        Args:
            workspace_id: The workspace UUID.

        Returns:
            int: Number of rules deleted.
        """
        from sqlalchemy import delete
        stmt = delete(ScopeRule).where(ScopeRule.workspace_id == workspace_id)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount

    async def bulk_create(
        self,
        workspace_id: uuid.UUID,
        rules_data: list[dict],
    ) -> list[ScopeRule]:
        """Insert multiple scope rules, skipping duplicates.

        Args:
            workspace_id: The workspace UUID.
            rules_data:   List of dicts with rule fields.

        Returns:
            list[ScopeRule]: The created (non-duplicate) rules.
        """
        created: list[ScopeRule] = []
        for data in rules_data:
            existing = await self.find_duplicate(
                workspace_id=workspace_id,
                rule_type=data["rule_type"],
                disposition=data["disposition"],
                value=data["value"],
            )
            if existing:
                continue  # Skip duplicates silently
            rule = ScopeRule(workspace_id=workspace_id, **data)
            self._session.add(rule)
            created.append(rule)

        if created:
            await self._session.flush()
            for rule in created:
                await self._session.refresh(rule)

        return created

    # ── Overview ──────────────────────────────────────────────────────────────

    async def get_overview(self, workspace_id: uuid.UUID) -> WorkspaceScopeOverview:
        """Compute scope configuration overview statistics.

        Args:
            workspace_id: The workspace UUID.

        Returns:
            WorkspaceScopeOverview: Aggregated scope stats.
        """
        # Total count
        total_stmt = select(func.count(ScopeRule.id)).where(
            ScopeRule.workspace_id == workspace_id
        )
        total = (await self._session.execute(total_stmt)).scalar_one()

        # Active allow count
        allow_stmt = select(func.count(ScopeRule.id)).where(
            and_(
                ScopeRule.workspace_id == workspace_id,
                ScopeRule.is_active.is_(True),
                ScopeRule.disposition == ScopeDisposition.ALLOW,
            )
        )
        active_allow = (await self._session.execute(allow_stmt)).scalar_one()

        # Active exclude count
        excl_stmt = select(func.count(ScopeRule.id)).where(
            and_(
                ScopeRule.workspace_id == workspace_id,
                ScopeRule.is_active.is_(True),
                ScopeRule.disposition == ScopeDisposition.EXCLUDE,
            )
        )
        active_exclude = (await self._session.execute(excl_stmt)).scalar_one()

        # Inactive count
        inactive_stmt = select(func.count(ScopeRule.id)).where(
            and_(
                ScopeRule.workspace_id == workspace_id,
                ScopeRule.is_active.is_(False),
            )
        )
        inactive = (await self._session.execute(inactive_stmt)).scalar_one()

        # Per-type breakdown (active rules only)
        type_stmt = (
            select(
                ScopeRule.rule_type,
                func.count(ScopeRule.id).label("cnt"),
            )
            .where(
                and_(
                    ScopeRule.workspace_id == workspace_id,
                    ScopeRule.is_active.is_(True),
                )
            )
            .group_by(ScopeRule.rule_type)
        )
        type_result = await self._session.execute(type_stmt)
        type_breakdown = {row.rule_type.value: row.cnt for row in type_result}

        return WorkspaceScopeOverview(
            workspace_id=workspace_id,
            total_rules=total,
            active_allow_rules=active_allow,
            active_exclude_rules=active_exclude,
            inactive_rules=inactive,
            has_scope_defined=active_allow > 0,
            rule_type_breakdown=type_breakdown,
        )
