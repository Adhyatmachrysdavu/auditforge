"""Uji unit Modul 1 — pengukuran waktu penyusunan laporan (tanpa DB)."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.eval.timing import active_work_seconds, timing_summary

T0 = datetime(2026, 8, 1, 9, 0, 0)


def _ev(action: str, minutes: float):
    """Peristiwa revisi palsu (duck-typed seperti FindingRevision)."""
    return SimpleNamespace(action=action, created_at=T0 + timedelta(minutes=minutes))


def test_active_work_ignores_long_gaps():
    # 0 → +10 mnt (600 dtk, dihitung) → +5 jam (jeda panjang, dibuang)
    #   → +5 jam 10 mnt (600 dtk, dihitung). Total 1200 dtk.
    stamps = [
        T0,
        T0 + timedelta(minutes=10),
        T0 + timedelta(hours=5),
        T0 + timedelta(hours=5, minutes=10),
    ]
    assert active_work_seconds(stamps) == 1200.0


def test_active_work_empty_and_single():
    assert active_work_seconds([]) == 0.0
    assert active_work_seconds([T0]) == 0.0


def test_active_work_unsorted_input():
    # Urutan masukan tak boleh memengaruhi hasil.
    stamps = [T0 + timedelta(minutes=10), T0, T0 + timedelta(minutes=20)]
    assert active_work_seconds(stamps) == 1200.0


def test_summary_without_baseline_claims_nothing():
    # Tanpa baseline, sistem melaporkan waktu aktual tapi TIDAK mengklaim penghematan.
    evs = [_ev("ai_draft", 0), _ev("edit", 10), _ev("approve", 20)]
    m = timing_summary(evs)
    assert m["active_seconds"] == 1200.0
    assert m["active_hours"] == 0.33
    assert m["baseline_hours"] is None
    assert m["saved_hours"] is None
    assert m["saved_ratio"] is None


def test_summary_with_baseline_computes_saving():
    evs = [_ev("ai_draft", 0), _ev("edit", 10), _ev("approve", 20)]
    m = timing_summary(evs, baseline_hours=8.0)
    assert m["active_hours"] == 0.33
    assert m["saved_hours"] == 7.67
    assert m["saved_ratio"] == 0.9588


def test_summary_baseline_zero_no_divzero():
    # Baseline 0 tak masuk akal → diperlakukan seperti tidak ada, bukan pembagian nol.
    evs = [_ev("edit", 0), _ev("approve", 5)]
    m = timing_summary(evs, baseline_hours=0.0)
    assert m["saved_ratio"] is None
    assert m["saved_hours"] is None


def test_summary_counts_actions_and_bounds():
    evs = [_ev("ai_draft", 0), _ev("edit", 5), _ev("edit", 10), _ev("approve", 15)]
    m = timing_summary(evs)
    assert m["event_count"] == 4
    assert m["events_by_action"] == {"ai_draft": 1, "edit": 2, "approve": 1}
    assert m["first_at"] == T0.isoformat()
    assert m["last_at"] == (T0 + timedelta(minutes=15)).isoformat()
    assert m["calendar_seconds"] == 900.0


def test_summary_empty_events():
    m = timing_summary([])
    assert m["event_count"] == 0
    assert m["first_at"] is None
    assert m["last_at"] is None
    assert m["active_seconds"] == 0.0
    assert m["calendar_seconds"] == 0.0
    assert m["events_by_action"] == {}
