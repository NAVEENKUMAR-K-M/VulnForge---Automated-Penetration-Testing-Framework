"""
User repository — data access layer for the ``users`` table.

Only this repository (and ``UserSessionRepository``) may issue queries
against user-related tables.  All service-layer code goes through these
methods — no raw SQLAlchemy in services.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User, dict, dict]):
    """Repository for User CRUD and auth-specific queries.

    Inherits standard CRUD from ``BaseRepository``.  All custom query
    methods specific to the ``users`` table are defined here.
    """

    model = User

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ── Lookup Methods ────────────────────────────────────────────────────────

    async def get_by_email(self, email: str) -> User | None:
        """Find a user by email address (case-insensitive).

        Args:
            email: The email address to search for.

        Returns:
            User | None: The matching user, or None.
        """
        stmt = select(User).where(
            User.email == email.lower().strip()
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Find a user by username (case-insensitive).

        Args:
            username: The username to search for.

        Returns:
            User | None: The matching user, or None.
        """
        stmt = select(User).where(
            User.username == username.lower().strip()
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Check whether a user with the given email already exists.

        Args:
            email: The email to check.

        Returns:
            bool: True if a user with this email exists.
        """
        return await self.get_by_email(email) is not None

    async def username_exists(self, username: str) -> bool:
        """Check whether a user with the given username already exists.

        Args:
            username: The username to check.

        Returns:
            bool: True if a user with this username exists.
        """
        return await self.get_by_username(username) is not None

    # ── Auth-Specific Updates ────────────────────────────────────────────────

    async def record_successful_login(self, user: User) -> User:
        """Update login metadata after a successful authentication.

        Resets ``failed_login_attempts`` to 0, clears any lockout, and
        sets ``last_login_at`` to the current UTC time.

        Args:
            user: The authenticated user.

        Returns:
            User: The updated user record.
        """
        return await self.update_fields(
            user,
            failed_login_attempts=0,
            locked_until=None,
            last_login_at=datetime.now(tz=timezone.utc),
        )

    async def record_failed_login(
        self,
        user: User,
        max_attempts: int,
        lockout_duration_minutes: int,
    ) -> User:
        """Increment the failed login counter and lock the account if needed.

        If ``failed_login_attempts + 1 >= max_attempts``, the account is
        locked until ``now + lockout_duration_minutes``.

        Args:
            user:                     The user who failed to authenticate.
            max_attempts:             Threshold before lockout triggers.
            lockout_duration_minutes: How long to lock the account.

        Returns:
            User: The updated user record.
        """
        new_attempts = user.failed_login_attempts + 1
        locked_until: datetime | None = None

        if new_attempts >= max_attempts:
            locked_until = datetime.now(tz=timezone.utc) + timedelta(
                minutes=lockout_duration_minutes
            )

        return await self.update_fields(
            user,
            failed_login_attempts=new_attempts,
            locked_until=locked_until,
        )

    async def set_password_reset_token(
        self,
        user: User,
        token_hash: str,
        expiry_minutes: int,
    ) -> User:
        """Store a password reset token hash and expiry on the user record.

        Args:
            user:           The user requesting a password reset.
            token_hash:     SHA-256 hex digest of the raw reset token.
            expiry_minutes: Minutes until the token expires.

        Returns:
            User: The updated user record.
        """
        expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=expiry_minutes)
        return await self.update_fields(
            user,
            password_reset_token_hash=token_hash,
            password_reset_expires_at=expires_at,
        )

    async def get_by_password_reset_token_hash(self, token_hash: str) -> User | None:
        """Find a user by their active password reset token hash.

        Args:
            token_hash: SHA-256 hex digest of the raw reset token.

        Returns:
            User | None: The user with this active reset token, or None.
        """
        stmt = select(User).where(
            User.password_reset_token_hash == token_hash
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def complete_password_reset(
        self,
        user: User,
        new_hashed_password: str,
    ) -> User:
        """Apply a new password hash and clear the reset token fields.

        Args:
            user:                The user completing the reset.
            new_hashed_password: bcrypt hash of the new password.

        Returns:
            User: The updated user record.
        """
        return await self.update_fields(
            user,
            hashed_password=new_hashed_password,
            password_reset_token_hash=None,
            password_reset_expires_at=None,
            failed_login_attempts=0,
            locked_until=None,
        )

    # ── Admin Operations ──────────────────────────────────────────────────────

    async def get_active_users(
        self,
        offset: int = 0,
        limit: int = 20,
    ) -> list[User]:
        """Return a paginated list of active (non-disabled) users.

        Args:
            offset: Pagination offset.
            limit:  Maximum number of users to return.

        Returns:
            list[User]: Active user records.
        """
        stmt = (
            select(User)
            .where(User.is_active.is_(True))
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def superuser_exists(self) -> bool:
        """Check whether any superuser account exists.

        Used during startup seeding to avoid creating duplicate superusers.

        Returns:
            bool: True if at least one superuser exists.
        """
        stmt = select(User).where(User.is_superuser.is_(True)).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
