"""
Unit tests for AuthService.

These tests run without a real database by providing mock repositories.
They test business logic in isolation — the actual SQL is tested in
integration tests.

Markers: ``@pytest.mark.unit``
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import (
    AccountDisabledError,
    AccountLockedError,
    AuthenticationError,
    ConflictError,
    PasswordResetTokenError,
)
from app.core.security import hash_password
from app.models.audit_log import AuditOutcome
from app.models.user import User, UserRole
from app.models.user_session import UserSession
from app.schemas.auth import PasswordResetConfirm
from app.schemas.user import UserCreate
from app.services.auth_service import AuthService


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_settings(**overrides: object) -> MagicMock:
    """Create a mock settings object with sensible test defaults."""
    settings = MagicMock()
    settings.secret_key = "a" * 64
    settings.algorithm = "HS256"
    settings.access_token_expire_minutes = 30
    settings.refresh_token_expire_days = 7
    settings.max_login_attempts = 5
    settings.lockout_duration_minutes = 15
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def make_user(**overrides: object) -> User:
    """Create a mock User ORM instance."""
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "test@vulnforge.io"
    user.username = "testanalyst"
    user.full_name = "Test Analyst"
    user.hashed_password = hash_password("Test!Pass1234")
    user.role = UserRole.ANALYST
    user.is_active = True
    user.is_superuser = False
    user.is_locked = False
    user.locked_until = None
    user.failed_login_attempts = 0
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    user.created_at = datetime.now(tz=timezone.utc)
    user.updated_at = datetime.now(tz=timezone.utc)
    for key, value in overrides.items():
        setattr(user, key, value)
    return user


def make_session(user_id: uuid.UUID, **overrides: object) -> UserSession:
    """Create a mock UserSession ORM instance."""
    session = MagicMock(spec=UserSession)
    session.id = uuid.uuid4()
    session.user_id = user_id
    session.is_revoked = False
    session.expires_at = datetime.now(tz=timezone.utc) + timedelta(days=7)
    session.is_valid = True
    for key, value in overrides.items():
        setattr(session, key, value)
    return session


def make_auth_service(
    *,
    user: User | None = None,
    db_session: MagicMock | None = None,
    settings: MagicMock | None = None,
) -> tuple[AuthService, MagicMock, MagicMock, MagicMock]:
    """Construct an AuthService with fully mocked repositories.

    Returns:
        Tuple of (auth_service, user_repo_mock, session_repo_mock, audit_repo_mock)
    """
    db = db_session or AsyncMock()
    cfg = settings or make_settings()
    svc = AuthService(db=db, settings=cfg)

    # Replace repos with mocks
    svc._user_repo = AsyncMock()
    svc._session_repo = AsyncMock()
    svc._audit_repo = AsyncMock()

    if user is not None:
        svc._user_repo.get_by_email.return_value = user
        svc._user_repo.get.return_value = user
        svc._user_repo.record_successful_login.return_value = user
        svc._user_repo.record_failed_login.return_value = user

    return svc, svc._user_repo, svc._session_repo, svc._audit_repo


# ── Registration Tests ────────────────────────────────────────────────────────

@pytest.mark.unit
class TestRegister:
    """Tests for AuthService.register()."""

    @pytest.mark.asyncio
    async def test_register_success(self) -> None:
        """New user can register with valid credentials."""
        svc, user_repo, session_repo, audit_repo = make_auth_service()
        new_user = make_user()

        user_repo.email_exists.return_value = False
        user_repo.username_exists.return_value = False
        user_repo.create_from_dict.return_value = new_user
        session_repo.create_session.return_value = MagicMock()
        audit_repo.create_entry.return_value = MagicMock()

        data = UserCreate(
            username="newanalyst",
            email="new@vulnforge.io",
            password="Str0ng!P4ssw0rd#",
        )

        result = await svc.register(data=data)

        assert result.user.email == new_user.email
        assert result.tokens.access_token
        assert result.tokens.refresh_token
        user_repo.create_from_dict.assert_called_once()
        audit_repo.create_entry.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_duplicate_email_raises(self) -> None:
        """Registration with duplicate email raises ConflictError."""
        svc, user_repo, _, _ = make_auth_service()
        user_repo.email_exists.return_value = True

        data = UserCreate(
            username="someuser",
            email="taken@vulnforge.io",
            password="Str0ng!P4ssw0rd#",
        )

        with pytest.raises(ConflictError):
            await svc.register(data=data)

    @pytest.mark.asyncio
    async def test_register_duplicate_username_raises(self) -> None:
        """Registration with duplicate username raises ConflictError."""
        svc, user_repo, _, _ = make_auth_service()
        user_repo.email_exists.return_value = False
        user_repo.username_exists.return_value = True

        data = UserCreate(
            username="taken",
            email="unique@vulnforge.io",
            password="Str0ng!P4ssw0rd#",
        )

        with pytest.raises(ConflictError):
            await svc.register(data=data)


# ── Login Tests ────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestLogin:
    """Tests for AuthService.login()."""

    @pytest.mark.asyncio
    async def test_login_success(self) -> None:
        """Valid credentials produce a token pair."""
        user = make_user()
        svc, user_repo, session_repo, audit_repo = make_auth_service(user=user)
        session_repo.create_session.return_value = MagicMock()

        result = await svc.login(email=user.email, password="Test!Pass1234")

        assert result.tokens.access_token
        assert result.tokens.refresh_token
        user_repo.record_successful_login.assert_called_once_with(user)

    @pytest.mark.asyncio
    async def test_login_wrong_password_raises(self) -> None:
        """Wrong password raises AuthenticationError."""
        user = make_user()
        svc, user_repo, _, audit_repo = make_auth_service(user=user)
        user_repo.record_failed_login.return_value = user

        with pytest.raises(AuthenticationError):
            await svc.login(email=user.email, password="WrongPassword123!")

    @pytest.mark.asyncio
    async def test_login_unknown_email_raises(self) -> None:
        """Unknown email raises AuthenticationError (same error as wrong password)."""
        svc, user_repo, _, _ = make_auth_service()
        user_repo.get_by_email.return_value = None

        with pytest.raises(AuthenticationError):
            await svc.login(email="nobody@vulnforge.io", password="Any!Pass1234")

    @pytest.mark.asyncio
    async def test_login_disabled_account_raises(self) -> None:
        """Disabled account raises AccountDisabledError before password check."""
        user = make_user(is_active=False)
        svc, user_repo, _, _ = make_auth_service(user=user)

        with pytest.raises(AccountDisabledError):
            await svc.login(email=user.email, password="Test!Pass1234")

    @pytest.mark.asyncio
    async def test_login_locked_account_raises(self) -> None:
        """Locked account raises AccountLockedError."""
        user = make_user(
            is_locked=True,
            locked_until=datetime.now(tz=timezone.utc) + timedelta(minutes=10),
        )
        svc, user_repo, _, _ = make_auth_service(user=user)

        with pytest.raises(AccountLockedError):
            await svc.login(email=user.email, password="Test!Pass1234")


# ── Token Refresh Tests ────────────────────────────────────────────────────────

@pytest.mark.unit
class TestRefreshTokens:
    """Tests for AuthService.refresh_tokens()."""

    @pytest.mark.asyncio
    async def test_refresh_success_rotates_token(self) -> None:
        """Valid refresh token produces new token pair and revokes old."""
        user = make_user()
        svc, user_repo, session_repo, audit_repo = make_auth_service(user=user)

        old_session = make_session(user_id=user.id)
        session_repo.get_by_token_hash.return_value = old_session
        session_repo.revoke_session.return_value = old_session
        session_repo.create_session.return_value = MagicMock()

        result = await svc.refresh_tokens(raw_refresh_token="a" * 43)

        assert result.access_token
        assert result.refresh_token
        session_repo.revoke_session.assert_called_once_with(old_session)
        session_repo.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_invalid_token_raises(self) -> None:
        """Non-existent or revoked token raises InvalidTokenError."""
        from app.core.exceptions import InvalidTokenError

        svc, _, session_repo, _ = make_auth_service()
        session_repo.get_by_token_hash.return_value = None

        with pytest.raises(InvalidTokenError):
            await svc.refresh_tokens(raw_refresh_token="bogus_token_string_here_pad")


# ── Logout Tests ───────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestLogout:
    """Tests for AuthService.logout() and logout_all()."""

    @pytest.mark.asyncio
    async def test_logout_revokes_session(self) -> None:
        """Logout revokes the specific session matching the token."""
        user = make_user()
        svc, _, session_repo, audit_repo = make_auth_service(user=user)

        session = make_session(user_id=user.id)
        session_repo.get_by_token_hash.return_value = session
        session_repo.revoke_session.return_value = session

        await svc.logout(user_id=user.id, raw_refresh_token="a" * 43)

        session_repo.revoke_session.assert_called_once_with(session)

    @pytest.mark.asyncio
    async def test_logout_all_revokes_all_sessions(self) -> None:
        """Logout all revokes every active session for the user."""
        user = make_user()
        svc, _, session_repo, audit_repo = make_auth_service(user=user)
        session_repo.revoke_all_user_sessions.return_value = 3

        count = await svc.logout_all(user_id=user.id)

        assert count == 3
        session_repo.revoke_all_user_sessions.assert_called_once_with(user.id)


# ── Password Reset Tests ───────────────────────────────────────────────────────

@pytest.mark.unit
class TestPasswordReset:
    """Tests for AuthService password reset flow."""

    @pytest.mark.asyncio
    async def test_request_reset_returns_token_for_existing_user(self) -> None:
        """Reset request returns a raw token for a valid email."""
        user = make_user()
        svc, user_repo, _, audit_repo = make_auth_service(user=user)
        user_repo.set_password_reset_token.return_value = user

        token = await svc.request_password_reset(email=user.email)

        assert token is not None
        assert len(token) > 10
        user_repo.set_password_reset_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_reset_returns_none_for_unknown_email(self) -> None:
        """Reset request returns None for non-existent email (no enumeration)."""
        svc, user_repo, _, _ = make_auth_service()
        user_repo.get_by_email.return_value = None

        token = await svc.request_password_reset(email="nobody@example.com")

        assert token is None

    @pytest.mark.asyncio
    async def test_confirm_reset_updates_password_and_revokes_sessions(self) -> None:
        """Successful reset updates hash and revokes all sessions."""
        from app.core.security import generate_password_reset_token, sha256_hash

        user = make_user()
        raw_token = generate_password_reset_token()
        user.password_reset_token_hash = sha256_hash(raw_token)
        user.password_reset_expires_at = datetime.now(tz=timezone.utc) + timedelta(
            minutes=10
        )

        svc, user_repo, session_repo, audit_repo = make_auth_service()
        user_repo.get_by_password_reset_token_hash.return_value = user
        user_repo.complete_password_reset.return_value = user
        session_repo.revoke_all_user_sessions.return_value = 2

        data = PasswordResetConfirm(token=raw_token, new_password="NewStr0ng!Pass#")
        await svc.confirm_password_reset(data=data)

        user_repo.complete_password_reset.assert_called_once()
        session_repo.revoke_all_user_sessions.assert_called_once_with(user.id)

    @pytest.mark.asyncio
    async def test_confirm_reset_expired_token_raises(self) -> None:
        """Expired reset token raises PasswordResetTokenError."""
        from app.core.security import generate_password_reset_token, sha256_hash

        user = make_user()
        raw_token = generate_password_reset_token()
        user.password_reset_token_hash = sha256_hash(raw_token)
        # Token expired 1 minute ago
        user.password_reset_expires_at = datetime.now(tz=timezone.utc) - timedelta(
            minutes=1
        )

        svc, user_repo, _, _ = make_auth_service()
        user_repo.get_by_password_reset_token_hash.return_value = user

        data = PasswordResetConfirm(token=raw_token, new_password="NewStr0ng!Pass#")

        with pytest.raises(PasswordResetTokenError):
            await svc.confirm_password_reset(data=data)
