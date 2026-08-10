"""Uji unit penghapusan penugasan — urutan tabel & prefiks penyimpanan (tanpa DB)."""
from __future__ import annotations

import pytest

from app.purge import (
    CASCADE_ORDER,
    confirmation_matches,
    storage_prefixes,
)


def test_prefiks_menutupi_berkas_mentah_dan_bukti():
    """Keduanya wajib: laporan tanpa bukti tak dapat dipertanggungjawabkan,
    dan bukti tanpa penugasan adalah data klien yang tertinggal."""
    assert storage_prefixes(7) == ["uploads/7/", "evidence/7/"]


def test_prefiks_selalu_berakhir_garis_miring():
    # Tanpa garis miring, prefiks "uploads/1" ikut menghapus "uploads/19/...".
    for p in storage_prefixes(1):
        assert p.endswith("/")


def test_prefiks_menolak_id_tak_masuk_akal():
    for buruk in (0, -3):
        with pytest.raises(ValueError):
            storage_prefixes(buruk)


def test_urutan_cascade_menghormati_kunci_asing():
    """Anak harus dihapus sebelum induknya, jika tidak basis data menolak."""
    urutan = list(CASCADE_ORDER)
    assert urutan.index("finding_revisions") < urutan.index("findings")
    assert urutan.index("finding_attachments") < urutan.index("findings")
    assert urutan.index("knowledge_entries") < urutan.index("findings")
    assert urutan.index("findings") < urutan.index("engagements")
    assert urutan.index("scan_uploads") < urutan.index("engagements")
    assert urutan.index("engagement_members") < urutan.index("engagements")
    assert urutan[-1] == "engagements"


def test_urutan_cascade_tak_memuat_duplikat():
    assert len(CASCADE_ORDER) == len(set(CASCADE_ORDER))


def test_konfirmasi_harus_sama_persis():
    assert confirmation_matches("Audit Portal 2026", "Audit Portal 2026") is True


def test_konfirmasi_mengabaikan_spasi_pinggir():
    assert confirmation_matches("Audit Portal 2026", "  Audit Portal 2026  ") is True


def test_konfirmasi_menolak_yang_keliru():
    for salah in ("audit portal 2026", "Audit Portal", "", "   ", None):
        assert confirmation_matches("Audit Portal 2026", salah) is False


def test_konfirmasi_menolak_nama_penugasan_kosong():
    # Penugasan tanpa nama tak boleh jadi celah "ketik apa saja".
    assert confirmation_matches("", "") is False
    assert confirmation_matches(None, "") is False
