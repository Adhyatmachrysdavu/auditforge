"""Uji unit R4 — kalimat ringkasan remediasi wajib ada di DOCX, bukan hanya HTML.

KENAPA INI ADA. Spec bagian 8 meminta satu kalimat yang menghitung berapa
temuan sudah tertutup dan diverifikasi. HTML dan PDF memperolehnya lewat
templat Jinja yang sama, sedangkan DOCX menulis paragrafnya sendiri. Ketiadaan
kalimat itu di DOCX tak membuat satu pun tes jatuh dan tak membuat endpoint
laporan membalas selain 200: laporannya hanya kehilangan satu paragraf, dan
justru DOCX yang biasanya dikirim ke klien.

Tes ini murni: tanpa DB, tanpa LLM, tanpa berkas contoh.
"""
from __future__ import annotations

import io

from app.reporting.docx_writer import render_docx
from app.reporting.report_data import ReportData, ReportFinding


def _temuan(nama: str, remediasi: str | None) -> ReportFinding:
    return ReportFinding(
        finding_id=1, title=nama, severity="high", status="approved", priority=2,
        cwe=None, owasp=None, cvss_score=None, cve=[], tools=["zap"], occurrences=1,
        description="", impact="", recommendation="", edited=False,
        remediation=remediasi,
    )


def _data(**ubah) -> ReportData:
    dasar = dict(
        org_name="PT Suryasoft Konsultama",
        report_title="Laporan Audit Keamanan",
        engagement_name="Uji Retest",
        client_name="PT Contoh",
        generated_at="2026-08-20 02:00 UTC",
        posture=None,
        summary_overview="",
        summary_key_risks="",
        summary_recommendations="",
        severity_counts={"high": 2},
        findings=[_temuan("SQL injection", "open"), _temuan("XSS", "fixed")],
        current_round=3,
        remediation_counts={"fixed": 1, "open": 1, "recurring": 0, "not_tested": 0},
    )
    dasar.update(ubah)
    return ReportData(**dasar)


def _teks(data: ReportData, bahasa: str) -> str:
    from docx import Document

    return "\n".join(
        p.text for p in Document(io.BytesIO(render_docx(data, lang=bahasa))).paragraphs
    )


def test_kalimat_ringkasan_muncul_di_docx_indonesia():
    assert (
        "1 dari 2 temuan telah tertutup dan diverifikasi (Putaran 3)."
        in _teks(_data(), "id")
    )


def test_kalimat_ringkasan_muncul_di_docx_inggris():
    assert (
        "1 of 2 findings have been closed and verified (Round 3)."
        in _teks(_data(), "en")
    )


def test_putaran_pertama_tak_mencetak_kalimat_apa_pun():
    # Penugasan yang tak memakai retest harus menghasilkan laporan yang
    # identik dengan sebelum fitur ini ada.
    teks = _teks(_data(current_round=1, remediation_counts={}), "id")
    assert "tertutup dan diverifikasi" not in teks
