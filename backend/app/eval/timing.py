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

**Waktu manusia dipisahkan dari waktu worker AI.** Revisi ber-`author_id`
`None` ditulis worker Celery (draf AI), bukan auditor; jarak antar-revisi
tersebut mencerminkan latensi LLM, bukan kerja manusia. Karena `baseline_hours`
berarti "berapa lama auditor menyusun laporan secara manual", klaim penghematan
dihitung **hanya dari waktu manusia** — apel dibandingkan apel. Waktu total
tetap dilaporkan (`active_seconds`) demi transparansi, tetapi tidak dipakai
untuk mengklaim apa pun.

Konsekuensinya, penugasan yang seluruh jejaknya berasal dari worker AI tidak
dapat mengklaim penghematan sama sekali: tak ada kerja manusia untuk
dibandingkan. Itu disengaja — sebelumnya kasus seperti itu melaporkan
penghematan ~98% yang sesungguhnya cuma mengukur latensi LLM.

Catatan: `active_seconds_human` dan `active_seconds` dihitung dari dua deret
peristiwa yang berbeda, sehingga **bukan** bilangan yang bisa dijumlahkan atau
dikurangkan satu sama lain.
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


def _is_human(event: object) -> bool:
    """True bila revisi ditulis manusia.

    Konvensi `FindingRevision`: draf yang disusun worker AI disimpan dengan
    `author_id=None` (lihat `workers/tasks.py`), sedangkan setiap aksi auditor
    membawa id penggunanya.
    """
    return getattr(event, "author_id", None) is not None


def _stamps_of(events: Iterable[object]) -> list[datetime]:
    """Ambil stempel waktu yang valid dari daftar peristiwa, terurut."""
    return _sorted_stamps(
        s
        for s in (getattr(e, "created_at", None) for e in events)
        if isinstance(s, datetime)
    )


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
    human_events = [e for e in events if _is_human(e)]
    stamps = _stamps_of(events)
    human_stamps = _stamps_of(human_events)

    by_action: dict[str, int] = {}
    for e in events:
        a = str(getattr(e, "action", "") or "unknown")
        by_action[a] = by_action.get(a, 0) + 1

    active = active_work_seconds(stamps, gap_seconds=gap_seconds)
    active_human = active_work_seconds(human_stamps, gap_seconds=gap_seconds)
    calendar = (
        (stamps[-1] - stamps[0]).total_seconds() if len(stamps) >= 2 else 0.0
    )

    # Klaim penghematan bersandar pada kerja MANUSIA: butuh minimal dua stempel
    # manusia agar ada durasi untuk dibandingkan. Jejak yang seluruhnya berasal
    # dari worker AI tidak mengukur apa pun tentang waktu auditor.
    measurable = len(human_stamps) >= 2

    saved_hours: float | None = None
    saved_ratio: float | None = None
    # Baseline <= 0 diperlakukan seperti tidak ada: tak ada yang bisa dibandingkan.
    if measurable and baseline_hours is not None and baseline_hours > 0:
        # Dihitung dari detik mentah, dibulatkan sekali di akhir: pembulatan
        # berantai lewat `active_hours` menghasilkan angka yang tidak konsisten.
        raw_saved = baseline_hours - active_human / 3600
        saved_hours = _round(raw_saved, 2)
        saved_ratio = _round(raw_saved / baseline_hours, 4)

    return {
        "event_count": len(events),
        "human_event_count": len(human_events),
        "ai_event_count": len(events) - len(human_events),
        "first_at": stamps[0].isoformat() if stamps else None,
        "last_at": stamps[-1].isoformat() if stamps else None,
        "calendar_seconds": _round(calendar, 2),
        "active_seconds": _round(active, 2),
        "active_hours": _round(active / 3600, 2),
        "active_seconds_human": _round(active_human, 2),
        "active_hours_human": _round(active_human / 3600, 2),
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
