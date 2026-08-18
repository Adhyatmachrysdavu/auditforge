"""verifikasi remediasi berbasis putaran (R4)

Revision ID: a9f3c7d21e08
Revises: d4b7e2c81f95
Create Date: 2026-08-18 10:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a9f3c7d21e08'
down_revision: str | None = 'd4b7e2c81f95'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'engagements',
        sa.Column('current_round', sa.Integer(), nullable=False, server_default='1'),
    )
    op.add_column(
        'scan_uploads',
        sa.Column('round', sa.Integer(), nullable=False, server_default='1'),
    )
    op.add_column('findings', sa.Column('rounds_seen', sa.JSON(), nullable=True))
    op.add_column(
        'findings', sa.Column('remediation_status', sa.String(length=20), nullable=True)
    )
    op.add_column('findings', sa.Column('remediation_note', sa.Text(), nullable=True))
    op.add_column(
        'findings', sa.Column('remediation_confirmed_round', sa.Integer(), nullable=True)
    )
    op.add_column(
        'findings', sa.Column('remediation_confirmed_by', sa.Integer(), nullable=True)
    )
    op.add_column(
        'findings',
        sa.Column('remediation_confirmed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_findings_remediation_confirmed_by',
        'findings', 'users',
        ['remediation_confirmed_by'], ['id'],
    )
    # Temuan lama diisi [1], BUKAN daftar kosong. Daftar kosong terbaca
    # "belum diuji" selamanya, sehingga penugasan lama tak akan pernah
    # menghasilkan usulan yang benar begitu putaran kedua dibuka.
    op.execute("UPDATE findings SET rounds_seen = '[1]' WHERE rounds_seen IS NULL")


def downgrade() -> None:
    op.drop_constraint(
        'fk_findings_remediation_confirmed_by', 'findings', type_='foreignkey'
    )
    op.drop_column('findings', 'remediation_confirmed_at')
    op.drop_column('findings', 'remediation_confirmed_by')
    op.drop_column('findings', 'remediation_confirmed_round')
    op.drop_column('findings', 'remediation_note')
    op.drop_column('findings', 'remediation_status')
    op.drop_column('findings', 'rounds_seen')
    op.drop_column('scan_uploads', 'round')
    op.drop_column('engagements', 'current_round')
