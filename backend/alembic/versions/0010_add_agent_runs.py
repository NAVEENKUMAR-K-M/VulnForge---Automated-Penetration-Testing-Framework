"""Add orchestrator agent tables — agent_runs + agent_actions.

Revision ID: 0010_add_agent_runs
Revises: 0009_add_rag_writeups
Create Date: 2026-11-11 00:00:00.000000+00:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0010_add_agent_runs"
down_revision: Union[str, None] = "0009_add_rag_writeups"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    run_status = postgresql.ENUM(
        "pending", "running", "awaiting_approval", "completed", "failed", "cancelled",
        name="agent_run_status_enum", create_type=False,
    )
    tier = postgresql.ENUM("passive", "active", name="agent_action_tier_enum", create_type=False)
    action_state = postgresql.ENUM(
        "proposed", "approved", "rejected", "executed", "failed", "skipped",
        name="agent_action_state_enum", create_type=False,
    )
    bind = op.get_bind()
    run_status.create(bind, checkfirst=True)
    tier.create(bind, checkfirst=True)
    action_state.create(bind, checkfirst=True)

    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("status", run_status, server_default="pending", nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_agent_runs_workspace", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["targets.id"], name="fk_agent_runs_target", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], name="fk_agent_runs_scan", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_agent_runs_created_by", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_agent_runs"),
    )
    op.create_index("ix_agent_runs_workspace_id", "agent_runs", ["workspace_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])

    op.create_table(
        "agent_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("target_value", sa.String(length=500), nullable=False),
        sa.Column("tier", tier, nullable=False),
        sa.Column("state", action_state, server_default="proposed", nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("scope_verdict", sa.String(length=32), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("result_ref", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], name="fk_agent_actions_run", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_agent_actions"),
    )
    op.create_index("ix_agent_actions_run_id", "agent_actions", ["run_id"])
    op.create_index("ix_agent_actions_state", "agent_actions", ["state"])


def downgrade() -> None:
    op.drop_index("ix_agent_actions_state", table_name="agent_actions")
    op.drop_index("ix_agent_actions_run_id", table_name="agent_actions")
    op.drop_table("agent_actions")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_workspace_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.execute("DROP TYPE IF EXISTS agent_action_state_enum")
    op.execute("DROP TYPE IF EXISTS agent_action_tier_enum")
    op.execute("DROP TYPE IF EXISTS agent_run_status_enum")
