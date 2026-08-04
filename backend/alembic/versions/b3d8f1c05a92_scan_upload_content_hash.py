"""sidik jari isi berkas pada scan_uploads

Revision ID: b3d8f1c05a92
Revises: a7c4e9b2f130
Create Date: 2026-08-04 05:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3d8f1c05a92'
down_revision: str | None = 'a7c4e9b2f130'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: berkas yang masuk sebelum kolom ini ada tidak punya hash, dan
    # tidak boleh dianggap duplikat karenanya. Terindeks karena setiap ingest
    # melakukan satu pencarian terhadapnya.
    op.add_column(
        'scan_uploads', sa.Column('content_hash', sa.String(length=64), nullable=True)
    )
    op.create_index(
        'ix_scan_uploads_content_hash', 'scan_uploads', ['content_hash']
    )


def downgrade() -> None:
    op.drop_index('ix_scan_uploads_content_hash', table_name='scan_uploads')
    op.drop_column('scan_uploads', 'content_hash')
