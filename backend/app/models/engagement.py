"""Model penugasan audit/pentest (engagement)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
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
    # --- Modul 1: baseline pembanding waktu penyusunan manual ---
    # Diisi manusia; sistem tak punya cara mengetahuinya sendiri. Kosong = tak
    # ada klaim penghematan.
    baseline_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_note: Mapped[str | None] = mapped_column(Text, nullable=True)
