"""Penyimpanan objek (MinIO) untuk berkas mentah scan & bukti."""
from __future__ import annotations

import io
from functools import lru_cache

from minio import Minio

from app.core.config import get_settings


@lru_cache
def get_minio() -> Minio:
    s = get_settings()
    return Minio(
        s.minio_endpoint,
        access_key=s.minio_access_key,
        secret_key=s.minio_secret_key,
        secure=s.minio_secure,
    )


def ensure_bucket(bucket: str | None = None) -> str:
    s = get_settings()
    bucket = bucket or s.minio_bucket
    client = get_minio()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    return bucket


def put_bytes(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    bucket = ensure_bucket()
    get_minio().put_object(
        bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
    )
    return key


def get_bytes(key: str) -> bytes:
    s = get_settings()
    resp = get_minio().get_object(s.minio_bucket, key)
    try:
        return resp.read()
    finally:
        resp.close()
        resp.release_conn()


def remove_object(key: str) -> None:
    """Hapus objek dari bucket (best-effort; abaikan bila sudah tak ada)."""
    s = get_settings()
    try:
        get_minio().remove_object(s.minio_bucket, key)
    except Exception:  # noqa: BLE001,S110 — penghapusan storage tak boleh meng-crash API
        pass


def remove_prefix(prefix: str) -> int:
    """Hapus seluruh objek berawalan `prefix`; kembalikan jumlah yang terhapus.

    Dipakai saat penugasan dihapus. Tanpa ini berkas scan mentah dan lampiran
    bukti milik klien tetap tersimpan di disk meski penugasannya sudah tak ada
    di basis data — data yang tak terjangkau aplikasi tetapi tetap ada, dan itu
    sulit dipertanggungjawabkan pada sistem yang menjanjikan sebaliknya.

    Best-effort seperti `remove_object`: kegagalan penyimpanan tak boleh
    membatalkan penghapusan yang sudah dilakukan di basis data.
    """
    s = get_settings()
    dihapus = 0
    try:
        client = get_minio()
        for obj in client.list_objects(s.minio_bucket, prefix=prefix, recursive=True):
            if obj.object_name:
                client.remove_object(s.minio_bucket, obj.object_name)
                dihapus += 1
    except Exception:  # noqa: BLE001,S110 — lihat alasan di remove_object
        pass
    return dihapus
