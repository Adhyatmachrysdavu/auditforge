"""tabel basis pengetahuan temuan (Modul 3)

Revision ID: d4b7e2c81f95
Revises: c5e1a90f4b26
Create Date: 2026-08-10 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4b7e2c81f95'
down_revision: str | None = 'c5e1a90f4b26'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'knowledge_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_finding_id', sa.Integer(), nullable=False),
        sa.Column('source_engagement_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('title_norm', sa.String(length=300), nullable=False),
        sa.Column('cwe', sa.String(length=32), nullable=True),
        sa.Column('owasp', sa.String(length=64), nullable=True),
        sa.Column('severity', sa.String(length=10), nullable=False),
        sa.Column('narrative', sa.JSON(), nullable=False),
        sa.Column('auditor_edited', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['source_finding_id'], ['findings.id']),
        sa.ForeignKeyConstraint(['source_engagement_id'], ['engagements.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        # Satu temuan menghasilkan paling banyak satu entri: buka-kembali lalu
        # setujui ulang tidak boleh menggandakan rujukan.
        sa.UniqueConstraint('source_finding_id', name='uq_knowledge_source_finding'),
    )
    op.create_index(
        'ix_knowledge_entries_source_finding_id',
        'knowledge_entries', ['source_finding_id'],
    )
    op.create_index(
        'ix_knowledge_entries_source_engagement_id',
        'knowledge_entries', ['source_engagement_id'],
    )
    op.create_index('ix_knowledge_entries_title_norm', 'knowledge_entries', ['title_norm'])
    op.create_index('ix_knowledge_entries_cwe', 'knowledge_entries', ['cwe'])


def downgrade() -> None:
    op.drop_index('ix_knowledge_entries_cwe', table_name='knowledge_entries')
    op.drop_index('ix_knowledge_entries_title_norm', table_name='knowledge_entries')
    op.drop_index(
        'ix_knowledge_entries_source_engagement_id', table_name='knowledge_entries'
    )
    op.drop_index(
        'ix_knowledge_entries_source_finding_id', table_name='knowledge_entries'
    )
    op.drop_table('knowledge_entries')
