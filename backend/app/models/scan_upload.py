"""Model unggahan berkas keluaran perkakas (scan output)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.models.enums import ScanTool, UploadStatus


class ScanUpload(Base):
    __tablename__ = "scan_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagements.id"))
    filename: Mapped[str] = mapped_column(String(255))
    tool: Mapped[str] = mapped_column(String(20), default=ScanTool.unknown.value)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=UploadStatus.uploaded.value)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Sidik jari isi berkas (SHA-256) untuk menolak unggahan ganda. Kosong pada
    # berkas yang masuk sebelum kolom ini ada.
    content_hash: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
