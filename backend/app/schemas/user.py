"""
User Pydantic schemas — request/response contracts for user endpoints.

Separation of concerns:
    UserCreate   → Registration payload (input only)
    UserUpdate   → Partial update payload (input only)
    UserResponse → Safe API response (NEVER includes hashed_password)
    UserInToken  → Minimal payload carried in JWT claims
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.models.user import UserRole
from app.schemas.common import TimestampedResponse, VulnForgeBaseModel


class UserCreate(VulnForgeBaseModel):
    """Schema for registering a new user account.

    Password is validated for minimum length here.  bcrypt hashing is
    done in the service layer — never in the schema.
    """

    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Unique username (alphanumeric, underscores, hyphens only).",
        examples=["pentest_analyst"],
    )
    email: EmailStr = Field(
        description="Valid email address used for authentication.",
        examples=["analyst@vulnforge.local"],
    )
    password: str = Field(
        min_length=12,
        max_length=128,
        description="Password (minimum 12 characters).",
        examples=["Str0ng!P4ssw0rd#"],
    )
    full_name: str | None = Field(
        default=None,
        max_length=200,
        description="Optional full display name.",
        examples=["Alice Johnson"],
    )

    @field_validator("username", mode="before")
    @classmethod
    def normalise_username(cls, v: str) -> str:
        """Normalise username to lowercase.

        Args:
            v: Raw username input.

        Returns:
            str: Lowercase username.
        """
        return v.lower().strip()

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        """Normalise email to lowercase.

        Args:
            v: Raw email input.

        Returns:
            str: Lowercase, stripped email.
        """
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Enforce password complexity requirements.

        Requires at least:
            - 1 uppercase letter
            - 1 lowercase letter
            - 1 digit
            - 1 special character

        Args:
            v: The plaintext password.

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


class UserUpdate(VulnForgeBaseModel):
    """Schema for partial user profile updates.

    All fields are optional — only provided fields are updated.
    Password changes go through the dedicated password change endpoint.
    """

    full_name: str | None = Field(
        default=None,
        max_length=200,
        description="Updated full display name.",
    )
    email: EmailStr | None = Field(
        default=None,
        description="Updated email address.",
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return v.lower().strip()


class UserAdminUpdate(VulnForgeBaseModel):
    """Schema for admin-level user updates (role, active status)."""

    role: UserRole | None = Field(default=None, description="New role assignment.")
    is_active: bool | None = Field(
        default=None,
        description="Enable or disable the account.",
    )
    full_name: str | None = Field(default=None, max_length=200)


class UserResponse(TimestampedResponse):
    """Safe user representation returned by the API.

    Deliberately EXCLUDES: hashed_password, password_reset_token_hash,
    failed_login_attempts, locked_until.
    """

    username: str = Field(description="Unique username.")
    email: str = Field(description="Email address.")
    full_name: str | None = Field(description="Full display name.")
    role: UserRole = Field(description="Platform role.")
    is_active: bool = Field(description="Whether the account is enabled.")
    is_superuser: bool = Field(description="Superuser status.")
    last_login_at: datetime | None = Field(
        description="UTC timestamp of last successful login."
    )


class UserInToken(VulnForgeBaseModel):
    """Minimal user representation embedded in JWT payload."""

    id: UUID = Field(description="User UUID.")
    email: str = Field(description="User email.")
    role: UserRole = Field(description="User role.")
    is_superuser: bool = Field(description="Superuser flag.")
