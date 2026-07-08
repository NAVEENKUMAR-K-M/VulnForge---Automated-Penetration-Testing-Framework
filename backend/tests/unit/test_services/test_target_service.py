"""
Unit tests for TargetService.

All tests use mocked repositories — no real DB required.
Business logic (access control, uniqueness, soft-delete, tag management)
is verified in isolation.

Markers: @pytest.mark.unit
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.models.target import Target, TargetType
from app.models.target_tag import TargetTag
from app.models.user import User, UserRole
from app.schemas.target import (
    BulkTagUpdate,
    TargetCreate,
    TargetDeactivate,
    TargetUpdate,
)
from app.services.target_service import TargetService


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_settings() -> MagicMock:
    return MagicMock()


def make_user(
    *,
    role: UserRole = UserRole.ANALYST,
    is_superuser: bool = False,
    user_id: uuid.UUID | None = None,
) -> User:
    u = MagicMock(spec=User)
    u.id = user_id or uuid.uuid4()
    u.email = "analyst@vulnforge.local"
    u.username = "analyst"
    u.role = role
    u.is_superuser = is_superuser
    u.is_active = True
    return u


def make_target(
    created_by_id: uuid.UUID,
    *,
    target_type: TargetType = TargetType.HOST,
    value: str = "10.0.0.1",
    is_active: bool = True,
    target_id: uuid.UUID | None = None,
) -> Target:
    t = MagicMock(spec=Target)
    t.id = target_id or uuid.uuid4()
    t.name = "Test Target"
    t.target_type = target_type
    t.value = value
    t.description = None
    t.scope_notes = None
    t.is_active = is_active
    t.created_by_id = created_by_id
    t.created_at = MagicMock()
    t.updated_at = MagicMock()
    return t


def make_tag(target_id: uuid.UUID, tag: str) -> TargetTag:
    t = MagicMock(spec=TargetTag)
    t.id = uuid.uuid4()
    t.target_id = target_id
    t.tag = tag
    t.created_at = MagicMock()
    return t


def make_service(target: Target | None = None) -> tuple[TargetService, MagicMock, MagicMock]:
    db = AsyncMock()
    svc = TargetService(db=db, settings=make_settings())
    svc._target_repo = AsyncMock()
    svc._audit_repo = AsyncMock()

    if target:
        svc._target_repo.get.return_value = target
        svc._target_repo.get_with_counts.return_value = (target, 0, 0)
        svc._target_repo.get_tags.return_value = []
    else:
        svc._target_repo.get.return_value = None

    svc._audit_repo.create_entry.return_value = MagicMock()
    return svc, svc._target_repo, svc._audit_repo


# ── Tests: Create Target ──────────────────────────────────────────────────────

@pytest.mark.unit
class TestCreateTarget:
    @pytest.mark.asyncio
    async def test_create_host_target(self) -> None:
        """Analyst can create a host target."""
        user = make_user()
        svc, repo, audit = make_service()
        repo.value_exists.return_value = False
        new_target = make_target(user.id, value="10.0.0.1")
        repo.create_from_dict.return_value = new_target
        repo.get_with_counts.return_value = (new_target, 0, 0)
        repo.get_tags.return_value = []

        data = TargetCreate(
            name="Test Host",
            target_type=TargetType.HOST,
            value="10.0.0.1",
        )
        result = await svc.create_target(data=data, current_user=user)

        repo.create_from_dict.assert_called_once()
        audit.create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_value_type_raises_conflict(self) -> None:
        """Creating a target with duplicate value+type raises ConflictError."""
        user = make_user()
        svc, repo, _ = make_service()
        repo.value_exists.return_value = True  # Already exists

        data = TargetCreate(
            name="Duplicate",
            target_type=TargetType.HOST,
            value="10.0.0.1",
        )
        with pytest.raises(ConflictError):
            await svc.create_target(data=data, current_user=user)

    @pytest.mark.asyncio
    async def test_create_target_with_tags(self) -> None:
        """Tags are saved when provided during creation."""
        user = make_user()
        svc, repo, _ = make_service()
        repo.value_exists.return_value = False
        new_target = make_target(user.id)
        repo.create_from_dict.return_value = new_target
        repo.get_with_counts.return_value = (new_target, 0, 0)
        repo.get_tags.return_value = []

        data = TargetCreate(
            name="Tagged Target",
            target_type=TargetType.DOMAIN,
            value="example.com",
            tags=["production", "external"],
        )
        await svc.create_target(data=data, current_user=user)
        repo.replace_tags.assert_called_once_with(
            new_target.id, ["production", "external"]
        )

    @pytest.mark.asyncio
    async def test_invalid_host_value_rejected_by_schema(self) -> None:
        """Invalid host value is caught at schema validation."""
        with pytest.raises(Exception):  # pydantic ValidationError
            TargetCreate(
                name="Bad Host",
                target_type=TargetType.HOST,
                value="224.0.0.1",  # Multicast — invalid
            )

    @pytest.mark.asyncio
    async def test_invalid_cidr_rejected_by_schema(self) -> None:
        """CIDR with /0 prefix rejected at schema level."""
        with pytest.raises(Exception):
            TargetCreate(
                name="Bad Network",
                target_type=TargetType.NETWORK,
                value="0.0.0.0/0",
            )

    @pytest.mark.asyncio
    async def test_invalid_domain_rejected_by_schema(self) -> None:
        """Single-label domain rejected at schema level."""
        with pytest.raises(Exception):
            TargetCreate(
                name="Bad Domain",
                target_type=TargetType.DOMAIN,
                value="localhost",
            )

    @pytest.mark.asyncio
    async def test_invalid_url_rejected_by_schema(self) -> None:
        """URL without scheme rejected at schema level."""
        with pytest.raises(Exception):
            TargetCreate(
                name="Bad URL",
                target_type=TargetType.URL,
                value="example.com",  # Missing https://
            )

    @pytest.mark.asyncio
    async def test_type_value_mismatch_rejected(self) -> None:
        """IP address declared as domain is rejected."""
        with pytest.raises(Exception):
            TargetCreate(
                name="Mismatch",
                target_type=TargetType.DOMAIN,
                value="192.168.1.1",  # IP, not domain
            )


# ── Tests: Access Control ─────────────────────────────────────────────────────

@pytest.mark.unit
class TestTargetAccessControl:
    @pytest.mark.asyncio
    async def test_creator_can_update_target(self) -> None:
        """Target creator can update their own target."""
        user = make_user()
        target = make_target(user.id)
        svc, repo, audit = make_service(target)

        data = TargetUpdate(name="Updated Name")
        await svc.update_target(target.id, data, user)

        audit.create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_creator_cannot_update_target(self) -> None:
        """Non-creator, non-admin cannot update another user's target."""
        owner = make_user()
        other = make_user(role=UserRole.ANALYST)
        target = make_target(owner.id)
        svc, _, _ = make_service(target)

        data = TargetUpdate(name="Should Fail")
        with pytest.raises(PermissionDeniedError):
            await svc.update_target(target.id, data, other)

    @pytest.mark.asyncio
    async def test_admin_can_update_any_target(self) -> None:
        """Platform admin can update any target regardless of creator."""
        owner = make_user()
        admin = make_user(role=UserRole.ADMIN)
        target = make_target(owner.id)
        svc, repo, _ = make_service(target)

        data = TargetUpdate(name="Admin Update")
        await svc.update_target(target.id, data, admin)

    @pytest.mark.asyncio
    async def test_superuser_can_update_any_target(self) -> None:
        """Superuser can update any target."""
        owner = make_user()
        superuser = make_user(is_superuser=True)
        target = make_target(owner.id)
        svc, _, _ = make_service(target)

        data = TargetUpdate(name="Super Update")
        await svc.update_target(target.id, data, superuser)


# ── Tests: Deactivate / Reactivate ───────────────────────────────────────────

@pytest.mark.unit
class TestDeactivateReactivate:
    @pytest.mark.asyncio
    async def test_creator_can_deactivate(self) -> None:
        """Creator can deactivate their target."""
        user = make_user()
        target = make_target(user.id, is_active=True)
        svc, repo, audit = make_service(target)

        data = TargetDeactivate(reason="End of engagement.")
        await svc.deactivate_target(target.id, data, user)

        assert target.is_active is False
        audit.create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_deactivating_inactive_target_raises(self) -> None:
        """Deactivating an already-inactive target raises ValidationError."""
        user = make_user()
        target = make_target(user.id, is_active=False)
        svc, _, _ = make_service(target)

        with pytest.raises(ValidationError):
            await svc.deactivate_target(target.id, TargetDeactivate(), user)

    @pytest.mark.asyncio
    async def test_reactivate_inactive_target(self) -> None:
        """Creator can reactivate an inactive target."""
        user = make_user()
        target = make_target(user.id, is_active=False)
        svc, repo, _ = make_service(target)

        await svc.reactivate_target(target.id, user)
        repo.update_fields.assert_called_once_with(target, is_active=True)

    @pytest.mark.asyncio
    async def test_reactivating_active_target_raises(self) -> None:
        """Reactivating an active target raises ValidationError."""
        user = make_user()
        target = make_target(user.id, is_active=True)
        svc, _, _ = make_service(target)

        with pytest.raises(ValidationError):
            await svc.reactivate_target(target.id, user)


# ── Tests: Tag Management ─────────────────────────────────────────────────────

@pytest.mark.unit
class TestTagManagement:
    @pytest.mark.asyncio
    async def test_add_tag_success(self) -> None:
        """Creator can add a valid tag."""
        user = make_user()
        target = make_target(user.id)
        svc, repo, _ = make_service(target)
        repo.get_tags.return_value = []
        repo.add_tag.return_value = make_tag(target.id, "production")

        await svc.add_tag(target.id, "production", user)
        repo.add_tag.assert_called_once_with(target.id, "production")

    @pytest.mark.asyncio
    async def test_add_tag_normalised_to_lowercase(self) -> None:
        """Tag is normalised to lowercase before being added."""
        user = make_user()
        target = make_target(user.id)
        svc, repo, _ = make_service(target)
        repo.get_tags.return_value = []
        repo.add_tag.return_value = make_tag(target.id, "production")

        await svc.add_tag(target.id, "PRODUCTION", user)
        repo.add_tag.assert_called_once_with(target.id, "production")

    @pytest.mark.asyncio
    async def test_add_invalid_tag_raises(self) -> None:
        """Adding an invalid tag raises ValueError."""
        user = make_user()
        target = make_target(user.id)
        svc, _, _ = make_service(target)

        with pytest.raises(ValueError):
            await svc.add_tag(target.id, "invalid tag!", user)

    @pytest.mark.asyncio
    async def test_add_tag_at_limit_raises_validation_error(self) -> None:
        """Adding a tag when at the 20-tag limit raises ValidationError."""
        user = make_user()
        target = make_target(user.id)
        svc, repo, _ = make_service(target)
        # 20 existing tags
        repo.get_tags.return_value = [
            make_tag(target.id, f"tag{i}") for i in range(20)
        ]

        with pytest.raises(ValidationError, match="maximum of 20"):
            await svc.add_tag(target.id, "new-tag", user)

    @pytest.mark.asyncio
    async def test_remove_existing_tag(self) -> None:
        """Creator can remove an existing tag."""
        user = make_user()
        target = make_target(user.id)
        svc, repo, _ = make_service(target)
        repo.remove_tag.return_value = True

        await svc.remove_tag(target.id, "production", user)
        repo.remove_tag.assert_called_once_with(target.id, "production")

    @pytest.mark.asyncio
    async def test_remove_nonexistent_tag_raises_404(self) -> None:
        """Removing a tag that doesn't exist raises NotFoundError."""
        user = make_user()
        target = make_target(user.id)
        svc, repo, _ = make_service(target)
        repo.remove_tag.return_value = False  # Tag not found

        with pytest.raises(NotFoundError):
            await svc.remove_tag(target.id, "ghost-tag", user)

    @pytest.mark.asyncio
    async def test_replace_tags_bulk(self) -> None:
        """replace_tags replaces the entire tag set."""
        user = make_user()
        target = make_target(user.id)
        svc, repo, audit = make_service(target)
        repo.replace_tags.return_value = []

        data = BulkTagUpdate(tags=["internal", "database", "critical"])
        await svc.replace_tags(target.id, data, user)

        repo.replace_tags.assert_called_once_with(
            target.id, ["internal", "database", "critical"]
        )
        audit.create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_replace_tags_with_empty_clears_all(self) -> None:
        """replace_tags with empty list clears all tags."""
        user = make_user()
        target = make_target(user.id)
        svc, repo, _ = make_service(target)
        repo.replace_tags.return_value = []

        data = BulkTagUpdate(tags=[])
        await svc.replace_tags(target.id, data, user)

        repo.replace_tags.assert_called_once_with(target.id, [])


# ── Tests: Not Found ──────────────────────────────────────────────────────────

@pytest.mark.unit
class TestNotFound:
    @pytest.mark.asyncio
    async def test_get_nonexistent_target_raises_404(self) -> None:
        """Getting a non-existent target raises NotFoundError."""
        user = make_user()
        svc, _, _ = make_service()  # No target

        with pytest.raises(NotFoundError):
            await svc.get_target(uuid.uuid4(), user)

    @pytest.mark.asyncio
    async def test_update_nonexistent_target_raises_404(self) -> None:
        """Updating a non-existent target raises NotFoundError."""
        user = make_user()
        svc, _, _ = make_service()

        with pytest.raises(NotFoundError):
            await svc.update_target(uuid.uuid4(), TargetUpdate(name="X"), user)


# ── Tests: Update Re-validation ───────────────────────────────────────────────

@pytest.mark.unit
class TestUpdateRevalidation:
    def test_update_requires_both_type_and_value(self) -> None:
        """Providing only type or only value in update raises ValidationError."""
        with pytest.raises(Exception):
            TargetUpdate(target_type=TargetType.HOST)  # Missing value

        with pytest.raises(Exception):
            TargetUpdate(value="10.0.0.1")  # Missing type

    def test_update_validates_value_for_type(self) -> None:
        """Updated value is re-validated against updated type."""
        with pytest.raises(Exception):
            TargetUpdate(
                target_type=TargetType.DOMAIN,
                value="192.168.1.1",  # IP address, not domain
            )

    def test_update_type_value_pair_is_valid(self) -> None:
        """Valid type+value pair passes schema validation."""
        data = TargetUpdate(
            target_type=TargetType.NETWORK,
            value="10.0.0.0/16",
        )
        assert data.value == "10.0.0.0/16"
