"""Model penugasan audit/pentest (engagement)."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    true as sa_true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.models.enums import EngagementStatus


class Engagement(Base):
    __tablename__ = "engagements"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    client_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=EngagementStatus.planning.value)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # --- D11: ringkasan eksekutif AI ---
    exec_summary_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    exec_summary_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exec_summary_prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # {overview, key_risks, recommendations, posture} hasil draf AI (auditor menyunting)
    exec_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Jumlah temuan saat ringkasan disusun. Ringkasan adalah snapshot dan tidak
    # ikut berubah saat temuan bertambah; angka ini yang membuat laporan bisa
    # memperingatkan bahwa ringkasannya sudah tidak sesuai isi.
    exec_summary_finding_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # --- Modul 1: baseline pembanding waktu penyusunan manual ---
    # Diisi manusia; sistem tak punya cara mengetahuinya sendiri. Kosong = tak
    # ada klaim penghematan.
    baseline_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # --- Modul 2: kelengkapan penugasan (modul "Pengelolaan Penugasan" di proposal) ---
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Boleh menjadi rujukan Basis Pengetahuan (Modul 3). Sebagian NDA melarang
    # data klien dipakai untuk keperluan lain sekalipun internal.
    kb_shareable: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=sa_true()
    )
    # --- R4: verifikasi remediasi (retest) ---
    # Putaran yang sedang berjalan. 1 = audit awal; 2 dan seterusnya = retest.
    # Dinaikkan hanya lewat tindakan sadar auditor, bukan otomatis dari waktu.
    current_round: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )
