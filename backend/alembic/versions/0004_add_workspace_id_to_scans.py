"""
Add workspace_id column to scans table.

Revision ID: 0004_add_workspace_id_to_scans
Revises: 0003_add_workspace_tables
Create Date: 2026-07-07 01:00:00.000000 UTC
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0004_add_workspace_id_to_scans"
down_revision: Union[str, None] = "0003_add_workspace_tables"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    """Add nullable workspace_id FK to scans for engagement grouping."""
    op.add_column(
        "scans",
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="FK to the workspace this scan belongs to.",
        ),
    )
    op.create_foreign_key(
        "fk_scans_workspace",
        "scans",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_scans_workspace_id", "scans", ["workspace_id"])


def downgrade() -> None:
    """Remove workspace_id from scans."""
    op.execute("DROP INDEX IF EXISTS idx_scans_workspace_id")
    op.drop_constraint("fk_scans_workspace", "scans", type_="foreignkey")
    op.drop_column("scans", "workspace_id")
