"""finding AI narrative columns (D10)

Revision ID: f4a1c8e2d6b9
Revises: e3c9a1f6b7d2
Create Date: 2026-08-06 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a1c8e2d6b9'
down_revision: str | None = 'e3c9a1f6b7d2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('findings', sa.Column('ai_model', sa.String(length=64), nullable=True))
    op.add_column('findings', sa.Column('ai_prompt_version', sa.String(length=32), nullable=True))
    op.add_column('findings', sa.Column('ai_draft', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('findings', 'ai_draft')
    op.drop_column('findings', 'ai_prompt_version')
    op.drop_column('findings', 'ai_model')
