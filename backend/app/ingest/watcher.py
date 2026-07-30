"""Pemindai folder terpantau (R3) — logika berkas murni, tanpa DB/MinIO/Celery.

Tata letak folder (di dalam `<base>`):

    inbox/<engagement_id>/berkas.ext   ← auditor/skrip menaruh berkas di sini
    processed/<engagement_id>/berkas.ext   ← dipindah setelah berhasil diurai
    failed/<engagement_id>/berkas.ext      ← dipindah bila gagal / engagement tak ada

Hanya subfolder ber-nama angka (= id penugasan) yang dipindai. Berkas yang baru
saja ditulis (mtime lebih muda dari `settle_seconds`) dilewati agar tak mengurai
berkas yang masih separuh tertulis. Fungsi di sini dapat diuji dengan folder
sementara tanpa bergantung pada layanan lain.
"""
from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

INBOX = "inbox"
PROCESSED = "processed"
FAILED = "failed"


def iter_inbox_files(
    base: str | Path, *, settle_seconds: float = 5.0, now: float | None = None
) -> Iterator[tuple[int, Path]]:
    """Hasilkan `(engagement_id, path)` untuk berkas stabil di `<base>/inbox/<eid>/`.

    Melewati: subfolder non-angka, berkas yang baru ditulis (< `settle_seconds`),
    dan entri yang bukan berkas biasa.
    """
    now = time.time() if now is None else now
    inbox = Path(base) / INBOX
    if not inbox.is_dir():
        return
    for sub in sorted(inbox.iterdir()):
        if not sub.is_dir() or not sub.name.isdigit():
            continue
        eid = int(sub.name)
        for f in sorted(sub.iterdir()):
            if not f.is_file():
                continue
            if now - f.stat().st_mtime < settle_seconds:
                continue  # masih ditulis → tunggu putaran berikutnya
            yield eid, f


def move_result(path: str | Path, base: str | Path, engagement_id: int, *, ok: bool) -> Path:
    """Pindah `path` ke `processed/<eid>/` (ok) atau `failed/<eid>/` (gagal).

    Pemindahan atomik dalam satu volume. Bila nama tujuan sudah ada, tambahkan
    sufiks agar tak menimpa berkas lama.
    """
    path = Path(path)
    dest_dir = Path(base) / (PROCESSED if ok else FAILED) / str(engagement_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if dest.exists():
        dest = dest_dir / f"{path.stem}_{int(path.stat().st_mtime)}{path.suffix}"
    path.replace(dest)
    return dest
