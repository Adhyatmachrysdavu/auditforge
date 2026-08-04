"""catat jumlah temuan saat ringkasan eksekutif dibuat

Revision ID: a7c4e9b2f130
Revises: f1a2b3c4d5e6
Create Date: 2026-08-04 03:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7c4e9b2f130'
down_revision: str | None = 'f1a2b3c4d5e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: ringkasan yang sudah ada sebelum kolom ini dibuat tidak diketahui
    # jumlah temuannya, dan tidak boleh dituduh basi hanya karena itu.
    op.add_column(
        'engagements',
        sa.Column('exec_summary_finding_count', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('engagements', 'exec_summary_finding_count')
