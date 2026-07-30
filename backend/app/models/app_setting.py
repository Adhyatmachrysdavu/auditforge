"""Penyimpanan pengaturan runtime (key-value), mis. konfigurasi LLM (D9/R2).

Nilai di sini menimpa `.env` (fallback) sehingga admin bisa mengubah Base URL /
key / model LLM dari panel tanpa rebuild/restart.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
