"""Registry — detektor terpasang + API untuk menjalankan semuanya sekaligus.

Menambah detektor baru = tambah satu berkas + satu baris di `DETECTORS`, sama
seperti pola registry `app/parsers/__init__.py:select_parser()`.
"""
from __future__ import annotations

from app.detectors.base import BaseDetector, DetectorMatch
from app.detectors.csrf import CsrfDetector
from app.detectors.lfi import LfiDetector
from app.detectors.sqli import SqliDetector

DETECTORS: list[BaseDetector] = [SqliDetector(), LfiDetector(), CsrfDetector()]


def run_detectors(*texts: str | None) -> list[DetectorMatch]:
    """Jalankan semua detektor terdaftar atas gabungan `texts`, kembalikan yang cocok.

    Urutan `DETECTORS` menentukan urutan hasil; kegagalan satu detektor
    (mis. regex meledak pada masukan aneh) tak boleh menggagalkan yang lain.
    """
    blob = "\n".join(t for t in texts if t)
    if not blob:
        return []
    out: list[DetectorMatch] = []
    for d in DETECTORS:
        try:
            m = d.detect(blob)
        except Exception:  # noqa: BLE001 — detektor rusak tak boleh menggagalkan ingest
            continue
        if m:
            out.append(m)
    return out


__all__ = ["run_detectors", "DetectorMatch", "BaseDetector", "DETECTORS"]
