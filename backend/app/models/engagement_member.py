"""Keanggotaan tim pada sebuah penugasan (Modul 2).

Keanggotaan inilah yang menentukan siapa boleh membuka sebuah penugasan —
lihat `app/access.py`. Administrator tidak perlu terdaftar; ia melihat semua.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class EngagementMember(Base):
    __tablename__ = "engagement_members"
    __table_args__ = (
        UniqueConstraint("engagement_id", "user_id", name="uq_engagement_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(
        ForeignKey("engagements.id"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # 'lead' | 'member' — keterangan peran di dalam tim, bukan RBAC aplikasi.
    role_in_team: Mapped[str] = mapped_column(String(20), default="member")
    added_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
