"""Pengukuran waktu penyusunan laporan (Modul 1) — deterministik, tanpa DB.

Indikator keberhasilan proposal menuntut bukti "penurunan waktu penyusunan
laporan minimal 50%". Data waktunya sudah terekam sejak awal di
`FindingRevision` (kolom `action` + `created_at`), sehingga metrik dapat
dihitung mundur untuk penugasan yang sudah berjalan.

Yang dihitung adalah **waktu kerja aktif**, bukan waktu kalender: selisih
antar-peristiwa yang lebih panjang dari ambang jeda dianggap istirahat dan
tidak dijumlahkan. Tanpa pembatasan itu angka akan mencakup malam dan akhir
pekan sehingga tak dapat dipertahankan saat ditanya.

Bila `baseline_hours` tidak diisi, modul ini melaporkan waktu aktual tetapi
tidak mengklaim penghematan apa pun — lebih baik kosong daripada mengarang.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

DEFAULT_GAP_SECONDS = 1800.0  # 30 menit


def active_work_seconds(
    timestamps: Iterable[datetime], *, gap_seconds: float = DEFAULT_GAP_SECONDS
) -> float:
    """Jumlah selisih antar-peristiwa berurutan yang lebih pendek dari `gap_seconds`."""
    ts = sorted(timestamps)
    total = 0.0
    for earlier, later in zip(ts, ts[1:]):
        delta = (later - earlier).total_seconds()
        if 0 < delta < gap_seconds:
            total += delta
    return total


def timing_summary(
    events: list[object],
    *,
    baseline_hours: float | None = None,
    gap_seconds: float = DEFAULT_GAP_SECONDS,
) -> dict[str, object]:
    """Ringkas jejak revisi menjadi metrik waktu (duck-typed: `.action`, `.created_at`)."""
    stamps = sorted(
        s for s in (getattr(e, "created_at", None) for e in events)
        if isinstance(s, datetime)
    )

    by_action: dict[str, int] = {}
    for e in events:
        a = str(getattr(e, "action", "") or "unknown")
        by_action[a] = by_action.get(a, 0) + 1

    active = active_work_seconds(stamps, gap_seconds=gap_seconds)
    calendar = (stamps[-1] - stamps[0]).total_seconds() if len(stamps) >= 2 else 0.0
    active_hours = round(active / 3600, 2)

    saved_hours: float | None = None
    saved_ratio: float | None = None
    # Baseline <= 0 diperlakukan seperti tidak ada: tak ada yang bisa dibandingkan.
    if baseline_hours is not None and baseline_hours > 0:
        saved_hours = round(baseline_hours - active_hours, 2)
        # Gunakan Decimal untuk rounding presisi dengan ROUND_HALF_UP
        d_ratio = Decimal(str(saved_hours)) / Decimal(str(baseline_hours))
        saved_ratio = float(d_ratio.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

    return {
        "event_count": len(events),
        "first_at": stamps[0].isoformat() if stamps else None,
        "last_at": stamps[-1].isoformat() if stamps else None,
        "calendar_seconds": round(calendar, 2),
        "active_seconds": round(active, 2),
        "active_hours": active_hours,
        "events_by_action": by_action,
        "baseline_hours": baseline_hours,
        "saved_hours": saved_hours,
        "saved_ratio": saved_ratio,
    }
