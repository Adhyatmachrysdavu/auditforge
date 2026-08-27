"""Model temuan (finding).

Skema inti untuk D2; kolom pengayaan penuh (UnifiedFinding) ditambah pada D3+.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.models.enums import FindingStatus, Severity


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagements.id"))
    source_upload_id: Mapped[int | None] = mapped_column(
        ForeignKey("scan_uploads.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(10), default=Severity.info.value)
    status: Mapped[str] = mapped_column(String(20), default=FindingStatus.draft.value)
    cvss_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cwe: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # --- D8: enrichment ---
    owasp: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cvss_vector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cve: Mapped[list[str]] = mapped_column(JSON, default=list)
    # --- D7: deduplikasi ---
    fingerprint: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    occurrences: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # --- D11: triase deterministik (1..4; None = belum ditriase) ---
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # daftar asal yang tergabung: [{"tool": "...", "upload_id": n}, ...]
    sources: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    # --- D10: naratif AI ---
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ai_prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # {description, impact, recommendation} hasil draf AI (auditor menyunting/menyetujui)
    ai_draft: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # --- D13: review & persetujuan ---
    # Naratif final hasil suntingan/persetujuan auditor (menang atas ai_draft di laporan).
    final_narrative: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    narrative_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # --- R4: verifikasi remediasi (retest) ---
    # Putaran tempat temuan ini pernah terlihat, mis. [1, 3]. Inilah yang
    # membuat ketidakhadiran terbaca tanpa menduplikasi temuan.
    rounds_seen: Mapped[list[int]] = mapped_column(JSON, default=list)
    # Keputusan auditor. None = belum ditegaskan; usulan sistem TIDAK disimpan.
    remediation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    remediation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Putaran saat penegasan diberikan. Dipakai menandai penegasan yang sudah
    # dibantah putaran berikutnya.
    remediation_confirmed_round: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    remediation_confirmed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    remediation_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class FindingRevision(Base):
    """Riwayat versi naratif & perubahan status satu temuan (keterlacakan D13)."""

    __tablename__ = "finding_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id"), index=True)
    # 'ai_draft' | 'edit' | 'submit' | 'approve' | 'reject' | 'false_positive' | 'reopen'
    action: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))  # status setelah aksi
    narrative: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # cuplikan naratif
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FindingAttachment(Base):
    """Lampiran bukti (screenshot/PoC) sebuah temuan; berkas di MinIO (D14)."""

    __tablename__ = "finding_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
