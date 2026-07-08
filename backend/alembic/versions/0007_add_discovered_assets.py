"""
0007_add_discovered_assets

Revision ID: 0007
Revises:     0006
Create Date: 2026-07-08

Schema changes:
    + CREATE TYPE asset_type_enum
    + CREATE TABLE discovered_assets
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Revision identifiers ──────────────────────────────────────────────────────

revision: str = "0007"
down_revision: str = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Create ENUM type ──────────────────────────────────────────────────────
    asset_type_enum = postgresql.ENUM(
        "domain",
        "ip",
        "port",
        "url",
        "cloud_resource",
        "other",
        name="asset_type_enum",
        create_type=False,
    )
    asset_type_enum.create(op.get_bind(), checkfirst=True)

    # ── Create discovered_assets table ────────────────────────────────────────
    op.create_table(
        "discovered_assets",
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
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "workspaces.id",
                ondelete="CASCADE",
                name="fk_assets_workspaces",
            ),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "targets.id",
                ondelete="CASCADE",
                name="fk_assets_targets",
            ),
            nullable=False,
        ),
        sa.Column(
            "scan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "scans.id",
                ondelete="SET NULL",
                name="fk_assets_scans",
            ),
            nullable=True,
        ),
        sa.Column(
            "asset_type",
            asset_type_enum,
            nullable=False,
        ),
        sa.Column(
            "value",
            sa.String(500),
            nullable=False,
        ),
        sa.Column(
            "source_tools",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "value",
            "asset_type",
            name="uq_discovered_assets_workspace_value_type",
        ),
    )

    op.create_index("idx_discovered_assets_workspace_id", "discovered_assets", ["workspace_id"])
    op.create_index("idx_discovered_assets_target_id", "discovered_assets", ["target_id"])
    op.create_index("idx_discovered_assets_scan_id", "discovered_assets", ["scan_id"])
    op.create_index("idx_discovered_assets_value", "discovered_assets", ["value"])
    op.create_index(
        "idx_discovered_assets_active",
        "discovered_assets",
        ["is_active"],
        postgresql_where=sa.text("is_active = TRUE"),
    )

    op.execute("""
        CREATE TRIGGER trg_discovered_assets_updated_at
        BEFORE UPDATE ON discovered_assets
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_discovered_assets_updated_at ON discovered_assets;")
    
    op.drop_index("idx_discovered_assets_active", table_name="discovered_assets")
    op.drop_index("idx_discovered_assets_value", table_name="discovered_assets")
    op.drop_index("idx_discovered_assets_scan_id", table_name="discovered_assets")
    op.drop_index("idx_discovered_assets_target_id", table_name="discovered_assets")
    op.drop_index("idx_discovered_assets_workspace_id", table_name="discovered_assets")
    
    op.drop_table("discovered_assets")
    op.execute("DROP TYPE IF EXISTS asset_type_enum;")
