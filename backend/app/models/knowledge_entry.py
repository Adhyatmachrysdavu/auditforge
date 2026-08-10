"""Entri Basis Pengetahuan Temuan (Modul 3).

Salinan **beku** naratif sebuah temuan pada saat ia disetujui. Perubahan
belakangan pada temuan asal sengaja tidak mengubah entri ini: rujukan yang
berubah diam-diam tidak dapat dipercaya.

Naratif disimpan **utuh**, tidak disamarkan — keputusan sadar demi kegunaan,
dengan tiga pengaman: hanya auditor/admin yang boleh membuka, `kb_shareable`
per penugasan menghormati NDA, dan akses baca dicatat ke `audit_logs`.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_finding_id: Mapped[int] = mapped_column(
        ForeignKey("findings.id"), index=True
    )
    source_engagement_id: Mapped[int] = mapped_column(
        ForeignKey("engagements.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    # Judul ternormalisasi (host/port/angka dibuang) untuk pencocokan lintas klien.
    title_norm: Mapped[str] = mapped_column(String(300), index=True)
    cwe: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    owasp: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str] = mapped_column(String(10))
    # {description, impact, recommendation} — naratif efektif saat disetujui.
    narrative: Mapped[dict] = mapped_column(JSON)
    # Benar bila naskahnya diketik auditor; salah bila draf AI disetujui apa adanya.
    auditor_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    usage_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
