"""anggota tim + periode & cakupan penugasan (Modul 2)

Revision ID: c5e1a90f4b26
Revises: b3d8f1c05a92
Create Date: 2026-08-04 07:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c5e1a90f4b26'
down_revision: str | None = 'b3d8f1c05a92'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('engagements', sa.Column('scope', sa.Text(), nullable=True))
    op.add_column('engagements', sa.Column('period_start', sa.Date(), nullable=True))
    op.add_column('engagements', sa.Column('period_end', sa.Date(), nullable=True))
    op.add_column(
        'engagements',
        sa.Column(
            'kb_shareable', sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )

    op.create_table(
        'engagement_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('engagement_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_in_team', sa.String(length=20), nullable=False),
        sa.Column('added_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['engagement_id'], ['engagements.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['added_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('engagement_id', 'user_id', name='uq_engagement_member'),
    )
    op.create_index(
        'ix_engagement_members_engagement_id', 'engagement_members', ['engagement_id']
    )
    op.create_index('ix_engagement_members_user_id', 'engagement_members', ['user_id'])

    # --- Pengisian: WAJIB berada di migrasi yang sama ---
    # Tanpa ini, pembatasan akses langsung mengunci setiap pengguna non-admin
    # dari seluruh penugasan yang sudah ada.
    conn = op.get_bind()

    # 1. Pembuat penugasan menjadi `lead`.
    conn.execute(
        sa.text(
            """
            INSERT INTO engagement_members
                (engagement_id, user_id, role_in_team, added_by, created_at)
            SELECT e.id, e.created_by, 'lead', NULL, NOW()
            FROM engagements e
            WHERE e.created_by IS NOT NULL
            """
        )
    )

    # 2. Penugasan tanpa pembuat jatuh ke seluruh administrator.
    conn.execute(
        sa.text(
            """
            INSERT INTO engagement_members
                (engagement_id, user_id, role_in_team, added_by, created_at)
            SELECT e.id, u.id, 'lead', NULL, NOW()
            FROM engagements e
            CROSS JOIN users u
            JOIN roles r ON r.id = u.role_id
            WHERE e.created_by IS NULL AND r.name = 'admin'
            """
        )
    )

    # 3. Verifikasi: tidak boleh ada penugasan tanpa anggota. Lebih baik migrasi
    #    gagal keras di sini daripada mengunci pengguna diam-diam.
    orphans = conn.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM engagements e
            WHERE NOT EXISTS (
                SELECT 1 FROM engagement_members m WHERE m.engagement_id = e.id
            )
            """
        )
    ).scalar()
    if orphans:
        raise RuntimeError(
            f"{orphans} penugasan tidak memperoleh anggota tim. "
            "Migrasi dibatalkan agar tidak ada pengguna yang terkunci."
        )


def downgrade() -> None:
    op.drop_index('ix_engagement_members_user_id', table_name='engagement_members')
    op.drop_index(
        'ix_engagement_members_engagement_id', table_name='engagement_members'
    )
    op.drop_table('engagement_members')
    op.drop_column('engagements', 'kb_shareable')
    op.drop_column('engagements', 'period_end')
    op.drop_column('engagements', 'period_start')
    op.drop_column('engagements', 'scope')
