"""R4 — verifikasi remediasi (retest) berbasis putaran.

Deterministik dan murni: tanpa basis data, tanpa LLM. Usulan status TIDAK
disimpan, melainkan dihitung ulang tiap kali dibaca, sehingga tak mungkin
basi. Yang tersimpan di basis data hanya keputusan auditor.

Desain: docs/superpowers/specs/2026-08-18-retest-putaran-design.md
"""
from __future__ import annotations

from collections.abc import Iterable

STATUS_NOT_TESTED = "not_tested"
STATUS_OPEN = "open"
STATUS_FIXED = "fixed"
STATUS_RECURRING = "recurring"

VALID_STATUSES = frozenset(
    {STATUS_NOT_TESTED, STATUS_OPEN, STATUS_FIXED, STATUS_RECURRING}
)


def _bersih(rounds_seen: list[int] | None) -> list[int]:
    """Urutkan dan buang duplikat. JSON dari DB bisa memuat apa saja."""
    return sorted({int(r) for r in (rounds_seen or [])})


def propose(rounds_seen: list[int] | None, current_round: int) -> str:
    """Usulan status remediasi dari riwayat penampakan.

    Ini USULAN, bukan penetapan. Ketidakhadiran sebuah temuan di putaran
    terbaru bukan bukti ia sudah diperbaiki: cakupan pemindaian bisa berbeda,
    target bisa sedang mati, atau perkakas kebetulan tak mendeteksi.
    """
    rounds = _bersih(rounds_seen)
    if current_round <= 1 or not rounds:
        return STATUS_NOT_TESTED
    if current_round not in rounds:
        return STATUS_FIXED
    # Terlihat di putaran berjalan. Kambuh bila ada putaran yang terlewat
    # antara penampakan pertama dan sekarang.
    awal = rounds[0]
    terlewat = any(r not in rounds for r in range(awal + 1, current_round))
    return STATUS_RECURRING if terlewat else STATUS_OPEN


def is_new_in_round(rounds_seen: list[int] | None, current_round: int) -> bool:
    """True bila temuan ini pertama kali terlihat pada putaran berjalan.

    Bukan status tersendiri — temuan baru memang terbuka — melainkan penanda
    tampilan agar auditor tahu mana yang muncul akibat perbaikan yang keliru.
    """
    rounds = _bersih(rounds_seen)
    return bool(rounds) and rounds[0] == current_round


def is_stale(
    confirmed_status: str | None,
    confirmed_round: int | None,
    rounds_seen: list[int] | None,
    current_round: int,
) -> bool:
    """True bila penegasan lama sudah dibantah putaran yang lebih baru.

    Penegasan tidak pernah dihapus — ia benar pada saat diberikan, dan
    menghapus keputusan manusia diam-diam merusak keterlacakan.
    """
    if not confirmed_status:
        return False
    if confirmed_round is None or confirmed_round >= current_round:
        return False
    return propose(rounds_seen, current_round) != confirmed_status


def effective_status(
    confirmed_status: str | None,
    confirmed_round: int | None,
    rounds_seen: list[int] | None,
    current_round: int,
) -> str | None:
    """Status yang berlaku untuk laporan. None = belum ditegaskan atau kedaluwarsa."""
    if not confirmed_status:
        return None
    if is_stale(confirmed_status, confirmed_round, rounds_seen, current_round):
        return None
    return confirmed_status


def summarize(rows: Iterable[object], current_round: int) -> dict[str, int]:
    """Hitung temuan per status yang BERLAKU. Usulan tak pernah ikut terhitung."""
    counts = {
        STATUS_FIXED: 0,
        STATUS_OPEN: 0,
        STATUS_RECURRING: 0,
        STATUS_NOT_TESTED: 0,
    }
    for r in rows:
        st = effective_status(
            getattr(r, "remediation_status", None),
            getattr(r, "remediation_confirmed_round", None),
            getattr(r, "rounds_seen", None),
            current_round,
        )
        if st in counts:
            counts[st] += 1
    return counts
