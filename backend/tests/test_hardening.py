"""Uji unit pengerasan produksi — nilai bawaan yang tak boleh lolos (tanpa DB)."""
from __future__ import annotations

import pytest

from app.core.hardening import (
    INSECURE_DEFAULTS,
    PRODUCTION_ENVIRONMENTS,
    assert_production_safe,
    unsafe_settings,
)

AMAN = {
    "secret_key": "8f2c1e9a7b3d5f60a4c8e2b7d9f1a3c5e7b9d1f3a5c7e9b1d3f5a7c9e1b3d5f7",
    "seed_admin_password": "kata-sandi-panjang-yang-diganti",
    "minio_secret_key": "objek-storage-rahasia-baru",
    "database_url": "postgresql+psycopg://auditforge:sandi-nyata@postgres:5432/auditforge",
}


def test_pengembangan_tidak_pernah_dihalangi():
    """Nilai bawaan memang untuk pengembangan; jangan ganggu alur lokal."""
    bawaan = dict(INSECURE_DEFAULTS)
    for env in ("development", "test", "staging", ""):
        assert unsafe_settings(environment=env, values=bawaan) == []


def test_produksi_menolak_seluruh_nilai_bawaan():
    bawaan = dict(INSECURE_DEFAULTS)
    hasil = unsafe_settings(environment="production", values=bawaan)
    assert set(hasil) == set(INSECURE_DEFAULTS)


def test_produksi_menerima_nilai_yang_sudah_diganti():
    assert unsafe_settings(environment="production", values=AMAN) == []


def test_hanya_yang_masih_bawaan_yang_dilaporkan():
    campuran = dict(AMAN)
    campuran["secret_key"] = INSECURE_DEFAULTS["secret_key"]
    assert unsafe_settings(environment="production", values=campuran) == ["secret_key"]


def test_nama_environment_tak_peka_huruf_besar_dan_spasi():
    bawaan = dict(INSECURE_DEFAULTS)
    for env in ("PRODUCTION", " Production ", "PROD"):
        assert unsafe_settings(environment=env, values=bawaan) != []


def test_prod_adalah_alias_production():
    assert "prod" in PRODUCTION_ENVIRONMENTS
    assert "production" in PRODUCTION_ENVIRONMENTS


def test_database_url_dikenali_dari_sandi_bawaannya():
    """URL boleh berubah host/port; yang berbahaya adalah sandi bawaannya."""
    values = dict(AMAN)
    values["database_url"] = "postgresql+psycopg://auditforge:auditforge@db.kantor:5432/auditforge"
    assert unsafe_settings(environment="production", values=values) == ["database_url"]


def test_nilai_kosong_dianggap_belum_diisi():
    values = dict(AMAN)
    values["secret_key"] = "   "
    assert unsafe_settings(environment="production", values=values) == ["secret_key"]


def test_assert_production_safe_diam_bila_aman():
    # Tidak melempar apa pun.
    assert_production_safe(environment="production", values=AMAN)
    assert_production_safe(environment="development", values=dict(INSECURE_DEFAULTS))


def test_assert_production_safe_melempar_dengan_pesan_yang_menuntun():
    with pytest.raises(RuntimeError) as exc:
        assert_production_safe(environment="production", values=dict(INSECURE_DEFAULTS))
    pesan = str(exc.value)
    # Menyebut setiap variabel yang salah, dalam bentuk yang dipakai di .env.
    assert "SECRET_KEY" in pesan
    assert "SEED_ADMIN_PASSWORD" in pesan
    assert "MINIO_SECRET_KEY" in pesan
    assert "DATABASE_URL" in pesan
    # Memberi tahu cara membuat nilai yang benar, bukan sekadar menolak.
    assert "openssl rand" in pesan
