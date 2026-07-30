"""D13: alur review — kolom review pada temuan + tabel riwayat revisi

Revision ID: b8e4d1f0a2c7
Revises: a7d3f0c2b8e5
Create Date: 2026-08-10 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e4d1f0a2c7'
down_revision: str | None = 'a7d3f0c2b8e5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Kolom review pada findings.
    op.add_column('findings', sa.Column('final_narrative', sa.JSON(), nullable=True))
    op.add_column(
        'findings',
        sa.Column('narrative_edited', sa.Boolean(), nullable=False,
                  server_default=sa.false()),
    )
    op.add_column('findings', sa.Column('reviewed_by', sa.Integer(), nullable=True))
    op.add_column(
        'findings', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_findings_reviewed_by_users', 'findings', 'users',
        ['reviewed_by'], ['id'],
    )

    # Tabel riwayat revisi.
    op.create_table(
        'finding_revisions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('finding_id', sa.Integer(), sa.ForeignKey('findings.id'), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('narrative', sa.JSON(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_finding_revisions_finding_id', 'finding_revisions', ['finding_id']
    )


def downgrade() -> None:
    op.drop_index('ix_finding_revisions_finding_id', table_name='finding_revisions')
    op.drop_table('finding_revisions')
    op.drop_constraint('fk_findings_reviewed_by_users', 'findings', type_='foreignkey')
    op.drop_column('findings', 'reviewed_at')
    op.drop_column('findings', 'reviewed_by')
    op.drop_column('findings', 'narrative_edited')
    op.drop_column('findings', 'final_narrative')
