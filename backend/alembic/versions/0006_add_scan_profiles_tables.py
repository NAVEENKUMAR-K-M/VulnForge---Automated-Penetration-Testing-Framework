"""
0006_add_scan_profiles_tables

Revision ID: 0006
Revises:     0005
Create Date: 2026-07-08

Schema changes:
    + CREATE TYPE profile_type_enum
    + CREATE TABLE scan_profiles
    + CREATE TABLE scan_profile_plugins
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Revision identifiers ──────────────────────────────────────────────────────

revision: str = "0006"
down_revision: str = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Create ENUM type ──────────────────────────────────────────────────────
    profile_type_enum = postgresql.ENUM(
        "quick_recon",
        "external_assessment",
        "infrastructure",
        "web_assessment",
        "custom",
        name="profile_type_enum",
        create_type=False,
    )
    profile_type_enum.create(op.get_bind(), checkfirst=True)

    # Note: scan_type_enum and priority_enum should already exist from scans setup
    # but we will rely on SQLAlchemy/Alembic auto-mapping them correctly.

    # ── Create scan_profiles table ────────────────────────────────────────────
    op.create_table(
        "scan_profiles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
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
        sa.Column(
            "name",
            sa.String(200),
            nullable=False,
        ),
        sa.Column(
            "profile_type",
            profile_type_enum,
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "is_builtin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "workspaces.id",
                ondelete="CASCADE",
                name="fk_scan_profiles_workspace",
            ),
            nullable=True,
        ),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="SET NULL",
                name="fk_scan_profiles_created_by",
            ),
            nullable=True,
        ),
        sa.Column(
            "default_scan_type",
            postgresql.ENUM(name="scan_type_enum", create_type=False),
            nullable=False,
            server_default="full",
        ),
        sa.Column(
            "default_priority",
            postgresql.ENUM(name="priority_enum", create_type=False),
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "timeout_minutes",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "cloned_from_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "scan_profiles.id",
                ondelete="SET NULL",
                name="fk_scan_profiles_cloned_from",
            ),
            nullable=True,
        ),
        sa.CheckConstraint(
            "char_length(trim(name)) > 0",
            name="ck_scan_profiles_name_nonempty",
        ),
        sa.CheckConstraint(
            "timeout_minutes IS NULL OR timeout_minutes > 0",
            name="ck_scan_profiles_timeout_positive",
        ),
    )

    op.create_index("idx_scan_profiles_workspace_id", "scan_profiles", ["workspace_id"])
    op.create_index("idx_scan_profiles_type", "scan_profiles", ["profile_type"])
    op.create_index(
        "idx_scan_profiles_builtin",
        "scan_profiles",
        ["is_builtin"],
        postgresql_where=sa.text("is_builtin = TRUE"),
    )

    op.execute("""
        CREATE TRIGGER trg_scan_profiles_updated_at
        BEFORE UPDATE ON scan_profiles
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    # ── Create scan_profile_plugins table ─────────────────────────────────────
    op.create_table(
        "scan_profile_plugins",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
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
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "scan_profiles.id",
                ondelete="CASCADE",
                name="fk_spp_scan_profiles",
            ),
            nullable=False,
        ),
        sa.Column(
            "plugin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "plugins.id",
                ondelete="CASCADE",
                name="fk_spp_plugins",
            ),
            nullable=False,
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "execution_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "config_override",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.UniqueConstraint(
            "profile_id",
            "plugin_id",
            name="uq_scan_profile_plugins_pair",
        ),
        sa.CheckConstraint(
            "execution_order >= 0",
            name="ck_scan_profile_plugins_order_nonneg",
        ),
    )

    op.create_index("idx_spp_profile_id", "scan_profile_plugins", ["profile_id"])
    op.create_index("idx_spp_plugin_id", "scan_profile_plugins", ["plugin_id"])
    op.create_index(
        "idx_spp_enabled",
        "scan_profile_plugins",
        ["profile_id", "is_enabled"],
        postgresql_where=sa.text("is_enabled = TRUE"),
    )

    op.execute("""
        CREATE TRIGGER trg_scan_profile_plugins_updated_at
        BEFORE UPDATE ON scan_profile_plugins
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_scan_profile_plugins_updated_at ON scan_profile_plugins;")
    op.drop_index("idx_spp_enabled", table_name="scan_profile_plugins")
    op.drop_index("idx_spp_plugin_id", table_name="scan_profile_plugins")
    op.drop_index("idx_spp_profile_id", table_name="scan_profile_plugins")
    op.drop_table("scan_profile_plugins")

    op.execute("DROP TRIGGER IF EXISTS trg_scan_profiles_updated_at ON scan_profiles;")
    op.drop_index("idx_scan_profiles_builtin", table_name="scan_profiles")
    op.drop_index("idx_scan_profiles_type", table_name="scan_profiles")
    op.drop_index("idx_scan_profiles_workspace_id", table_name="scan_profiles")
    op.drop_table("scan_profiles")

    op.execute("DROP TYPE IF EXISTS profile_type_enum;")
