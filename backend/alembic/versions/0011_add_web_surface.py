"""Add web attack-surface tables — http_endpoints + http_transactions.

Revision ID: 0011_add_web_surface
Revises: 0010_add_agent_runs
Create Date: 2026-11-11 00:00:00.000000+00:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0011_add_web_surface"
down_revision: Union[str, None] = "0010_add_agent_runs"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    http_method = postgresql.ENUM(
        "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE",
        name="http_method_enum", create_type=False,
    )
    tx_source = postgresql.ENUM(
        "crawler", "dast", "agent", "manual", "verification",
        name="http_tx_source_enum", create_type=False,
    )
    bind = op.get_bind()
    http_method.create(bind, checkfirst=True)
    tx_source.create(bind, checkfirst=True)

    op.create_table(
        "http_endpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("method", http_method, nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("source_tools", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("requires_auth", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_http_endpoints_workspaces", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], name="fk_http_endpoints_targets", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], name="fk_http_endpoints_scans", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_http_endpoints"),
        sa.UniqueConstraint("workspace_id", "method", "url", name="uq_http_endpoints_workspace_method_url"),
    )
    op.create_index("ix_http_endpoints_workspace_id", "http_endpoints", ["workspace_id"])
    op.create_index("ix_http_endpoints_url", "http_endpoints", ["url"])
    op.create_index("idx_http_endpoints_target_id", "http_endpoints", ["target_id"])
    op.create_index("idx_http_endpoints_scan_id", "http_endpoints", ["scan_id"])
    op.create_index(
        "idx_http_endpoints_active", "http_endpoints", ["is_active"],
        postgresql_where=sa.text("is_active = TRUE"),
    )

    op.create_table(
        "http_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("vulnerability_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", tx_source, server_default="crawler", nullable=False),
        sa.Column("method", http_method, nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("request_headers", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("request_body", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_headers", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_http_tx_workspaces", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["endpoint_id"], ["http_endpoints.id"], name="fk_http_tx_endpoints", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], name="fk_http_tx_scans", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vulnerability_id"], ["vulnerabilities.id"], name="fk_http_tx_vulns", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_http_transactions"),
    )
    op.create_index("idx_http_transactions_workspace_id", "http_transactions", ["workspace_id"])
    op.create_index("idx_http_transactions_endpoint_id", "http_transactions", ["endpoint_id"])
    op.create_index("idx_http_transactions_vulnerability_id", "http_transactions", ["vulnerability_id"])
    op.create_index("idx_http_transactions_scan_id", "http_transactions", ["scan_id"])


def downgrade() -> None:
    op.drop_table("http_transactions")
    op.drop_index("idx_http_endpoints_active", table_name="http_endpoints")
    op.drop_index("idx_http_endpoints_scan_id", table_name="http_endpoints")
    op.drop_index("idx_http_endpoints_target_id", table_name="http_endpoints")
    op.drop_index("ix_http_endpoints_url", table_name="http_endpoints")
    op.drop_index("ix_http_endpoints_workspace_id", table_name="http_endpoints")
    op.drop_table("http_endpoints")
    op.execute("DROP TYPE IF EXISTS http_tx_source_enum")
    op.execute("DROP TYPE IF EXISTS http_method_enum")
