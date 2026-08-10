"""Uji unit nama berkas pada header unduhan (tanpa DB).

Header HTTP hanya boleh memuat latin-1. Nama penugasan dan nama berkas bukti
datang dari manusia, jadi ia bisa memuat tanda pisah, kutip melengkung, atau
huruf beraksen — dan itu cukup untuk membuat seluruh unduhan gagal 500.
"""
from __future__ import annotations

import pytest

from app.reporting.filenames import ascii_fallback, content_disposition


def test_ascii_biasa_tak_berubah():
    assert ascii_fallback("Laporan Audit 2026") == "Laporan Audit 2026"


def test_em_dash_tidak_meruntuhkan_header():
    """Kasus nyata: nama penugasan ber-em-dash membuat report.pdf balas 500."""
    hasil = ascii_fallback("Audit Infrastruktur Internal — Fase 1")
    assert hasil.isascii()
    assert "Audit Infrastruktur Internal" in hasil
    assert "Fase 1" in hasil


def test_huruf_beraksen_diturunkan_bukan_dibuang():
    assert ascii_fallback("Análisis Segurança") == "Analisis Seguranca"


def test_kutip_melengkung_dan_tanda_lain():
    hasil = ascii_fallback("Audit “Portal” — v2")
    assert hasil.isascii()
    assert "Portal" in hasil


def test_pemisah_jalur_dibuang():
    # Nama berkas yang memuat pemisah jalur dapat menulis ke luar direktori.
    assert "/" not in ascii_fallback("a/b\\c")
    assert "\\" not in ascii_fallback("a/b\\c")


def test_kutip_ganda_dibuang_agar_header_tak_pecah():
    assert '"' not in ascii_fallback('lapor"an')


def test_nama_kosong_punya_pengganti():
    for kosong in ("", "   ", None):
        assert ascii_fallback(kosong) == "laporan"


def test_nama_yang_seluruhnya_non_ascii_tetap_menghasilkan_sesuatu():
    hasil = ascii_fallback("日本語")
    assert hasil
    assert hasil.isascii()


def test_content_disposition_dapat_dikodekan_latin1():
    """Inti masalahnya: Starlette meng-encode header sebagai latin-1."""
    for nama in (
        "Audit Infrastruktur Internal — Fase 1.pdf",
        "Análisis “Segurança”.docx",
        "日本語.pdf",
    ):
        header = content_disposition(nama)
        header.encode("latin-1")  # tak boleh melempar


def test_content_disposition_memuat_kedua_bentuk():
    header = content_disposition("Audit — 2026.pdf")
    assert header.startswith("attachment; ")
    assert 'filename="' in header
    # RFC 5987: bentuk UTF-8 agar peramban modern tetap memperoleh nama aslinya.
    assert "filename*=UTF-8''" in header
    assert "%E2%80%94" in header  # em-dash ter-persen-kode


def test_content_disposition_menghormati_disposisi():
    assert content_disposition("a.pdf", disposition="inline").startswith("inline; ")


@pytest.mark.parametrize("nama", ["a.pdf", "Ünïcödé.docx", "spasi banyak.pdf"])
def test_content_disposition_selalu_aman(nama):
    content_disposition(nama).encode("latin-1")
