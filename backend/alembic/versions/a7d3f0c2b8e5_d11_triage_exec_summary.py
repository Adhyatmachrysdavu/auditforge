"""D11: kolom triase temuan + ringkasan eksekutif penugasan

Revision ID: a7d3f0c2b8e5
Revises: f4a1c8e2d6b9
Create Date: 2026-08-07 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7d3f0c2b8e5'
down_revision: str | None = 'f4a1c8e2d6b9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Triase deterministik pada temuan (D11).
    op.add_column('findings', sa.Column('priority', sa.Integer(), nullable=True))
    op.add_column('findings', sa.Column('priority_score', sa.Float(), nullable=True))
    # Ringkasan eksekutif AI pada penugasan (D11).
    op.add_column(
        'engagements',
        sa.Column('exec_summary_generated', sa.Boolean(), nullable=False,
                  server_default=sa.false()),
    )
    op.add_column(
        'engagements', sa.Column('exec_summary_model', sa.String(length=64), nullable=True)
    )
    op.add_column(
        'engagements',
        sa.Column('exec_summary_prompt_version', sa.String(length=32), nullable=True),
    )
    op.add_column('engagements', sa.Column('exec_summary', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('engagements', 'exec_summary')
    op.drop_column('engagements', 'exec_summary_prompt_version')
    op.drop_column('engagements', 'exec_summary_model')
    op.drop_column('engagements', 'exec_summary_generated')
    op.drop_column('findings', 'priority_score')
    op.drop_column('findings', 'priority')
