"""finding enrichment columns (D8)

Revision ID: d2b8e5a3f9c1
Revises: c1a7f2d9e4b0
Create Date: 2026-08-04 09:05:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2b8e5a3f9c1'
down_revision: str | None = 'c1a7f2d9e4b0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('findings', sa.Column('owasp', sa.String(length=64), nullable=True))
    op.add_column('findings', sa.Column('cvss_vector', sa.String(length=128), nullable=True))
    op.add_column(
        'findings',
        sa.Column('cve', sa.JSON(), server_default=sa.text("'[]'"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('findings', 'cve')
    op.drop_column('findings', 'cvss_vector')
    op.drop_column('findings', 'owasp')
