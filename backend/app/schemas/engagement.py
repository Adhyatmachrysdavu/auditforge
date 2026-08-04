"""Skema Pydantic untuk penugasan (engagement) & unggahan/temuan."""
from __future__ import annotations

from datetime import datetime

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
