"""Aturan keputusan ingest — deterministik, tanpa DB.

Dua keputusan yang menentukan apakah sebuah berkas boleh diproses:

1. **Boleh diurai ulang?** Hanya berkas yang gagal dan berkas mentahnya masih
   ada. Mengulang berkas yang sudah berhasil menaikkan `occurrences` setiap
   temuan di dalamnya; deduplikasi mencegah baris ganda, tetapi tidak mencegah
   angka kemunculan menjadi keliru — padahal angka itu ikut menentukan
   prioritas triase.

2. **Duplikat?** Berkas dengan isi yang sama ditolak **hanya bila** berkas
   sebelumnya sudah BERHASIL diurai. Kata "berhasil" itu inti aturannya: berkas
   yang dulu gagal harus tetap boleh dikirim ulang, sebab kegagalannya bisa
   disebabkan parser yang belum ada. Tanpa pengecualian ini, menambah parser
   baru tidak akan pernah membuat berkas lama dapat masuk.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any, Protocol

_REPARSEABLE = "failed"
_PARSED = "parsed"


class _UploadRow(Protocol):
    """Bentuk minimal baris unggahan yang dibutuhkan aturan duplikat."""

    status: str
    content_hash: str | None


def sha256_of(content: bytes) -> str:
    """Sidik jari isi berkas untuk deteksi duplikat."""
    return hashlib.sha256(content).hexdigest()


def can_reparse(*, status: str, has_storage_key: bool) -> tuple[bool, str]:
    """(boleh, alasan). `alasan` kosong bila boleh."""
    if status != _REPARSEABLE:
        return False, (
            f"Hanya berkas gagal yang dapat diurai ulang "
            f"(status saat ini: {status})."
        )
    if not has_storage_key:
        return False, "Berkas mentah tidak lagi tersedia di penyimpanan."
    return True, ""


def is_duplicate(*, content_hash: str | None, parsed_hashes: set[str]) -> bool:
    """True bila isi berkas ini sudah pernah BERHASIL diurai di penugasan yang sama."""
    if not content_hash:
        return False  # berkas lama tanpa hash: jangan pernah dianggap duplikat
    return content_hash in parsed_hashes


def parsed_hashes_from(rows: Iterable[_UploadRow]) -> set[str]:
    """Himpunan hash dari baris yang BERHASIL diurai saja.

    Penyaringan status sengaja hidup di sini, bukan di SQL: inilah separuh aturan
    yang menanggung beban — berkas yang dulu gagal tidak boleh menghalangi
    pengiriman ulang — sehingga ia harus dapat diuji tanpa basis data.
    """
    return {
        row.content_hash
        for row in rows
        if row.status == _PARSED and row.content_hash
    }


def parsed_duplicate_of(
    rows: Iterable[_UploadRow], *, content_hash: str | None
) -> Any | None:
    """Baris `parsed` pertama yang isinya identik; None bila bukan duplikat.

    Mengembalikan barisnya (bukan sekadar bool) agar pesan galat dapat menyebut
    unggahan mana yang sudah memuat isi tersebut.
    """
    candidates = [
        row for row in rows if row.status == _PARSED and row.content_hash
    ]
    if not is_duplicate(
        content_hash=content_hash, parsed_hashes=parsed_hashes_from(candidates)
    ):
        return None
    return next(row for row in candidates if row.content_hash == content_hash)
