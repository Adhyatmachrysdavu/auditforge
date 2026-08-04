"""Uji unit aturan ingest — urai ulang & deteksi duplikat (tanpa DB)."""
from __future__ import annotations

from app.ingest.rules import can_reparse, is_duplicate, sha256_of


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


def test_sha256_stable_and_differentiating():
    assert sha256_of(b"halo") == sha256_of(b"halo")
    assert sha256_of(b"halo") != sha256_of(b"halo ")
    assert len(sha256_of(b"halo")) == 64
