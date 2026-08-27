"""Skema Pydantic untuk penugasan (engagement) & unggahan/temuan."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class EngagementCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    client_name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class EngagementOut(BaseModel):
    id: int
    name: str
    client_name: str
    description: str | None
    status: str
    created_by: int | None


class EngagementDetailOut(EngagementOut):
    # --- D11: ringkasan eksekutif AI ---
    exec_summary_generated: bool = False
    exec_summary_model: str | None = None
    exec_summary_prompt_version: str | None = None
    exec_summary: dict | None = None
    # --- Modul 1: baseline waktu ---
    baseline_hours: float | None = None
    baseline_note: str | None = None
    # --- Modul 2: kelengkapan penugasan ---
    scope: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    kb_shareable: bool = True
    # --- R4: verifikasi remediasi ---
    current_round: int = 1


class MemberOut(BaseModel):
    """Satu anggota tim penugasan, sudah digabung dengan data penggunanya."""

    user_id: int
    email: str
    full_name: str
    role: str          # peran RBAC aplikasi (admin/auditor/analyst)
    role_in_team: str  # 'lead' | 'member'


class MemberIn(BaseModel):
    user_id: int
    role_in_team: str = "member"


class EngagementDetailsIn(BaseModel):
    """Kelengkapan penugasan (modul "Pengelolaan Penugasan" di proposal)."""

    scope: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    kb_shareable: bool = True


class EngagementDeleteIn(BaseModel):
    """Konfirmasi penghapusan: nama penugasan diketik ulang persis."""

    confirm_name: str


class EngagementDeleteOut(BaseModel):
    """Apa saja yang benar-benar terhapus, agar dapat diperiksa kemudian."""

    engagement_id: int
    name: str
    findings: int
    uploads: int
    knowledge_entries: int
    storage_objects: int


class BaselineIn(BaseModel):
    """Angka pembanding waktu penyusunan manual (Modul 1)."""

    baseline_hours: float | None = Field(default=None, ge=0)
    baseline_note: str | None = None


class ScanUploadOut(BaseModel):
    id: int
    engagement_id: int
    filename: str
    tool: str
    status: str
    error: str | None = None
    # Diputuskan server (app.ingest.rules.can_reparse) supaya antarmuka tidak
    # menurunkan aturannya sendiri dan ikut basi saat aturannya bertambah.
    can_reparse: bool = False


class FindingOut(BaseModel):
    id: int
    engagement_id: int
    source_upload_id: int | None
    title: str
    severity: str
    status: str
    cwe: str | None
    cvss_score: float | None
    owasp: str | None = None
    cve: list[str] = []
    occurrences: int = 1
    tools: list[str] = []
    ai_generated: bool = False
    priority: int | None = None
    priority_score: float | None = None
    # --- R4: verifikasi remediasi ---
    rounds_seen: list[int] = []
    remediation_status: str | None = None
    # Dihitung, hanya-baca. Tak pernah disimpan agar tak mungkin basi.
    remediation_proposal: str = "not_tested"
    # True bila penegasan lama sudah dibantah putaran berikutnya.
    remediation_stale: bool = False


class FindingDetailOut(FindingOut):
    description: str | None = None
    cvss_vector: str | None = None
    ai_model: str | None = None
    ai_prompt_version: str | None = None
    ai_draft: dict | None = None
    # --- D13: review ---
    final_narrative: dict | None = None
    narrative_edited: bool = False
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None


class NarrativeEditIn(BaseModel):
    description: str = Field(default="", max_length=8000)
    impact: str = Field(default="", max_length=8000)
    recommendation: str = Field(default="", max_length=8000)
    note: str | None = Field(default=None, max_length=1000)


class StatusChangeIn(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=1000)


class FindingRevisionOut(BaseModel):
    id: int
    action: str
    status: str
    narrative: dict | None = None
    note: str | None = None
    author_id: int | None = None
    created_at: datetime | None = None


class AttachmentOut(BaseModel):
    id: int
    finding_id: int
    filename: str
    content_type: str
    size: int
    uploaded_by: int | None = None
    created_at: datetime | None = None


class NarrativeJobOut(BaseModel):
    queued: int
    skipped: int


class SummaryJobOut(BaseModel):
    queued: bool
    findings: int


class TriageResultOut(BaseModel):
    triaged: int


class RemediationIn(BaseModel):
    """Penegasan status remediasi oleh auditor."""

    status: str
    note: str | None = Field(default=None, max_length=1000)
