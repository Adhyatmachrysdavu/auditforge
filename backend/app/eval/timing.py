"""Pengukuran waktu penyusunan laporan (Modul 1) — deterministik, tanpa DB.

Indikator keberhasilan proposal menuntut bukti "penurunan waktu penyusunan
laporan minimal 50%". Data waktunya sudah terekam sejak awal di
`FindingRevision` (kolom `action` + `created_at`), sehingga metrik dapat
dihitung mundur untuk penugasan yang sudah berjalan.

Yang dihitung adalah **waktu kerja aktif**, bukan waktu kalender. Selisih
antar-peristiwa berurutan dijumlahkan, tetapi **dibatasi** paling banyak
`gap_seconds` per selisih: jeda yang lebih panjang dianggap sebagian besar
istirahat, sehingga hanya menyumbang `gap_seconds` — bukan nol, dan bukan
durasi penuhnya. Pembatasan (bukan pembuangan) dipilih agar auditor yang
menyimpan sekali setelah menulis 45 menit tidak tercatat nol detik, sementara
malam dan akhir pekan tetap tidak ikut terhitung.

Bila `baseline_hours` tidak diisi, modul ini melaporkan waktu aktual tetapi
tidak mengklaim penghematan apa pun — lebih baik kosong daripada mengarang.
Hal yang sama berlaku saat data waktunya tidak cukup: dengan kurang dari dua
stempel waktu tidak ada durasi yang bisa dihitung, sehingga `measurable`
bernilai `False` dan klaim penghematan ditahan (`None`) walau baseline terisi.
Tanpa penjagaan itu penugasan tanpa riwayat revisi akan melaporkan penghematan
100%, padahal yang sebenarnya terjadi adalah tidak ada data.

Keterbatasan yang diketahui (belum ditangani, sengaja):

- **Waktu mesin ikut terhitung.** Revisi ber-`action` `ai_draft` ditulis worker
  Celery, bukan manusia; jarak antar-revisi tersebut mencerminkan latensi LLM.
  Angka "waktu penyusunan" di modul ini karena itu mencakup waktu tunggu worker
  AI, bukan murni waktu manusia. Pemisahan waktu manusia vs waktu AI
  direncanakan sebagai pekerjaan terpisah — sampai itu selesai, angka ini harus
  dibaca sebagai batas atas waktu manusia.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

DEFAULT_GAP_SECONDS = 1800.0  # 30 menit


def _round(value: float, digits: int = 2) -> float:
    """Pembulatan tunggal untuk seluruh modul (ROUND_HALF_UP, bukan banker's rounding)."""
    quant = Decimal(1).scaleb(-digits)  # 2 → Decimal("0.01")
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def _as_utc(value: datetime) -> datetime:
    """Samakan kesadaran zona waktu: yang naive dianggap UTC.

    Kolom basis datanya `DateTime(timezone=True)`, tetapi jejak lama maupun
    objek uji bisa saja naive. Mencampur keduanya membuat `sorted()` melempar
    `TypeError` (galat 500 di produksi), jadi normalisasi dilakukan lebih dulu.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _sorted_stamps(timestamps: Iterable[datetime]) -> list[datetime]:
    """Urutkan stempel waktu setelah disamakan ke UTC."""
    return sorted(_as_utc(t) for t in timestamps)


def active_work_seconds(
    timestamps: Iterable[datetime], *, gap_seconds: float = DEFAULT_GAP_SECONDS
) -> float:
    """Jumlah selisih antar-peristiwa berurutan, tiap selisih dibatasi `gap_seconds`.

    Selisih yang lebih panjang dari ambang menyumbang tepat `gap_seconds`,
    sehingga sesi kerja panjang yang jarang disimpan tetap terhitung tanpa
    membuat jeda semalam ikut masuk.
    """
    ts = _sorted_stamps(timestamps)
    total = 0.0
    for earlier, later in zip(ts, ts[1:]):
        delta = (later - earlier).total_seconds()
        if delta > 0:
            total += min(delta, gap_seconds)
    return total


def timing_summary(
    events: Sequence[object],
    *,
    baseline_hours: float | None = None,
    gap_seconds: float = DEFAULT_GAP_SECONDS,
) -> dict[str, object]:
    """Ringkas jejak revisi menjadi metrik waktu (duck-typed: `.action`, `.created_at`)."""
    stamps = _sorted_stamps(
        s for s in (getattr(e, "created_at", None) for e in events)
        if isinstance(s, datetime)
    )

    by_action: dict[str, int] = {}
    for e in events:
        a = str(getattr(e, "action", "") or "unknown")
        by_action[a] = by_action.get(a, 0) + 1

    # Kurang dari dua stempel waktu → tak ada durasi yang bisa dihitung sama sekali.
    measurable = len(stamps) >= 2
    active = active_work_seconds(stamps, gap_seconds=gap_seconds)
    calendar = (stamps[-1] - stamps[0]).total_seconds() if measurable else 0.0

    saved_hours: float | None = None
    saved_ratio: float | None = None
    # Baseline <= 0 diperlakukan seperti tidak ada: tak ada yang bisa dibandingkan.
    # Tanpa `measurable`, baseline yang terisi akan menghasilkan klaim hemat 100%
    # yang menyesatkan — itu bukan penghematan, itu ketiadaan data.
    if measurable and baseline_hours is not None and baseline_hours > 0:
        # Dihitung dari detik mentah, dibulatkan sekali di akhir: pembulatan
        # berantai lewat `active_hours` menghasilkan angka yang tidak konsisten.
        raw_saved = baseline_hours - active / 3600
        saved_hours = _round(raw_saved, 2)
        saved_ratio = _round(raw_saved / baseline_hours, 4)

    return {
        "event_count": len(events),
        "first_at": stamps[0].isoformat() if stamps else None,
        "last_at": stamps[-1].isoformat() if stamps else None,
        "calendar_seconds": _round(calendar, 2),
        "active_seconds": _round(active, 2),
        "active_hours": _round(active / 3600, 2),
        "events_by_action": by_action,
        "measurable": measurable,
        "baseline_hours": baseline_hours,
        "saved_hours": saved_hours,
        "saved_ratio": saved_ratio,
    }


def aggregate_timing(items: Sequence[dict[str, object]]) -> dict[str, object]:
    """Rata-ratakan penghematan lintas penugasan, hanya dari yang benar-benar terukur.

    Penyaringan memakai `measurable` (bukan sekadar `saved_ratio is not None`)
    agar penugasan tanpa jejak revisi tidak pernah ikut menaikkan rata-rata.
    Tanpa satu pun penugasan terukur, hasilnya `None` — bukan pembagian nol.
    """
    ratios: list[float] = [
        float(r)  # type: ignore[arg-type]
        for i in items
        if i.get("measurable") and (r := i.get("saved_ratio")) is not None
    ]
    avg = _round(sum(ratios) / len(ratios), 4) if ratios else None
    return {"engagements_measured": len(ratios), "avg_saved_ratio": avg}
