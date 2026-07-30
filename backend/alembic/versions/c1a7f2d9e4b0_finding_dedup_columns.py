"""finding dedup columns (D7)

Revision ID: c1a7f2d9e4b0
Revises: 7650f33b3bab
Create Date: 2026-08-03 09:10:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a7f2d9e4b0'
down_revision: str | None = '7650f33b3bab'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('findings', sa.Column('fingerprint', sa.String(length=64), nullable=True))
    op.add_column(
        'findings',
        sa.Column('occurrences', sa.Integer(), server_default='1', nullable=False),
    )
    op.add_column(
        'findings',
        sa.Column('sources', sa.JSON(), server_default=sa.text("'[]'"), nullable=True),
    )
    op.create_index('ix_findings_fingerprint', 'findings', ['fingerprint'])


def downgrade() -> None:
    op.drop_index('ix_findings_fingerprint', table_name='findings')
    op.drop_column('findings', 'sources')
    op.drop_column('findings', 'occurrences')
    op.drop_column('findings', 'fingerprint')
