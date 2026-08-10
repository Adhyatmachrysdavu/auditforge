"""Uji unit Modul 2 — perbandingan naratif AI vs auditor (tanpa DB)."""
from __future__ import annotations

from app.review_diff import SECTIONS, diff_narrative


def test_identical_narrative_has_zero_change():
    n = {"description": "Ada kerentanan", "impact": "Data bocor", "recommendation": "Tambal"}
    d = diff_narrative(n, dict(n))
    assert d["overall_changed_ratio"] == 0.0
    for s in SECTIONS:
        assert d["sections"][s]["changed_ratio"] == 0.0
        assert d["sections"][s]["added"] == []
        assert d["sections"][s]["removed"] == []


def test_detects_added_and_removed_words():
    before = {"description": "Ada kerentanan lama", "impact": "", "recommendation": ""}
    after = {"description": "Ada kerentanan kritis", "impact": "", "recommendation": ""}
    d = diff_narrative(before, after)
    sec = d["sections"]["description"]
    assert "kritis" in sec["added"]
    assert "lama" in sec["removed"]
    assert 0.0 < sec["changed_ratio"] <= 1.0


def test_missing_draft_counts_as_fully_written_by_auditor():
    # Tak ada draf AI: seluruh isi naratif ditulis manusia → perubahan penuh.
    after = {"description": "Ditulis auditor", "impact": "Dampak", "recommendation": "Saran"}
    d = diff_narrative(None, after)
    assert d["overall_changed_ratio"] == 1.0
    assert d["sections"]["description"]["before"] == ""


def test_unedited_draft_is_zero_change_not_full_removal():
    """Auditor menerima draf AI apa adanya → nol perubahan, bukan 100%.

    `final_narrative` yang kosong berarti auditor tak menyunting; laporan pun
    memakai draf AI sebagai naratif efektif (`report_data._narrative`). Diff
    harus mengikuti aturan yang sama, jika tidak indikator proposal terbaca
    persis terbalik.
    """
    draft = {
        "description": "Sistem mendukung TLS lawas",
        "impact": "Memudahkan pemetaan permukaan serangan",
        "recommendation": "Aktifkan hanya TLS 1.2 ke atas",
    }
    for kosong in (None, {}, {"description": "", "impact": "  ", "recommendation": ""}):
        d = diff_narrative(draft, kosong)
        assert d["overall_changed_ratio"] == 0.0
        assert d["edited"] is False
        assert d["ai_drafted"] is True
        for s in SECTIONS:
            sec = d["sections"][s]
            assert sec["added"] == []
            assert sec["removed"] == []
            # Naratif efektif = draf AI, jadi kedua sisi menampilkan teks itu.
            assert sec["after"] == sec["before"]


def test_flags_report_who_wrote_the_narrative():
    n = {"description": "isi", "impact": "", "recommendation": ""}
    disunting = diff_narrative({"description": "asal"}, n)
    assert disunting["edited"] is True
    assert disunting["ai_drafted"] is True

    tanpa_draf = diff_narrative(None, n)
    assert tanpa_draf["edited"] is True
    assert tanpa_draf["ai_drafted"] is False

    kosong = diff_narrative(None, None)
    assert kosong["edited"] is False
    assert kosong["ai_drafted"] is False


def test_both_empty_is_not_a_change():
    d = diff_narrative(None, None)
    assert d["overall_changed_ratio"] == 0.0
    for s in SECTIONS:
        assert d["sections"][s]["changed_ratio"] == 0.0


def test_ignores_unknown_keys_and_non_dict_input():
    # Naratif lama bisa memuat kunci lain; hanya tiga bagian resmi yang dibandingkan.
    before = {"description": "A", "catatan": "abaikan"}
    after = {"description": "B", "catatan": "abaikan juga"}
    d = diff_narrative(before, after)
    assert set(d["sections"].keys()) == set(SECTIONS)
    # Masukan yang bukan dict tidak boleh meledak.
    assert diff_narrative("bukan dict", None)["overall_changed_ratio"] == 0.0


def test_overall_ratio_weighted_by_length_not_section_count():
    # Satu bagian panjang yang tak berubah tidak boleh tertutup oleh satu
    # bagian pendek yang berubah total.
    long_same = " ".join(["kata"] * 40)
    before = {"description": long_same, "impact": "x", "recommendation": ""}
    after = {"description": long_same, "impact": "y", "recommendation": ""}
    d = diff_narrative(before, after)
    assert d["sections"]["impact"]["changed_ratio"] == 1.0
    assert d["overall_changed_ratio"] < 0.2
