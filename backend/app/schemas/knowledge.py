"""Skema Basis Pengetahuan dan pencarian temuan lintas penugasan (Modul 3)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class KnowledgeEntryOut(BaseModel):
    id: int
    source_finding_id: int
    source_engagement_id: int
    # Nama penugasan & klien asal ditampilkan mencolok di UI agar auditor selalu
    # sadar sedang melihat data klien lain.
    source_engagement_name: str
    source_client_name: str
    title: str
    cwe: str | None
    owasp: str | None
    severity: str
    narrative: dict
    auditor_edited: bool
    usage_count: int
    created_at: datetime


class KnowledgeSuggestion(BaseModel):
    entry: KnowledgeEntryOut
    score: float


class FindingSearchOut(BaseModel):
    id: int
    engagement_id: int
    engagement_name: str
    client_name: str
    title: str
    severity: str
    status: str
    priority: int | None
    cwe: str | None
    owasp: str | None
    cvss_score: float | None
