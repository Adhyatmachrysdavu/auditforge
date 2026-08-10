"""Pengerasan produksi — nilai bawaan yang tak boleh lolos ke server.

Nilai-nilai di bawah ini sengaja ada agar `docker compose up` langsung jalan
untuk pengembangan. Justru karena itu ia berbahaya: nilainya **terbit di repo
publik**, sehingga siapa pun yang membacanya dapat menandatangani token admin
sendiri bila `secret_key` tak pernah diganti.

Modul ini murni (tanpa I/O) sehingga dapat diuji tanpa infrastruktur, lalu
dipanggil `core/config.py` saat aplikasi memuat pengaturannya. Sifatnya
**fail-closed**: di lingkungan produksi aplikasi menolak menyala, bukan menyala
sambil memperingatkan — peringatan pada log gampang terlewat, kegagalan boot
tidak.
"""
from __future__ import annotations

# Lingkungan yang dianggap produksi (dibandingkan setelah dipangkas & huruf kecil).
PRODUCTION_ENVIRONMENTS: frozenset[str] = frozenset({"production", "prod"})

# Nama pengaturan → nilai bawaan yang tak boleh dipakai di produksi.
INSECURE_DEFAULTS: dict[str, str] = {
    "secret_key": "dev-secret-change-me-in-production",
    "seed_admin_password": "admin12345",
    "minio_secret_key": "auditforge-secret",
    "database_url": (
        "postgresql+psycopg://auditforge:auditforge@postgres:5432/auditforge"
    ),
}

# Sebagian nilai boleh berubah sebagian tanpa menjadi aman: URL basis data
# boleh berganti host dan port, tetapi sandinya tetap sandi bawaan.
_SUBSTRING_CHECKS: dict[str, str] = {
    "database_url": "://auditforge:auditforge@",
}

# Cara membuat nilai pengganti, ditampilkan pada pesan galat.
_CARA_MEMBUAT = "openssl rand -hex 32"


def _is_default(name: str, value: object) -> bool:
    """True bila `value` masih nilai bawaan (atau kosong) untuk pengaturan itu."""
    teks = str(value or "").strip()
    if not teks:
        return True
    petunjuk = _SUBSTRING_CHECKS.get(name)
    if petunjuk is not None:
        return petunjuk in teks
    return teks == INSECURE_DEFAULTS.get(name)


def unsafe_settings(*, environment: str, values: dict[str, object]) -> list[str]:
    """Nama pengaturan yang masih bernilai bawaan, urut seperti INSECURE_DEFAULTS.

    Di luar produksi selalu kosong: nilai bawaan memang untuk pengembangan dan
    tidak boleh mengganggu alur lokal.
    """
    if (environment or "").strip().lower() not in PRODUCTION_ENVIRONMENTS:
        return []
    return [
        name
        for name in INSECURE_DEFAULTS
        if name in values and _is_default(name, values[name])
    ]


def assert_production_safe(*, environment: str, values: dict[str, object]) -> None:
    """Lempar `RuntimeError` bila ada nilai bawaan yang lolos ke produksi."""
    salah = unsafe_settings(environment=environment, values=values)
    if not salah:
        return
    daftar = "\n".join(f"  - {name.upper()}" for name in salah)
    raise RuntimeError(
        "AuditForge menolak menyala: ENVIRONMENT=production tetapi variabel "
        f"berikut masih bernilai bawaan pengembangan.\n{daftar}\n\n"
        "Nilai-nilai itu tertulis di repositori publik, sehingga siapa pun "
        "dapat menandatangani token admin sendiri. Isi setiap variabel di "
        f"berkas .env dengan nilai acak, mis. `{_CARA_MEMBUAT}`, lalu nyalakan "
        "ulang. Untuk menjalankan secara lokal, cukup pakai "
        "ENVIRONMENT=development."
    )
