"""
ScanProfile repository — database access for profiles and profile plugins.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.plugin import Plugin
from app.models.scan_profile import ProfileType, ScanProfile, ScanProfilePlugin
from app.repositories.base import BaseRepository


class ScanProfileRepository(BaseRepository[ScanProfile, dict, dict]):
    """Repository for ScanProfile and ScanProfilePlugin data access."""

    model = ScanProfile

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── Eager-load helper ─────────────────────────────────────────────────────

    async def get_with_plugins(self, profile_id: uuid.UUID) -> ScanProfile | None:
        """Fetch a profile with all ScanProfilePlugin rows eagerly loaded.

        Each ScanProfilePlugin also eagerly loads its Plugin to provide
        display_name, phase, etc. for the API response.

        Args:
            profile_id: The profile UUID.

        Returns:
            ScanProfile | None: Profile with profile_plugins loaded.
        """
        stmt = (
            select(ScanProfile)
            .options(
                selectinload(ScanProfile.profile_plugins).selectinload(
                    ScanProfilePlugin.plugin
                )
            )
            .where(ScanProfile.id == profile_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ── List ──────────────────────────────────────────────────────────────────

    async def list_profiles(
        self,
        *,
        workspace_id: uuid.UUID | None = None,
        include_platform_wide: bool = True,
        active_only: bool = True,
        profile_type: ProfileType | None = None,
        search: str | None = None,
        include_builtin: bool = True,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ScanProfile], int]:
        """Return paginated scan profiles with plugin counts.

        Args:
            workspace_id:           Filter to a specific workspace.
            include_platform_wide:  Also include profiles where workspace_id IS NULL.
            active_only:            Exclude inactive profiles.
            profile_type:           Optional type filter.
            search:                 ILIKE search against name.
            include_builtin:        Include builtin profiles.
            offset:                 Pagination offset.
            limit:                  Max results.

        Returns:
            tuple[list[ScanProfile], int]: Profiles and total count.
        """
        conditions: list[Any] = []

        if active_only:
            conditions.append(ScanProfile.is_active.is_(True))

        if not include_builtin:
            conditions.append(ScanProfile.is_builtin.is_(False))

        if profile_type is not None:
            conditions.append(ScanProfile.profile_type == profile_type)

        if search:
            conditions.append(ScanProfile.name.ilike(f"%{search}%"))

        # Workspace scoping: platform-wide (NULL) OR specific workspace
        if workspace_id is not None and include_platform_wide:
            conditions.append(
                or_(
                    ScanProfile.workspace_id == workspace_id,
                    ScanProfile.workspace_id.is_(None),
                )
            )
        elif workspace_id is not None:
            conditions.append(ScanProfile.workspace_id == workspace_id)
        elif not include_platform_wide:
            conditions.append(ScanProfile.workspace_id.isnot(None))

        # Count
        count_stmt = select(func.count(ScanProfile.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total = (await self._session.execute(count_stmt)).scalar_one()

        # Main query
        stmt = (
            select(ScanProfile)
            .options(selectinload(ScanProfile.profile_plugins))
        )
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(ScanProfile.is_builtin.desc(), ScanProfile.name).offset(offset).limit(limit)

        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all()), total

    # ── Lookup ────────────────────────────────────────────────────────────────

    async def get_builtins(self) -> list[ScanProfile]:
        """Return all builtin profiles.

        Returns:
            list[ScanProfile]: System-shipped profiles.
        """
        stmt = (
            select(ScanProfile)
            .where(ScanProfile.is_builtin.is_(True))
            .options(selectinload(ScanProfile.profile_plugins).selectinload(ScanProfilePlugin.plugin))
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_builtin_by_type(
        self, profile_type: ProfileType
    ) -> ScanProfile | None:
        """Return the builtin profile for a given type.

        Args:
            profile_type: The builtin profile type.

        Returns:
            ScanProfile | None
        """
        stmt = select(ScanProfile).where(
            and_(
                ScanProfile.profile_type == profile_type,
                ScanProfile.is_builtin.is_(True),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def name_exists_in_scope(
        self,
        name: str,
        workspace_id: uuid.UUID | None,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """Check for a name collision in the same scope (workspace or global).

        Args:
            name:         The profile name to check.
            workspace_id: The workspace scope (None = global).
            exclude_id:   Profile UUID to exclude (for update checks).

        Returns:
            bool: True if a profile with this name already exists in scope.
        """
        conditions: list[Any] = [ScanProfile.name == name]
        if workspace_id is None:
            conditions.append(ScanProfile.workspace_id.is_(None))
        else:
            conditions.append(ScanProfile.workspace_id == workspace_id)
        if exclude_id:
            conditions.append(ScanProfile.id != exclude_id)

        stmt = select(func.count(ScanProfile.id)).where(and_(*conditions))
        count = (await self._session.execute(stmt)).scalar_one()
        return count > 0

    # ── Plugin Management ─────────────────────────────────────────────────────

    async def get_profile_plugin(
        self,
        profile_id: uuid.UUID,
        plugin_id: uuid.UUID,
    ) -> ScanProfilePlugin | None:
        """Fetch a specific profile-plugin entry.

        Args:
            profile_id: Profile UUID.
            plugin_id:  Plugin UUID.

        Returns:
            ScanProfilePlugin | None
        """
        stmt = select(ScanProfilePlugin).where(
            and_(
                ScanProfilePlugin.profile_id == profile_id,
                ScanProfilePlugin.plugin_id == plugin_id,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_plugin_to_profile(
        self,
        profile_id: uuid.UUID,
        plugin_id: uuid.UUID,
        is_enabled: bool = True,
        execution_order: int = 0,
        config_override: dict | None = None,
    ) -> ScanProfilePlugin:
        """Add a plugin to a profile.

        Idempotent — returns existing entry if it already exists.

        Args:
            profile_id:       Profile UUID.
            plugin_id:        Plugin UUID.
            is_enabled:       Enable state.
            execution_order:  Execution order.
            config_override:  Config overrides.

        Returns:
            ScanProfilePlugin: Created or existing entry.
        """
        existing = await self.get_profile_plugin(profile_id, plugin_id)
        if existing:
            return existing

        entry = ScanProfilePlugin(
            profile_id=profile_id,
            plugin_id=plugin_id,
            is_enabled=is_enabled,
            execution_order=execution_order,
            config_override=config_override or {},
        )
        self._session.add(entry)
        await self._session.flush()
        await self._session.refresh(entry)
        return entry

    async def remove_plugin_from_profile(
        self,
        profile_id: uuid.UUID,
        plugin_id: uuid.UUID,
    ) -> bool:
        """Remove a plugin from a profile.

        Args:
            profile_id: Profile UUID.
            plugin_id:  Plugin UUID.

        Returns:
            bool: True if found and removed.
        """
        entry = await self.get_profile_plugin(profile_id, plugin_id)
        if entry is None:
            return False
        await self._session.delete(entry)
        await self._session.flush()
        return True

    async def get_enabled_plugins_for_profile(
        self, profile_id: uuid.UUID
    ) -> list[ScanProfilePlugin]:
        """Return all enabled plugin entries for a profile, with plugin data.

        Used by the scan dispatch engine to build the plugin execution plan.

        Args:
            profile_id: Profile UUID.

        Returns:
            list[ScanProfilePlugin]: Enabled entries ordered by execution_order.
        """
        stmt = (
            select(ScanProfilePlugin)
            .options(selectinload(ScanProfilePlugin.plugin))
            .where(
                and_(
                    ScanProfilePlugin.profile_id == profile_id,
                    ScanProfilePlugin.is_enabled.is_(True),
                )
            )
            .order_by(ScanProfilePlugin.execution_order)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def copy_plugins_to_profile(
        self,
        source_profile_id: uuid.UUID,
        target_profile_id: uuid.UUID,
    ) -> int:
        """Copy all plugin entries from one profile to another.

        Used during profile cloning.

        Args:
            source_profile_id: UUID of the profile to copy from.
            target_profile_id: UUID of the profile to copy into.

        Returns:
            int: Number of plugin entries copied.
        """
        stmt = select(ScanProfilePlugin).where(
            ScanProfilePlugin.profile_id == source_profile_id
        )
        result = await self._session.execute(stmt)
        entries = list(result.scalars().all())

        for entry in entries:
            new_entry = ScanProfilePlugin(
                profile_id=target_profile_id,
                plugin_id=entry.plugin_id,
                is_enabled=entry.is_enabled,
                execution_order=entry.execution_order,
                config_override=dict(entry.config_override),
            )
            self._session.add(new_entry)

        if entries:
            await self._session.flush()
        return len(entries)

    async def get_plugin_by_name(self, name: str) -> Plugin | None:
        """Fetch a plugin by its machine name.

        Args:
            name: Plugin machine name (e.g., 'nmap_scanner').

        Returns:
            Plugin | None
        """
        stmt = select(Plugin).where(Plugin.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
