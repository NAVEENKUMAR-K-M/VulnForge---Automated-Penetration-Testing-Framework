"""
Target repository — all database access for targets and target tags.

Design Rules:
    - Type-specific search filters are applied here (e.g., filter by TargetType).
    - Tag operations (add/remove/replace) are isolated in dedicated methods.
    - List queries join with scan and vulnerability counts in a single query.
    - Access scoping (workspace, user) is applied as filters here.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import Scan
from app.models.target import Target, TargetType
from app.models.target_tag import TargetTag
from app.models.vulnerability import Vulnerability, VulnerabilityStatus
from app.repositories.base import BaseRepository
from app.schemas.target import TargetSummary


class TargetRepository(BaseRepository[Target, dict, dict]):
    """Repository for Target and TargetTag data access."""

    model = Target

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── Lookup ────────────────────────────────────────────────────────────────

    async def get_by_value(
        self,
        value: str,
        target_type: TargetType,
    ) -> Target | None:
        """Find a target by its exact normalised value and type.

        Used to detect duplicates before insertion.

        Args:
            value:       The normalised target value.
            target_type: The target type to match.

        Returns:
            Target | None: The existing target, or None.
        """
        stmt = select(Target).where(
            and_(
                Target.value == value,
                Target.target_type == target_type,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def value_exists(self, value: str, target_type: TargetType) -> bool:
        """Check whether a target with this value+type combination exists.

        Args:
            value:       Normalised target value.
            target_type: Target type.

        Returns:
            bool: True if the combination already exists.
        """
        return await self.get_by_value(value, target_type) is not None

    # ── Paginated List with Counts ────────────────────────────────────────────

    async def list_with_counts(
        self,
        *,
        active_only: bool = True,
        target_type: TargetType | None = None,
        tag_filter: str | None = None,
        search: str | None = None,
        workspace_id: uuid.UUID | None = None,
        created_by_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[TargetSummary], int]:
        """Return paginated targets with aggregated scan and vulnerability counts.

        Uses LEFT JOIN subqueries to avoid N+1 queries.

        Args:
            active_only:    If True, exclude inactive (soft-deleted) targets.
            target_type:    Optional type filter.
            tag_filter:     Optional tag label filter (exact match).
            search:         ILIKE search against name and value.
            workspace_id:   Filter targets that have scans in this workspace.
            created_by_id:  Filter by creator.
            offset:         Pagination offset.
            limit:          Max results.

        Returns:
            tuple[list[TargetSummary], int]: Summaries and total count.
        """
        # ── Subqueries ─────────────────────────────────────────────────────
        scan_count_sq = (
            select(
                Scan.target_id,
                func.count(Scan.id).label("scan_count"),
            )
            .group_by(Scan.target_id)
            .subquery()
        )

        open_vuln_sq = (
            select(
                Vulnerability.target_id,
                func.count(Vulnerability.id).label("open_vuln_count"),
            )
            .where(
                Vulnerability.status.in_(
                    [VulnerabilityStatus.OPEN, VulnerabilityStatus.CONFIRMED]
                )
            )
            .group_by(Vulnerability.target_id)
            .subquery()
        )

        # ── Build conditions ───────────────────────────────────────────────
        conditions: list[Any] = []

        if active_only:
            conditions.append(Target.is_active.is_(True))

        if target_type is not None:
            conditions.append(Target.target_type == target_type)

        if created_by_id is not None:
            conditions.append(Target.created_by_id == created_by_id)

        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(
                    Target.name.ilike(pattern),
                    Target.value.ilike(pattern),
                )
            )

        if tag_filter:
            conditions.append(
                Target.id.in_(
                    select(TargetTag.target_id).where(
                        TargetTag.tag == tag_filter.lower().strip()
                    )
                )
            )

        if workspace_id is not None:
            conditions.append(
                Target.id.in_(
                    select(Scan.target_id).where(
                        Scan.workspace_id == workspace_id
                    )
                )
            )

        # ── Count ──────────────────────────────────────────────────────────
        count_stmt = select(func.count(Target.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total = (await self._session.execute(count_stmt)).scalar_one()

        # ── Main query ─────────────────────────────────────────────────────
        stmt = (
            select(
                Target,
                func.coalesce(scan_count_sq.c.scan_count, 0).label("scan_count"),
                func.coalesce(open_vuln_sq.c.open_vuln_count, 0).label("open_vuln_count"),
            )
            .outerjoin(scan_count_sq, scan_count_sq.c.target_id == Target.id)
            .outerjoin(open_vuln_sq, open_vuln_sq.c.target_id == Target.id)
        )
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Target.created_at.desc()).offset(offset).limit(limit)

        result = await self._session.execute(stmt)

        summaries: list[TargetSummary] = []
        for row in result:
            target: Target = row[0]
            # Load tags — they're a separate table; we load them per-row here.
            # For list views this is acceptable; full detail uses eager loading.
            tags = await self.get_tags(target.id)
            summaries.append(
                TargetSummary(
                    id=target.id,
                    name=target.name,
                    target_type=target.target_type,
                    value=target.value,
                    is_active=target.is_active,
                    created_by_id=target.created_by_id,
                    created_at=target.created_at,
                    updated_at=target.updated_at,
                    tags=[t.tag for t in tags],
                    scan_count=row.scan_count,
                    open_vulnerability_count=row.open_vuln_count,
                )
            )

        return summaries, total

    async def get_with_counts(
        self,
        target_id: uuid.UUID,
    ) -> tuple[Target, int, int] | None:
        """Fetch a single target with scan and vulnerability counts.

        Args:
            target_id: The target UUID.

        Returns:
            tuple[Target, scan_count, open_vuln_count] | None
        """
        scan_count_sq = (
            select(func.count(Scan.id))
            .where(Scan.target_id == target_id)
            .scalar_subquery()
        )
        open_vuln_sq = (
            select(func.count(Vulnerability.id))
            .where(
                and_(
                    Vulnerability.target_id == target_id,
                    Vulnerability.status.in_(
                        [VulnerabilityStatus.OPEN, VulnerabilityStatus.CONFIRMED]
                    ),
                )
            )
            .scalar_subquery()
        )

        stmt = select(
            Target,
            scan_count_sq.label("scan_count"),
            open_vuln_sq.label("open_vuln_count"),
        ).where(Target.id == target_id)

        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        return row[0], row.scan_count, row.open_vuln_count

    # ── Tag Management ────────────────────────────────────────────────────────

    async def get_tags(self, target_id: uuid.UUID) -> list[TargetTag]:
        """Fetch all tags for a target.

        Args:
            target_id: The target UUID.

        Returns:
            list[TargetTag]: All tags for this target, ordered alphabetically.
        """
        stmt = (
            select(TargetTag)
            .where(TargetTag.target_id == target_id)
            .order_by(TargetTag.tag)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add_tag(self, target_id: uuid.UUID, tag: str) -> TargetTag:
        """Add a single tag to a target.

        Idempotent — if the tag already exists, returns the existing record.

        Args:
            target_id: The target UUID.
            tag:       Normalised tag string.

        Returns:
            TargetTag: The new or existing tag record.
        """
        existing = await self._get_tag(target_id, tag)
        if existing:
            return existing

        from datetime import datetime, timezone
        tag_record = TargetTag(
            target_id=target_id,
            tag=tag,
            created_at=datetime.now(tz=timezone.utc),
        )
        self._session.add(tag_record)
        await self._session.flush()
        await self._session.refresh(tag_record)
        return tag_record

    async def remove_tag(self, target_id: uuid.UUID, tag: str) -> bool:
        """Remove a specific tag from a target.

        Args:
            target_id: The target UUID.
            tag:       The tag string to remove.

        Returns:
            bool: True if the tag was found and removed, False if it didn't exist.
        """
        existing = await self._get_tag(target_id, tag)
        if existing is None:
            return False
        await self._session.delete(existing)
        await self._session.flush()
        return True

    async def replace_tags(
        self, target_id: uuid.UUID, new_tags: list[str]
    ) -> list[TargetTag]:
        """Replace all tags for a target with the provided set.

        PUT semantics — deletes all existing tags and inserts the new ones.

        Args:
            target_id: The target UUID.
            new_tags:  Complete new tag set (already validated and normalised).

        Returns:
            list[TargetTag]: The newly created tag records.
        """
        from datetime import datetime, timezone
        from sqlalchemy import delete

        # Delete all existing tags
        await self._session.execute(
            delete(TargetTag).where(TargetTag.target_id == target_id)
        )
        await self._session.flush()

        # Insert new tags
        if not new_tags:
            return []

        now = datetime.now(tz=timezone.utc)
        new_records = [
            TargetTag(target_id=target_id, tag=tag, created_at=now)
            for tag in new_tags
        ]
        for record in new_records:
            self._session.add(record)
        await self._session.flush()
        for record in new_records:
            await self._session.refresh(record)
        return new_records

    async def _get_tag(
        self, target_id: uuid.UUID, tag: str
    ) -> TargetTag | None:
        """Internal: fetch a specific tag record.

        Args:
            target_id: The target UUID.
            tag:       Tag string.

        Returns:
            TargetTag | None
        """
        stmt = select(TargetTag).where(
            and_(
                TargetTag.target_id == target_id,
                TargetTag.tag == tag,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ── Stats ─────────────────────────────────────────────────────────────────

    async def get_type_distribution(self) -> dict[str, int]:
        """Return count of active targets grouped by type.

        Used by the platform dashboard.

        Returns:
            dict[str, int]: Maps target_type value to count.
        """
        stmt = (
            select(
                Target.target_type,
                func.count(Target.id).label("count"),
            )
            .where(Target.is_active.is_(True))
            .group_by(Target.target_type)
        )
        result = await self._session.execute(stmt)
        return {row.target_type.value: row.count for row in result}

    async def get_all_tags_for_target(self, target_id: uuid.UUID) -> list[str]:
        """Return all tag labels for a target as plain strings.

        Args:
            target_id: The target UUID.

        Returns:
            list[str]: Sorted tag labels.
        """
        tags = await self.get_tags(target_id)
        return [t.tag for t in tags]
