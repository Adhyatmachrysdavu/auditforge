"""Uji unit Modul 1 — pengukuran waktu penyusunan laporan (tanpa DB)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

from app.eval.timing import active_work_seconds, aggregate_timing, timing_summary

T0 = datetime(2026, 8, 1, 9, 0, 0)


def _ev(action: str, minutes: float):
    """Peristiwa revisi palsu (duck-typed seperti FindingRevision)."""
    return SimpleNamespace(action=action, created_at=T0 + timedelta(minutes=minutes))


def test_active_work_clamps_long_gaps():
    # 0 → +10 mnt (600 dtk, penuh) → +5 jam (jeda panjang, dibatasi 1800 dtk)
    #   → +5 jam 10 mnt (600 dtk, penuh). Total 3000 dtk.
    stamps = [
        T0,
        T0 + timedelta(minutes=10),
        T0 + timedelta(hours=5),
        T0 + timedelta(hours=5, minutes=10),
    ]
    assert active_work_seconds(stamps) == 3000.0


def test_active_work_gap_exactly_at_threshold():
    # Selisih persis sama dengan ambang: dihitung penuh, bukan dipotong ganda.
    stamps = [T0, T0 + timedelta(seconds=1800)]
    assert active_work_seconds(stamps) == 1800.0
    # Sedikit di atas ambang tetap menyumbang tepat 1800.
    stamps = [T0, T0 + timedelta(seconds=1801)]
    assert active_work_seconds(stamps) == 1800.0


def test_active_work_custom_gap_seconds():
    # Ambang kustom 300 dtk: selisih 600 dtk dibatasi jadi 300.
    stamps = [T0, T0 + timedelta(minutes=10), T0 + timedelta(minutes=13)]
    assert active_work_seconds(stamps, gap_seconds=300.0) == 300.0 + 180.0


def test_active_work_empty_and_single():
    assert active_work_seconds([]) == 0.0
    assert active_work_seconds([T0]) == 0.0


def test_active_work_unsorted_input():
    # Urutan masukan tak boleh memengaruhi hasil.
    stamps = [T0 + timedelta(minutes=10), T0, T0 + timedelta(minutes=20)]
    assert active_work_seconds(stamps) == 1200.0


def test_active_work_mixed_aware_and_naive_stamps():
    # Kolom DB `DateTime(timezone=True)`; jejak lama bisa naive. Campuran keduanya
    # tak boleh melempar TypeError — yang naive dianggap UTC.
    aware = (T0 + timedelta(minutes=10)).replace(tzinfo=UTC)
    assert active_work_seconds([T0, aware]) == 600.0
    # Zona non-UTC dibandingkan pada titik waktu absolutnya, bukan angka jamnya:
    # 16:10 WIB = 09:10 UTC, jadi selisihnya tetap 10 menit dari T0 (naive=UTC).
    wib = timezone(timedelta(hours=7))
    later_wib = datetime(2026, 8, 1, 16, 10, 0, tzinfo=wib)  # 09:10 UTC
    assert active_work_seconds([T0, later_wib]) == 600.0


def test_summary_mixed_aware_and_naive_does_not_crash():
    evs = [
        SimpleNamespace(action="edit", created_at=T0),
        SimpleNamespace(
            action="approve",
            created_at=(T0 + timedelta(minutes=10)).replace(tzinfo=UTC),
        ),
    ]
    m = timing_summary(evs)
    assert m["measurable"] is True
    assert m["active_seconds"] == 600.0
    assert m["calendar_seconds"] == 600.0


def test_summary_without_baseline_claims_nothing():
    # Tanpa baseline, sistem melaporkan waktu aktual tapi TIDAK mengklaim penghematan.
    evs = [_ev("ai_draft", 0), _ev("edit", 10), _ev("approve", 20)]
    m = timing_summary(evs)
    assert m["active_seconds"] == 1200.0
    assert m["active_hours"] == 0.33
    assert m["measurable"] is True
    assert m["baseline_hours"] is None
    assert m["saved_hours"] is None
    assert m["saved_ratio"] is None


def test_summary_with_baseline_computes_saving():
    # Menguji properti domain, bukan konstanta hasil pembulatan.
    evs = [_ev("ai_draft", 0), _ev("edit", 10), _ev("approve", 20)]
    baseline = 8.0
    m = timing_summary(evs, baseline_hours=baseline)
    active_hours = 1200.0 / 3600
    assert m["measurable"] is True
    assert m["saved_hours"] == abs(m["saved_hours"])  # penghematan positif
    assert abs(float(m["saved_hours"]) - (baseline - active_hours)) < 0.01
    ratio = float(m["saved_ratio"])
    assert 0.0 < ratio < 1.0
    assert abs(ratio - (baseline - active_hours) / baseline) < 0.0001


def test_summary_no_events_with_baseline_claims_nothing():
    # C1: baseline terisi + tanpa peristiwa BUKAN penghematan 100%, tapi "tak ada data".
    m = timing_summary([], baseline_hours=8.0)
    assert m["measurable"] is False
    assert m["saved_hours"] is None
    assert m["saved_ratio"] is None
    assert m["baseline_hours"] == 8.0


def test_summary_single_event_with_baseline_claims_nothing():
    # Satu stempel waktu tak menghasilkan durasi apa pun → tak terukur.
    m = timing_summary([_ev("ai_draft", 0)], baseline_hours=8.0)
    assert m["measurable"] is False
    assert m["saved_hours"] is None
    assert m["saved_ratio"] is None


def test_summary_negative_saving_when_slower_than_baseline():
    # Waktu aktif melebihi baseline → penghematan negatif, bukan galat.
    evs = [_ev("edit", 0), _ev("edit", 20), _ev("approve", 40)]  # 2400 dtk = 0.667 jam
    m = timing_summary(evs, baseline_hours=0.25)
    assert float(m["saved_hours"]) < 0
    assert float(m["saved_ratio"]) < 0
    assert abs(float(m["saved_hours"]) - (0.25 - 2400.0 / 3600)) < 0.01


def test_summary_baseline_zero_no_divzero():
    # Baseline 0 tak masuk akal → diperlakukan seperti tidak ada, bukan pembagian nol.
    evs = [_ev("edit", 0), _ev("approve", 5)]
    m = timing_summary(evs, baseline_hours=0.0)
    assert m["saved_ratio"] is None
    assert m["saved_hours"] is None


def test_summary_custom_gap_seconds_changes_active_time():
    evs = [_ev("edit", 0), _ev("edit", 10), _ev("approve", 20)]
    assert timing_summary(evs)["active_seconds"] == 1200.0
    assert timing_summary(evs, gap_seconds=300.0)["active_seconds"] == 600.0


def test_summary_counts_actions_and_bounds():
    evs = [_ev("ai_draft", 0), _ev("edit", 5), _ev("edit", 10), _ev("approve", 15)]
    m = timing_summary(evs)
    assert m["event_count"] == 4
    assert m["events_by_action"] == {"ai_draft": 1, "edit": 2, "approve": 1}
    assert m["first_at"] == T0.replace(tzinfo=UTC).isoformat()
    assert m["last_at"] == (
        T0 + timedelta(minutes=15)
    ).replace(tzinfo=UTC).isoformat()
    assert m["calendar_seconds"] == 900.0


def test_summary_empty_events():
    m = timing_summary([])
    assert m["event_count"] == 0
    assert m["first_at"] is None
    assert m["last_at"] is None
    assert m["active_seconds"] == 0.0
    assert m["calendar_seconds"] == 0.0
    assert m["events_by_action"] == {}
    assert m["measurable"] is False


def _item(measurable: bool, saved_ratio: float | None) -> dict:
    return {"measurable": measurable, "saved_ratio": saved_ratio}


def test_aggregate_timing_none_measured():
    # Tak ada yang terukur → None, bukan ZeroDivisionError.
    agg = aggregate_timing([_item(False, None), _item(False, None)])
    assert agg == {"engagements_measured": 0, "avg_saved_ratio": None}
    assert aggregate_timing([]) == {"engagements_measured": 0, "avg_saved_ratio": None}


def test_aggregate_timing_single_measured():
    agg = aggregate_timing([_item(True, 0.5), _item(False, None)])
    assert agg == {"engagements_measured": 1, "avg_saved_ratio": 0.5}


def test_aggregate_timing_mixed_ignores_unmeasurable():
    # Penugasan tanpa jejak revisi tak boleh ikut menaikkan rata-rata,
    # bahkan bila (secara keliru) membawa saved_ratio.
    items = [_item(True, 0.4), _item(True, 0.6), _item(False, 1.0), _item(False, None)]
    agg = aggregate_timing(items)
    assert agg == {"engagements_measured": 2, "avg_saved_ratio": 0.5}


def test_aggregate_timing_accepts_full_summary_dicts():
    # Bentuk nyata yang dipakai route: hasil timing_summary + kolom penugasan.
    evs = [_ev("edit", 0), _ev("approve", 10)]
    measured = {"engagement_id": 1, **timing_summary(evs, baseline_hours=8.0)}
    empty = {"engagement_id": 2, **timing_summary([], baseline_hours=8.0)}
    agg = aggregate_timing([measured, empty])
    assert agg["engagements_measured"] == 1
    assert agg["avg_saved_ratio"] == measured["saved_ratio"]
