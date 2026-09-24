"""Uji unit D8+D17 — `_enrich_finding` memakai pustaka deteksi plugin untuk backfill.

Murni (tanpa DB/infra/AI): `pytest tests/test_tasks_enrich.py`.
"""
from __future__ import annotations

from app.parsers.base import UnifiedFinding
from app.workers.tasks import _enrich_finding


def test_detector_backfills_missing_cwe_and_owasp():
    uf = UnifiedFinding(
        title="Unhandled DB error",
        description="Response leaked: you have an error in your sql syntax near line 1",
    )
    _enrich_finding(uf)
    assert uf.cwe == "CWE-89"
    assert uf.raw["_owasp"].startswith("A03")
    assert uf.raw["_detector_matches"][0]["id"] == "SQLI"


def test_detector_never_overrides_tool_supplied_cwe():
    # Perkakas sudah bilang XSS (CWE-79); teks kebetulan mirip galat SQL juga —
    # backfill tak boleh menimpa data perkakas, hanya mengisi yang kosong.
    uf = UnifiedFinding(
        title="Reflected XSS",
        description="Also observed: you have an error in your sql syntax",
        cwe="CWE-79",
    )
    _enrich_finding(uf)
    assert uf.cwe == "CWE-79"
    # Tetap tercatat untuk keterlacakan meski tak dipakai backfill.
    assert uf.raw["_detector_matches"][0]["id"] == "SQLI"


def test_no_detector_match_leaves_raw_key_absent():
    uf = UnifiedFinding(title="Outdated TLS version", description="TLS 1.0 is enabled.")
    _enrich_finding(uf)
    assert "_detector_matches" not in uf.raw
