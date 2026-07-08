"""Add metadata to DiscoveredAsset

Revision ID: 30cec625e23c
Revises: 0008
Create Date: 2026-07-08 15:23:45.688593+00:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '30cec625e23c'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    op.add_column('discovered_assets', sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))

def downgrade() -> None:
    op.drop_column('discovered_assets', 'metadata')
