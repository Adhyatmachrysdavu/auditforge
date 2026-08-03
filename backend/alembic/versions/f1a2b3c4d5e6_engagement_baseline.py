"""engagement baseline waktu penyusunan (Modul 1)

Revision ID: f1a2b3c4d5e6
Revises: c9f2a6b3d5e8
Create Date: 2026-08-03 14:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: str | None = 'c9f2a6b3d5e8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('engagements', sa.Column('baseline_hours', sa.Float(), nullable=True))
    op.add_column('engagements', sa.Column('baseline_note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('engagements', 'baseline_note')
    op.drop_column('engagements', 'baseline_hours')
