"""
Add password reset fields to users table.

Revision ID: 0002_add_password_reset_fields
Revises: 0001_initial_schema
Create Date: 2026-07-06 01:00:00.000000 UTC
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_password_reset_fields"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    """Add password_reset_token_hash and password_reset_expires_at to users."""
    op.add_column(
        "users",
        sa.Column(
            "password_reset_token_hash",
            sa.String(128),
            nullable=True,
            comment="SHA-256 digest of active password reset token.",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "password_reset_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="UTC expiry of the password reset token.",
        ),
    )
    # Partial index: only index rows with an active reset token
    op.execute("""
        CREATE INDEX idx_users_pwd_reset_token
        ON users (password_reset_token_hash)
        WHERE password_reset_token_hash IS NOT NULL
    """)


def downgrade() -> None:
    """Remove password reset columns from users."""
    op.execute("DROP INDEX IF EXISTS idx_users_pwd_reset_token")
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_token_hash")
