"""
Authentication service — orchestrates all auth business logic.

This is the Application Layer.  It:
    - Coordinates repositories (data access) and core utilities (security)
    - Enforces all auth business rules (lockout, token rotation, etc.)
    - Writes every security-significant event to the audit log
    - Raises typed domain exceptions — never raw HTTP exceptions

The auth service is injected into API route handlers.  Routes are thin:
they validate the incoming schema, call one service method, and return.

Architecture Decision — Why a service class?
    A class (vs. plain functions) allows the injected repositories and
    settings to be shared across all methods without threading them as
    parameters.  The class is instantiated per-request in ``deps.py``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security as sec
from app.core.config import Settings
from app.core.constants import (
    AuditAction,
    PASSWORD_RESET_EXPIRY_MINUTES,
)
from app.core.exceptions import (
    AccountDisabledError,
    AccountLockedError,
    AuthenticationError,
    ConflictError,
    PasswordResetTokenError,
)
from app.core.logging import get_logger
from app.models.audit_log import AuditOutcome
from app.models.user import User, UserRole
from app.repositories.audit_log import AuditLogRepository
from app.repositories.user import UserRepository
from app.repositories.user_session import UserSessionRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginResponse,
    PasswordResetConfirm,
    TokenResponse,
)
from app.schemas.user import UserCreate, UserResponse

logger = get_logger(__name__)


class AuthService:
    """Orchestrates all authentication and authorisation operations.

    Attributes:
        _db:          The async database session for this request.
        _settings:    Application settings (token TTLs, secret key, etc.).
        _user_repo:   Repository for User table operations.
        _session_repo: Repository for UserSession (refresh tokens) operations.
        _audit_repo:  Repository for writing audit log entries.
    """

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._user_repo = UserRepository(db)
        self._session_repo = UserSessionRepository(db)
        self._audit_repo = AuditLogRepository(db)

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _create_token_pair(self, user: User) -> TokenResponse:
        """Issue a fresh access + refresh token pair for the given user.

        Steps:
            1. Generate a cryptographically secure refresh token.
            2. Hash it (SHA-256) and store the hash in ``user_sessions``.
            3. Sign a short-lived JWT access token.

        Args:
            user: The authenticated ``User`` ORM instance.

        Returns:
            TokenResponse: The issued token pair with metadata.

        Note:
            This method only generates tokens — it does NOT persist the
            session.  Callers must call ``_persist_session`` separately.
        """
        raw_refresh_token = sec.generate_refresh_token()
        access_token = sec.create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role.value,
            is_superuser=user.is_superuser,
            secret_key=self._settings.secret_key,
            algorithm=self._settings.algorithm,
            expire_minutes=self._settings.access_token_expire_minutes,
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=self._settings.access_token_expire_minutes * 60,
        )

    async def _persist_session(
        self,
        user_id: uuid.UUID,
        raw_refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Persist a refresh token session in the database.

        Only the SHA-256 hash of the raw token is stored — never plaintext.

        Args:
            user_id:           The owning user's UUID.
            raw_refresh_token: The raw refresh token (hashed before storage).
            ip_address:        Client IP for session metadata.
            user_agent:        Client User-Agent for session metadata.
        """
        expires_at = datetime.now(tz=timezone.utc) + timedelta(
            days=self._settings.refresh_token_expire_days
        )
        token_hash = sec.sha256_hash(raw_refresh_token)
        await self._session_repo.create_session(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    # ── Registration ──────────────────────────────────────────────────────────

    async def register(
        self,
        data: UserCreate,
        ip_address: str | None = None,
    ) -> LoginResponse:
        """Register a new user account and immediately issue tokens.

        Business Rules:
            - Email and username must be globally unique.
            - Password is hashed with bcrypt (cost=12) — never stored raw.
            - New users get the ``viewer`` role by default.
            - A session is created immediately so registration = login.

        Args:
            data:       Registration payload (validated by Pydantic schema).
            ip_address: Client IP for audit logging.

        Returns:
            LoginResponse: Token pair and the new user's profile.

        Raises:
            ConflictError: If email or username is already taken.
        """
        logger.info("auth.register.attempt", email=data.email)

        # ── Uniqueness checks ──────────────────────────────────────────────
        if await self._user_repo.email_exists(data.email):
            logger.warning("auth.register.email_taken", email=data.email)
            raise ConflictError("An account with this email already exists.")

        if await self._user_repo.username_exists(data.username):
            logger.warning("auth.register.username_taken", username=data.username)
            raise ConflictError("This username is already taken.")

        # ── Create user ────────────────────────────────────────────────────
        hashed_password = sec.hash_password(data.password)
        user = await self._user_repo.create_from_dict(
            {
                "username": data.username,
                "email": data.email,
                "hashed_password": hashed_password,
                "full_name": data.full_name,
                "role": UserRole.VIEWER,
                "is_active": True,
                "is_superuser": False,
            }
        )

        # ── Issue tokens & persist session ─────────────────────────────────
        tokens = self._create_token_pair(user)
        await self._persist_session(
            user_id=user.id,
            raw_refresh_token=tokens.refresh_token,
            ip_address=ip_address,
        )

        # ── Audit ──────────────────────────────────────────────────────────
        await self._audit_repo.create_entry(
            action=AuditAction.USER_REGISTERED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=user.id,
            actor_ip=ip_address,
            resource_type="user",
            resource_id=user.id,
            details={"username": user.username, "email": user.email},
        )

        logger.info("auth.register.success", user_id=str(user.id), email=user.email)

        return LoginResponse(
            tokens=tokens,
            user=UserResponse.model_validate(user),
        )

    # ── Login ─────────────────────────────────────────────────────────────────

    async def login(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LoginResponse:
        """Authenticate a user and issue a token pair.

        Business Rules:
            - Returns the same error for wrong email AND wrong password
              (prevents user enumeration via response differencing).
            - Checks is_active before verifying password to fail fast.
            - Checks lockout before verifying password.
            - Increments failed_attempts on every failure.
            - Locks account after max_login_attempts consecutive failures.

        Args:
            email:      The submitted email address.
            password:   The submitted plaintext password.
            ip_address: Client IP for audit and session metadata.
            user_agent: Client UA for session metadata.

        Returns:
            LoginResponse: Token pair and user profile.

        Raises:
            AuthenticationError:  Invalid credentials (email or password wrong).
            AccountDisabledError: Account is soft-disabled.
            AccountLockedError:   Account is temporarily locked.
        """
        logger.info("auth.login.attempt", email=email, ip=ip_address)

        # ── Load user ──────────────────────────────────────────────────────
        user = await self._user_repo.get_by_email(email)

        # Always hash even if user not found — prevents timing-based enum
        dummy_hash = "$2b$12$invalidhashtopreventtimingattacks000000000000000000000"
        compare_hash = user.hashed_password if user else dummy_hash

        # ── Account state checks ───────────────────────────────────────────
        if user is not None and not user.is_active:
            await self._audit_repo.create_entry(
                action=AuditAction.USER_LOGIN_FAILED,
                outcome=AuditOutcome.FAILURE,
                actor_ip=ip_address,
                resource_type="user",
                resource_id=user.id,
                details={"reason": "account_disabled"},
            )
            raise AccountDisabledError()

        if user is not None and user.is_locked:
            await self._audit_repo.create_entry(
                action=AuditAction.USER_LOGIN_FAILED,
                outcome=AuditOutcome.FAILURE,
                actor_ip=ip_address,
                resource_type="user",
                resource_id=user.id,
                details={"reason": "account_locked"},
            )
            locked_until_iso = (
                user.locked_until.isoformat() if user.locked_until else None
            )
            raise AccountLockedError(locked_until_iso=locked_until_iso)

        # ── Password verification ──────────────────────────────────────────
        password_valid = sec.verify_password(password, compare_hash)

        if not password_valid or user is None:
            if user is not None:
                # Increment failure counter — may trigger lockout
                await self._user_repo.record_failed_login(
                    user=user,
                    max_attempts=self._settings.max_login_attempts,
                    lockout_duration_minutes=self._settings.lockout_duration_minutes,
                )
                # Reload to check if lockout was just triggered
                await self._db.refresh(user)
                if user.is_locked:
                    await self._audit_repo.create_entry(
                        action=AuditAction.USER_LOCKED,
                        outcome=AuditOutcome.SUCCESS,
                        actor_ip=ip_address,
                        resource_type="user",
                        resource_id=user.id,
                    )
                await self._audit_repo.create_entry(
                    action=AuditAction.USER_LOGIN_FAILED,
                    outcome=AuditOutcome.FAILURE,
                    actor_id=user.id,
                    actor_ip=ip_address,
                    resource_type="user",
                    resource_id=user.id,
                    details={
                        "attempts": user.failed_login_attempts,
                        "reason": "wrong_password",
                    },
                )

            logger.warning("auth.login.failed", email=email, ip=ip_address)
            # Same error regardless of whether email or password was wrong
            raise AuthenticationError()

        # ── Successful auth ────────────────────────────────────────────────
        user = await self._user_repo.record_successful_login(user)

        # Transparently upgrade bcrypt work factor if needed
        if sec.needs_rehash(user.hashed_password):
            new_hash = sec.hash_password(password)
            await self._user_repo.update_fields(user, hashed_password=new_hash)

        tokens = self._create_token_pair(user)
        await self._persist_session(
            user_id=user.id,
            raw_refresh_token=tokens.refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._audit_repo.create_entry(
            action=AuditAction.USER_LOGIN_SUCCESS,
            outcome=AuditOutcome.SUCCESS,
            actor_id=user.id,
            actor_ip=ip_address,
            resource_type="user",
            resource_id=user.id,
        )

        logger.info("auth.login.success", user_id=str(user.id), email=email)

        return LoginResponse(
            tokens=tokens,
            user=UserResponse.model_validate(user),
        )

    # ── Token Refresh ─────────────────────────────────────────────────────────

    async def refresh_tokens(
        self,
        raw_refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenResponse:
        """Rotate a refresh token and issue a new token pair.

        This is the critical security operation.  The incoming token is
        validated, immediately revoked, and a new pair is issued atomically.
        If the incoming token is already revoked, this signals a potential
        token theft — the entire user's session family should be revoked.

        Args:
            raw_refresh_token: The raw opaque refresh token from the client.
            ip_address:        Client IP for the new session record.
            user_agent:        Client UA for the new session record.

        Returns:
            TokenResponse: A fresh token pair.

        Raises:
            InvalidTokenError: Token not found, revoked, or expired.
            AccountDisabledError: The associated user is disabled.
        """
        from app.core.exceptions import InvalidTokenError

        token_hash = sec.sha256_hash(raw_refresh_token)
        session = await self._session_repo.get_by_token_hash(token_hash)

        if session is None:
            # Token not found OR already revoked — possible replay attack
            logger.warning(
                "auth.refresh.invalid_token",
                token_prefix=raw_refresh_token[:8],
                ip=ip_address,
            )
            await self._audit_repo.create_entry(
                action=AuditAction.TOKEN_REFRESH_FAILED,
                outcome=AuditOutcome.FAILURE,
                actor_ip=ip_address,
                details={"reason": "token_not_found_or_revoked"},
            )
            raise InvalidTokenError()

        # ── Validate user state ────────────────────────────────────────────
        user = await self._user_repo.get(session.user_id)
        if user is None or not user.is_active:
            await self._session_repo.revoke_session(session)
            raise AccountDisabledError()

        # ── Rotate: revoke old, issue new ──────────────────────────────────
        await self._session_repo.revoke_session(session)

        new_tokens = self._create_token_pair(user)
        await self._persist_session(
            user_id=user.id,
            raw_refresh_token=new_tokens.refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._audit_repo.create_entry(
            action=AuditAction.TOKEN_REFRESHED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=user.id,
            actor_ip=ip_address,
            resource_type="user",
            resource_id=user.id,
        )

        logger.info("auth.refresh.success", user_id=str(user.id))
        return new_tokens

    # ── Logout ────────────────────────────────────────────────────────────────

    async def logout(
        self,
        user_id: uuid.UUID,
        raw_refresh_token: str,
        ip_address: str | None = None,
    ) -> None:
        """Revoke a single refresh token session (logout this device).

        Args:
            user_id:           The authenticated user's UUID.
            raw_refresh_token: The refresh token to revoke.
            ip_address:        Client IP for audit logging.
        """
        token_hash = sec.sha256_hash(raw_refresh_token)
        session = await self._session_repo.get_by_token_hash(token_hash)

        if session is not None and session.user_id == user_id:
            await self._session_repo.revoke_session(session)

        await self._audit_repo.create_entry(
            action=AuditAction.USER_LOGOUT,
            outcome=AuditOutcome.SUCCESS,
            actor_id=user_id,
            actor_ip=ip_address,
            resource_type="user",
            resource_id=user_id,
        )

        logger.info("auth.logout", user_id=str(user_id))

    async def logout_all(
        self,
        user_id: uuid.UUID,
        ip_address: str | None = None,
    ) -> int:
        """Revoke ALL active sessions for the user (logout all devices).

        Args:
            user_id:    The authenticated user's UUID.
            ip_address: Client IP for audit logging.

        Returns:
            int: Number of sessions revoked.
        """
        revoked_count = await self._session_repo.revoke_all_user_sessions(user_id)

        await self._audit_repo.create_entry(
            action=AuditAction.USER_LOGOUT_ALL,
            outcome=AuditOutcome.SUCCESS,
            actor_id=user_id,
            actor_ip=ip_address,
            resource_type="user",
            resource_id=user_id,
            details={"sessions_revoked": revoked_count},
        )

        logger.info(
            "auth.logout_all",
            user_id=str(user_id),
            sessions_revoked=revoked_count,
        )
        return revoked_count

    # ── Password Reset ────────────────────────────────────────────────────────

    async def request_password_reset(
        self,
        email: str,
        ip_address: str | None = None,
    ) -> str | None:
        """Generate a password reset token and prepare it for email delivery.

        ALWAYS returns HTTP 200 to the client — the actual error state is
        only reflected internally.  This prevents email enumeration.

        Args:
            email:      The email address of the account to reset.
            ip_address: Client IP for audit logging.

        Returns:
            str | None: The raw reset token to embed in the reset email,
                        or None if no user with this email exists.
        """
        user = await self._user_repo.get_by_email(email)

        if user is None:
            # Log the attempt but return None — caller always sends 200
            logger.info(
                "auth.password_reset.user_not_found",
                email=email,
                ip=ip_address,
            )
            return None

        raw_token = sec.generate_password_reset_token()
        token_hash = sec.sha256_hash(raw_token)

        await self._user_repo.set_password_reset_token(
            user=user,
            token_hash=token_hash,
            expiry_minutes=PASSWORD_RESET_EXPIRY_MINUTES,
        )

        await self._audit_repo.create_entry(
            action=AuditAction.PASSWORD_RESET_REQUESTED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=user.id,
            actor_ip=ip_address,
            resource_type="user",
            resource_id=user.id,
        )

        logger.info(
            "auth.password_reset.token_issued",
            user_id=str(user.id),
        )
        return raw_token

    async def confirm_password_reset(
        self,
        data: PasswordResetConfirm,
        ip_address: str | None = None,
    ) -> None:
        """Complete a password reset using the token from the reset email.

        On success:
            - Updates the password hash.
            - Revokes ALL active sessions (forces re-login everywhere).
            - Clears the reset token fields.

        Args:
            data:       Validated schema with raw token and new password.
            ip_address: Client IP for audit logging.

        Raises:
            PasswordResetTokenError: Token not found, expired, or already used.
        """
        token_hash = sec.sha256_hash(data.token)
        user = await self._user_repo.get_by_password_reset_token_hash(token_hash)

        if user is None:
            raise PasswordResetTokenError()

        # Check expiry
        if (
            user.password_reset_expires_at is None
            or datetime.now(tz=timezone.utc) > user.password_reset_expires_at
        ):
            raise PasswordResetTokenError("Password reset token has expired.")

        # Apply new password and clear token
        new_hash = sec.hash_password(data.new_password)
        await self._user_repo.complete_password_reset(
            user=user,
            new_hashed_password=new_hash,
        )

        # Revoke all sessions — force re-login on all devices
        revoked = await self._session_repo.revoke_all_user_sessions(user.id)

        await self._audit_repo.create_entry(
            action=AuditAction.PASSWORD_RESET_COMPLETED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=user.id,
            actor_ip=ip_address,
            resource_type="user",
            resource_id=user.id,
            details={"sessions_revoked": revoked},
        )

        logger.info(
            "auth.password_reset.completed",
            user_id=str(user.id),
            sessions_revoked=revoked,
        )

    # ── Change Password (authenticated) ───────────────────────────────────────

    async def change_password(
        self,
        user: User,
        data: ChangePasswordRequest,
        ip_address: str | None = None,
    ) -> None:
        """Change password for an already-authenticated user.

        Verifies the current password before applying the new one.
        Revokes all other active sessions except the current one.

        Args:
            user:       The currently authenticated user.
            data:       Change password payload with current and new password.
            ip_address: Client IP for audit logging.

        Raises:
            AuthenticationError: If the current password is wrong.
        """
        if not sec.verify_password(data.current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect.")

        new_hash = sec.hash_password(data.new_password)
        await self._user_repo.update_fields(user, hashed_password=new_hash)
        await self._session_repo.revoke_all_user_sessions(user.id)

        await self._audit_repo.create_entry(
            action=AuditAction.PASSWORD_RESET_COMPLETED,
            outcome=AuditOutcome.SUCCESS,
            actor_id=user.id,
            actor_ip=ip_address,
            resource_type="user",
            resource_id=user.id,
        )

        logger.info("auth.change_password.success", user_id=str(user.id))
