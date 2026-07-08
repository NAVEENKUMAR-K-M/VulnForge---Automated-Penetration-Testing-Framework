"""Add workspace_targets table

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-08 18:00:00.000000+00:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    op.create_table(
        'workspace_targets',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['target_id'], ['targets.id'], name='fk_workspace_targets_targets', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_workspace_targets_workspaces', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'target_id', name='uq_workspace_targets_pair')
    )
    op.create_index('idx_workspace_targets_target_id', 'workspace_targets', ['target_id'], unique=False)
    op.create_index('idx_workspace_targets_workspace_id', 'workspace_targets', ['workspace_id'], unique=False)
    op.execute("CREATE TRIGGER trg_workspace_targets_updated_at BEFORE UPDATE ON workspace_targets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_workspace_targets_updated_at ON workspace_targets")
    op.drop_index('idx_workspace_targets_workspace_id', table_name='workspace_targets')
    op.drop_index('idx_workspace_targets_target_id', table_name='workspace_targets')
    op.drop_table('workspace_targets')
