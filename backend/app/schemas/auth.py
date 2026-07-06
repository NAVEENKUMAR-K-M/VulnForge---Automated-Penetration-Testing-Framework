"""
Authentication Pydantic schemas — request/response contracts for auth endpoints.
"""

from __future__ import annotations

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import VulnForgeBaseModel
from app.schemas.user import UserResponse


class LoginRequest(VulnForgeBaseModel):
    """Credentials for the login endpoint."""

    email: EmailStr = Field(
        description="User's email address.",
        examples=["analyst@vulnforge.local"],
    )
    password: str = Field(
        description="User's plaintext password.",
        examples=["Str0ng!P4ssw0rd#"],
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.lower().strip()


class TokenResponse(VulnForgeBaseModel):
    """Token pair returned after successful authentication or refresh.

    Attributes:
        access_token:  Short-lived JWT (30 min). Put in ``Authorization: Bearer``.
        refresh_token: Long-lived opaque token (7 days). Use to refresh.
        token_type:    Always ``"bearer"``.
        expires_in:    Access token lifetime in seconds.
    """

    access_token: str = Field(description="JWT access token.")
    refresh_token: str = Field(description="Opaque refresh token.")
    token_type: str = Field(default="bearer", description="OAuth2 token type.")
    expires_in: int = Field(description="Access token lifetime in seconds.")


class LoginResponse(VulnForgeBaseModel):
    """Full login response including token pair and user profile."""

    tokens: TokenResponse = Field(description="Issued token pair.")
    user: UserResponse = Field(description="Authenticated user profile.")


class RefreshRequest(VulnForgeBaseModel):
    """Refresh token presented to obtain a new token pair."""

    refresh_token: str = Field(
        description="The opaque refresh token issued at login.",
        min_length=10,
    )


class LogoutRequest(VulnForgeBaseModel):
    """Refresh token to revoke on logout."""

    refresh_token: str = Field(
        description="The refresh token to invalidate.",
        min_length=10,
    )


class PasswordResetRequest(VulnForgeBaseModel):
    """Email address for the password reset request flow."""

    email: EmailStr = Field(
        description="Email of the account to reset.",
        examples=["analyst@vulnforge.local"],
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.lower().strip()


class PasswordResetConfirm(VulnForgeBaseModel):
    """Token and new password for completing a password reset."""

    token: str = Field(
        description="The raw password reset token received via email.",
        min_length=10,
    )
    new_password: str = Field(
        min_length=12,
        max_length=128,
        description="New password (minimum 12 characters).",
    )

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Enforce password complexity on the new password.

        Args:
            v: The proposed new password.

        Returns:
            str: The validated password.

        Raises:
            ValueError: If complexity requirements are not met.
        """
        errors: list[str] = []
        if not any(c.isupper() for c in v):
            errors.append("at least one uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in v):
            errors.append("at least one special character")
        if errors:
            raise ValueError(f"Password must contain {', '.join(errors)}.")
        return v


class ChangePasswordRequest(VulnForgeBaseModel):
    """Current and new password for an authenticated password change."""

    current_password: str = Field(description="The user's current password.")
    new_password: str = Field(
        min_length=12,
        max_length=128,
        description="New password (minimum 12 characters).",
    )

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str, info: object) -> str:
        """Validate complexity and ensure new password differs from current.

        Args:
            v:    The proposed new password.
            info: Pydantic validation info (contains other field values).

        Returns:
            str: The validated new password.

        Raises:
            ValueError: If the password fails complexity or matches current.
        """
        errors: list[str] = []
        if not any(c.isupper() for c in v):
            errors.append("at least one uppercase letter")
        if not any(c.islower() for c in v):
            errors.append("at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            errors.append("at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in v):
            errors.append("at least one special character")
        if errors:
            raise ValueError(f"Password must contain {', '.join(errors)}.")
        return v
