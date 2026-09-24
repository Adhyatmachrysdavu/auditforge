"""Pustaka deteksi kerentanan deterministik, tanpa AI, berbasis plugin (D17).

Lihat `base.py` untuk kontrak plugin dan `registry.py` untuk daftar terpasang.
"""
from __future__ import annotations

from app.detectors.base import BaseDetector, DetectorMatch
from app.detectors.registry import DETECTORS, run_detectors

__all__ = ["BaseDetector", "DetectorMatch", "DETECTORS", "run_detectors"]
