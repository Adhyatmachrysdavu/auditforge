"""Penghapusan penugasan — keputusan deterministik, tanpa DB maupun penyimpanan.

Menghapus penugasan berarti menghapus temuan, naratif, riwayat revisi, lampiran
bukti, entri Basis Pengetahuan, dan berkas mentah di MinIO. Karena itu dua hal
dipisahkan ke modul murni ini agar dapat diuji tanpa infrastruktur:

1. **Urutan tabel.** Anak sebelum induk, jika tidak kunci asing menolak dan
   penghapusan gagal separuh jalan.
2. **Prefiks penyimpanan.** Salah menuliskannya berarti berkas klien tertinggal
   di disk — atau, lebih buruk, berkas penugasan lain ikut terhapus.

Jejak audit (`audit_logs`) **tidak** ikut dihapus: ia justru catatan bahwa
penghapusan itu terjadi, dan tak punya kunci asing ke `engagements`.
"""
from __future__ import annotations

# Urutan penghapusan; anak lebih dulu, `engagements` terakhir.
CASCADE_ORDER: tuple[str, ...] = (
    "finding_revisions",
    "finding_attachments",
    "knowledge_entries",
    "findings",
    "scan_uploads",
    "engagement_members",
    "engagements",
)


def storage_prefixes(engagement_id: int) -> list[str]:
    """Prefiks MinIO milik satu penugasan.

    Garis miring penutup wajib: tanpa itu prefiks `uploads/1` juga akan
    menyapu `uploads/19/…`.
    """
    if not isinstance(engagement_id, int) or engagement_id < 1:
        raise ValueError(f"engagement_id tak sah: {engagement_id!r}")
    return [f"uploads/{engagement_id}/", f"evidence/{engagement_id}/"]


def confirmation_matches(name: str | None, typed: str | None) -> bool:
    """True bila pengguna mengetik ulang nama penugasan dengan tepat.

    Sengaja peka huruf besar-kecil. Yang diminta bukan sekadar persetujuan,
    melainkan bukti bahwa pengguna membaca penugasan mana yang akan hilang.
    Penugasan tanpa nama tak boleh menjadi celah "ketik apa saja".
    """
    asli = (name or "").strip()
    if not asli:
        return False
    return asli == (typed or "").strip()
