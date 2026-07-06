#!/usr/bin/env python3
"""
Generate a cryptographically secure SECRET_KEY for VulnForge.

Usage:
    python scripts/generate_secret.py
"""

import secrets
import string


def generate_secret_key(length: int = 64) -> str:
    """Generate a URL-safe, cryptographically secure secret key.

    Args:
        length: Number of bytes of randomness. Default is 64 (512-bit).

    Returns:
        A hex-encoded secret key string.
    """
    return secrets.token_hex(length)


def generate_password(length: int = 24) -> str:
    """Generate a strong random password for initial setup.

    Args:
        length: Password length. Default is 24 characters.

    Returns:
        A strong random password string.
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        # Ensure all character class requirements are met
        if (
            any(c.isupper() for c in password)
            and any(c.islower() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%^&*" for c in password)
        ):
            return password


if __name__ == "__main__":
    secret_key = generate_secret_key()
    db_password = generate_password()
    redis_password = generate_password()
    admin_password = generate_password()

    print("\n" + "=" * 60)
    print("  VulnForge — Generated Secrets")
    print("=" * 60)
    print(f"\nSECRET_KEY={secret_key}")
    print(f"\nPOSTGRES_PASSWORD={db_password}")
    print(f"\nREDIS_PASSWORD={redis_password}")
    print(f"\nFIRST_SUPERUSER_PASSWORD={admin_password}")
    print("\n" + "=" * 60)
    print("  ⚠️  Store these values securely. Never commit to git.")
    print("=" * 60 + "\n")
