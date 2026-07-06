"""
UserSession repository — data access for the ``user_sessions`` table.

Handles refresh token lifecycle: creation, validation lookup, revocation,
and cleanup of expired sessions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_session import UserSession
from app.repositories.base import BaseRepository


class UserSessionRepository(BaseRepository[UserSession, dict, dict]):
    """Repository for refresh token session management.

    All refresh token DB operations are isolated here — nothing in the
    application should call session-related SQL directly.
    """

    model = UserSession

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        """Find an active session by refresh token hash.

        Only returns sessions that are not revoked and not expired.

        Args:
            token_hash: SHA-256 hex digest of the raw refresh token.

        Returns:
            UserSession | None: The active session, or None.
        """
        now = datetime.now(tz=timezone.utc)
        stmt = select(UserSession).where(
            and_(
                UserSession.refresh_token_hash == token_hash,
                UserSession.is_revoked.is_(False),
                UserSession.expires_at > now,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_session(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UserSession:
        """Create a new refresh token session.

        Args:
            user_id:     The owning user's UUID.
            token_hash:  SHA-256 hex digest of the raw refresh token.
            expires_at:  UTC expiry timestamp of this session.
            ip_address:  Client IP at the time of issuance.
            user_agent:  Client User-Agent string.

        Returns:
            UserSession: The newly created session record.
        """
        return await self.create_from_dict(
            {
                "user_id": user_id,
                "refresh_token_hash": token_hash,
                "expires_at": expires_at,
                "is_revoked": False,
                "ip_address": ip_address,
                "user_agent": user_agent,
            }
        )

    async def revoke_session(self, session: UserSession) -> UserSession:
        """Mark a single session as revoked.

        Args:
            session: The session to revoke.

        Returns:
            UserSession: The updated (revoked) session.
        """
        return await self.update_fields(session, is_revoked=True)

    async def revoke_all_user_sessions(self, user_id: uuid.UUID) -> int:
        """Revoke ALL active sessions for a given user.

        Used for logout-all-devices and post-password-reset invalidation.

        Args:
            user_id: The user whose sessions should be revoked.

        Returns:
            int: Number of sessions revoked.
        """
        stmt = (
            update(UserSession)
            .where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_revoked.is_(False),
                )
            )
            .values(is_revoked=True)
        )
        result = await self._session.execute(stmt)
        return result.rowcount  # type: ignore[return-value]

    async def get_active_sessions_for_user(
        self, user_id: uuid.UUID
    ) -> list[UserSession]:
        """Return all non-revoked, non-expired sessions for a user.

        Args:
            user_id: The user whose active sessions to retrieve.

        Returns:
            list[UserSession]: Active session records.
        """
        now = datetime.now(tz=timezone.utc)
        stmt = select(UserSession).where(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_revoked.is_(False),
                UserSession.expires_at > now,
            )
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_expired_sessions(self) -> int:
        """Delete sessions that have passed their expiry time.

        Intended to be called periodically by a Celery beat task to keep
        the ``user_sessions`` table from growing indefinitely.

        Returns:
            int: Number of sessions deleted.
        """
        from sqlalchemy import delete as sql_delete

        now = datetime.now(tz=timezone.utc)
        stmt = sql_delete(UserSession).where(UserSession.expires_at < now)
        result = await self._session.execute(stmt)
        return result.rowcount  # type: ignore[return-value]
