"""Uji unit Modul 3 — naratif efektif & syarat entri Basis Pengetahuan (tanpa DB)."""
from __future__ import annotations

from types import SimpleNamespace

from app.knowledge.entries import (
    effective_narrative,
    is_auditor_edited,
    should_create_entry,
)

DRAF = {
    "description": "Draf AI menjelaskan kerentanan",
    "impact": "Draf AI menjelaskan dampak",
    "recommendation": "Draf AI menyarankan perbaikan",
}
FINAL = {
    "description": "Auditor menulis ulang uraiannya",
    "impact": "Auditor menulis ulang dampaknya",
    "recommendation": "Auditor menulis ulang sarannya",
}


def test_final_menang_atas_draf():
    f = SimpleNamespace(final_narrative=dict(FINAL), ai_draft=dict(DRAF))
    assert effective_narrative(f) == FINAL
    assert is_auditor_edited(f) is True


def test_final_kosong_jatuh_ke_draf_ai():
    """Auditor menerima draf apa adanya — naratifnya tetap ada, bukan hilang."""
    for kosong in (None, {}, {"description": "", "impact": "  ", "recommendation": ""}):
        f = SimpleNamespace(final_narrative=kosong, ai_draft=dict(DRAF))
        assert effective_narrative(f) == DRAF
        assert is_auditor_edited(f) is False


def test_keduanya_kosong_menghasilkan_bagian_kosong():
    f = SimpleNamespace(final_narrative=None, ai_draft=None)
    assert effective_narrative(f) == {
        "description": "", "impact": "", "recommendation": ""
    }
    assert is_auditor_edited(f) is False


def test_spasi_dipangkas_dan_kunci_asing_dibuang():
    f = SimpleNamespace(
        final_narrative={"description": "  ada  ", "catatan": "abaikan"},
        ai_draft=None,
    )
    n = effective_narrative(f)
    assert n["description"] == "ada"
    assert set(n.keys()) == {"description", "impact", "recommendation"}


def test_masukan_bukan_dict_tidak_meledak():
    f = SimpleNamespace(final_narrative="bukan dict", ai_draft=42)
    assert effective_narrative(f) == {
        "description": "", "impact": "", "recommendation": ""
    }


def test_entri_dibuat_saat_disetujui_dan_boleh_dibagi():
    ok, alasan = should_create_entry(
        status="approved", kb_shareable=True, narrative=DRAF, already_exists=False
    )
    assert ok is True
    assert alasan == ""


def test_status_selain_approved_ditolak():
    for st in ("draft", "in_review", "rejected", "false_positive"):
        ok, alasan = should_create_entry(
            status=st, kb_shareable=True, narrative=DRAF, already_exists=False
        )
        assert ok is False
        assert "disetujui" in alasan


def test_kb_shareable_mati_menghormati_kontrak_klien():
    ok, alasan = should_create_entry(
        status="approved", kb_shareable=False, narrative=DRAF, already_exists=False
    )
    assert ok is False
    assert "berbagi" in alasan


def test_naratif_kosong_tidak_menjadi_entri():
    ok, alasan = should_create_entry(
        status="approved",
        kb_shareable=True,
        narrative={"description": "", "impact": "", "recommendation": ""},
        already_exists=False,
    )
    assert ok is False
    assert "kosong" in alasan


def test_entri_ganda_dicegah():
    """Buka-kembali lalu setujui lagi tidak boleh menggandakan entri."""
    ok, alasan = should_create_entry(
        status="approved", kb_shareable=True, narrative=DRAF, already_exists=True
    )
    assert ok is False
    assert "sudah" in alasan
