"""
0005_add_scope_rules_table

Revision ID: 0005
Revises:     0004
Create Date: 2026-07-08

Schema changes:
    + CREATE TYPE scope_rule_type_enum
    + CREATE TYPE scope_disposition_enum
    + CREATE TABLE scope_rules
    + INDEX idx_scope_rules_workspace_id
    + INDEX idx_scope_rules_disposition
    + INDEX idx_scope_rules_active (partial — active only)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# ── Revision identifiers ──────────────────────────────────────────────────────

revision: str = "0005"
down_revision: str = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Create ENUM types ─────────────────────────────────────────────────────
    scope_rule_type_enum = postgresql.ENUM(
        "domain",
        "subdomain",
        "cidr",
        "wildcard",
        "host",
        name="scope_rule_type_enum",
        create_type=True,
    )
    scope_disposition_enum = postgresql.ENUM(
        "allow",
        "exclude",
        name="scope_disposition_enum",
        create_type=True,
    )
    scope_rule_type_enum.create(op.get_bind(), checkfirst=True)
    scope_disposition_enum.create(op.get_bind(), checkfirst=True)

    # ── Create scope_rules table ──────────────────────────────────────────────
    op.create_table(
        "scope_rules",
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
                name="fk_scope_rules_workspace",
            ),
            nullable=False,
        ),
        sa.Column(
            "rule_type",
            scope_rule_type_enum,
            nullable=False,
        ),
        sa.Column(
            "disposition",
            scope_disposition_enum,
            nullable=False,
            server_default="allow",
        ),
        sa.Column(
            "value",
            sa.String(500),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="RESTRICT",
                name="fk_scope_rules_users",
            ),
            nullable=False,
        ),
        # Constraints
        sa.UniqueConstraint(
            "workspace_id",
            "rule_type",
            "disposition",
            "value",
            name="uq_scope_rules_workspace_type_value",
        ),
        sa.CheckConstraint(
            "char_length(trim(value)) > 0",
            name="ck_scope_rules_value_nonempty",
        ),
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    op.create_index(
        "idx_scope_rules_workspace_id",
        "scope_rules",
        ["workspace_id"],
    )
    op.create_index(
        "idx_scope_rules_disposition",
        "scope_rules",
        ["disposition"],
    )
    # Partial index — only active rules (the hot path for scope engine queries)
    op.create_index(
        "idx_scope_rules_active",
        "scope_rules",
        ["workspace_id", "is_active"],
        postgresql_where=sa.text("is_active = TRUE"),
    )
    op.create_index(
        "idx_scope_rules_created_by_id",
        "scope_rules",
        ["created_by_id"],
    )

    # ── Trigger: auto-update updated_at ──────────────────────────────────────
    op.execute("""
        CREATE TRIGGER trg_scope_rules_updated_at
        BEFORE UPDATE ON scope_rules
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_scope_rules_updated_at ON scope_rules;")
    op.drop_index("idx_scope_rules_created_by_id", table_name="scope_rules")
    op.drop_index("idx_scope_rules_active", table_name="scope_rules")
    op.drop_index("idx_scope_rules_disposition", table_name="scope_rules")
    op.drop_index("idx_scope_rules_workspace_id", table_name="scope_rules")
    op.drop_table("scope_rules")
    op.execute("DROP TYPE IF EXISTS scope_disposition_enum;")
    op.execute("DROP TYPE IF EXISTS scope_rule_type_enum;")
