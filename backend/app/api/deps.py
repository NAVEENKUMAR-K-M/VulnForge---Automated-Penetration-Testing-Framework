"""
FastAPI dependency injection for VulnForge.

All reusable dependencies live here:
    - Database session injection
    - Settings injection
    - Service factory dependencies
    - JWT token extraction and validation
    - Current user resolution
    - Role-based access control (RBAC) factory

Design:
    Dependencies form a chain — each depends on simpler ones.
    ``require_role(UserRole.ADMIN)`` is a dependency factory that returns
    a FastAPI dependency, keeping RBAC declarative at the route level.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core import security as sec
from app.core.constants import ROLE_HIERARCHY
from app.core.exceptions import (
    AccountDisabledError,
    InvalidTokenError,
    PermissionDeniedError,
)
from app.core.logging import get_logger
from app.database.session import get_db
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.services.auth_service import AuthService

logger = get_logger(__name__)

# ── Scheme ────────────────────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(
    scheme_name="JWT",
    description="JWT Bearer token. Obtain via POST /api/v1/auth/login.",
    auto_error=False,  # We raise our own typed exceptions, not generic 403
)


# ── Simple Dependencies ───────────────────────────────────────────────────────

async def get_settings_dep() -> Settings:
    """Provide the cached Settings singleton.

    Returns:
        Settings: The application settings.
    """
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
DatabaseDep = Annotated[AsyncSession, Depends(get_db)]


# ── Service Factory Dependencies ──────────────────────────────────────────────

async def get_auth_service(
    db: DatabaseDep,
    settings: SettingsDep,
) -> AuthService:
    """Construct and return an ``AuthService`` for the current request.

    Args:
        db:       Injected async database session.
        settings: Injected application settings.

    Returns:
        AuthService: A service instance scoped to this request.
    """
    return AuthService(db=db, settings=settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


# ── Token Extraction & Validation ─────────────────────────────────────────────

async def get_raw_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> str:
    """Extract the raw JWT string from the Authorization header.

    Args:
        credentials: Parsed Bearer credentials from the Authorization header.

    Returns:
        str: The raw JWT string.

    Raises:
        InvalidTokenError: If no Bearer token is present.
    """
    if credentials is None or not credentials.credentials:
        raise InvalidTokenError("No authentication token provided.")
    return credentials.credentials


async def get_token_payload(
    token: Annotated[str, Depends(get_raw_token)],
    settings: SettingsDep,
) -> dict:
    """Verify and decode the JWT access token.

    Args:
        token:    Raw JWT string from Authorization header.
        settings: Settings providing secret key and algorithm.

    Returns:
        dict: Decoded JWT payload.

    Raises:
        TokenExpiredError:  Access token has expired.
        InvalidTokenError:  Signature invalid or type mismatch.
    """
    return sec.verify_access_token(
        token,
        secret_key=settings.secret_key,
        algorithm=settings.algorithm,
    )


TokenPayloadDep = Annotated[dict, Depends(get_token_payload)]


# ── Current User Dependencies ─────────────────────────────────────────────────

async def get_current_user(
    payload: TokenPayloadDep,
    db: DatabaseDep,
) -> User:
    """Resolve the authenticated user from the JWT payload.

    Loads the full User record from the database using the ``sub`` claim.
    This ensures the user's current DB state (active, role) is always
    reflected — stale JWT claims cannot grant access to a disabled account.

    Args:
        payload: Decoded JWT payload.
        db:      Async database session.

    Returns:
        User: The authenticated User ORM instance.

    Raises:
        InvalidTokenError:   Token subject is missing or not a valid UUID.
        AccountDisabledError: The user account has been disabled.
    """
    user_id = sec.extract_user_id_from_token(payload)
    user_repo = UserRepository(db)
    user = await user_repo.get(user_id)

    if user is None:
        raise InvalidTokenError("User associated with token no longer exists.")

    if not user.is_active:
        raise AccountDisabledError()

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the current authenticated, active user.

    This is the standard dependency for any protected endpoint.
    Equivalent to ``get_current_user`` but aliased for clarity.

    Args:
        current_user: Resolved from ``get_current_user``.

    Returns:
        User: The active authenticated user.
    """
    return current_user


CurrentUserDep = Annotated[User, Depends(get_current_active_user)]


# ── RBAC Factory ──────────────────────────────────────────────────────────────

def require_role(minimum_role: UserRole):
    """Dependency factory enforcing a minimum role requirement.

    Usage:
        @router.delete("/users/{id}")
        async def delete_user(
            user: User = Depends(require_role(UserRole.ADMIN))
        ):
            ...

    Superusers bypass all role checks.

    Args:
        minimum_role: The minimum ``UserRole`` required to access the endpoint.

    Returns:
        Callable: A FastAPI dependency that resolves to the current User
                  if they have sufficient privileges.
    """

    async def _check_role(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        """Inner dependency that validates role hierarchy.

        Args:
            current_user: The resolved authenticated user.

        Returns:
            User: The current user if role check passes.

        Raises:
            PermissionDeniedError: If user's role is below the minimum required.
        """
        if current_user.is_superuser:
            return current_user

        user_level = ROLE_HIERARCHY.get(current_user.role.value, -1)
        required_level = ROLE_HIERARCHY.get(minimum_role.value, 999)

        if user_level < required_level:
            logger.warning(
                "auth.rbac.denied",
                user_id=str(current_user.id),
                user_role=current_user.role.value,
                required_role=minimum_role.value,
            )
            raise PermissionDeniedError()

        return current_user

    return _check_role


def require_superuser():
    """Dependency that restricts access to superusers only.

    Returns:
        Callable: FastAPI dependency resolving to the current superuser.
    """

    async def _check_superuser(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        """Validate that the current user is a superuser.

        Args:
            current_user: The resolved authenticated user.

        Returns:
            User: The current superuser.

        Raises:
            PermissionDeniedError: If the user is not a superuser.
        """
        if not current_user.is_superuser:
            raise PermissionDeniedError()
        return current_user

    return _check_superuser


def get_client_ip(request: Request) -> str | None:
    """Extract the real client IP, respecting ``X-Forwarded-For`` headers.

    Args:
        request: The FastAPI request object.

    Returns:
        str | None: The client IP address string, or None.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first (leftmost) IP — that's the original client
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None
