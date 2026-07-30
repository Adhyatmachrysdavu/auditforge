"""D14: lampiran bukti temuan (MinIO)

Revision ID: c9f2a6b3d5e8
Revises: b8e4d1f0a2c7
Create Date: 2026-08-11 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9f2a6b3d5e8'
down_revision: str | None = 'b8e4d1f0a2c7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'finding_attachments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('finding_id', sa.Integer(), sa.ForeignKey('findings.id'), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=False),
        sa.Column('content_type', sa.String(length=128), nullable=True),
        sa.Column('size', sa.Integer(), nullable=True),
        sa.Column('uploaded_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_finding_attachments_finding_id', 'finding_attachments', ['finding_id']
    )


def downgrade() -> None:
    op.drop_index('ix_finding_attachments_finding_id', table_name='finding_attachments')
    op.drop_table('finding_attachments')
