"""Model jejak audit (audit trail).

Setiap aksi mutasi (POST/PUT/PATCH/DELETE) dicatat oleh middleware audit.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50))
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(300))
    entity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
