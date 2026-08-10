"""Uji unit Modul 3 — pencocokan judul temuan lintas penugasan (tanpa DB)."""
from __future__ import annotations

from types import SimpleNamespace

from app.knowledge.matching import (
    normalize_title,
    rank_matches,
    score_match,
    title_tokens,
)


def test_normalize_membuang_host_port_dan_kata_umum():
    assert normalize_title("TLS Version Detection on example.com:443") == "tls version"


def test_normalize_membuang_url_penuh():
    hasil = normalize_title("Cross Site Scripting (Reflected) at http://example.com/search?q=1")
    assert hasil == "cross site scripting reflected"


def test_normalize_membuang_alamat_ip_dan_angka():
    assert normalize_title("Open Port 8080 on 192.168.1.10") == "open port"


def test_normalize_mempertahankan_nama_teknologi():
    # 'log4j2' mengandung angka tetapi bukan angka berdiri sendiri — harus bertahan.
    hasil = normalize_title("Apache Log4j2 Remote Code Execution (Log4Shell)")
    assert "log4j2" in hasil
    assert "log4shell" in hasil


def test_normalize_teks_kosong_aman():
    assert normalize_title("") == ""
    assert normalize_title("   ") == ""
    # Judul yang seluruhnya kata umum menyusut menjadi kosong, bukan meledak.
    assert normalize_title("the a an of") == ""


def test_title_tokens_unik():
    assert title_tokens("tls version tls") == {"tls", "version"}
    assert title_tokens("") == set()


def test_cwe_sama_dan_judul_sama_memberi_skor_penuh():
    s = score_match(
        a_cwe="CWE-79", a_title_norm="cross site scripting",
        b_cwe="CWE-79", b_title_norm="cross site scripting",
    )
    assert s == 1.0


def test_cwe_berbeda_dibatasi_kemiripan_judul_saja():
    # Tanpa kesamaan CWE, skor tak boleh melampaui bobot judul (0.4).
    s = score_match(
        a_cwe="CWE-79", a_title_norm="cross site scripting",
        b_cwe="CWE-89", b_title_norm="cross site scripting",
    )
    assert s == 0.4


def test_cwe_kosong_tidak_dianggap_cocok():
    # Dua temuan tanpa CWE bukan berarti ber-CWE sama.
    s = score_match(
        a_cwe=None, a_title_norm="cross site scripting",
        b_cwe=None, b_title_norm="cross site scripting",
    )
    assert s == 0.4


def test_cwe_huruf_besar_kecil_dan_spasi_diabaikan():
    s = score_match(
        a_cwe=" cwe-79 ", a_title_norm="xss",
        b_cwe="CWE-79", b_title_norm="xss",
    )
    assert s == 1.0


def test_judul_tanpa_irisan_hanya_menyisakan_bobot_cwe():
    s = score_match(
        a_cwe="CWE-79", a_title_norm="alpha beta",
        b_cwe="CWE-79", b_title_norm="gamma delta",
    )
    assert s == 0.6


def test_rank_mengurutkan_dan_menyaring_ambang():
    target = SimpleNamespace(cwe="CWE-79", title_norm="cross site scripting")
    kandidat = [
        SimpleNamespace(id=1, cwe="CWE-79", title_norm="cross site scripting"),
        SimpleNamespace(id=2, cwe="CWE-79", title_norm="cross site scripting stored"),
        SimpleNamespace(id=3, cwe="CWE-311", title_norm="mixed content"),
    ]
    hasil = rank_matches(target, kandidat, limit=5, min_score=0.3)
    assert [c.id for c, _ in hasil] == [1, 2]
    assert hasil[0][1] > hasil[1][1]


def test_rank_menghormati_limit_dan_daftar_kosong():
    target = SimpleNamespace(cwe="CWE-79", title_norm="xss")
    kandidat = [SimpleNamespace(id=i, cwe="CWE-79", title_norm="xss") for i in range(5)]
    assert len(rank_matches(target, kandidat, limit=2)) == 2
    assert rank_matches(target, [], limit=2) == []
