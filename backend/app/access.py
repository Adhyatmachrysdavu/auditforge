"""Keputusan akses penugasan (Modul 2) — deterministik, tanpa DB.

Aturannya sengaja hanya satu kalimat: administrator melihat seluruh penugasan;
siapa pun selain itu hanya melihat penugasan tempat ia terdaftar sebagai
anggota tim. Peran tinggi tidak memberi jalan pintas — seorang auditor tetap
tidak dapat membuka penugasan klien yang bukan garapannya.

Bersifat *fail-closed*: apa pun yang tidak secara eksplisit diizinkan, ditolak.
"""
from __future__ import annotations

ADMIN_ROLE = "admin"


def can_access_engagement(*, role: str, is_member: bool) -> bool:
    """True bila pengguna berperan `role` boleh membuka penugasan tersebut."""
    if role == ADMIN_ROLE:
        return True
    return bool(is_member)


def needs_engagement_filter(role: str) -> bool:
    """True bila daftar/agregat perlu disaring untuk peran ini.

    Dipisah agar route pemanggil tidak menuliskan `role != "admin"` sendiri-
    sendiri lalu menyimpang diam-diam ketika aturannya kelak berubah.
    """
    return role != ADMIN_ROLE
