"""
ScanProfile service — business logic for profile management.

Key Responsibilities:
    1. CRUD for ScanProfile records
    2. Plugin enable/disable per profile
    3. Profile cloning (builtin → custom, custom → custom)
    4. Builtin profile seeding on startup
    5. Profile resolution for scan dispatch (merge plugin configs)

Access Control:
    - Any authenticated user: list profiles, get profile details
    - Analyst+: create custom profiles
    - Creator OR Admin: update/delete custom profiles
    - Builtin profiles: NEVER editable or deletable
    - Workspace-scoped profiles: workspace OWNER only
"""

from __future__ import annotations

import uuid
from typing import Any

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
from app.models.scan_profile import ProfileType, ScanProfile, ScanProfilePlugin
from app.models.user import User, UserRole
from app.repositories.audit_log import AuditLogRepository
from app.repositories.scan_profile import ScanProfileRepository
from app.schemas.common import PaginatedResponse
from app.schemas.scan_profile import (
    ProfilePluginAdd,
    ScanProfileClone,
    ScanProfileCreate,
    ScanProfilePluginResponse,
    ScanProfilePluginUpdate,
    ScanProfileResponse,
    ScanProfileSummary,
    ScanProfileUpdate,
)

logger = get_logger(__name__)

# ── Builtin Profile Definitions ───────────────────────────────────────────────
# Defines the default plugin sets for each builtin profile type.
# Keys match Plugin.name in the plugins registry.
# At seeding time, the service resolves names → UUIDs.

BUILTIN_PROFILES: list[dict] = [
    {
        "name": "Quick Recon",
        "profile_type": ProfileType.QUICK_RECON,
        "description": (
            "Fast passive intelligence gathering. "
            "Performs DNS enumeration, WHOIS lookup, Shodan search, "
            "and basic port discovery. Duration: ~5 minutes. "
            "Safe to run without alerting targets."
        ),
        "default_scan_type": "reconnaissance",
        "default_priority": "medium",
        "timeout_minutes": 30,
        "tags": ["recon", "passive", "quick"],
        "plugins": [
            "dns_enum",
            "whois_lookup",
            "shodan_query",
            "port_discovery",
        ],
    },
    {
        "name": "External Assessment",
        "profile_type": ProfileType.EXTERNAL_ASSESSMENT,
        "description": (
            "Comprehensive external attack surface assessment. "
            "Full recon followed by active vulnerability scanning. "
            "Includes subdomain enumeration, port scanning, "
            "service fingerprinting, and CVE detection. Duration: ~2 hours."
        ),
        "default_scan_type": "full",
        "default_priority": "medium",
        "timeout_minutes": 180,
        "tags": ["external", "full", "assessment"],
        "plugins": [
            "dns_enum",
            "whois_lookup",
            "subdomain_enum",
            "shodan_query",
            "port_discovery",
            "nmap_scanner",
            "ssl_audit",
            "nuclei_cve",
        ],
    },
    {
        "name": "Infrastructure Assessment",
        "profile_type": ProfileType.INFRASTRUCTURE,
        "description": (
            "Network-focused deep assessment for internal or external infrastructure. "
            "CIDR sweep, Nmap full port scan, service detection, "
            "CVE database correlation, SSL/TLS audit, "
            "and SMB/RDP exposure checks. Duration: ~4 hours."
        ),
        "default_scan_type": "vulnerability",
        "default_priority": "medium",
        "timeout_minutes": 300,
        "tags": ["infrastructure", "network", "cve"],
        "plugins": [
            "nmap_scanner",
            "port_discovery",
            "ssl_audit",
            "nuclei_cve",
            "smb_check",
            "rdp_check",
            "banner_grab",
        ],
    },
    {
        "name": "Web Assessment",
        "profile_type": ProfileType.WEB_ASSESSMENT,
        "description": (
            "Web application-focused assessment. "
            "Covers OWASP Top 10 checks, HTTP header analysis, "
            "directory and file bruteforcing, nikto scan, "
            "nuclei web templates, and JavaScript analysis. Duration: ~2 hours."
        ),
        "default_scan_type": "vulnerability",
        "default_priority": "medium",
        "timeout_minutes": 180,
        "tags": ["web", "owasp", "application"],
        "plugins": [
            "nikto_scanner",
            "nuclei_web",
            "header_check",
            "dir_brute",
            "js_analyzer",
            "ssl_audit",
        ],
    },
    {
        "name": "Custom",
        "profile_type": ProfileType.CUSTOM,
        "description": (
            "Empty custom profile. Add your own plugins and configure each "
            "one independently. Use this as a starting point for "
            "engagement-specific configurations."
        ),
        "default_scan_type": "full",
        "default_priority": "medium",
        "timeout_minutes": None,
        "tags": ["custom"],
        "plugins": [],  # No default plugins
    },
]


class ScanProfileService:
    """Orchestrates all scan profile business logic.

    Attributes:
        _db:           Async database session.
        _settings:     Application settings.
        _profile_repo: Profile data access.
        _audit_repo:   Audit log writer.
    """

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._profile_repo = ScanProfileRepository(db)
        self._audit_repo = AuditLogRepository(db)

    # ── Internal Helpers ──────────────────────────────────────────────────────

    async def _get_or_404(self, profile_id: uuid.UUID) -> ScanProfile:
        profile = await self._profile_repo.get_with_plugins(profile_id)
        if profile is None:
            raise NotFoundError("ScanProfile", str(profile_id))
        return profile

    def _require_edit_permission(
        self, profile: ScanProfile, user: User
    ) -> None:
        """Assert the user can edit a custom profile.

        Builtin profiles are NEVER editable.

        Args:
            profile: The profile to check.
            user:    Requesting user.

        Raises:
            ValidationError:      If profile is builtin.
            PermissionDeniedError: If user is not creator or admin.
        """
        if profile.is_builtin:
            raise ValidationError(
                "Builtin profiles cannot be modified. "
                "Clone this profile first to create an editable copy."
            )
        if user.is_superuser:
            return
        if user.role == UserRole.ADMIN:
            return
        if profile.created_by_id != user.id:
            raise PermissionDeniedError(
                "Only the profile creator or an admin can modify this profile."
            )

    def _build_plugin_response(
        self, pp: ScanProfilePlugin
    ) -> ScanProfilePluginResponse:
        """Build a ScanProfilePluginResponse from an eagerly-loaded entry."""
        return ScanProfilePluginResponse(
            id=pp.id,
            profile_id=pp.profile_id,
            plugin_id=pp.plugin_id,
            is_enabled=pp.is_enabled,
            execution_order=pp.execution_order,
            config_override=pp.config_override,
            created_at=pp.created_at,
            updated_at=pp.updated_at,
            plugin_name=pp.plugin.name,
            plugin_display_name=pp.plugin.display_name,
            plugin_phase=pp.plugin.phase.value,
            plugin_version=pp.plugin.version,
            plugin_is_enabled=pp.plugin.is_enabled,
        )

    async def _build_response(self, profile: ScanProfile) -> ScanProfileResponse:
        """Build a full ScanProfileResponse from an ORM instance."""
        # Ensure profile_plugins are loaded with plugin data
        profile_with_plugins = await self._profile_repo.get_with_plugins(profile.id)
        if profile_with_plugins is None:
            raise NotFoundError("ScanProfile", str(profile.id))

        enabled_count = sum(
            1 for pp in profile_with_plugins.profile_plugins if pp.is_enabled
        )
        plugin_responses = [
            self._build_plugin_response(pp)
            for pp in sorted(
                profile_with_plugins.profile_plugins,
                key=lambda x: x.execution_order,
            )
        ]

        return ScanProfileResponse(
            id=profile_with_plugins.id,
            name=profile_with_plugins.name,
            profile_type=profile_with_plugins.profile_type,
            description=profile_with_plugins.description,
            is_builtin=profile_with_plugins.is_builtin,
            is_active=profile_with_plugins.is_active,
            workspace_id=profile_with_plugins.workspace_id,
            created_by_id=profile_with_plugins.created_by_id,
            default_scan_type=profile_with_plugins.default_scan_type,
            default_priority=profile_with_plugins.default_priority,
            timeout_minutes=profile_with_plugins.timeout_minutes,
            tags=profile_with_plugins.tags,
            cloned_from_id=profile_with_plugins.cloned_from_id,
            created_at=profile_with_plugins.created_at,
            updated_at=profile_with_plugins.updated_at,
            plugin_count=enabled_count,
            total_plugin_entries=len(profile_with_plugins.profile_plugins),
            plugins=plugin_responses,
        )

    # ── Builtin Profile Seeding ───────────────────────────────────────────────

    async def seed_builtin_profiles(self) -> None:
        """Create builtin profiles if they do not already exist.

        Called once on application startup via the lifespan event.
        Idempotent — skips profiles that already exist.
        Existing builtin profiles are NOT updated (they are considered stable).
        """
        for defn in BUILTIN_PROFILES:
            existing = await self._profile_repo.get_builtin_by_type(
                defn["profile_type"]
            )
            if existing:
                continue

            profile = await self._profile_repo.create_from_dict(
                {
                    "name": defn["name"],
                    "profile_type": defn["profile_type"],
                    "description": defn["description"],
                    "is_builtin": True,
                    "is_active": True,
                    "workspace_id": None,
                    "created_by_id": None,
                    "default_scan_type": defn["default_scan_type"],
                    "default_priority": defn["default_priority"],
                    "timeout_minutes": defn["timeout_minutes"],
                    "tags": defn["tags"],
                }
            )

            # Add default plugins by name
            for plugin_name in defn["plugins"]:
                plugin = await self._profile_repo.get_plugin_by_name(plugin_name)
                if plugin is None:
                    logger.warning(
                        "builtin_profile.plugin_not_found",
                        profile=defn["name"],
                        plugin_name=plugin_name,
                    )
                    continue
                order = defn["plugins"].index(plugin_name)
                await self._profile_repo.add_plugin_to_profile(
                    profile_id=profile.id,
                    plugin_id=plugin.id,
                    is_enabled=True,
                    execution_order=order,
                )

            logger.info(
                "builtin_profile.seeded",
                profile_type=defn["profile_type"].value,
                name=defn["name"],
            )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create_profile(
        self,
        data: ScanProfileCreate,
        current_user: User,
        ip_address: str | None = None,
    ) -> ScanProfileResponse:
        """Create a new custom scan profile.

        Args:
            data:         Validated creation payload.
            current_user: The requesting user.
            ip_address:   Client IP for audit.

        Returns:
            ScanProfileResponse: The created profile.

        Raises:
            ConflictError: If a profile with this name exists in the same scope.
        """
        if await self._profile_repo.name_exists_in_scope(
            data.name, data.workspace_id
        ):
            raise ConflictError(
                f"A profile named '{data.name}' already exists in this scope."
            )

        profile = await self._profile_repo.create_from_dict(
            {
                "name": data.name,
                "profile_type": data.profile_type,
                "description": data.description,
                "is_builtin": False,
                "is_active": True,
                "workspace_id": data.workspace_id,
                "created_by_id": current_user.id,
                "default_scan_type": data.default_scan_type,
                "default_priority": data.default_priority,
                "timeout_minutes": data.timeout_minutes,
                "tags": data.tags,
            }
        )

        # Add initial plugins
        for plugin_cfg in data.plugins:
            await self._profile_repo.add_plugin_to_profile(
                profile_id=profile.id,
                plugin_id=plugin_cfg.plugin_id,
                is_enabled=plugin_cfg.is_enabled,
                execution_order=plugin_cfg.execution_order,
                config_override=plugin_cfg.config_override,
            )

        await self._audit_repo.create_entry(
            action=AuditAction.PROFILE_CREATED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="scan_profile",
            resource_id=profile.id,
            details={"name": data.name, "profile_type": data.profile_type.value},
        )

        logger.info(
            "scan_profile.created",
            profile_id=str(profile.id),
            name=data.name,
            user_id=str(current_user.id),
        )

        return await self._build_response(profile)

    async def list_profiles(
        self,
        current_user: User,
        *,
        workspace_id: uuid.UUID | None = None,
        active_only: bool = True,
        profile_type: ProfileType | None = None,
        search: str | None = None,
        include_builtin: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[ScanProfileSummary]:
        """List scan profiles with pagination.

        Args:
            current_user:   The requesting user.
            workspace_id:   Limit to workspace scope.
            active_only:    Exclude inactive profiles.
            profile_type:   Optional type filter.
            search:         Name search.
            include_builtin: Include builtin profiles.
            page:           1-indexed page.
            page_size:      Items per page.

        Returns:
            PaginatedResponse[ScanProfileSummary]: Paginated summaries.
        """
        offset = (page - 1) * page_size
        profiles, total = await self._profile_repo.list_profiles(
            workspace_id=workspace_id,
            include_platform_wide=True,
            active_only=active_only,
            profile_type=profile_type,
            search=search,
            include_builtin=include_builtin,
            offset=offset,
            limit=page_size,
        )

        summaries = [
            ScanProfileSummary(
                id=p.id,
                name=p.name,
                profile_type=p.profile_type,
                description=p.description,
                is_builtin=p.is_builtin,
                is_active=p.is_active,
                workspace_id=p.workspace_id,
                created_by_id=p.created_by_id,
                default_scan_type=p.default_scan_type,
                default_priority=p.default_priority,
                timeout_minutes=p.timeout_minutes,
                tags=p.tags,
                cloned_from_id=p.cloned_from_id,
                plugin_count=sum(
                    1 for pp in p.profile_plugins if pp.is_enabled
                ),
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in profiles
        ]

        return PaginatedResponse[ScanProfileSummary].build(
            items=summaries, total=total, page=page, page_size=page_size
        )

    async def get_profile(
        self,
        profile_id: uuid.UUID,
        current_user: User,
    ) -> ScanProfileResponse:
        """Get a profile by ID with full plugin details.

        Args:
            profile_id:   Profile UUID.
            current_user: The requesting user.

        Returns:
            ScanProfileResponse: Full profile with plugins.
        """
        profile = await self._get_or_404(profile_id)
        return await self._build_response(profile)

    async def update_profile(
        self,
        profile_id: uuid.UUID,
        data: ScanProfileUpdate,
        current_user: User,
        ip_address: str | None = None,
    ) -> ScanProfileResponse:
        """Partially update a custom profile's metadata.

        Args:
            profile_id:   Profile UUID.
            data:         Partial update payload.
            current_user: The requesting user.
            ip_address:   Client IP.

        Returns:
            ScanProfileResponse: Updated profile.
        """
        profile = await self._get_or_404(profile_id)
        self._require_edit_permission(profile, current_user)

        update_data = data.model_dump(exclude_unset=True)

        # Name conflict check
        if "name" in update_data:
            if await self._profile_repo.name_exists_in_scope(
                update_data["name"],
                profile.workspace_id,
                exclude_id=profile_id,
            ):
                raise ConflictError(
                    f"A profile named '{update_data['name']}' already exists."
                )

        # Clear timeout with explicit 0
        if update_data.get("timeout_minutes") == 0:
            update_data["timeout_minutes"] = None

        for field, value in update_data.items():
            setattr(profile, field, value)
        self._db.add(profile)
        await self._db.flush()
        await self._db.refresh(profile)

        await self._audit_repo.create_entry(
            action=AuditAction.PROFILE_UPDATED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="scan_profile",
            resource_id=profile.id,
            details={"changes": list(update_data.keys())},
        )

        return await self._build_response(profile)

    async def delete_profile(
        self,
        profile_id: uuid.UUID,
        current_user: User,
        ip_address: str | None = None,
    ) -> None:
        """Permanently delete a custom profile.

        Args:
            profile_id:   Profile UUID.
            current_user: The requesting user.
            ip_address:   Client IP.

        Raises:
            ValidationError: If profile is builtin.
        """
        profile = await self._get_or_404(profile_id)
        self._require_edit_permission(profile, current_user)

        await self._db.delete(profile)
        await self._db.flush()

        await self._audit_repo.create_entry(
            action=AuditAction.PROFILE_DELETED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="scan_profile",
            resource_id=profile_id,
            details={"name": profile.name},
        )

        logger.info("scan_profile.deleted", profile_id=str(profile_id))

    # ── Clone ─────────────────────────────────────────────────────────────────

    async def clone_profile(
        self,
        profile_id: uuid.UUID,
        data: ScanProfileClone,
        current_user: User,
        ip_address: str | None = None,
    ) -> ScanProfileResponse:
        """Clone a profile (builtin or custom) into a new CUSTOM profile.

        All plugin entries including config overrides are copied.
        The clone is always a CUSTOM profile — it is fully editable.

        Args:
            profile_id:   UUID of the source profile.
            data:         Clone config (name, workspace, description).
            current_user: The requesting user.
            ip_address:   Client IP.

        Returns:
            ScanProfileResponse: The new cloned profile.
        """
        source = await self._get_or_404(profile_id)

        if await self._profile_repo.name_exists_in_scope(
            data.name, data.workspace_id
        ):
            raise ConflictError(
                f"A profile named '{data.name}' already exists in this scope."
            )

        clone = await self._profile_repo.create_from_dict(
            {
                "name": data.name,
                "profile_type": ProfileType.CUSTOM,
                "description": data.description or source.description,
                "is_builtin": False,
                "is_active": True,
                "workspace_id": data.workspace_id,
                "created_by_id": current_user.id,
                "default_scan_type": source.default_scan_type,
                "default_priority": source.default_priority,
                "timeout_minutes": source.timeout_minutes,
                "tags": list(source.tags),
                "cloned_from_id": source.id,
            }
        )

        copied = await self._profile_repo.copy_plugins_to_profile(
            source_profile_id=source.id,
            target_profile_id=clone.id,
        )

        await self._audit_repo.create_entry(
            action=AuditAction.PROFILE_CLONED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=current_user.id,
            actor_ip=ip_address,
            resource_type="scan_profile",
            resource_id=clone.id,
            details={
                "cloned_from": str(source.id),
                "cloned_from_name": source.name,
                "plugins_copied": copied,
            },
        )

        logger.info(
            "scan_profile.cloned",
            source_id=str(source.id),
            clone_id=str(clone.id),
            plugins_copied=copied,
        )

        return await self._build_response(clone)

    # ── Plugin Management ─────────────────────────────────────────────────────

    async def add_plugin(
        self,
        profile_id: uuid.UUID,
        data: ProfilePluginAdd,
        current_user: User,
        ip_address: str | None = None,
    ) -> ScanProfileResponse:
        """Add a plugin to a profile.

        Idempotent — adding an already-present plugin returns 200.

        Args:
            profile_id:   Profile UUID.
            data:         Plugin add payload.
            current_user: The requesting user.
            ip_address:   Client IP.

        Returns:
            ScanProfileResponse: Updated profile.
        """
        profile = await self._get_or_404(profile_id)
        self._require_edit_permission(profile, current_user)

        await self._profile_repo.add_plugin_to_profile(
            profile_id=profile_id,
            plugin_id=data.plugin_id,
            is_enabled=data.is_enabled,
            execution_order=data.execution_order,
            config_override=data.config_override,
        )

        logger.info(
            "scan_profile.plugin.added",
            profile_id=str(profile_id),
            plugin_id=str(data.plugin_id),
        )

        return await self._build_response(profile)

    async def remove_plugin(
        self,
        profile_id: uuid.UUID,
        plugin_id: uuid.UUID,
        current_user: User,
        ip_address: str | None = None,
    ) -> ScanProfileResponse:
        """Remove a plugin from a profile.

        Args:
            profile_id:   Profile UUID.
            plugin_id:    Plugin UUID to remove.
            current_user: The requesting user.
            ip_address:   Client IP.

        Returns:
            ScanProfileResponse: Updated profile.

        Raises:
            NotFoundError: If plugin is not in this profile.
        """
        profile = await self._get_or_404(profile_id)
        self._require_edit_permission(profile, current_user)

        removed = await self._profile_repo.remove_plugin_from_profile(
            profile_id=profile_id, plugin_id=plugin_id
        )
        if not removed:
            raise NotFoundError("Plugin in profile", str(plugin_id))

        logger.info(
            "scan_profile.plugin.removed",
            profile_id=str(profile_id),
            plugin_id=str(plugin_id),
        )

        return await self._build_response(profile)

    async def update_plugin(
        self,
        profile_id: uuid.UUID,
        plugin_id: uuid.UUID,
        data: ScanProfilePluginUpdate,
        current_user: User,
        ip_address: str | None = None,
    ) -> ScanProfileResponse:
        """Update a plugin entry in a profile (enable, order, config_override).

        Args:
            profile_id:   Profile UUID.
            plugin_id:    Plugin UUID.
            data:         Update payload.
            current_user: The requesting user.
            ip_address:   Client IP.

        Returns:
            ScanProfileResponse: Updated profile.

        Raises:
            NotFoundError: If plugin is not in this profile.
        """
        profile = await self._get_or_404(profile_id)
        self._require_edit_permission(profile, current_user)

        entry = await self._profile_repo.get_profile_plugin(profile_id, plugin_id)
        if entry is None:
            raise NotFoundError("Plugin in profile", str(plugin_id))

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(entry, field, value)
        self._db.add(entry)
        await self._db.flush()
        await self._db.refresh(entry)

        logger.info(
            "scan_profile.plugin.updated",
            profile_id=str(profile_id),
            plugin_id=str(plugin_id),
            changes=list(update_data.keys()),
        )

        return await self._build_response(profile)

    # ── Scan Dispatch Integration ──────────────────────────────────────────────

    async def resolve_plugin_configs(
        self,
        profile_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Resolve the final plugin configuration list for scan dispatch.

        Called by the Scan service when dispatching a scan.
        Returns only ENABLED plugins where the global Plugin.is_enabled = True.
        Merges Profile.config_override on top of Plugin.default_config.

        Args:
            profile_id: The profile UUID.

        Returns:
            list[dict]: Each item: {
                "plugin_id": UUID,
                "plugin_name": str,
                "module_path": str,
                "execution_order": int,
                "config": dict  (merged final config)
            }
        """
        entries = await self._profile_repo.get_enabled_plugins_for_profile(profile_id)

        resolved = []
        for entry in entries:
            plugin = entry.plugin
            # Skip globally-disabled plugins
            if not plugin.is_enabled:
                logger.warning(
                    "scan_profile.dispatch.plugin_globally_disabled",
                    profile_id=str(profile_id),
                    plugin_name=plugin.name,
                )
                continue

            merged_config = {
                **plugin.default_config,
                **entry.config_override,
            }

            resolved.append(
                {
                    "plugin_id": plugin.id,
                    "plugin_name": plugin.name,
                    "module_path": plugin.module_path,
                    "execution_order": entry.execution_order,
                    "config": merged_config,
                }
            )

        return sorted(resolved, key=lambda x: x["execution_order"])
