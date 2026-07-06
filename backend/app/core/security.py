"""
Cryptographic security utilities for VulnForge.

Responsibilities:
    - Password hashing and verification (bcrypt, cost=12)
    - JWT access token creation and verification
    - Refresh token and password reset token generation
    - SHA-256 token hashing for safe DB storage

Architecture Decisions:
    - ``passlib`` wraps bcrypt so the hash format is portable and upgradeable.
    - Refresh tokens are *opaque* random bytes — their SHA-256 hash is stored
      in the DB.  If the DB is breached, the attacker cannot derive the raw
      tokens from the hashes.
    - JWT uses HS256 (HMAC-SHA256) with a 64-byte secret key.  RS256 would
      be appropriate for distributed systems where resource servers need to
      verify tokens without access to the secret — not required here.
    - ``verify_access_token`` raises typed exceptions rather than returning
      None, so callers cannot forget to check the return value.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.constants import (
    ACCESS_TOKEN_TYPE,
    PASSWORD_RESET_TOKEN_BYTES,
    REFRESH_TOKEN_BYTES,
)
from app.core.exceptions import InvalidTokenError, TokenExpiredError

# ── Password Hashing ──────────────────────────────────────────────────────────

_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)
"""
Passlib CryptContext configured for bcrypt with work factor 12.

Work factor 12 yields ~250ms per hash on modern hardware:
    - Fast enough for user-facing login
    - Too slow for brute-force attacks (< 4 hashes/second)

``deprecated="auto"`` means passlib will transparently re-hash passwords
using the old work factor on next login if the rounds are ever increased.
"""


def hash_password(plaintext: str) -> str:
    """Hash a plaintext password using bcrypt.

    Args:
        plaintext: The raw password string from the user.

    Returns:
        str: A bcrypt hash string (60 characters, includes salt and cost).

    Example:
        >>> h = hash_password("hunter2")
        >>> h.startswith("$2b$12$")
        True
    """
    return _pwd_context.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Uses a constant-time comparison internally to prevent timing attacks.

    Args:
        plaintext: The raw password submitted by the user.
        hashed:    The bcrypt hash stored in the database.

    Returns:
        bool: True if the password matches the hash.
    """
    return _pwd_context.verify(plaintext, hashed)


def needs_rehash(hashed: str) -> bool:
    """Return True if the hash was created with an old work factor.

    Call this after a successful ``verify_password`` and rehash if True.
    This transparently upgrades existing hashes when the work factor increases.

    Args:
        hashed: The existing bcrypt hash from the database.

    Returns:
        bool: True if the hash should be rehashed with the current settings.
    """
    return _pwd_context.needs_update(hashed)


# ── Token Hashing ─────────────────────────────────────────────────────────────

def sha256_hash(token: str) -> str:
    """Return the hex-encoded SHA-256 digest of a token string.

    Used to hash refresh tokens and password reset tokens before DB storage.
    The raw token is only ever held in memory and sent to the client — the
    hash is what is persisted.

    Args:
        token: The raw token string (URL-safe base64 bytes).

    Returns:
        str: 64-character lowercase hex string (SHA-256 digest).
    """
    return hashlib.sha256(token.encode()).hexdigest()


# ── Refresh Token Generation ──────────────────────────────────────────────────

def generate_refresh_token() -> str:
    """Generate a cryptographically secure refresh token.

    Returns:
        str: A URL-safe base64-encoded string of ``REFRESH_TOKEN_BYTES``
             random bytes (~43 characters for 32 bytes).
    """
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def generate_password_reset_token() -> str:
    """Generate a cryptographically secure password reset token.

    Returns:
        str: A URL-safe base64-encoded string of ``PASSWORD_RESET_TOKEN_BYTES``
             random bytes (~43 characters for 32 bytes).
    """
    return secrets.token_urlsafe(PASSWORD_RESET_TOKEN_BYTES)


# ── JWT Access Token ──────────────────────────────────────────────────────────

def create_access_token(
    *,
    user_id: uuid.UUID,
    email: str,
    role: str,
    is_superuser: bool,
    secret_key: str,
    algorithm: str,
    expire_minutes: int,
) -> str:
    """Create a signed JWT access token.

    The payload includes:
        - ``sub``: Subject (user UUID as string)
        - ``email``: User email (for display, not for lookup)
        - ``role``: User role string
        - ``is_superuser``: Superuser bypass flag
        - ``type``: Always ``"access"`` (distinguishes from other token types)
        - ``iat``: Issued-at timestamp
        - ``exp``: Expiry timestamp

    Args:
        user_id:      The authenticating user's UUID.
        email:        The authenticating user's email.
        role:         The user's role string (e.g., ``"analyst"``).
        is_superuser: Whether the user has superuser privileges.
        secret_key:   HMAC signing secret from settings.
        algorithm:    JWT algorithm (``"HS256"``).
        expire_minutes: Token lifetime in minutes.

    Returns:
        str: Signed compact JWT string.
    """
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=expire_minutes)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "is_superuser": is_superuser,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def verify_access_token(
    token: str,
    *,
    secret_key: str,
    algorithm: str,
) -> dict[str, Any]:
    """Decode and verify a JWT access token.

    Validates:
        - Signature (HMAC)
        - Expiry (``exp`` claim)
        - Token type (must be ``"access"``)

    Args:
        token:      The raw JWT string from the Authorization header.
        secret_key: HMAC signing secret from settings.
        algorithm:  JWT algorithm (``"HS256"``).

    Returns:
        dict[str, Any]: The decoded payload dictionary.

    Raises:
        TokenExpiredError:  If the ``exp`` claim is in the past.
        InvalidTokenError:  If signature verification fails or the token
                            type claim is not ``"access"``.
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError as exc:
        # python-jose raises JWTError for both expired and invalid tokens.
        # Check the message to differentiate — this is the library's API.
        if "expired" in str(exc).lower():
            raise TokenExpiredError() from exc
        raise InvalidTokenError() from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise InvalidTokenError("Token type mismatch.")

    return payload


def extract_user_id_from_token(payload: dict[str, Any]) -> uuid.UUID:
    """Extract and parse the user UUID from a decoded token payload.

    Args:
        payload: Decoded JWT payload dict from ``verify_access_token``.

    Returns:
        uuid.UUID: The authenticated user's UUID.

    Raises:
        InvalidTokenError: If the ``sub`` claim is missing or not a valid UUID.
    """
    sub = payload.get("sub")
    if not sub:
        raise InvalidTokenError("Token is missing subject claim.")
    try:
        return uuid.UUID(sub)
    except ValueError as exc:
        raise InvalidTokenError("Token subject is not a valid UUID.") from exc
