"""Skema temuan terpadu (`UnifiedFinding`) + antarmuka `BaseParser`.

Setiap parser perkakas mengubah keluaran mentah menjadi daftar `UnifiedFinding`
yang seragam, sehingga sisa pipeline (dedup, enrichment, AI) tidak perlu tahu
format asal.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, Field

from app.models.enums import ScanTool, Severity


class UnifiedFinding(BaseModel):
    """Representasi temuan yang sudah dinormalisasi (lintas-perkakas)."""

    title: str
    description: str | None = None
    severity: Severity = Severity.info
    tool: ScanTool = ScanTool.unknown
    target: str | None = None  # host/URL/port terdampak
    cwe: str | None = None
    cvss_score: float | None = None
    references: list[str] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)  # rekaman asli (untuk keterlacakan)

    def to_description(self) -> str:
        """Gabungkan target + deskripsi + referensi menjadi satu teks."""
        parts: list[str] = []
        if self.target:
            parts.append(f"Target: {self.target}")
        if self.description:
            parts.append(self.description)
        if self.references:
            parts.append("Referensi: " + ", ".join(self.references[:5]))
        return "\n\n".join(parts) or self.title


class BaseParser(ABC):
    """Antarmuka parser per perkakas."""

    tool: ClassVar[ScanTool] = ScanTool.unknown

    @classmethod
    @abstractmethod
    def sniff(cls, filename: str, content: bytes) -> bool:
        """True bila parser ini mengenali berkas (deteksi otomatis)."""

    @abstractmethod
    def parse(self, content: bytes) -> list[UnifiedFinding]:
        """Ubah byte keluaran perkakas menjadi daftar UnifiedFinding."""
