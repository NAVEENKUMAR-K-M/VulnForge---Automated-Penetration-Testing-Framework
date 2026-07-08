"""
Unit tests for ScanProfileService.

Tests profile CRUD, builtin seeding, cloning, and plugin resolution.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.models.plugin import PluginPhase
from app.models.scan import Priority, ScanType
from app.models.scan_profile import ProfileType
from app.models.user import UserRole
from app.schemas.scan_profile import (
    ProfilePluginAdd,
    ScanProfileClone,
    ScanProfileCreate,
    ScanProfilePluginUpdate,
    ScanProfileUpdate,
)
from app.services.scan_profile_service import ScanProfileService, BUILTIN_PROFILES


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_settings() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_profile_repo() -> AsyncMock:
    repo = AsyncMock()
    # By default, pretend no name conflicts exist
    repo.name_exists_in_scope.return_value = False
    return repo


@pytest.fixture
def mock_audit_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(
    mock_db: AsyncMock,
    mock_settings: MagicMock,
    mock_profile_repo: AsyncMock,
    mock_audit_repo: AsyncMock,
) -> ScanProfileService:
    svc = ScanProfileService(mock_db, mock_settings)
    svc._profile_repo = mock_profile_repo
    svc._audit_repo = mock_audit_repo
    return svc


@pytest.fixture
def user() -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.is_superuser = False
    u.role = UserRole.ANALYST
    return u


@pytest.fixture
def custom_profile(user) -> MagicMock:
    p = MagicMock()
    p.id = uuid.uuid4()
    p.is_builtin = False
    p.created_by_id = user.id
    p.workspace_id = uuid.uuid4()
    p.profile_plugins = []
    p.timeout_minutes = 60
    return p


@pytest.fixture
def builtin_profile() -> MagicMock:
    p = MagicMock()
    p.id = uuid.uuid4()
    p.is_builtin = True
    p.created_by_id = None
    p.workspace_id = None
    p.profile_plugins = []
    return p


# ── Builtin Seeding Tests ─────────────────────────────────────────────────────

@pytest.mark.unit
async def test_seed_builtin_profiles_creates_missing(
    service: ScanProfileService, mock_profile_repo: AsyncMock
) -> None:
    """Test that missing builtin profiles are created with their plugins."""
    # Act as if no profiles exist
    mock_profile_repo.get_builtin_by_type.return_value = None
    mock_profile_repo.create_from_dict.return_value = MagicMock(id=uuid.uuid4())
    mock_plugin = MagicMock(id=uuid.uuid4())
    mock_profile_repo.get_plugin_by_name.return_value = mock_plugin

    await service.seed_builtin_profiles()

    # Should create one for each definition
    assert mock_profile_repo.create_from_dict.call_count == len(BUILTIN_PROFILES)
    # Should add plugins for all definitions that have plugins
    total_plugins = sum(len(d["plugins"]) for d in BUILTIN_PROFILES)
    assert mock_profile_repo.add_plugin_to_profile.call_count == total_plugins


@pytest.mark.unit
async def test_seed_builtin_profiles_skips_existing(
    service: ScanProfileService, mock_profile_repo: AsyncMock
) -> None:
    """Test that existing builtin profiles are skipped."""
    # Act as if all exist
    mock_profile_repo.get_builtin_by_type.return_value = MagicMock()

    await service.seed_builtin_profiles()

    mock_profile_repo.create_from_dict.assert_not_called()
    mock_profile_repo.add_plugin_to_profile.assert_not_called()


# ── CRUD Tests ────────────────────────────────────────────────────────────────

@pytest.mark.unit
async def test_create_profile_success(
    service: ScanProfileService, mock_profile_repo: AsyncMock, user: MagicMock
) -> None:
    data = ScanProfileCreate(
        name="Test Profile",
        profile_type=ProfileType.CUSTOM,
        default_scan_type=ScanType.FULL,
        default_priority=Priority.MEDIUM,
        tags=["test"],
    )
    mock_profile_repo.name_exists_in_scope.return_value = False
    
    # Mock create return
    created = MagicMock(id=uuid.uuid4())
    mock_profile_repo.create_from_dict.return_value = created

    # Mock build_response to avoid needing actual ORM plugin loading logic
    service._build_response = AsyncMock()

    await service.create_profile(data, user)

    mock_profile_repo.create_from_dict.assert_called_once()
    service._build_response.assert_called_once_with(created)


@pytest.mark.unit
async def test_create_profile_name_conflict(
    service: ScanProfileService, mock_profile_repo: AsyncMock, user: MagicMock
) -> None:
    data = ScanProfileCreate(
        name="Existing",
        profile_type=ProfileType.CUSTOM,
    )
    mock_profile_repo.name_exists_in_scope.return_value = True

    with pytest.raises(ConflictError, match="already exists"):
        await service.create_profile(data, user)


@pytest.mark.unit
async def test_update_profile_success(
    service: ScanProfileService, mock_profile_repo: AsyncMock, custom_profile: MagicMock, user: MagicMock, mock_db: AsyncMock
) -> None:
    mock_profile_repo.get_with_plugins.return_value = custom_profile
    service._build_response = AsyncMock()

    data = ScanProfileUpdate(name="New Name", timeout_minutes=0)
    
    await service.update_profile(custom_profile.id, data, user)

    # 0 should become None
    assert custom_profile.timeout_minutes is None
    assert custom_profile.name == "New Name"
    mock_db.flush.assert_called_once()


@pytest.mark.unit
async def test_update_profile_builtin_denied(
    service: ScanProfileService, mock_profile_repo: AsyncMock, builtin_profile: MagicMock, user: MagicMock
) -> None:
    mock_profile_repo.get_with_plugins.return_value = builtin_profile

    data = ScanProfileUpdate(name="New Name")
    
    with pytest.raises(ValidationError, match="Builtin profiles cannot be modified"):
        await service.update_profile(builtin_profile.id, data, user)


@pytest.mark.unit
async def test_update_profile_not_creator_denied(
    service: ScanProfileService, mock_profile_repo: AsyncMock, custom_profile: MagicMock, user: MagicMock
) -> None:
    # Set creator to someone else
    custom_profile.created_by_id = uuid.uuid4()
    mock_profile_repo.get_with_plugins.return_value = custom_profile

    data = ScanProfileUpdate(name="New Name")
    
    with pytest.raises(PermissionDeniedError, match="Only the profile creator"):
        await service.update_profile(custom_profile.id, data, user)


@pytest.mark.unit
async def test_delete_profile_success(
    service: ScanProfileService, mock_profile_repo: AsyncMock, custom_profile: MagicMock, user: MagicMock, mock_db: AsyncMock
) -> None:
    mock_profile_repo.get_with_plugins.return_value = custom_profile

    await service.delete_profile(custom_profile.id, user)

    mock_db.delete.assert_called_once_with(custom_profile)


# ── Clone Tests ───────────────────────────────────────────────────────────────

@pytest.mark.unit
async def test_clone_profile_success(
    service: ScanProfileService, mock_profile_repo: AsyncMock, builtin_profile: MagicMock, user: MagicMock
) -> None:
    mock_profile_repo.get_with_plugins.return_value = builtin_profile
    mock_profile_repo.name_exists_in_scope.return_value = False
    
    cloned = MagicMock(id=uuid.uuid4())
    mock_profile_repo.create_from_dict.return_value = cloned
    mock_profile_repo.copy_plugins_to_profile.return_value = 5
    service._build_response = AsyncMock()

    data = ScanProfileClone(name="My Clone")
    
    await service.clone_profile(builtin_profile.id, data, user)

    mock_profile_repo.create_from_dict.assert_called_once()
    mock_profile_repo.copy_plugins_to_profile.assert_called_once_with(
        source_profile_id=builtin_profile.id,
        target_profile_id=cloned.id,
    )


# ── Plugin Resolution ─────────────────────────────────────────────────────────

@pytest.mark.unit
async def test_resolve_plugin_configs(
    service: ScanProfileService, mock_profile_repo: AsyncMock
) -> None:
    # Setup a mock plugin that is enabled
    mock_plugin1 = MagicMock()
    mock_plugin1.is_enabled = True
    mock_plugin1.name = "plugin1"
    mock_plugin1.default_config = {"threads": 10, "mode": "safe"}

    mock_entry1 = MagicMock()
    mock_entry1.plugin = mock_plugin1
    mock_entry1.execution_order = 1
    mock_entry1.config_override = {"threads": 50}  # override

    # Setup a mock plugin that is globally disabled
    mock_plugin2 = MagicMock()
    mock_plugin2.is_enabled = False
    mock_plugin2.name = "plugin2"

    mock_entry2 = MagicMock()
    mock_entry2.plugin = mock_plugin2
    mock_entry2.execution_order = 2

    mock_profile_repo.get_enabled_plugins_for_profile.return_value = [mock_entry1, mock_entry2]

    resolved = await service.resolve_plugin_configs(uuid.uuid4())

    # Plugin 2 should be skipped because it's globally disabled
    assert len(resolved) == 1
    
    # Plugin 1 config should be merged
    assert resolved[0]["plugin_name"] == "plugin1"
    assert resolved[0]["config"] == {"threads": 50, "mode": "safe"}
