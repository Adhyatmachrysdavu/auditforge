"""Uji unit R4 — verifikasi remediasi berbasis putaran (tanpa DB, tanpa LLM)."""
from __future__ import annotations

from types import SimpleNamespace

from app.retest import (
    STATUS_FIXED,
    STATUS_NOT_TESTED,
    STATUS_OPEN,
    STATUS_RECURRING,
    effective_status,
    is_new_in_round,
    is_stale,
    propose,
    summarize,
)


def test_putaran_satu_belum_ada_pembanding():
    assert propose([1], 1) == STATUS_NOT_TESTED


def test_rounds_seen_kosong_dianggap_belum_diuji():
    # Data lama sebelum kolom ini ada; jangan menyimpulkan apa pun.
    assert propose([], 3) == STATUS_NOT_TESTED
    assert propose(None, 3) == STATUS_NOT_TESTED


def test_tak_terlihat_di_putaran_berjalan_berarti_tertutup():
    assert propose([1], 2) == STATUS_FIXED


def test_masih_terlihat_berarti_terbuka():
    assert propose([1, 2], 2) == STATUS_OPEN


def test_temuan_baru_di_putaran_belakangan_juga_terbuka():
    # Pertama terlihat di putaran 2; tak ada putaran terlewat sebelum itu.
    assert propose([2], 2) == STATUS_OPEN


def test_putaran_terlewat_di_tengah_berarti_kambuh():
    assert propose([1, 3], 3) == STATUS_RECURRING


def test_terlihat_berturut_turut_bukan_kambuh():
    assert propose([1, 2, 3], 3) == STATUS_OPEN


def test_baru_di_putaran_ini():
    assert is_new_in_round([2, 3], 2) is True
    assert is_new_in_round([1, 2], 2) is False
    assert is_new_in_round([], 2) is False


def test_penegasan_dibantah_putaran_berikutnya_jadi_kedaluwarsa():
    # Ditegaskan tertutup di putaran 2, lalu terlihat lagi di putaran 3.
    assert is_stale(STATUS_FIXED, 2, [1, 3], 3) is True
    assert effective_status(STATUS_FIXED, 2, [1, 3], 3) is None


def test_penegasan_yang_masih_sejalan_tidak_kedaluwarsa():
    assert is_stale(STATUS_OPEN, 2, [1, 2, 3], 3) is False
    assert effective_status(STATUS_OPEN, 2, [1, 2, 3], 3) == STATUS_OPEN


def test_penegasan_pada_putaran_berjalan_tidak_pernah_kedaluwarsa():
    assert is_stale(STATUS_FIXED, 3, [1], 3) is False


def test_belum_ditegaskan_bukan_kedaluwarsa_dan_tak_berlaku():
    assert is_stale(None, None, [1, 2], 2) is False
    assert effective_status(None, None, [1, 2], 2) is None


def test_summarize_hanya_menghitung_status_yang_berlaku():
    rows = [
        # ditegaskan tertutup di putaran 2, masih sejalan
        SimpleNamespace(remediation_status=STATUS_FIXED, remediation_confirmed_round=2,
                        rounds_seen=[1]),
        # ditegaskan terbuka, masih sejalan
        SimpleNamespace(remediation_status=STATUS_OPEN, remediation_confirmed_round=2,
                        rounds_seen=[1, 2]),
        # belum ditegaskan → tidak dihitung
        SimpleNamespace(remediation_status=None, remediation_confirmed_round=None,
                        rounds_seen=[1, 2]),
    ]
    assert summarize(rows, 2) == {
        STATUS_FIXED: 1,
        STATUS_OPEN: 1,
        STATUS_RECURRING: 0,
        STATUS_NOT_TESTED: 0,
    }
