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
