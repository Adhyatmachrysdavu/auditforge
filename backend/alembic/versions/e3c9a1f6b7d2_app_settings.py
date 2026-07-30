"""app_settings table (D9/R2)

Revision ID: e3c9a1f6b7d2
Revises: d2b8e5a3f9c1
Create Date: 2026-08-05 10:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3c9a1f6b7d2'
down_revision: str | None = 'd2b8e5a3f9c1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('app_settings')
