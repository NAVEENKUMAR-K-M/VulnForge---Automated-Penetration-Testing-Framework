"""
Add workspaces and workspace_members tables.

Revision ID: 0003_add_workspace_tables
Revises: 0002_add_password_reset_fields
Create Date: 2026-07-07 00:00:00.000000 UTC
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0003_add_workspace_tables"
down_revision: Union[str, None] = "0002_add_password_reset_fields"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    """Create workspace and workspace_members tables with all constraints."""

    # ── Enum Types ────────────────────────────────────────────────────────────
    workspace_status_enum = postgresql.ENUM(
        "active", "completed", "archived",
        name="workspace_status_enum",
        create_type=False,
    )
    workspace_status_enum.create(op.get_bind(), checkfirst=True)

    workspace_member_role_enum = postgresql.ENUM(
        "owner", "member", "viewer",
        name="workspace_member_role_enum",
        create_type=False,
    )
    workspace_member_role_enum.create(op.get_bind(), checkfirst=True)

    # ── Table: workspaces ─────────────────────────────────────────────────────
    op.create_table(
        "workspaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("client_name", sa.String(200), nullable=True),
        sa.Column("client_contact", sa.String(200), nullable=True),
        sa.Column(
            "status",
            workspace_status_enum,
            nullable=False,
            server_default="active",
        ),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "settings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_workspaces_owner",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_workspaces_dates",
        ),
        sa.CheckConstraint(
            "char_length(trim(name)) > 0",
            name="ck_workspaces_name_nonempty",
        ),
    )
    op.create_index("idx_workspaces_owner_id", "workspaces", ["owner_id"])
    op.create_index("idx_workspaces_status", "workspaces", ["status"])
    op.execute("""
        CREATE INDEX idx_workspaces_active
        ON workspaces (status)
        WHERE is_archived = FALSE
    """)
    op.execute(
        "CREATE TRIGGER trg_workspaces_updated_at BEFORE UPDATE ON workspaces "
        "FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()"
    )

    # ── Table: workspace_members ──────────────────────────────────────────────
    op.create_table(
        "workspace_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            workspace_member_role_enum,
            nullable=False,
        ),
        sa.Column("invited_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "user_id",
            name="uq_workspace_members_pair",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_wm_workspaces",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_wm_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_id"],
            ["users.id"],
            name="fk_wm_invited_by",
            ondelete="SET NULL",
        ),
    )
    op.create_index("idx_wm_workspace_id", "workspace_members", ["workspace_id"])
    op.create_index("idx_wm_user_id", "workspace_members", ["user_id"])
    op.create_index("idx_wm_role", "workspace_members", ["role"])


def downgrade() -> None:
    """Drop workspace tables and enum types."""
    op.execute("DROP TABLE IF EXISTS workspace_members CASCADE")
    op.execute("DROP TABLE IF EXISTS workspaces CASCADE")
    op.execute("DROP TYPE IF EXISTS workspace_member_role_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS workspace_status_enum CASCADE")
