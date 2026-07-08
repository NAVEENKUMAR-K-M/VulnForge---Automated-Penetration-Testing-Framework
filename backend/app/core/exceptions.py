"""
Core exception hierarchy for VulnForge.

Architecture Decision:
    All domain exceptions inherit from ``VulnForgeError`` so callers can
    catch the entire hierarchy with a single ``except VulnForgeError`` while
    still being able to catch narrow types when needed.

    HTTP status codes are expressed as attributes on the exception class,
    not as magic integers scattered through the codebase.  The FastAPI
    exception handler in ``main.py`` reads them to produce consistent
    responses.

    Auth exceptions are intentionally vague in their ``detail`` messages
    to prevent information disclosure (user enumeration, etc.).
"""

from __future__ import annotations

from http import HTTPStatus


class VulnForgeError(Exception):
    """Base exception for all VulnForge domain errors.

    Attributes:
        message:     Human-readable error description.
        status_code: HTTP status code this exception maps to.
    """

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.__class__.message
        super().__init__(self.message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r})"


# ── Authentication Exceptions ──────────────────────────────────────────────────

class AuthenticationError(VulnForgeError):
    """Raised when authentication credentials are invalid or missing.

    Intentionally generic — do not expose whether email or password was wrong.
    """

    status_code: int = HTTPStatus.UNAUTHORIZED
    message: str = "Invalid credentials."


class InvalidTokenError(VulnForgeError):
    """Raised when a JWT or refresh token fails validation."""

    status_code: int = HTTPStatus.UNAUTHORIZED
    message: str = "Token is invalid or has expired."


class TokenExpiredError(InvalidTokenError):
    """Raised when a token's expiry time has passed."""

    message: str = "Token has expired."


class RefreshTokenRevokedError(InvalidTokenError):
    """Raised when a refresh token has already been used or revoked."""

    message: str = "Refresh token has been revoked."


class AccountDisabledError(VulnForgeError):
    """Raised when a user attempts to authenticate with a disabled account."""

    status_code: int = HTTPStatus.FORBIDDEN
    message: str = "Account is disabled. Contact your administrator."


class AccountLockedError(VulnForgeError):
    """Raised when a user account is temporarily locked due to failed logins.

    Attributes:
        locked_until_iso: ISO-8601 string of the lockout expiry time.
    """

    status_code: int = 423  # 423 Locked (WebDAV, appropriate here)
    message: str = "Account is temporarily locked due to repeated failed login attempts."

    def __init__(self, locked_until_iso: str | None = None) -> None:
        super().__init__(self.message)
        self.locked_until_iso = locked_until_iso


class PasswordResetTokenError(VulnForgeError):
    """Raised when a password reset token is invalid or expired."""

    status_code: int = HTTPStatus.BAD_REQUEST
    message: str = "Password reset token is invalid or has expired."


# ── Authorisation Exceptions ───────────────────────────────────────────────────

class PermissionDeniedError(VulnForgeError):
    """Raised when an authenticated user lacks the required role or permission."""

    status_code: int = HTTPStatus.FORBIDDEN
    message: str = "You do not have permission to perform this action."


class ScopeViolationError(VulnForgeError):
    """Raised when a scan target is outside the workspace's authorized scope.

    Distinct from PermissionDeniedError — this is a scope/authorization check
    failure, not an RBAC failure.  Carries the scope engine's reason string.

    Args:
        reason: Human-readable explanation from the scope engine.
    """

    status_code: int = HTTPStatus.FORBIDDEN
    message: str = "Target is outside the authorized scope for this workspace."

    def __init__(self, reason: str | None = None) -> None:
        self.message = reason or self.__class__.message
        super(VulnForgeError, self).__init__(self.message)


# ── Resource Exceptions ────────────────────────────────────────────────────────

class NotFoundError(VulnForgeError):
    """Raised when a requested resource does not exist.

    Args:
        resource: Human-readable resource name (e.g., 'Scan', 'Target').
        identifier: The value that was looked up.
    """

    status_code: int = HTTPStatus.NOT_FOUND
    message: str = "Resource not found."

    def __init__(self, resource: str = "Resource", identifier: str | None = None) -> None:
        msg = f"{resource} not found."
        if identifier:
            msg = f"{resource} '{identifier}' not found."
        super().__init__(msg)


class ConflictError(VulnForgeError):
    """Raised when a create/update would violate a uniqueness constraint."""

    status_code: int = HTTPStatus.CONFLICT
    message: str = "A resource with the given identifier already exists."


class ValidationError(VulnForgeError):
    """Raised when business-layer validation fails (distinct from Pydantic validation)."""

    status_code: int = HTTPStatus.UNPROCESSABLE_ENTITY
    message: str = "Validation failed."


# ── Infrastructure Exceptions ──────────────────────────────────────────────────

class DatabaseError(VulnForgeError):
    """Raised when a database operation fails unexpectedly."""

    status_code: int = HTTPStatus.SERVICE_UNAVAILABLE
    message: str = "A database error occurred."


class PluginError(VulnForgeError):
    """Raised when a security plugin fails to execute."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    message: str = "Plugin execution failed."


class PluginTimeoutError(PluginError):
    """Raised when a plugin subprocess exceeds its timeout."""

    message: str = "Plugin execution timed out."


class ReportGenerationError(VulnForgeError):
    """Raised when report generation fails."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    message: str = "Report generation failed."
