"""Uji unit aturan ingest — urai ulang & deteksi duplikat (tanpa DB)."""
from __future__ import annotations

from types import SimpleNamespace

from app.ingest.rules import (
    can_reparse,
    is_duplicate,
    parsed_duplicate_of,
    parsed_hashes_from,
    sha256_of,
)


def _row(upload_id: int, status: str, content_hash: str | None):
    """Baris ScanUpload palsu — hanya field yang dibaca aturan duplikat."""
    return SimpleNamespace(id=upload_id, status=status, content_hash=content_hash)


def test_reparse_allowed_for_failed_with_file():
    ok, reason = can_reparse(status="failed", has_storage_key=True)
    assert ok is True
    assert reason == ""


def test_reparse_rejected_when_file_missing():
    ok, reason = can_reparse(status="failed", has_storage_key=False)
    assert ok is False
    assert "penyimpanan" in reason.lower()


def test_reparse_rejected_for_parsed():
    # Mengulang berkas yang sudah berhasil akan menaikkan occurrences tiap
    # temuan — dan angka itu ikut menentukan prioritas triase.
    ok, reason = can_reparse(status="parsed", has_storage_key=True)
    assert ok is False
    assert "gagal" in reason.lower()


def test_reparse_rejected_while_parsing():
    # Menghindari dua task parse berjalan atas berkas yang sama.
    ok, reason = can_reparse(status="parsing", has_storage_key=True)
    assert ok is False
    assert reason != ""


def test_reparse_rejected_for_uploaded():
    ok, _ = can_reparse(status="uploaded", has_storage_key=True)
    assert ok is False


def test_duplicate_when_hash_already_parsed():
    assert is_duplicate(content_hash="abc", parsed_hashes={"abc", "def"}) is True


def test_not_duplicate_when_hash_unseen():
    assert is_duplicate(content_hash="xyz", parsed_hashes={"abc"}) is False


def test_not_duplicate_when_hash_missing():
    # Berkas lama tanpa hash tak boleh dianggap duplikat.
    assert is_duplicate(content_hash=None, parsed_hashes={"abc"}) is False
    assert is_duplicate(content_hash="", parsed_hashes={"abc"}) is False


def test_not_duplicate_against_empty_set():
    # Himpunan kosong = belum ada berkas yang BERHASIL diurai. Berkas yang dulu
    # gagal tidak masuk himpunan ini, sehingga boleh dikirim ulang — inilah yang
    # membuat berkas lama bisa hidup lagi saat parser baru ditambahkan.
    assert is_duplicate(content_hash="abc", parsed_hashes=set()) is False


def test_parsed_hashes_only_counts_parsed_rows():
    # Inti aturan: hanya baris `parsed` yang boleh menghalangi berkas baru.
    rows = [
        _row(1, "parsed", "aaa"),
        _row(2, "failed", "bbb"),
        _row(3, "uploaded", "ccc"),
        _row(4, "parsing", "ddd"),
    ]
    assert parsed_hashes_from(rows) == {"aaa"}


def test_parsed_hashes_skips_rows_without_hash():
    rows = [_row(1, "parsed", None), _row(2, "parsed", ""), _row(3, "parsed", "aaa")]
    assert parsed_hashes_from(rows) == {"aaa"}


def test_parsed_duplicate_returns_the_parsed_row():
    rows = [_row(9, "parsed", "aaa"), _row(10, "failed", "aaa")]
    dup = parsed_duplicate_of(rows, content_hash="aaa")
    assert dup is not None
    assert dup.id == 9


def test_parsed_duplicate_ignores_failed_row_with_same_hash():
    # Percobaan yang gagal wajib boleh dikirim/diurai ulang — termasuk saat ada
    # baris lain berisi hash yang sama.
    rows = [_row(10, "failed", "aaa"), _row(11, "parsing", "aaa")]
    assert parsed_duplicate_of(rows, content_hash="aaa") is None


def test_parsed_duplicate_none_when_hash_missing():
    rows = [_row(9, "parsed", "aaa")]
    assert parsed_duplicate_of(rows, content_hash=None) is None
    assert parsed_duplicate_of(rows, content_hash="") is None


def test_parsed_duplicate_none_when_no_rows():
    assert parsed_duplicate_of([], content_hash="aaa") is None


def test_sha256_stable_and_differentiating():
    assert sha256_of(b"halo") == sha256_of(b"halo")
    assert sha256_of(b"halo") != sha256_of(b"halo ")
    assert len(sha256_of(b"halo")) == 64
