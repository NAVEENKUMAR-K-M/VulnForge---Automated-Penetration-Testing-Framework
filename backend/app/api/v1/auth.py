"""
Auth API router — HTTP interface for all authentication endpoints.

Route handlers are intentionally thin:
    1. Validate incoming schema (Pydantic does this automatically)
    2. Extract request metadata (client IP, User-Agent)
    3. Call exactly ONE service method
    4. Return the response

No business logic, no raw SQL, no security decisions live here.
All of that is in ``AuthService``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import (
    AuthServiceDep,
    CurrentUserDep,
    get_auth_service,
    get_client_ip,
    require_role,
)
from app.core.constants import API_AUTH_TAG
from app.models.user import UserRole
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserCreate, UserResponse

router = APIRouter(
    prefix="/auth",
    tags=[API_AUTH_TAG],
)


@router.post(
    "/register",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description=(
        "Create a new user account and immediately receive an access/refresh token pair. "
        "New accounts are assigned the **viewer** role by default. "
        "Email and username must be unique across the platform."
    ),
)
async def register(
    request: Request,
    data: UserCreate,
    auth_service: AuthServiceDep,
) -> LoginResponse:
    """Register endpoint.

    Args:
        request:      FastAPI request (for IP extraction).
        data:         Validated registration payload.
        auth_service: Injected auth service.

    Returns:
        LoginResponse: Token pair + user profile.
    """
    ip = get_client_ip(request)
    return await auth_service.register(data=data, ip_address=ip)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive tokens",
    description=(
        "Exchange email + password for an access token (30 min) and refresh token (7 days). "
        "The same error is returned for wrong email AND wrong password to prevent enumeration. "
        "Accounts are locked after 5 consecutive failed attempts."
    ),
)
async def login(
    request: Request,
    data: LoginRequest,
    auth_service: AuthServiceDep,
) -> LoginResponse:
    """Login endpoint.

    Args:
        request:      FastAPI request (for IP and User-Agent extraction).
        data:         Validated login credentials.
        auth_service: Injected auth service.

    Returns:
        LoginResponse: Token pair + user profile.
    """
    ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    return await auth_service.login(
        email=data.email,
        password=data.password,
        ip_address=ip,
        user_agent=user_agent,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and get new tokens",
    description=(
        "Present a valid refresh token to receive a new access + refresh token pair. "
        "The old refresh token is immediately revoked (token rotation). "
        "Presenting a revoked token indicates possible token theft."
    ),
)
async def refresh_tokens(
    request: Request,
    data: RefreshRequest,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    """Token refresh endpoint.

    Args:
        request:      FastAPI request (for IP extraction).
        data:         Validated refresh request with raw refresh token.
        auth_service: Injected auth service.

    Returns:
        TokenResponse: Fresh token pair.
    """
    ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    return await auth_service.refresh_tokens(
        raw_refresh_token=data.refresh_token,
        ip_address=ip,
        user_agent=user_agent,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke this device's session",
    description="Revoke the presented refresh token, invalidating this device's session.",
)
async def logout(
    request: Request,
    data: LogoutRequest,
    current_user: CurrentUserDep,
    auth_service: AuthServiceDep,
) -> Response:
    """Logout endpoint (single device).

    Args:
        request:      FastAPI request (for IP extraction).
        data:         Validated logout request containing the refresh token.
        current_user: Currently authenticated user (requires valid access token).
        auth_service: Injected auth service.

    Returns:
        Response: 204 No Content.
    """
    ip = get_client_ip(request)
    await auth_service.logout(
        user_id=current_user.id,
        raw_refresh_token=data.refresh_token,
        ip_address=ip,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/logout-all",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Revoke all active sessions",
    description="Revoke all refresh tokens for the current user, logging out all devices.",
)
async def logout_all(
    request: Request,
    current_user: CurrentUserDep,
    auth_service: AuthServiceDep,
) -> MessageResponse:
    """Logout all devices endpoint.

    Args:
        request:      FastAPI request (for IP extraction).
        current_user: Currently authenticated user.
        auth_service: Injected auth service.

    Returns:
        MessageResponse: Confirmation with count of revoked sessions.
    """
    ip = get_client_ip(request)
    revoked = await auth_service.logout_all(
        user_id=current_user.id,
        ip_address=ip,
    )
    return MessageResponse(
        message=f"Successfully revoked {revoked} active session(s)."
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Return the profile of the currently authenticated user.",
)
async def get_me(current_user: CurrentUserDep) -> UserResponse:
    """Current user profile endpoint.

    Args:
        current_user: The authenticated user resolved from the JWT.

    Returns:
        UserResponse: The user's profile (no sensitive fields).
    """
    return UserResponse.model_validate(current_user)


@router.post(
    "/password-reset/request",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Request a password reset email",
    description=(
        "Send a password reset link to the given email address. "
        "Always returns 200 regardless of whether the email exists "
        "(prevents email enumeration). "
        "Reset tokens expire after 15 minutes."
    ),
)
async def request_password_reset(
    request: Request,
    data: PasswordResetRequest,
    auth_service: AuthServiceDep,
) -> MessageResponse:
    """Password reset request endpoint.

    In production this would trigger an email via a background task.
    The raw token returned from the service is what would be embedded
    in the reset URL and sent via email.

    Args:
        request:      FastAPI request (for IP extraction).
        data:         Validated request containing the email.
        auth_service: Injected auth service.

    Returns:
        MessageResponse: Always 200, regardless of email existence.
    """
    ip = get_client_ip(request)
    _raw_token = await auth_service.request_password_reset(
        email=data.email,
        ip_address=ip,
    )
    # TODO: Dispatch email via Celery task if _raw_token is not None
    # background_tasks.add_task(send_reset_email, email=data.email, token=_raw_token)
    return MessageResponse(
        message=(
            "If an account with this email exists, a password reset link "
            "has been sent. The link expires in 15 minutes."
        )
    )


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Complete a password reset",
    description=(
        "Apply a new password using the token received by email. "
        "On success, ALL active sessions are revoked — all devices must re-authenticate."
    ),
)
async def confirm_password_reset(
    request: Request,
    data: PasswordResetConfirm,
    auth_service: AuthServiceDep,
) -> MessageResponse:
    """Password reset confirmation endpoint.

    Args:
        request:      FastAPI request (for IP extraction).
        data:         Validated reset confirmation with token and new password.
        auth_service: Injected auth service.

    Returns:
        MessageResponse: Confirmation that password was changed.
    """
    ip = get_client_ip(request)
    await auth_service.confirm_password_reset(data=data, ip_address=ip)
    return MessageResponse(
        message="Password has been reset successfully. Please log in with your new password."
    )


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    response_model=MessageResponse,
    summary="Change password (authenticated)",
    description=(
        "Change the current user's password. Requires the current password. "
        "All other active sessions are revoked on success."
    ),
)
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    current_user: CurrentUserDep,
    auth_service: AuthServiceDep,
) -> MessageResponse:
    """Authenticated password change endpoint.

    Args:
        request:      FastAPI request (for IP extraction).
        data:         Current and new password payload.
        current_user: The authenticated user.
        auth_service: Injected auth service.

    Returns:
        MessageResponse: Confirmation of password change.
    """
    ip = get_client_ip(request)
    await auth_service.change_password(
        user=current_user,
        data=data,
        ip_address=ip,
    )
    return MessageResponse(
        message="Password changed successfully. Other sessions have been revoked."
    )
