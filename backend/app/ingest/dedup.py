"""Pencarian duplikat berkas dalam satu penugasan.

Satu-satunya tempat kueri duplikat ditulis. Sebelumnya kueri yang sama disalin
di jalur unggah manual dan jalur watcher, sehingga aturan intinya — hanya berkas
yang sudah BERHASIL diurai yang menghalangi berkas baru — hidup di dua SQL
terpisah tanpa satu pun tes yang mengunci. Kueri di sini dibuat setipis mungkin;
keputusannya diambil fungsi murni di `rules.py` yang diuji tanpa basis data.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingest.rules import parsed_duplicate_of
from app.models.scan_upload import ScanUpload


def find_parsed_duplicate(
    db: Session, *, engagement_id: int, content_hash: str | None
) -> ScanUpload | None:
    """Unggahan di penugasan ini yang isinya identik DAN sudah berhasil diurai.

    None berarti berkas boleh diproses: entah isinya belum pernah masuk, entah
    percobaan sebelumnya gagal (yang gagal wajib boleh dikirim ulang).
    """
    if not content_hash:
        return None  # berkas lama tanpa hash: jangan pernah dianggap duplikat
    rows = db.scalars(
        select(ScanUpload).where(
            ScanUpload.engagement_id == engagement_id,
            ScanUpload.content_hash == content_hash,
        )
    ).all()
    return parsed_duplicate_of(rows, content_hash=content_hash)
