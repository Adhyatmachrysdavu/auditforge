"""Antarmuka detektor kerentanan deterministik (D17 — masukan pembimbing lapangan).

Tiap detektor memeriksa TEKS yang sudah terkumpul pada temuan (judul, deskripsi,
referensi) — tak pernah mengirim permintaan baru ke target manapun, konsisten
dengan prinsip AuditForge yang post-scan-only (lihat CLAUDE.md: "never scans or
exploits anything"). Cocok untuk kelas kerentanan yang punya penanda tekstual
jelas pada evidensi yang sudah dikumpulkan perkakas lain (mis. pesan galat SQL,
urutan `../` pada path, ketiadaan token anti-CSRF yang disebut eksplisit).

Hasil deteksi dipakai untuk mem-backfill CWE saat perkakas sumber tak
menyertakannya (lihat `app/workers/tasks.py:_enrich_finding`), sehingga ikut
mengalir ke OWASP dan ke payload naratif AI — persis usulan pembimbing lapangan
bahwa keluaran pustaka ini "bisa digunakan AI untuk meng-improve hasil scan
mereka".
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class DetectorMatch:
    """Satu kecocokan: detektor mana, label kelas kerentanan, CWE, dan cuplikan bukti."""

    detector_id: str
    label: str
    cwe: str
    evidence: str


class BaseDetector(ABC):
    """Satu plugin: satu kelas kerentanan, satu pola pemeriksaan deterministik.

    Menambah kelas baru (mis. XXE, SSRF) berarti menambah satu subclass di
    `app/detectors/` dan mendaftarkannya di `registry.py` — tak menyentuh kode
    lain (lihat pola serupa pada `app/parsers/`).
    """

    id: ClassVar[str]
    label: ClassVar[str]
    cwe: ClassVar[str]

    @abstractmethod
    def detect(self, text: str) -> DetectorMatch | None:
        """Kembalikan `DetectorMatch` bila `text` memuat penanda kelas ini, else `None`."""
